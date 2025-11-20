# app/main.py
import time
import logging
from app.config import settings
from app.mqtt_client import MQTTClient
from app.archiver import Archiver
from app.db.client import init_db

def main():
    logging.basicConfig(level=settings.LOG_LEVEL)

    print("Inicializando Base de Datos...")
    init_db()

    mqtt = MQTTClient()
    archiver = Archiver()

    mqtt.start()
    archiver.start()

    print("Servicio EDGE iniciado.")

    try:
        while True:
            time.sleep(60)
    except KeyboardInterrupt:
        mqtt.stop()
        archiver.stop()

if __name__ == "__main__":
    main()
