# app/notifier.py
import time, logging, requests
from app.config import settings
from app.cache_manager import CacheManager

logger = logging.getLogger(__name__)

class Notifier:
    def __init__(self):
        self.redis = CacheManager().redis_client  # usar redis para guardar timestamp de ultimo envio
        self.cooldown = settings.ALERT_COOLDOWN_SECONDS
        self.api_key = settings.RESEND_API_KEY
        self.from_addr = settings.RESEND_FROM
        self.to_addrs = settings.RESEND_TO

    def _can_send(self, alert_key):
        key = f"alert:sent:{alert_key}"
        last = self.redis.get(key)
        if last:
            last_ts = float(last)
            if time.time() - last_ts < self.cooldown:
                return False
        return True

    def _mark_sent(self, alert_key):
        key = f"alert:sent:{alert_key}"
        self.redis.setex(key, self.cooldown, str(time.time()))

    def send_email(self, subject, body, recipients=None):
        # ejemplo Resend: usar su API de emails (POST /emails)
        url = "https://api.resend.com/emails"
        headers = {"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"}
        payload = {
            "from": self.from_addr,
            "to": recipients or self.to_addrs,
            "subject": subject,
            "html": body
        }
        r = requests.post(url, headers=headers, json=payload, timeout=10)
        r.raise_for_status()
        return r.json()

    def enqueue_alert(self, alert_payload):
        # definir un identificador (ej sensor:tipo:seq)
        seq = alert_payload.get("seq")
        ts = alert_payload.get("ts")
        alert_key = f"{seq}:{ts}"
        if not self._can_send(alert_key):
            logger.info("Debounced alert %s", alert_key)
            return False

        subject = f"Alerta sensores seq:{seq}"
        body = f"<pre>{json.dumps(alert_payload, indent=2)}</pre>"
        try:
            self.send_email(subject, body)
            self._mark_sent(alert_key)
            logger.info("Alerta enviada %s", alert_key)
            return True
        except Exception as e:
            logger.exception("Error enviando alerta: %s", e)
            return False
