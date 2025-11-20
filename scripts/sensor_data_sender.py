# scripts/sensor_data_sender.py
import json
import time
import random
from datetime import datetime
import paho.mqtt.client as mqtt
import os
from dotenv import load_dotenv

# Cargar variables del archivo .env
load_dotenv()

MQTT_HOST = os.getenv("MQTT_HOST", "host.docker.internal")
MQTT_PORT = int(os.getenv("MQTT_PORT", "1883"))
TOPIC = os.getenv("TOPIC", "sensors/data")


def gen_random_packet():
    return {
        "seq": random.randint(1, 99999),
        "alerta": random.choice([0, 0, 0, 1]),
        "ts": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "samples": [
            {
                "id": 1,
                "soil": {"raw": random.randint(400, 900), "pct": random.randint(10, 80)},
                "tilt": random.choice([0, 1]),
                "vib": {"pulse": random.randint(50, 1000), "hit": random.choice([0, 1])}
            },
            {
                "id": 2,
                "soil": {"raw": random.randint(400, 900), "pct": random.randint(10, 80)},
                "tilt": random.choice([0, 1]),
                "vib": {"pulse": random.randint(50, 1000), "hit": random.choice([0, 1])}
            }
        ]
    }


def main():
    client = mqtt.Client()

    print(f"[MQTT] Conectando a {MQTT_HOST}:{MQTT_PORT} ...")
    client.connect(MQTT_HOST, MQTT_PORT)
    client.loop_start()

    while True:
        data = gen_random_packet()
        client.publish(TOPIC, json.dumps(data))
        print("[MQTT] Enviado:", data)
        time.sleep(2)


if __name__ == "__main__":
    main()
