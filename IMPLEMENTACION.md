# Implementación — Integrar la API del modelo en el web service del ETL

**Proyecto:** `bank-pipeline` · **Objetivo:** que el ETL (dashboard) y la API del
modelo (predicción + reentrenamiento) corran en **un solo web service Docker** en
Render, en un único proceso.

> Documento pensado para ejecutarse junto a un agente de código IA. Las tareas
> van en orden, con **criterio de aceptación** cada una. No avances hasta cumplirlo.

---

## Contexto (estado actual verificado del repo)

El repo HOY contiene solo:

```
bank-pipeline/
├── etl/  (app.py, db.py, process_data.py, requirements.txt, Dockerfile, templates/)
├── data/ · docs/ · reports/
├── docker-compose.yml
└── README.md
```

- El ETL es una app Flask que se despliega como web service en Render.
- Escribe `bank_clean` en **Supabase** (lee `SUPABASE_URL`) y usa Render Postgres
  para `bank_raw`/`etl_*` (lee `DATABASE_URL` o `DB_*`).
- En `bank_clean`, el ETL hace `id = raw_id` (mismo valor en cada etapa), así que
  buscar por `id` es equivalente a buscar por `raw_id`.

### Qué vamos a agregar

```
bank-pipeline/
├── Dockerfile            ← NUEVO (raíz) — imagen combinada
├── requirements.txt      ← NUEVO (raíz) — deps ETL + modelo
├── wsgi.py               ← NUEVO (raíz) — monta ambas apps
├── etl/                  ← SIN CAMBIOS
└── model_api/            ← NUEVO paquete (predicción + reentrenamiento)
    ├── __init__.py
    ├── app.py · config.py · db.py · features.py · storage.py
    ├── training.py · model_service.py · retrain.py · auth.py
    ├── train_base_model.py
    └── artifacts/        ← base_model.joblib (se genera, se versiona)
```

### Arquitectura resultante

Un proceso, un puerto. `DispatcherMiddleware` monta:
- `/` → dashboard del ETL (`/`, `/health`, `/run`, `/upload`, `/data/*`, …)
- `/model/...` → API del modelo (`/model/predict`, `/model/predict/batch`,
  `/model/retrain`, `/model/retrain/status/<id>`, `/model/model-info`, `/model/health`)

---

## Guardrails (no romper)

1. **No modificar `etl/`.** El ETL ya está evaluado y funcionando. `wsgi.py` lo
   importa tal cual (añade su carpeta al path).
2. **`model_api` es un paquete con imports relativos** (`from . import ...`). Esto
   evita que su `db.py` colisione con el `db.py` del ETL. No volver a imports planos.
3. **Un solo worker de gunicorn** (`--workers 1 --threads 4`). El modelo en memoria
   y el hot-swap viven en el proceso; con más workers no se comparten.
4. **El modelo base se genera como módulo:** `python -m model_api.train_base_model`.
   Correr `python model_api/app.py` directo NO funciona (imports relativos).
5. **Sin credenciales en el código.** Todo por variables de entorno (`.env` local,
   panel de Render en producción). `.env` no se versiona.
6. **`base_model.joblib` SÍ se versiona** (va horneado en la imagen como fallback).

---

## Fase 1 — Agregar archivos al repo

**Tarea 1.1** — Copiar la carpeta `model_api/` (versión paquete) a la raíz, junto a `etl/`.
**Tarea 1.2** — Copiar a la raíz: `wsgi.py`, `requirements.txt` (combinado), `Dockerfile` (combinado).
**Tarea 1.3** — Crear la subcarpeta vacía `model_api/artifacts/`.

**Criterio de aceptación:** el árbol del repo coincide con el de la sección
"Qué vamos a agregar". `python -m py_compile wsgi.py model_api/*.py` no da errores.

## Fase 2 — Supabase

**Tarea 2.1** — En Supabase → Storage, crear un bucket **privado** llamado `models`.
**Tarea 2.2** — (Nada manual con tablas) `model_scores` y `retrain_jobs` se crean
solas al arrancar el servicio.

**Criterio de aceptación:** el bucket `models` existe y está vacío.

## Fase 3 — Configuración de entorno (local)

**Tarea 3.1** — Crear `model_api/.env` desde `model_api/.env.example`:

```
SUPABASE_URL=postgresql://...        # la misma del ETL (lectura de bank_clean)
SUPABASE_PROJECT_URL=https://XXXX.supabase.co
SUPABASE_SERVICE_KEY=eyJ...service_role...
API_KEY=un-token-secreto
```

**Criterio de aceptación:** las 4 variables están definidas y `.env` está en `.gitignore`.

## Fase 4 — Modelo base y prueba local

**Tarea 4.1** — Instalar deps combinadas (mismo `scikit-learn` que la imagen):
```bash
pip install -r requirements.txt
```

**Tarea 4.2** — Poblar `bank_clean`: subir un CSV por el dashboard y correr el ETL
una vez. (Alternativa: exportar `bank_clean` a CSV y usar `--csv`.)

**Tarea 4.3** — Generar el modelo base (desde la raíz del repo):
```bash
python -m model_api.train_base_model --sample 10000
```

**Criterio de aceptación:** existen `model_api/artifacts/base_model.joblib` y
`model_api/artifacts/model_card.json`, y el comando imprimió métricas (incluye `gini`).

**Tarea 4.4** — Levantar la app combinada:
```bash
python wsgi.py        # servidor de desarrollo werkzeug, puerto 8000
```

**Tarea 4.5** — Prueba de humo:
```bash
curl localhost:8000/health
curl localhost:8000/model/health
curl -X POST localhost:8000/model/predict \
  -H "X-API-Key: un-token-secreto" -H "Content-Type: application/json" \
  -d '{"raw_id": 1}'
```

**Criterio de aceptación:** `/model/predict` devuelve `prob_deposit`, `pred_deposit`
y `model_version`; aparece una fila nueva en la tabla `model_scores` de Supabase.

## Fase 5 — Commit y push

**Tarea 5.1**
```bash
git add model_api wsgi.py requirements.txt Dockerfile
git commit -m "feat: API de modelo integrada en el web service (ETL + modelo)"
git push
```

**Criterio de aceptación:** en GitHub aparecen los archivos nuevos, incluido
`model_api/artifacts/base_model.joblib`, y NO aparece `.env`.

## Fase 6 — Reconfigurar Render

**Tarea 6.1** — Web service → Settings → Docker:
- Dockerfile Path: `./Dockerfile`
- Docker Build Context Directory: `.` (raíz)

**Tarea 6.2** — Environment → agregar: `SUPABASE_PROJECT_URL`, `SUPABASE_SERVICE_KEY`,
`API_KEY`. Mantener `SUPABASE_URL` y `DB_*` existentes.

**Tarea 6.3** — Health Check Path: `/health` (sin cambios).

**Tarea 6.4** — Disparar deploy manual.

**Criterio de aceptación:** en los logs de Render aparece
`Modelo inicial cargado: version=...` y el servicio queda "Live".

## Fase 7 — Verificación en producción

```bash
curl https://TU-SERVICIO.onrender.com/health
curl https://TU-SERVICIO.onrender.com/model/health
curl https://TU-SERVICIO.onrender.com/model/model-info -H "X-API-Key: ..."
curl -X POST https://TU-SERVICIO.onrender.com/model/retrain \
  -H "X-API-Key: ..." -H "Content-Type: application/json" -d '{"sample_size": 5000}'
# luego sondear:
curl https://TU-SERVICIO.onrender.com/model/retrain/status/<job_id> -H "X-API-Key: ..."
```

**Criterio de aceptación:** el reentrenamiento devuelve `job_id`, el estado pasa a
`done` con métricas, y `/model/model-info` refleja la nueva `model_version`.

---

## Mapa de endpoints (referencia)

| Método | Ruta | Auth |
|---|---|---|
| GET | `/health`, `/`, `/run`, `/upload`, `/data/*` … (ETL) | según ETL |
| GET | `/model/health` | No |
| GET | `/model/model-info` | Sí |
| POST | `/model/predict` `{raw_id, threshold?}` | Sí |
| POST | `/model/predict/batch` `{raw_ids[], threshold?}` | Sí |
| POST | `/model/retrain` `{sample_size?}` | Sí |
| GET | `/model/retrain/status/<job_id>` | Sí |

Auth: header `X-API-Key: <API_KEY>`.

---

## Limitaciones conocidas (útiles para el informe / defensa)

- **Memoria del free tier:** un proceso carga dashboard + pandas + scikit-learn +
  modelo. Si hay reinicios por RAM, bajar `n_estimators` (ej. 100) en
  `model_api/training.py` o reducir la muestra.
- **Contención en el reentrenamiento:** entrenamiento y dashboard comparten proceso;
  un `/model/retrain` puede poner lento el dashboard mientras dura.
- **Un solo job de reentrenamiento a la vez** (se valida contra `retrain_jobs`).
- **Entrenamiento sobre muestra** (default 5.000), no sobre todo el dataset, por los
  límites de CPU/RAM.

## Próximos pasos (fuera de este documento)

- Botón "Reentrenar" en `etl/templates/dashboard.html` que llame a `/model/retrain`
  y sondee `/model/retrain/status/<job_id>`.
- Conectar la tabla `model_scores` a Metabase para el dashboard BI.
