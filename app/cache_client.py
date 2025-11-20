# app/cache_client.py
import redis
from app.config import settings


def create_redis_client():
    """
    Devuelve un cliente Redis Cloud basado en REDIS_URL.
    """
    return redis.from_url(
        settings.REDIS_URL,
        decode_responses=True
    )
