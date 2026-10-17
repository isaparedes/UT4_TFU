"""
Configuración de la base de datos (PostgreSQL).

"""
import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base

DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql+psycopg2://tfu3:tfu3@db:5432/tfu3",
)

engine = create_engine(DATABASE_URL, pool_pre_ping=True)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


def get_db():
    """Dependencia de FastAPI: una sesión por request, sin estado entre requests."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


