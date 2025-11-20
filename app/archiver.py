# app/archiver.py
import threading, time, logging
from datetime import datetime, timedelta
from app.config import settings
from app.cache_manager import CacheManager
from app.db.client import pg_session
from app.db.models import SensorReading

logger = logging.getLogger(__name__)

class Archiver(threading.Thread):
    def __init__(self):
        super().__init__(daemon=True)
        self._stop = threading.Event()
        self.cache = CacheManager()
        self.interval = settings.ARCHIVER_RUN_EVERY_MINUTES * 60

    def run(self):
        while not self._stop.wait(self.interval):
            try:
                self.archive_once()
            except Exception as e:
                logger.exception("Archiver error: %s", e)

    def archive_once(self):
        # ejemplo por tiempo: mover lecturas anteriores a (now - threshold_days)
        threshold = datetime.utcnow() - timedelta(days=settings.ARCHIVE_THRESHOLD_DAYS)
        # asumiendo que tus históricos usan listas "sensor:tipo:id:historico" con timestamp en cada elemento
        # buscar keys con pattern
        for tipo in ['humedad','vibracion','inclinacion']:
            pattern = f"sensor:{tipo}:*:historico"
            for key in self.cache.redis_client.scan_iter(match=pattern):
                items = self.cache.redis_client.lrange(key, 0, -1)
                to_archive = []
                keep = []
                for item in items:
                    obj = json.loads(item)
                    ts = datetime.fromisoformat(obj['timestamp'])
                    if ts < threshold:
                        to_archive.append(obj)
                    else:
                        keep.append(item)
                # insertar to_archive en Postgres
                with pg_session() as session:
                    for obj in to_archive:
                        sr = SensorReading.from_cache_obj(tipo, obj)
                        session.add(sr)
                    session.commit()
                # reescribir lista con keep (mantener orden)
                if to_archive:
                    self.cache.redis_client.ltrim(key, 0, len(keep)-1)  # ejemplo simple; ajustar según orden
