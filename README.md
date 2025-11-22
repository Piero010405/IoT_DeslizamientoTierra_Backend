# 📦 IoT EDGE BACKEND — Proyecto Dockerizado

Este proyecto implementa:

✔ Backend Edge en Python
✔ Suscriptor MQTT (ESP32 → Mosquitto → Backend)
✔ Cacheo de datos en Redis Cloud
✔ Persistencia histórica en Postgres (Render) o SQLite (modo dev)
✔ Envío de alertas vía Resend
✔ Simulador de sensores MQTT para pruebas

## 🚀 1. Requisitos

Docker + Docker Compose

Mosquitto corriendo en tu máquina local:

mosquitto -v

Archivo .env configurado correctamente

Redis Cloud (host, port, username, password)

Opcional: Postgres en Render

## ⚙️ 2. Archivo .env de ejemplo

Crea .env en la raíz:

```ini
APP_ENV=development

# MQTT
MQTT_HOST=host.docker.internal
MQTT_PORT=1883
MQTT_TOPIC_PREFIX=sensors/#

# Redis Cloud
REDIS_HOST=redis-xxxxx.gce.cloud.redislabs.com
REDIS_PORT=16138
REDIS_USER=default
REDIS_PASSWORD=xxxxxxxxxxxx

# Base de datos (Render)
DATABASE_URL=

# Resend
RESEND_API_KEY=xxxxxxx
RESEND_FROM=alerts@yourdomain.com
RESEND_TO=your_email@example.com

LOG_LEVEL=INFO
```

## 🏗 3. Construir contenedores

```bash
docker-compose build
```

## ▶️ 4. Ejecutar proyecto

```bash
docker-compose up
```

Esto lanzará dos contenedores:

edge_app

Ejecuta app/main.py

Escucha MQTT

Guarda en Redis Cloud

Sincroniza histórico con DB

Envía alertas vía Resend

sensor_simulator

## ▶️ 5. Ejecutar el envio de data simulado (opcional)

Ejecuta el scripts/sensor_data_sender.py

```bash
docker compose --profile sim up sensor_simulator
```

Envía paquetes JSON cada 2 segundos al broker MQTT

## 📡 5. Simulación de Sensores

El contenedor sensor_simulator enviará mensajes como:

```json
{
  "seq": 123,
  "alerta": 0,
  "ts": "2025-02-01 12:33:10",
  "samples": [
    {
      "id": 1,
      "soil": {"raw": 612, "pct": 40},
      "tilt": 0,
      "vib": {"pulse": 900, "hit": 0}
    },
    {
      "id": 2,
      "soil": {"raw": 701, "pct": 31},
      "tilt": 1,
      "vib": {"pulse": 1320, "hit": 1}
    }
  ]
}
```

## 🗄 6. Base de datos

Modo desarrollo:

Si APP_ENV=development o DATABASE_URL= vacío:

➡ usa SQLite local en local_dev.sqlite

Modo producción:

Cuando tengas tu base en Render:

```ini
APP_ENV=production
DATABASE_URL=postgres://user:pass@host/db
```

## 🔔 7. Alertas vía Resend

En notifier.py usamos:

```python
import resend
resend.api_key = settings.RESEND_API_KEY
resend.Emails.send({...})
```

## 🔍 8. Logs

Ver logs del edge app:

```bash
docker logs -f edge_app
```

Ver logs del simulador:

```bash
docker logs -f sensor_simulator
```

## 🛑 9. Detener

```bash
docker-compose down
```

## 🧪 10. Pruebas manuales MQTT

Si quieres publicar manualmente un mensaje:

```bash
mosquitto_pub -h localhost -t sensors/data -m '{"seq":1,"alerta":1,...}'
```
