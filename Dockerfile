FROM python:3.11-slim

WORKDIR /app

# Dependencias del sistema para psycopg2 / numpy / scikit-learn
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential libpq-dev \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copiamos ambos módulos preservando su estructura (no se aplanan)
COPY etl/ ./etl/
COPY model_api/ ./model_api/
COPY wsgi.py .

ENV PORT=8000
EXPOSE 8000

# --workers 1 a propósito: el modelo en memoria y el hot-swap viven en el
# proceso; con un único worker + threads, dashboard y modelo comparten estado.
CMD gunicorn --workers 1 --threads 4 --timeout 120 --bind 0.0.0.0:${PORT} wsgi:application
