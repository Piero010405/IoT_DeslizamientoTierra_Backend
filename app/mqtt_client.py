# app/mqtt_client.py
import json, logging
import paho.mqtt.client as mqtt
from app.config import settings
from app.cache_manager import CacheManager

logger = logging.getLogger(__name__)

class MQTTClient:
    def __init__(self):
        self.client = mqtt.Client(client_id=settings.MQTT_CLIENT_ID, clean_session=False)
        if settings.MQTT_USER:
            self.client.username_pw_set(settings.MQTT_USER, settings.MQTT_PASS)
        self.client.on_connect = self.on_connect
        self.client.on_message = self.on_message
        self.cache = CacheManager()  # wrapper sobre funciones_redis.py

    def on_connect(self, client, userdata, flags, rc):
        logger.info("Conectado a MQTT, rc=%s", rc)
        client.subscribe(settings.MQTT_TOPIC_PREFIX, qos=1)

    def on_message(self, client, userdata, msg):
        try:
            payload = msg.payload.decode()
            data = json.loads(payload)
            # parseo según estructura enviada
            # su JSON contiene "samples": [...]
            for sample in data.get("samples", []):
                sensor_id = sample.get("id")
                # soil/humedad
                if "soil" in sample:
                    pct = sample["soil"].get("pct")
                    raw = sample["soil"].get("raw")
                    self.cache.guardar_humedad(sensor_id, porcentaje=pct, valor_raw=raw)
                if "tilt" in sample:
                    self.cache.guardar_inclinacion(sensor_id, estado=sample.get("tilt"))
                if "vib" in sample:
                    self.cache.guardar_vibracion(sensor_id, pulse=sample["vib"].get("pulse"), hit=sample["vib"].get("hit"))

                # si campo alerta==1 en el mensaje padre -> notificador externo
            # gestionar alert global
            if data.get("alerta") == 1:
                from app.notifier import Notifier
                Notifier().enqueue_alert(data)
        except Exception as e:
            logger.exception("Error procesando mensaje MQTT: %s", e)

    def start(self):
        self.client.connect(settings.MQTT_HOST, settings.MQTT_PORT, keepalive=60)
        self.client.loop_start()

    def stop(self):
        self.client.loop_stop()
        self.client.disconnect()
