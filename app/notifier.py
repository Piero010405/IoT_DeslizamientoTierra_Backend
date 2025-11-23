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

    def _can_send(self):
        """
        Devuelve True si han pasado más de N segundos desde la última alerta enviada.
        """
        redis_key = "alert:last_sent"
        last_ts = self.redis.get(redis_key)

        if last_ts is None:
            return True

        try:
            last_ts = float(last_ts)
        except ValueError:
            return True  # si algo raro ocurrió

        now = time.time()

        # Diferencia en segundos
        diff = now - last_ts
        if diff < self.cooldown:
            logger.info(f"[NOTIFIER] Cooldown activo ({int(self.cooldown - diff)}s restantes)")
            return False

        return True


    def _mark_sent(self):
        """Marca el timestamp del último correo enviado."""
        redis_key = "alert:last_sent"
        self.redis.set(redis_key, str(time.time()))

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

    def _progress_bar(self, value, color):
        value = max(0, min(100, int(value)))  # clamp

        return f"""
        <div style="width:100%;background:#0d1117;height:10px;border-radius:4px;margin-top:4px;">
            <div style="width:{value}%;height:10px;background:{color};border-radius:4px;"></div>
        </div>
        """

    
    def _format_payload_as_tables_and_visuals(self, payload):
        seq = payload.get("seq")
        alerta = payload.get("alerta")
        ts = payload.get("ts")
        samples = payload.get("samples", [])

        alerta_txt = "Sí (1)" if alerta == 1 else "No (0)"

        html = f"""
        <h3 style="color:#32ff9b;">📋 Datos Generales</h3>
        <table style="width:100%;border-collapse:collapse;">
            <tr><td style="border:1px solid #1f2933;padding:8px;">Secuencia</td>
                <td style="border:1px solid #1f2933;padding:8px;">{seq}</td></tr>
            <tr><td style="border:1px solid #1f2933;padding:8px;">Es alerta</td>
                <td style="border:1px solid #1f2933;padding:8px;">{alerta_txt}</td></tr>
            <tr><td style="border:1px solid #1f2933;padding:8px;">Timestamp</td>
                <td style="border:1px solid #1f2933;padding:8px;">{ts}</td></tr>
        </table>

        <h3 style="color:#32ff9b;margin-top:30px;">🧪 Detalle por Sensor</h3>
        """

        for s in samples:
            sid = s.get("id", "?")

            soil = s.get("soil", {})
            humid_pct = soil.get("pct", 0)

            vib = s.get("vib", {})
            vib_pulse = vib.get("pulse", 0)

            tilt = s.get("tilt", 0)
            hit = vib.get("hit", 0)

            tilt_txt = "Inclinado (1)" if tilt == 1 else "Normal (0)"
            hit_txt = "Sí (1)" if hit == 1 else "No (0)"

            html += f"""
            <div style="margin-top:25px;">
                <h4 style="color:#72ffbf;">Sensor #{sid}</h4>

                <table style="width:100%;border-collapse:collapse;">
                    <tr>
                        <td style="border:1px solid #1f2933;padding:8px;">Humedad (%)</td>
                        <td style="border:1px solid #1f2933;padding:8px;">
                            {humid_pct}%<br>
                            {self._progress_bar(humid_pct, "#32ff9b")}
                        </td>
                    </tr>

                    <tr>
                        <td style="border:1px solid #1f2933;padding:8px;">Vibración (pulse)</td>
                        <td style="border:1px solid #1f2933;padding:8px;">
                            {vib_pulse}<br>
                            {self._progress_bar(min(vib_pulse/10,100), "#39c7ff")}
                        </td>
                    </tr>

                    <tr>
                        <td style="border:1px solid #1f2933;padding:8px;">Inclinación (tilt)</td>
                        <td style="border:1px solid #1f2933;padding:8px;">{tilt_txt}</td>
                    </tr>

                    <tr>
                        <td style="border:1px solid #1f2933;padding:8px;">Impacto (hit)</td>
                        <td style="border:1px solid #1f2933;padding:8px;">{hit_txt}</td>
                    </tr>
                </table>

                <p style="color:#9ca3af;font-size:12px;margin-top:10px;">
                    • <strong>pct:</strong> porcentaje de humedad estimado<br>
                    • <strong>pulse:</strong> intensidad de vibración detectada<br>
                    • <strong>tilt:</strong> 1 indica inclinación peligrosa<br>
                    • <strong>hit:</strong> 1 indica impacto brusco<br>
                </p>
            </div>
            """

        return html

    def _format_payload_as_tables_and_visuals(self, payload):
        seq = payload.get("seq")
        alerta = payload.get("alerta")
        ts = payload.get("ts")
        samples = payload.get("samples", [])

        alerta_txt = "Sí (1)" if alerta == 1 else "No (0)"

        html = f"""
        <h3 style="color:#32ff9b;">📋 Datos Generales</h3>
        <table style="width:100%;border-collapse:collapse;">
            <tr><td style="border:1px solid #1f2933;padding:8px;">Secuencia</td>
                <td style="border:1px solid #1f2933;padding:8px;">{seq}</td></tr>
            <tr><td style="border:1px solid #1f2933;padding:8px;">Es alerta</td>
                <td style="border:1px solid #1f2933;padding:8px;">{alerta_txt}</td></tr>
            <tr><td style="border:1px solid #1f2933;padding:8px;">Timestamp</td>
                <td style="border:1px solid #1f2933;padding:8px;">{ts}</td></tr>
        </table>

        <h3 style="color:#32ff9b;margin-top:30px;">🧪 Detalle por Sensor</h3>
        """

        for s in samples:
            sid = s.get("id", "?")

            soil = s.get("soil", {})
            humid_pct = soil.get("pct", 0)

            vib = s.get("vib", {})
            vib_pulse = vib.get("pulse", 0)

            tilt = s.get("tilt", 0)
            hit = vib.get("hit", 0)

            tilt_txt = "Inclinado (1)" if tilt == 1 else "Normal (0)"
            hit_txt = "Sí (1)" if hit == 1 else "No (0)"

            html += f"""
            <div style="margin-top:25px;">
                <h4 style="color:#72ffbf;">Sensor #{sid}</h4>

                <table style="width:100%;border-collapse:collapse;">
                    <tr>
                        <td style="border:1px solid #1f2933;padding:8px;">Humedad (%)</td>
                        <td style="border:1px solid #1f2933;padding:8px;">
                            {humid_pct}%<br>
                            {self._progress_bar(humid_pct, "#32ff9b")}
                        </td>
                    </tr>

                    <tr>
                        <td style="border:1px solid #1f2933;padding:8px;">Vibración (pulse)</td>
                        <td style="border:1px solid #1f2933;padding:8px;">
                            {vib_pulse}<br>
                            {self._progress_bar(min(vib_pulse/10,100), "#39c7ff")}
                        </td>
                    </tr>

                    <tr>
                        <td style="border:1px solid #1f2933;padding:8px;">Inclinación (tilt)</td>
                        <td style="border:1px solid #1f2933;padding:8px;">{tilt_txt}</td>
                    </tr>

                    <tr>
                        <td style="border:1px solid #1f2933;padding:8px;">Impacto (hit)</td>
                        <td style="border:1px solid #1f2933;padding:8px;">{hit_txt}</td>
                    </tr>
                </table>

                <p style="color:#9ca3af;font-size:12px;margin-top:10px;">
                    • <strong>pct:</strong> porcentaje de humedad estimado<br>
                    • <strong>pulse:</strong> intensidad de vibración detectada<br>
                    • <strong>tilt:</strong> 1 indica inclinación peligrosa<br>
                    • <strong>hit:</strong> 1 indica impacto brusco<br>
                </p>
            </div>
            """

        return html


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

        if not self._can_send():
            return False

        subject = f"⚠️ Alerta detectada — paquete seq={seq}"

         # Render datos en tabla + barras visuales
        pretty_tables = self._format_payload_as_tables_and_visuals(alert_payload)

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

                    <!-- ALERTA ROJA -->
                    <tr>
                    <td style="padding:18px;background:#2b0f12;border-left:4px solid #ff4d4d;">
                        <p style="margin:0;font-size:15px;color:#ff9999;">
                        ⚠️ <strong>ALERTA CRÍTICA:</strong> Se han detectado condiciones que podrían indicar riesgo de deslizamiento.
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

                        <h3 style="color:#32ff9b;margin-top:30px;">📊 Resumen del paquete (estilo dashboard)</h3>

                        {pretty_tables}

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
            self._mark_sent()

        return sent
