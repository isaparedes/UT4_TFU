# Patrón de facilidad de modificación y despliegue: External Configuration Store
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    SESSION_SECRET: str
    JWT_SECRET: str
    GOOGLE_CLIENT_ID: str
    GOOGLE_CLIENT_SECRET: str
    GOOGLE_REDIRECT_URI: str = "http://localhost:8000/auth/google/callback"

    DATABASE_URL: str
    REDIS_URL: str = "redis://redis:6379/0"
    REDIS_QUEUE_URL: str = "redis://redis:6379/1"

    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60

    JOB_TIMEOUT: int = 60
    JOB_RESULT_TTL: int = 86400
    JOB_FAILURE_TTL: int = 604800
    CACHE_TTL_LISTA: int = 30
    CACHE_TTL_DETALLE: int = 60
    VALET_TTL: int = 60

    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore"
    )

settings = Settings()


