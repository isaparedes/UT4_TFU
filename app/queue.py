# Patrón de rendimiento: Queue-Based Load Leveling
import redis
from rq import Queue
from app.settings import settings

redis_queue = redis.Redis.from_url(
    settings.REDIS_QUEUE_URL # Patrón de facilidad de modificación y despliegue: External Configuration Store
)

adopciones_queue = Queue(
    "adopciones",
    connection=redis_queue
)