import os
from types import SimpleNamespace
import yaml


def _dict_to_ns(obj):
    if isinstance(obj, dict):
        return SimpleNamespace(**{k: _dict_to_ns(v) for k, v in obj.items()})
    elif isinstance(obj, list):
        return [_dict_to_ns(i) for i in obj]
    return obj


# 1) Cargar YAML
yaml_path = os.path.join(os.path.dirname(__file__), "config.yaml")
with open(yaml_path, "r") as f:
    data = yaml.safe_load(f)

cfg = _dict_to_ns(data)


# 2) Fusionar YAML + .env → crear settings planos
class Settings:
    # MQTT
    MQTT_HOST = os.getenv("MQTT_HOST", cfg.mqtt.host)
    MQTT_PORT = int(os.getenv("MQTT_PORT", cfg.mqtt.port))
    MQTT_TOPIC_PREFIX = os.getenv("MQTT_TOPIC_PREFIX", cfg.mqtt.topic_prefix)

    MQTT_USER = os.getenv("MQTT_USER", cfg.mqtt.user)
    MQTT_PASS = os.getenv("MQTT_PASS", cfg.mqtt.password)

    # Redis
    REDIS_HOST = os.getenv("REDIS_HOST")
    REDIS_PORT = os.getenv("REDIS_PORT")
    REDIS_USER = os.getenv("REDIS_USER")
    REDIS_PASSWORD = os.getenv("REDIS_PASSWORD")

    # Email alerts
    RESEND_API_KEY = os.getenv("RESEND_API_KEY")
    RESEND_FROM = os.getenv("RESEND_FROM", cfg.alerts.resend_email_from)
    RESEND_TO = os.getenv("RESEND_TO", ",".join(cfg.alerts.resend_email_to))

    # Otros
    APP_ENV = os.getenv("APP_ENV", "development")

    # Archiver
    ARCHIVER_MODE = cfg.archiver.mode
    ARCHIVE_THRESHOLD_DAYS = cfg.archiver.threshold_days
    ARCHIVER_RUN_EVERY_MINUTES = cfg.archiver.run_every_minutes


settings = Settings()
