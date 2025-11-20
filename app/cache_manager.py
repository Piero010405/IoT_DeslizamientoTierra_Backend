# app/cache_manager.py
from funcs.funciones_redis import SensorCacheManager
from app.cache_client import create_redis_client


class CloudSensorCacheManager(SensorCacheManager):
    """
    Extiende SensorCacheManager para usar SIEMPRE Redis Cloud.
    Reemplaza el redis_client interno del manager original.
    """
    def __init__(self):
        super().__init__(host="localhost", port=6379, db=0)  # valores dummy
        self.redis_client = create_redis_client()
