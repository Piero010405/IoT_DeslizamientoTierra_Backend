# app/main.py
import logging
from app.config import settings
from app.mqtt_client import MQTTClient
from app.archiver import Archiver
from app.notifier import Notifier

def main():
    logging.basicConfig(level=settings.LOG_LEVEL)
    mqtt = MQTTClient()
    notifier = Notifier()
    archiver = Archiver()

    # iniciar mqtt client (con loop en background)
    mqtt.start()  # dejará el cliente en loop_start()

    # iniciar archiver como thread / scheduler
    archiver.start()

    # el proceso principal puede dormir o exponer health endpoint
    try:
        while True:
            time.sleep(60)
    except KeyboardInterrupt:
        mqtt.stop()
        archiver.stop()

if __name__ == "__main__":
    main()
