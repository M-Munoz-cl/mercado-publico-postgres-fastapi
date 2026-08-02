import os
from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")

if not DATABASE_URL:
    raise ValueError("No se encontró DATABASE_URL en el archivo .env")

# Crear conexion a base postgres
engine = create_engine(DATABASE_URL)
# Fabrica que crea nuevas sesiones de base de datos (sesion permite trabajar con la base) Es mas comodo que usar engine
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Para que las clases se interpreten como tablas sql
Base = declarative_base()

# Funcion que abre una sesion
def obtener_db():
    # abre sesion
    db = SessionLocal()

    try:
        # Entrega la sesion
        yield db
    finally:
        # la cierra
        db.close()


