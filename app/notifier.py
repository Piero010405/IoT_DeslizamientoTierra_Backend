# app/notifier.py
import time
import logging
import json
import resend

from app.config import settings
from app.cache_manager import CloudSensorCacheManager as CacheManager

logger = logging.getLogger(__name__)


class Notifier:
    def __init__(self):
        # Redis para cooldown
        self.redis = CacheManager().redis_client

        # Config
        self.cooldown = settings.ALERT_COOLDOWN_SECONDS
        self.api_key = settings.RESEND_API_KEY
        self.from_addr = settings.RESEND_FROM
        self.to_addrs = self._parse_recipients(settings.RESEND_TO)

        # Inicializar Resend API
        resend.api_key = self.api_key

    # ======================================================
    # Helpers
    # ======================================================

    def _parse_recipients(self, value):
        """
        Permite que RESEND_TO sea:
        - un correo único
        - una lista separada por comas
        - un array en .env (si usas python-dotenv 1.0)
        """
        if isinstance(value, list):
            return value

        if "," in value:
            return [v.strip() for v in value.split(",")]

        return [value]

    def _can_send(self, alert_key):
        """
        Devuelve True si han pasado más de N segundos desde el último envío de esta alerta.
        """
        redis_key = f"alert:sent:{alert_key}"
        last_ts = self.redis.get(redis_key)

        if last_ts is None:
            return True

        try:
            last_ts = float(last_ts)
        except ValueError:
            return True  # Valor corrupto → permitir envío

        now = time.time()
        if now - last_ts < self.cooldown:
            logger.info(f"[NOTIFIER] Cooldown activo para {alert_key}")
            return False

        return True

    def _mark_sent(self, alert_key):
        redis_key = f"alert:sent:{alert_key}"
        self.redis.setex(redis_key, self.cooldown, str(time.time()))

    # ======================================================
    # Email Sender
    # ======================================================

    def send_email(self, subject, html):
        """
        Wrapper directo al cliente oficial Resend v2.x.x
        """
        try:
            response = resend.Emails.send({
                "from": self.from_addr,
                "to": self.to_addrs,
                "subject": subject,
                "html": html,
            })

            logger.info(f"[NOTIFIER] Email enviado: {response}")
            return True

        except Exception as e:
            logger.exception("Error enviando email con Resend: %s", e)
            return False

    # ======================================================
    # Main alert handler
    # ======================================================

    def enqueue_alert(self, alert_payload):
        """
        alert_payload = {
            "seq": 10,
            "alerta": 1,
            "ts": "2025-11-19 22:01:00",
            "samples": [...]
        }
        """

        seq = alert_payload.get("seq")
        ts = alert_payload.get("ts")

        if seq is None or ts is None:
            logger.error("[NOTIFIER] Payload de alerta inválido: falta seq o ts")
            return False

        alert_key = f"{seq}:{ts}"

        if not self._can_send(alert_key):
            return False

        subject = f"⚠️ Alerta detectada — paquete seq={seq}"
        html_body = (
            "<h2>Alerta generada por sensores</h2>"
            "<p>A continuación los datos del evento:</p>"
            f"<pre>{json.dumps(alert_payload, indent=2)}</pre>"
        )

        sent = self.send_email(subject, html_body)

        if sent:
            self._mark_sent(alert_key)

        return sent
