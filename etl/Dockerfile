FROM python:3.11-slim

WORKDIR /app

# Rutas relativas al root bank-pipeline/ (build context en Render)
COPY etl/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY etl/process_data.py .

# Incluye el CSV dentro de la imagen (Render no tiene volumes)
COPY data/bank.csv /data/bank.csv

CMD ["python", "process_data.py"]
