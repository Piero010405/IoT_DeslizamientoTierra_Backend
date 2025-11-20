# app/archiver.py
import threading
import time
import logging
import json
from datetime import datetime, timedelta

from app.config import settings
from app.cache_manager import CloudSensorCacheManager as CacheManager
from app.db.client import SessionLocal
from app.db.models import SensorPacket, SensorPanel

logger = logging.getLogger(__name__)


class Archiver(threading.Thread):
    def __init__(self):
        super().__init__(daemon=True)
        self._stop = threading.Event()
        self.cache = CacheManager()
        self.interval = settings.ARCHIVER_RUN_EVERY_MINUTES * 60

     # Método para parar el hilo
    def stop(self):
        self._stop.set()

    def run(self):
        while not self._stop.wait(self.interval):
            try:
                self.archive_once()
            except Exception as e:
                logger.exception("Archiver error: %s", e)

    def archive_once(self):
        """
        Lee datos desde Redis y los mueve a Postgres como históricos.
        Mueve únicamente los datos cuya fecha < threshold (fríos).
        """
        logger.info("Archiver: iniciando ciclo de archivado...")

        threshold_days = settings.ARCHIVE_THRESHOLD_DAYS
        threshold = datetime.utcnow() - timedelta(days=threshold_days)

        # Keys en Redis con historicos
        patterns = [
            "sensor:humedad:*:historico",
            "sensor:vibracion:*:historico",
            "sensor:inclinacion:*:historico"
        ]

        redis = self.cache.redis_client

        for pattern in patterns:
            for key in redis.scan_iter(match=pattern):
                items = redis.lrange(key, 0, -1)
                cold_items = []
                keep_items = []

                for raw in items:
                    obj = json.loads(raw)
                    ts = datetime.fromisoformat(obj["timestamp"])

                    if ts < threshold:
                        cold_items.append(obj)
                    else:
                        keep_items.append(raw)

                if cold_items:
                    logger.info(f"Archiver: {len(cold_items)} items fríos en {key}")

                    # Guardar en BD histórica
                    self._write_to_postgres(cold_items)

                    # Actualizar Redis con solo los calientes
                    redis.delete(key)
                    for item in keep_items:
                        redis.lpush(key, item)

    def _write_to_postgres(self, items):
        """Inserta lecturas frías en la BD usando tu estructura oficial."""
        with SessionLocal() as session:
            for packet_obj in items:

                pkt = SensorPacket(
                    seq=packet_obj.get("seq"),
                    timestamp=datetime.fromisoformat(packet_obj["timestamp"]),
                    alerta=packet_obj.get("alerta", 0)
                )
                session.add(pkt)
                session.flush()  # Obtener id

                for sample in packet_obj.get("samples", []):
                    panel = SensorPanel(
                        sample_id=sample["id"],
                        soil_raw=sample["soil"]["raw"],
                        soil_pct=sample["soil"]["pct"],
                        tilt=sample["tilt"],
                        vib_pulse=sample["vib"]["pulse"],
                        vib_hit=sample["vib"]["hit"],
                        packet_id=pkt.id
                    )
                    session.add(panel)

            session.commit()
