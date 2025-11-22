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

    def _generate_insights(self, payload):
        insights = []
        samples = payload.get("samples", [])

        for s in samples:
            sid = s.get("id")

            # Humedad
            soil = s.get("soil", {})
            pct = soil.get("pct")
            if pct is not None:
                if pct > 80:
                    insights.append(f"• Sensor #{sid}: humedad extremadamente alta ({pct}%).")
                elif pct < 20:
                    insights.append(f"• Sensor #{sid}: humedad peligrosamente baja ({pct}%).")

            # Inclinación
            if s.get("tilt") == 1:
                insights.append(f"• Sensor #{sid}: inclinación detectada.")

            # Vibración
            vib = s.get("vib", {})
            pulse = vib.get("pulse")
            if pulse and pulse > 800:
                insights.append(f"• Sensor #{sid}: vibración elevada (pulse={pulse}).")

            if vib.get("hit") == 1:
                insights.append(f"• Sensor #{sid}: impacto detectado.")

        if not insights:
            return "<p>No se detectaron anomalías adicionales en los sensores.</p>"

        return "<br>".join(f"<p>{i}</p>" for i in insights)


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
        html_body = f"""
        <table width="100%" cellpadding="0" cellspacing="0" 
            style="background:#0b0f14;padding:20px;font-family:Arial,Helvetica,sans-serif;color:#e6e6e6;">
        <tr>
            <td align="center">
            <table width="600" cellpadding="0" cellspacing="0" 
                    style="background:#141a22;border-radius:12px;overflow:hidden;border:1px solid #1f2933;">
                
                <!-- Header -->
                <tr>
                <td style="background:#0d1218;padding:20px;text-align:center;">
                    <h1 style="margin:0;font-size:24px;color:#32ff9b;">
                    ⚠️ Alerta de Monitoreo — Instituto Geofísico del Perú
                    </h1>
                    <p style="margin:8px 0 0;color:#9ca3af;font-size:13px;">
                    Sistema de vigilancia de deslizamientos en tiempo real
                    </p>
                </td>
                </tr>

                <!-- Body -->
                <tr>
                <td style="padding:25px;color:#e5e5e5;font-size:15px;line-height:1.5;">
                    <h2 style="color:#32ff9b;margin-top:0;">Detalles de la alerta</h2>

                    <p><strong>Secuencia:</strong> {seq}</p>
                    <p><strong>Timestamp:</strong> {ts}</p>

                    <!-- Insights -->
                    <div style="margin-top:20px;padding:15px;background:#1d242d;border-left:4px solid #32ff9b;border-radius:6px;">
                    <h3 style="margin-top:0;color:#32ff9b;">🔍 Análisis rápido del evento</h3>
                    {self._generate_insights(alert_payload)}
                    </div>

                    <h3 style="color:#32ff9b;margin-top:30px;">📦 Datos completos del paquete</h3>
                    <pre style="
                    background:#0d1117;
                    color:#8affc7;
                    padding:16px;
                    border-radius:8px;
                    font-size:13px;
                    line-height:1.4;
                    white-space:pre-wrap;
                    ">{json.dumps(alert_payload, indent=2)}</pre>

                    <p style="color:#6b7280;font-size:13px;margin-top:20px;text-align:center;">
                    Enviado automáticamente por el sistema EDGE IoT — Proyecto de Monitoreo de Deslizamientos
                    </p>
                </td>
                </tr>

            </table>
            </td>
        </tr>
        </table>
        """


        sent = self.send_email(subject, html_body)

        if sent:
            self._mark_sent(alert_key)

        return sent
