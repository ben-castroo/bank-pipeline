FROM python:3.11-slim

WORKDIR /app

# Dependencias del sistema mínimas para psycopg2 / numpy
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential libpq-dev \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

ENV PORT=8000
EXPOSE 8000

# IMPORTANTE: --workers 1 a propósito.
# El modelo en memoria y el estado del hot-swap viven en el proceso; con un
# único worker (y varios threads) todo el servicio comparte el mismo modelo.
# Más workers requerirían un mecanismo de recarga compartido (limitación
# conocida del free tier, documentada en el informe).
CMD gunicorn --workers 1 --threads 4 --timeout 120 --bind 0.0.0.0:${PORT} app:app
