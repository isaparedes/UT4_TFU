from fastapi import FastAPI
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from app.database import Base, engine
from app import models  # noqa: F401  (registra los modelos en Base.metadata)
from app import auth, animales, hogares, adopciones

app = FastAPI(
    title="TFU4 - Refugio de animales",
    description="Demo de componentes, escalabilidad horizontal, contenedores, "
                 "ACID y servicios sin estado (UT4).",
    version="1.0.0",
)


@app.on_event("startup")
def crear_tablas():
    Base.metadata.create_all(bind=engine)

# Patrón de disponibilidad: Health Endpoint Monitoring (API)
@app.get("/api-health")
def salud():
    """Usado por el balanceador / demo para saber qué instancia respondió."""
    import socket
    return {"status": "healthy", "instance": socket.gethostname()}

# Patrón de disponibilidad: Health Endpoint Monitoring (Base de datos)
@app.get("/db-health")
def health_check():
    try:
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))

        return {
            "status": "healthy",
            "database": "connected"
        }

    except SQLAlchemyError:
        raise HTTPException(
            status_code=503,
            detail={
                "status": "unhealthy",
                "database": "disconnected"
            }
        )


app.include_router(auth.router)
app.include_router(animales.router)
app.include_router(hogares.router)
app.include_router(adopciones.router)
