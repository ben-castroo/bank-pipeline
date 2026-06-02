# Bank Marketing — Pipeline ETL

Pipeline de procesamiento y limpieza de datos para campañas de depósitos a plazo,  
desplegado en **Render** (Web Service + PostgreSQL) con **Supabase** como destino de datos limpios.

## Arquitectura

```
CSV / Excel
    │
    ▼
Flask Web Service (Render)
    │
    ├─► bank_raw        (Render PostgreSQL — datos originales)
    ├─► etl_reports     (Render PostgreSQL — métricas por ejecución)
    ├─► etl_rejected    (Render PostgreSQL — filas descartadas)
    ├─► etl_row_logs    (Render PostgreSQL — log granular por fila)
    └─► bank_clean      (Supabase — datos limpios listos para análisis)
```

## Estructura del proyecto

```
bank-pipeline/
├── etl/
│   ├── Dockerfile          ← imagen del Web Service
│   ├── requirements.txt
│   ├── db.py               ← conexiones (Render PG + Supabase) y DDL
│   ├── process_data.py     ← pipeline ETL completo
│   ├── app.py              ← Flask: dashboard + API endpoints
│   └── templates/
│       └── dashboard.html
├── data/
│   ├── bank_demo.csv           ← dataset de demo (25 filas con errores)
│   └── bank_estructura_test.csv ← CSV con columnas inválidas para probar validación
├── docs/
│   ├── despliegue.md       ← guía paso a paso Render + Supabase
│   ├── procesamiento.md    ← documentación detallada de process_data.py
│   └── resumen.md          ← resumen de validaciones y reglas de limpieza
├── docker-compose.yml      ← entorno local de desarrollo
└── README.md
```

## Columnas esperadas (17)

`age, job, marital, education, default, balance, housing, loan, contact, day, month, duration, campaign, pdays, previous, poutcome, deposit`

## Despliegue

Ver [docs/despliegue.md](docs/despliegue.md) para la guía completa de Render + Supabase.

## Desarrollo local

```bash
# Requiere Docker Desktop
docker compose up --build
```

El servicio queda disponible en `http://localhost:8000`.  
Variables de entorno configuradas en `docker-compose.yml` (BD local PostgreSQL).

## Validaciones aplicadas

| Paso | Descripción |
|------|-------------|
| Estructura | Verifica las 17 columnas exactas |
| Deduplicación | Elimina copias exactas (conserva la primera) |
| Normalización | Texto a minúsculas, espacios eliminados, vacíos → `unknown` |
| Rangos | `age` 18–100, `day` 1–31, `duration ≥ 0`, `campaign ≥ 1`, etc. |
| Categorías | Listas blancas para `job`, `marital`, `education`, `contact`, `poutcome` |
| Binarias | `yes/no` → `True/False`; valores inválidos → `NULL` |
| Nulos críticos | Elimina filas con nulos en campos obligatorios |

Ver [docs/resumen.md](docs/resumen.md) para el detalle completo.

