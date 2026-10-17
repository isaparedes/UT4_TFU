from fastapi import FastAPI, HTTPException
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from redis.exceptions import RedisError
from app.cache import redis_client
from app.database import Base, engine
from app import models  
from app import auth, animales, hogares, adopciones
from app.settings import settings
from starlette.middleware.sessions import SessionMiddleware
from fastapi import FastAPI, HTTPException, Depends
from app.auth import requerir_admin

app = FastAPI(
    title="TFU4 - Refugio de animales",
    description="Demo de aplicación de patrones de disponibilidad, rendimiento, "
    "seguridad y facilidad de modificación/despliegue (UT4).",
    version="1.0.0",
)

app.add_middleware(
    SessionMiddleware,
    secret_key= settings.SESSION_SECRET, # Patrón de facilidad de modificación y despliegue: External Configuration Store
    same_site="lax",
    https_only=False,  
)


@app.on_event("startup")
def crear_tablas():
    Base.metadata.create_all(bind=engine)

# Patrón de disponibilidad: Health Endpoint Monitoring (API)
@app.get("/api-health", dependencies=[Depends(requerir_admin)])
def api_health():
    """Usado por el balanceador / demo para saber qué instancia respondió."""
    import socket
    return {"status": "healthy", "instance": socket.gethostname()}

# Patrón de disponibilidad: Health Endpoint Monitoring (Base de datos)
@app.get("/db-health", dependencies=[Depends(requerir_admin)])
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

# Patrón de disponibilidad: Health Endpoint Monitoring (Caché Redis)
@app.get("/redis-health", dependencies=[Depends(requerir_admin)])
def redis_health_check():
    try:
        redis_client.ping()

        return {
            "status": "healthy",
            "redis": "connected"
        }

    except RedisError:
        raise HTTPException(
            status_code=503,
            detail={
                "status": "unhealthy",
                "redis": "disconnected"
            }
        )


app.include_router(auth.router)
app.include_router(animales.router)
app.include_router(hogares.router)
app.include_router(adopciones.router)
