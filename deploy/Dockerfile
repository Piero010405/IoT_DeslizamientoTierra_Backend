FROM python:3.11-slim

# ==========
# 1. Sistema base
# ==========
WORKDIR /app

# Instalamos dependencias básicas del OS para psycopg2-binary
RUN apt-get update && apt-get install -y \
    build-essential \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# ==========
# 2. Instalar dependencias de Python
# ==========
COPY app/requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt

# ==========
# 3. Copiar proyecto
# ==========
COPY . /app

ENV PYTHONUNBUFFERED=1

# ==========
# 4. Comando por defecto
# ==========
CMD ["python", "-u", "app/main.py"]
