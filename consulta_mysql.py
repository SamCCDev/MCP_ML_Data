import os
import pandas as pd
from sqlalchemy import create_engine
from dotenv import load_dotenv

def consultar_datos():
    """Conecta a la base de datos MySQL y consulta las transacciones."""
    print("Conectando a MySQL para consultar datos...")
    load_dotenv()
    host = os.getenv("MYSQL_HOST")
    database = os.getenv("MYSQL_DATABASE")
    user = os.getenv("MYSQL_USER")
    password = os.getenv("MYSQL_PASSWORD")
    port = os.getenv("MYSQL_PORT", "3306")
    
    # Crear engine usando SQLAlchemy y pymysql
    engine = create_engine(f"mysql+pymysql://{user}:{password}@{host}:{port}/{database}")
    
    query = "SELECT * FROM transacciones_ecommerce LIMIT 10"
    
    try:
        df = pd.read_sql(query, con=engine)
        print("\n=== Consulta Exitosa ===")
        print("Mostrando los primeros 10 registros:")
        print("-" * 50)
        print(df.to_string(index=False))
        print("-" * 50)
    except Exception as e:
        print(f"Error al consultar la base de datos: {e}")

if __name__ == "__main__":
    consultar_datos()
