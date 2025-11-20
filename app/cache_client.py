# app/cache_client.py
import redis
from app.config import settings

def create_redis_client():
    return redis.Redis(
        host=settings.REDIS_HOST,
        port=settings.REDIS_PORT,
        username=settings.REDIS_USER,
        password=settings.REDIS_PASSWORD,
        decode_responses=True
    )
