FROM python:3.11-slim

WORKDIR /app

# Rutas relativas al root bank-pipeline/ (build context en Render)
COPY etl/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY etl/db.py .
COPY etl/process_data.py .

# CSV eliminado del contenedor: se carga dinámicamente desde el dashboard

COPY etl/app.py .
COPY etl/templates/ /app/templates/

CMD ["python", "app.py"]
