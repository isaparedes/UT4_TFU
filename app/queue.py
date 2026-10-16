# Patrón de rendimiento: Queue-Based Load Leveling
import os
import redis
from rq import Queue

redis_queue = redis.Redis.from_url(
    os.getenv("REDIS_QUEUE_URL", "redis://redis:6379/1")
)

adopciones_queue = Queue(
    "adopciones",
    connection=redis_queue
)