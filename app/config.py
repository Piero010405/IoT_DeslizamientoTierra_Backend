import os
from dotenv import load_dotenv

load_dotenv()

class Settings:
    REDIS_URL = os.getenv("REDIS_URL")

    DATABASE_URL = os.getenv("DATABASE_URL")

    MQTT_HOST = os.getenv("MQTT_HOST")
    MQTT_PORT = int(os.getenv("MQTT_PORT", "1883"))
    MQTT_USER = os.getenv("MQTT_USER")
    MQTT_PASS = os.getenv("MQTT_PASS")
    MQTT_CLIENT_ID = os.getenv("MQTT_CLIENT_ID")
    MQTT_TOPIC_PREFIX = os.getenv("MQTT_TOPIC_PREFIX")

    ALERT_COOLDOWN_SECONDS = int(os.getenv("ALERT_COOLDOWN_SECONDS", "300"))
    ARCHIVE_THRESHOLD_DAYS = int(os.getenv("ARCHIVE_THRESHOLD_DAYS", "1"))
    ARCHIVER_RUN_EVERY_MINUTES = int(os.getenv("ARCHIVER_RUN_EVERY_MINUTES", "60"))

    LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")

    RESEND_API_KEY = os.getenv("RESEND_API_KEY")
    RESEND_FROM = os.getenv("RESEND_FROM")
    RESEND_TO = os.getenv("RESEND_TO")


settings = Settings()
