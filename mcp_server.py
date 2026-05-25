"""
================================================================================
SERVIDOR MCP (Model Context Protocol) PARA PROCESAMIENTO DE DATOS DE ML
================================================================================

Este archivo representa el "Servidor" en la arquitectura MCP. Su única función es
exponer capacidades locales (como acceso a bases de datos y scripts de limpieza de datos)
hacia el exterior, para que cualquier Modelo de Lenguaje (LLM) pueda llamarlas de 
manera estandarizada, sin que el LLM necesite saber CÓMO están implementadas internamente.

SOPORTA DOS TIPOS DE TRANSPORTES:
1. stdio (Por defecto): Comunicación por entrada/salida estándar para procesos locales.
2. sse: Crea un servidor Web real en http://localhost:8000/sse que envía eventos al cliente,
   permitiendo inspección visual por red.
"""

import os
import sys
import pandas as pd
from sqlalchemy import create_engine, text
from dotenv import load_dotenv
from mcp.server.fastmcp import FastMCP
from sklearn.impute import SimpleImputer
from sklearn.preprocessing import OneHotEncoder

# ------------------------------------------------------------------------------
# 1. INICIALIZACIÓN DEL SERVIDOR MCP
# ------------------------------------------------------------------------------
# Usamos 'FastMCP' de Anthropic para registrar herramientas y recursos.
mcp = FastMCP("ML_MySQL_Server")


# ------------------------------------------------------------------------------
# 2. CONEXIÓN A LA BASE DE DATOS (MySQL)
# ------------------------------------------------------------------------------
def get_db_engine():
    """Carga las variables de entorno de forma segura y crea la conexión a MySQL."""
    load_dotenv()
    host = os.getenv("MYSQL_HOST")
    database = os.getenv("MYSQL_DATABASE")
    user = os.getenv("MYSQL_USER")
    password = os.getenv("MYSQL_PASSWORD")
    port = os.getenv("MYSQL_PORT", "3306")
    return create_engine(f"mysql+pymysql://{user}:{password}@{host}:{port}/{database}")


# ------------------------------------------------------------------------------
# 3. HERRAMIENTA 1: EXTRACCIÓN DE DATOS
# ------------------------------------------------------------------------------
@mcp.tool()
def extraer_datos_mysql(limit: int = 100) -> str:
    """Extrae transacciones de MySQL y las guarda en un CSV local.
    
    Args:
        limit (int): Cantidad máxima de filas a descargar.
    """
    engine = get_db_engine()
    query = text(f"SELECT * FROM transacciones_ecommerce LIMIT {limit}")
    
    try:
        with engine.connect() as connection:
            df = pd.read_sql(query, con=connection)
        
        output_file = "temp_dataset.csv"
        df.to_csv(output_file, index=False)
        return f"[ÉXITO] Se extrajeron {len(df)} registros de MySQL y se guardaron en {output_file}."
        
    except Exception as e:
        return f"[ERROR] No se pudo extraer la información: {str(e)}"


# ------------------------------------------------------------------------------
# 4. HERRAMIENTA 2: PIPELINE DE PREPARACIÓN DE DATOS PARA ML
# ------------------------------------------------------------------------------
@mcp.tool()
def transformar_y_exportar_ml(file_path: str = "temp_dataset.csv") -> str:
    """Aplica imputación numérica y One-Hot Encoding, guardando el archivo listo para ML.
    
    Args:
        file_path (str): Ubicación del dataset crudo a limpiar.
    """
    if not os.path.exists(file_path):
        return f"[ERROR] El archivo '{file_path}' no existe. Ejecuta extraer_datos_mysql primero."
        
    try:
        df = pd.read_csv(file_path)
        
        # A. IMPUTACIÓN DE NULOS con la mediana
        imputer = SimpleImputer(strategy='median')
        df['monto_compra_bs'] = imputer.fit_transform(df[['monto_compra_bs']])
        
        # B. ONE-HOT ENCODING (zona y metodo_pago)
        encoder = OneHotEncoder(sparse_output=False, drop='first')
        vars_cat = ['zona', 'metodo_pago']
        encoded = encoder.fit_transform(df[vars_cat])
        encoded_cols = encoder.get_feature_names_out(vars_cat)
        
        df_encoded = pd.DataFrame(encoded, columns=encoded_cols, index=df.index)
        df_final = pd.concat([df.drop(columns=vars_cat), df_encoded], axis=1)
        
        # C. ESTRUCTURACIÓN DE TIPOS Y FORMATO FINAL
        df_final['id_cliente'] = df_final['id_cliente'].astype(int)
        df_final['monto_compra_bs'] = df_final['monto_compra_bs'].astype(float)
        for col in encoded_cols:
            df_final[col] = df_final[col].astype(bool)
            
        output_path = "dataset_ml_ready.csv"
        df_final.to_csv(output_path, index=False)
        return f"[ÉXITO] Pipeline completado. Datos listos en '{output_path}'. Columnas finales: {list(df_final.columns)}"
        
    except Exception as e:
        return f"[ERROR] Falló la transformación de datos: {str(e)}"


# ------------------------------------------------------------------------------
# 5. INICIO DE LA EJECUCIÓN (SOPORTE STDIO / SSE)
# ------------------------------------------------------------------------------
if __name__ == "__main__":
    # Detección dinámica de modo de ejecución por argumentos
    transport_mode = "stdio"
    if len(sys.argv) > 1 and sys.argv[1].lower() == "sse":
        transport_mode = "sse"
        
    if transport_mode == "sse":
        # Inicia un servidor web FastAPI/Starlette local para servir SSE en el puerto 8000
        print("🌐 Iniciando Servidor MCP en modo SSE (Web Server) en http://localhost:8000/sse ...", file=sys.stderr)
        mcp.run(transport='sse')
    else:
        # Inicia el flujo por comunicación de consola oculta (stdio)
        print("🔌 Iniciando Servidor MCP en modo stdio (Consola local)...", file=sys.stderr)
        mcp.run(transport='stdio')
