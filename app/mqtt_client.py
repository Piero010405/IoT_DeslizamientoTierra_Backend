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
        self.client = mqtt.Client(
            client_id=settings.MQTT_CLIENT_ID,
            clean_session=False
        )

        if settings.MQTT_USER:
            self.client.username_pw_set(settings.MQTT_USER, settings.MQTT_PASS)

        self.client.on_connect = self.on_connect
        self.client.on_message = self.on_message

        self.cache = CloudSensorCacheManager()

    def on_connect(self, client, userdata, flags, rc):
        logger.info(f"[MQTT] Conectado rc={rc}")
        client.subscribe(settings.MQTT_TOPIC_PREFIX, qos=1)

    def on_message(self, client, userdata, msg):
        try:
            payload = json.loads(msg.payload.decode())
            seq = payload["seq"]
            alerta = int(payload["alerta"])
            ts = datetime.fromisoformat(payload["ts"])

            # Guardado en Redis
            for sample in payload["samples"]:
                sid = str(sample["id"])

                if "soil" in sample:
                    self.cache.guardar_humedad(
                        sid,
                        porcentaje=sample["soil"]["pct"],
                        valor_raw=sample["soil"]["raw"]
                    )

                self.cache.guardar_inclinacion(sid, sample["tilt"])
                self.cache.guardar_vibracion(
                    sid,
                    pulse=sample["vib"]["pulse"],
                    hit=sample["vib"]["hit"]
                )

            # Guardado en Postgres
            with SessionLocal() as db:
                p = SensorPacket(seq=seq, timestamp=ts, alerta=bool(alerta))
                db.add(p)
                db.flush()

                for sample in payload["samples"]:
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

            # Si alerta == 1 → Notificar
            if alerta == 1:
                from app.notifier import Notifier
                Notifier().enqueue_alert(payload)

        except Exception as e:
            logger.exception(f"Error procesando MQTT: {e}")

    def start(self):
        self.client.connect(settings.MQTT_HOST, settings.MQTT_PORT)
        self.client.loop_start()

    def stop(self):
        self.client.loop_stop()
        self.client.disconnect()
