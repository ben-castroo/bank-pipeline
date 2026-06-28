# model_api — Servicio de predicción de depósito a plazo

API REST (Flask) que predice la probabilidad de que un cliente suscriba un
depósito a plazo (`deposit`), usando los datos ya limpios de `bank_clean`.
Se integra al pipeline existente: los datos se suben por la UI del ETL, se
limpian y se guardan en Supabase; este servicio los puntúa.

## Arquitectura

```
Dashboard ETL (Flask)  ──>  bank_clean (Supabase)  ──>  model_api (este servicio)
                                                              │
                                          predicciones ───────┤──> model_scores (Supabase) ──> Metabase
                                          modelo .joblib ─────┘──> Supabase Storage (hot reload)
```

- **Predicción**: liviana y síncrona. Recibe `raw_id`(s), busca en `bank_clean`,
  predice y escribe en `model_scores`.
- **Reentrenamiento**: pesado y asíncrono. Entrena sobre una **muestra
  estratificada** (default 5.000), sube el nuevo modelo a Storage, hace
  **hot swap** en memoria y registra el job en `retrain_jobs`.
- **Modelo**: el pipeline completo de scikit-learn (preprocesamiento +
  clasificador) se serializa junto en un solo `.joblib` → sin train/serve skew.
- `duration` se excluye del modelo (data leakage).

## Tablas que crea (automáticamente al arrancar)

- `model_scores`: `id, raw_id, prob_deposit, pred_deposit, threshold, model_version, scored_at`
- `retrain_jobs`: `job_id, status, sample_size, model_version, metrics, started_at, finished_at, error`

## Setup local

```bash
cd model_api
cp .env.example .env          # completa tus credenciales
pip install -r requirements.txt

# 1) entrena y hornea el modelo base (una vez)
python train_base_model.py --sample 10000      # o --csv data/bank_clean_export.csv

# 2) levanta el API
python app.py                  # http://localhost:8000
```

## Endpoints

| Método | Ruta | Descripción | Auth |
|---|---|---|---|
| GET | `/health` | Estado y versión del modelo | No |
| GET | `/model-info` | Algoritmo, versión y métricas | Sí |
| POST | `/predict` | Predice un `raw_id` | Sí |
| POST | `/predict/batch` | Predice una lista de `raw_ids` | Sí |
| POST | `/retrain` | Lanza reentrenamiento (job async) | Sí |
| GET | `/retrain/status/<job_id>` | Estado del job | Sí |

Autenticación: header `X-API-Key: <tu API_KEY>`.

### Ejemplos

```bash
# Predicción individual
curl -X POST http://localhost:8000/predict \
  -H "X-API-Key: $API_KEY" -H "Content-Type: application/json" \
  -d '{"raw_id": 42, "threshold": 0.4}'

# Respuesta:
# {"raw_id":42,"prob_deposit":0.7312,"pred_deposit":true,"model_version":"2025-06-28T15:30:00Z","threshold":0.4}

# Lote
curl -X POST http://localhost:8000/predict/batch \
  -H "X-API-Key: $API_KEY" -H "Content-Type: application/json" \
  -d '{"raw_ids": [1,2,3], "threshold": 0.5}'

# Reentrenar (responde de inmediato con job_id)
curl -X POST http://localhost:8000/retrain \
  -H "X-API-Key: $API_KEY" -H "Content-Type: application/json" \
  -d '{"sample_size": 5000}'

# Estado del job
curl http://localhost:8000/retrain/status/<job_id> -H "X-API-Key: $API_KEY"
```

## Despliegue en Render

Usa `render.yaml` (Blueprint) o crea un Web Service Docker con `rootDir=model_api`.
Carga como secretos: `SUPABASE_DB_URL`, `SUPABASE_PROJECT_URL`,
`SUPABASE_SERVICE_KEY`, `API_KEY`. El `healthCheckPath` es `/health`.

## Para reentrenar desde la UI del ETL

La interfaz del dashboard (otro servicio) llama a `POST /retrain` y luego
sondea `GET /retrain/status/<job_id>` para avisar cuando termina. El API key
viaja en el header `X-API-Key`.

## Notas para la defensa

- **¿Por qué un contenedor aparte?** Separa responsabilidades: el scoring es
  liviano y frecuente; el entrenamiento es pesado y ocasional. Permite escalar
  y desplegar cada uno por separado.
- **¿Cómo evitan train/serve skew?** El pipeline completo (preprocesamiento +
  modelo) se serializa junto; el API solo hace `predict_proba`, nunca
  reimplementa la limpieza.
- **¿Por qué entrenar sobre muestra?** El free tier tiene RAM/CPU limitadas;
  una muestra estratificada de 5.000 entrena rápido sin perder representatividad.
- **¿Dónde vive el modelo y por qué?** En Supabase Storage, porque el disco de
  Render es efímero (se perdería al reiniciar). Se carga al arrancar y se
  reemplaza en caliente tras cada reentrenamiento.
- **Limitaciones conocidas** (sirven para el ítem de la rúbrica): un solo worker
  para coherencia del modelo en memoria; un solo reentrenamiento concurrente;
  el entrenamiento sobre muestra, no sobre todo el dataset.
