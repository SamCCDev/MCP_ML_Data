"""
================================================================================
SERVIDOR MCP (Model Context Protocol) PARA PROCESAMIENTO DE DATOS DE ML
================================================================================

Este archivo representa el "Servidor" en la arquitectura MCP. Su única función es
exponer capacidades locales (como acceso a bases de datos y scripts de limpieza de datos)
hacia el exterior, para que cualquier Modelo de Lenguaje (LLM) pueda llamarlas de 
manera estandarizada, sin que el LLM necesite saber CÓMO están implementadas internamente.

El Servidor NO toma decisiones; solo ofrece "Herramientas" (Tools) y las ejecuta cuando
el cliente se lo solicita a través de un canal de comunicación estándar (stdio).
"""

import os
import pandas as pd
from sqlalchemy import create_engine, text
from dotenv import load_dotenv
from mcp.server.fastmcp import FastMCP
from sklearn.impute import SimpleImputer
from sklearn.preprocessing import OneHotEncoder

# ------------------------------------------------------------------------------
# 1. INICIALIZACIÓN DEL SERVIDOR MCP
# ------------------------------------------------------------------------------
# Usamos 'FastMCP' de Anthropic, que es un framework de alto nivel para crear
# servidores MCP en Python de manera extremadamente rápida y sencilla.
mcp = FastMCP("ML_MySQL_Server")


# ------------------------------------------------------------------------------
# 2. CONEXIÓN A LA BASE DE DATOS (MySQL)
# ------------------------------------------------------------------------------
def get_db_engine():
    """
    Carga las variables de entorno de forma segura utilizando python-dotenv y
    crea un motor (engine) de conexión de SQLAlchemy para interactuar con MySQL.
    
    ¿Por qué hacerlo así?
    Para evitar exponer credenciales en repositorios públicos. El archivo .env
    contiene las claves reales, mientras que este código solo las lee dinámicamente.
    """
    load_dotenv()
    host = os.getenv("MYSQL_HOST")
    database = os.getenv("MYSQL_DATABASE")
    user = os.getenv("MYSQL_USER")
    password = os.getenv("MYSQL_PASSWORD")
    port = os.getenv("MYSQL_PORT", "3306")
    
    # Creamos un motor estándar de SQLAlchemy para dialecto MySQL + PyMySQL
    return create_engine(f"mysql+pymysql://{user}:{password}@{host}:{port}/{database}")


# ------------------------------------------------------------------------------
# 3. HERRAMIENTA 1: EXTRACCIÓN DE DATOS
# ------------------------------------------------------------------------------
# El decorador @mcp.tool() le indica a FastMCP que esta función es una herramienta
# que debe ser anunciada y expuesta a cualquier LLM que se conecte al servidor.
@mcp.tool()
def extraer_datos_mysql(limit: int = 100) -> str:
    """
    Extrae transacciones de la tabla 'transacciones_ecommerce' en MySQL y las guarda en un CSV local.
    
    ¿Cómo funciona?
    1. Abre una conexión segura y explícita a la base de datos MySQL.
    2. Ejecuta una consulta SELECT limitada al número de filas solicitado.
    3. Descarga la información a un DataFrame de Pandas.
    4. Guarda los datos crudos localmente en un archivo temporal ('temp_dataset.csv').
    
    Args:
        limit (int): Cantidad máxima de filas a descargar desde la base de datos.
        
    Returns:
        str: Un mensaje de confirmación legible para el LLM.
    """
    engine = get_db_engine()
    
    # Usamos text() de SQLAlchemy para sanitizar la consulta SQL.
    query = text(f"SELECT * FROM transacciones_ecommerce LIMIT {limit}")
    
    try:
        # SOLUCIÓN AL ERROR 'OptionEngine' has no attribute 'execute':
        # En SQLAlchemy 2.0+ debemos abrir explícitamente una conexión usando
        # "with engine.connect() as connection" en lugar de pasar el engine directo a pandas.
        with engine.connect() as connection:
            df = pd.read_sql(query, con=connection)
        
        # Guardamos a nivel local
        output_file = "temp_dataset.csv"
        df.to_csv(output_file, index=False)
        
        # Devolvemos un reporte de éxito para que el LLM sepa qué ocurrió en nuestro servidor
        return f"[ÉXITO] Se extrajeron {len(df)} registros de MySQL y se guardaron en {output_file}."
        
    except Exception as e:
        return f"[ERROR] No se pudo extraer la información: {str(e)}"


# ------------------------------------------------------------------------------
# 4. HERRAMIENTA 2: PIPELINE DE PREPARACIÓN DE DATOS PARA ML
# ------------------------------------------------------------------------------
@mcp.tool()
def transformar_y_exportar_ml(file_path: str = "temp_dataset.csv") -> str:
    """
    Toma un archivo CSV con datos crudos, aplica imputación numérica y 
    One-Hot Encoding, guardando un archivo limpio listo para Machine Learning.
    
    ¿Cómo funciona?
    1. Lee el archivo CSV crudo generado por la herramienta anterior.
    2. Aplica SimpleImputer para rellenar los valores nulos (NaN) en la columna 
       monto_compra_bs utilizando la mediana histórica.
    3. Aplica One-Hot Encoding a las columnas categóricas ('zona' y 'metodo_pago')
       para convertirlas en columnas booleanas (0 y 1) entendibles por XGBoost/Scikit-Learn.
    4. Convierte todos los tipos a estrictamente numéricos (int, float, bool).
    5. Guarda el dataset final listo en 'dataset_ml_ready.csv'.
    
    Args:
        file_path (str): Ubicación del dataset crudo a limpiar.
        
    Returns:
        str: Un reporte del procesamiento completado.
    """
    # Validación básica de existencia de archivos locales
    if not os.path.exists(file_path):
        return f"[ERROR] El archivo '{file_path}' no existe. Por favor, ejecuta extraer_datos_mysql primero."
        
    try:
        df = pd.read_csv(file_path)
        
        # A. IMPUTACIÓN DE NULOS
        # Encontramos la mediana de 'monto_compra_bs' y reemplazamos los 5 nulos
        imputer = SimpleImputer(strategy='median')
        df['monto_compra_bs'] = imputer.fit_transform(df[['monto_compra_bs']])
        
        # B. ONE-HOT ENCODING (Variables Categóricas)
        # Convertimos 'zona' y 'metodo_pago' en columnas binarias (dummies)
        encoder = OneHotEncoder(sparse_output=False, drop='first')
        vars_cat = ['zona', 'metodo_pago']
        encoded = encoder.fit_transform(df[vars_cat])
        encoded_cols = encoder.get_feature_names_out(vars_cat)
        
        # Creamos un nuevo dataframe con las variables codificadas
        df_encoded = pd.DataFrame(encoded, columns=encoded_cols, index=df.index)
        
        # Concatenamos y eliminamos las columnas originales de texto plano
        df_final = pd.concat([df.drop(columns=vars_cat), df_encoded], axis=1)
        
        # C. ESTRUCTURACIÓN DE TIPOS Y FORMATO FINAL
        # Garantizamos tipos puros para evitar errores en modelos matemáticos de ML
        df_final['id_cliente'] = df_final['id_cliente'].astype(int)
        df_final['monto_compra_bs'] = df_final['monto_compra_bs'].astype(float)
        for col in encoded_cols:
            df_final[col] = df_final[col].astype(bool) # Booleanos legibles por sklearn
            
        output_path = "dataset_ml_ready.csv"
        df_final.to_csv(output_path, index=False)
        
        return f"[ÉXITO] Pipeline completado. Datos listos en '{output_path}'. Columnas finales: {list(df_final.columns)}"
        
    except Exception as e:
        return f"[ERROR] Falló la transformación de datos: {str(e)}"


# ------------------------------------------------------------------------------
# 5. INICIO DE LA EJECUCIÓN (TRANSPORTE STDIO)
# ------------------------------------------------------------------------------
if __name__ == "__main__":
    # MCP soporta múltiples transportes. Usamos 'stdio' (entrada/salida de consola)
    # que es el estándar industrial para integraciones locales de agentes de IA.
    # Escribimos los logs técnicos a stderr para no contaminar el canal de datos de stdout.
    print("Iniciando Servidor MCP en transporte stdio...", file=os.sys.stderr)
    mcp.run(transport='stdio')
