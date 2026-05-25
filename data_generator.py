import pandas as pd
import numpy as np
import random
import subprocess
import os
from sqlalchemy import create_engine
from dotenv import load_dotenv

def generar_datos():
    """Genera 100 transacciones de E-commerce simuladas."""
    print("Generando dataset crudo...")
    num_records = 500
    zonas = ['Equipetrol', 'Urubó', 'Centro', 'Plan 3000']
    metodos_pago = ['QR', 'Tarjeta', 'Efectivo']
    
    data = {
        'id_cliente': range(1, num_records + 1),
        'zona': [random.choice(zonas) for _ in range(num_records)],
        'monto_compra_bs': [round(random.uniform(50.0, 5000.0), 2) for _ in range(num_records)],
        'metodo_pago': [random.choice(metodos_pago) for _ in range(num_records)]
    }
    
    df = pd.DataFrame(data)
    
    # Introducir intencionalmente 5 nulos en la columna monto_compra_bs
    indices_nulos = random.sample(range(num_records), 5)
    df.loc[indices_nulos, 'monto_compra_bs'] = np.nan
    
    # Guardar a nivel local
    file_name = 'dataset_crudo.csv'
    df.to_csv(file_name, index=False)
    print(f"Archivo {file_name} generado con éxito.")
    
    return file_name

def subir_a_github(file_name):
    """Inicializa git, hace commit y push al repositorio destino."""
    repo_url = "https://github.com/SamCCDev/MCP_ML_Data.git"
    
    commands = [
        ["git", "init"],
        ["git", "add", file_name],
        ["git", "commit", "-m", "Update data"],
        ["git", "branch", "-M", "main"],
        # Se captura el posible error si remote ya existe, pero se intenta añadir
        ["git", "remote", "add", "origin", repo_url],
        ["git", "push", "-u", "origin", "main"]
    ]
    
    for cmd in commands:
        try:
            # os.system se puede usar, pero subprocess.run provee mejor manejo de errores
            subprocess.run(cmd, check=True, capture_output=True, text=True)
            print(f"Ejecutado correctamente: {' '.join(cmd)}")
        except subprocess.CalledProcessError as e:
            if "remote origin already exists" in e.stderr:
                continue
            print(f"Advertencia/Error al ejecutar '{' '.join(cmd)}':\n{e.stderr}")

def cargar_a_mysql(file_name):
    """Carga el dataset generado a la base de datos MySQL."""
    print("Conectando a MySQL para cargar datos...")
    load_dotenv()
    host = os.getenv("MYSQL_HOST")
    database = os.getenv("MYSQL_DATABASE")
    user = os.getenv("MYSQL_USER")
    password = os.getenv("MYSQL_PASSWORD")
    port = os.getenv("MYSQL_PORT", "3306")
    
    # Crear engine usando SQLAlchemy y pymysql
    engine = create_engine(f"mysql+pymysql://{user}:{password}@{host}:{port}/{database}")
    
    try:
        df = pd.read_csv(file_name)
        table_name = "transacciones_ecommerce"
        # Usamos if_exists='replace' para sobreescribir la tabla
        df.to_sql(name=table_name, con=engine, if_exists='replace', index=False)
        print(f"Datos cargados exitosamente en la tabla '{table_name}'.")
    except Exception as e:
        print(f"Error al cargar datos en MySQL: {e}")

if __name__ == "__main__":
    archivo = generar_datos()
    cargar_a_mysql(archivo)
    subir_a_github(archivo)
