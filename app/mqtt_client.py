# app/mqtt_client.py
import json
import logging
import paho.mqtt.client as mqtt
from datetime import datetime

from app.config import settings
from app.cache_manager import CloudSensorCacheManager
from app.db.client import SessionLocal
from app.db.models import SensorPacket, SensorPanel

logger = logging.getLogger(__name__)


class MQTTClient:
    def __init__(self):

        # Cliente sin client_id (se genera automáticamente)
        self.client = mqtt.Client(
            client_id="edge_app",
            clean_session=False
        )

        self.client.on_connect = self.on_connect
        self.client.on_message = self.on_message

        self.cache = CloudSensorCacheManager()

    # ============
    # CONEXIÓN
    # ============
    def on_connect(self, client, userdata, flags, rc):
        if rc == 0:
            logger.info("[MQTT] Conectado correctamente a Mosquitto")
        else:
            logger.error(f"[MQTT] Error de conexión rc={rc}")

        # Te suscribes al topic raíz (tus sensores publican ahí)
        client.subscribe(settings.MQTT_TOPIC_PREFIX, qos=1)

    # ============
    # RECEPCIÓN
    # ============
    def on_message(self, client, userdata, msg):
        try:
            payload = json.loads(msg.payload.decode())
        except Exception:
            logger.error("⚠ Error: no se pudo parsear JSON recibido")
            return

        try:
            seq = payload["seq"]
            alerta = int(payload["alerta"])
            ts = datetime.fromisoformat(payload["ts"])
            samples = payload["samples"]
        except KeyError as e:
            logger.error(f"⚠ Payload inválido, falta campo: {e}")
            return

        # ============
        # GUARDAR EN REDIS
        # ============
        for sample in samples:
            sid = str(sample["id"])

            # Humedad
            if "soil" in sample:
                try:
                    self.cache.guardar_humedad(
                        sid,
                        porcentaje=sample["soil"]["pct"],
                        valor_raw=sample["soil"]["raw"]
                    )
                except Exception:
                    logger.error("⚠ Error guardando humedad")

            # Inclinación
            try:
                self.cache.guardar_inclinacion(sid, sample["tilt"])
            except Exception:
                logger.error("⚠ Error guardando inclinación")

            # Vibración
            try:
                self.cache.guardar_vibracion(
                    sid,
                    pulse=sample["vib"]["pulse"],
                    hit=sample["vib"]["hit"]
                )
            except Exception:
                logger.error("⚠ Error guardando vibración")

        # ============
        # GUARDAR EN POSTGRES
        # ============
        with SessionLocal() as db:
            try:
                p = SensorPacket(
                    seq=seq,
                    timestamp=ts,
                    alerta=bool(alerta)
                )
                db.add(p)
                db.flush()

                for sample in samples:
                    panel = SensorPanel(
                        sample_id=sample["id"],
                        soil_raw=sample["soil"]["raw"],
                        soil_pct=sample["soil"]["pct"],
                        tilt=sample["tilt"],
                        vib_pulse=sample["vib"]["pulse"],
                        vib_hit=sample["vib"]["hit"],
                        packet_id=p.id
                    )
                    db.add(panel)

                db.commit()

            except Exception as e:
                logger.exception(f"⚠ Error guardando en Postgres: {e}")
                db.rollback()

        # ============
        # ALERTA
        # ============
        try:
            if alerta == 1:
                from app.notifier import Notifier
                Notifier().enqueue_alert(payload)
        except Exception:
            logger.error("⚠ Error enviando alerta")

    # ============
    # ARRANCAR CLIENTE
    # ============
    def start(self):
        logger.info(f"[MQTT] Conectando a {settings.MQTT_HOST}:{settings.MQTT_PORT}")
        self.client.connect(settings.MQTT_HOST, settings.MQTT_PORT)
        self.client.loop_start()

    def stop(self):
        self.client.loop_stop()
        self.client.disconnect()
