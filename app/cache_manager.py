# app/cache_manager.py
from funcs.funciones_redis import SensorCacheManager

class CacheManager(SensorCacheManager):
    def __init__(self):
        # cargar host/port/cred desde settings en lugar de localhost
        from app.config import settings
        super().__init__(host=settings.REDIS_HOST,
                         port=settings.REDIS_PORT,
                         db=settings.REDIS_DB)
        # si tienes REDIS_URL, parseala y usa redis.from_url
