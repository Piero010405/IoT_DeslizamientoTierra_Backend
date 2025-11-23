# app/mqtt_client.py
import json
import logging
import paho.mqtt.client as mqtt
from datetime import datetime, timezone

from app.config import settings
from app.cache_manager import CloudSensorCacheManager
from app.db.client import SessionLocal
from app.db.models import SensorPacket, SensorPanel

logger = logging.getLogger(__name__)


class MQTTClient:
    def __init__(self):

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
            samples = payload["samples"]

            # Timestamp REAL generado en backend
            ts = datetime.now(timezone.utc)
            payload["ts"] = ts.isoformat()

        except KeyError as e:
            logger.error(f"⚠ Payload inválido, falta campo: {e}")
            return

        # ============
        # GUARDAR ÚLTIMO PAQUETE EN REDIS
        # ============
        try:
            self.cache.guardar_ultimo_paquete(
                seq=seq,
                timestamp=ts.isoformat(),
                payload=payload
            )
        except Exception as e:
            logger.error(f"⚠ Error guardando último paquete en Redis → {e}")

        # ============
        # GUARDAR SENSORES EN REDIS (humedad, inclinación, vibración)
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
                except Exception as e:
                    logger.error(f"⚠ Error guardando humedad → {e}")

            # Inclinación
            try:
                self.cache.guardar_inclinacion(sid, sample["tilt"])
            except Exception as e:
                logger.error(f"⚠ Error guardando inclinación → {e}")

            # Vibración
            try:
                self.cache.guardar_vibracion(
                    sid,
                    pulse=sample["vib"]["pulse"],
                    hit=sample["vib"]["hit"]
                )
            except Exception as e:
                logger.error(f"⚠ Error guardando vibración → {e}")

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
                self.cache.guardar_alerta(
                    seq=seq,
                    ts=ts.isoformat(),
                    payload=payload
                )

                from app.notifier import Notifier
                Notifier().enqueue_alert(payload)

        except Exception as e:
            logger.error(f"⚠ Error procesando alerta → {e}")

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
