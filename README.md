# Bank Marketing — Pipeline ETL

Pipeline de **procesamiento y limpieza** de datos para campañas de depósitos a plazo.  
Fase actual: ETL → PostgreSQL (`bank_raw` + `bank_clean`). El modelo de ML va en una fase posterior.

## Arquitectura

```
Excel/CSV  →  Contenedor ETL (Python)  →  PostgreSQL
                  │                           ├── bank_raw   (origen)
                  │                           └── bank_clean (tipado + validado)
```

**Por qué no API todavía:** en esta fase el dato entra por archivo batch. Una API tiene sentido cuando exista captura continua o un servicio de scoring en producción.

## Requisitos

- [Docker Desktop](https://www.docker.com/products/docker-desktop/) (Windows)
- Archivo de datos en `data/` con nombre `bank.csv` o `bank.xlsx`

Columnas esperadas (17):

`age, job, marital, education, default, balance, housing, loan, contact, day, month, duration, campaign, pdays, previous, poutcome, deposit`

## Uso rápido

1. Coloca tu dataset en `data/bank.csv` (o `bank.xlsx`).
2. Desde esta carpeta:

```bash
docker compose up --build
```

3. Verificar en PostgreSQL:

```bash
docker exec -it bank_postgres psql -U postgres -d bankdb -c "SELECT COUNT(*) FROM bank_raw;"
docker exec -it bank_postgres psql -U postgres -d bankdb -c "SELECT COUNT(*) FROM bank_clean;"
docker exec -it bank_postgres psql -U postgres -d bankdb -c "SELECT * FROM bank_clean LIMIT 5;"
```

4. Reporte de calidad generado por el ETL: `reports/quality_report.json`

## Estructura

```
bank-pipeline/
├── docker-compose.yml
├── data/                 # bank.csv o bank.xlsx (no versionar datos reales)
├── etl/
│   ├── Dockerfile
│   ├── requirements.txt
│   └── process_data.py
├── sql/
│   └── init.sql
└── reports/              # salida del ETL (montado como volumen)
```

## Para el informe de evaluación

Documentar explícitamente:

| Control | Qué hace |
|--------|----------|
| Estructura | Valida las 17 columnas requeridas |
| Raw layer | Conserva datos originales en `bank_raw` |
| Duplicados | Elimina filas repetidas |
| Tipos | Numéricos, booleanos yes/no, categorías |
| Rangos | Edad 18–100, día 1–31, pdays ≥ -1, etc. |
| Categorías | Listas blancas (marital, education, contact, poutcome) |
| Nulos | `dropna` en columnas críticas |
| Trazabilidad | `quality_report.json` con conteos antes/después |

## Siguiente fase (fuera de este repo por ahora)

- Feature engineering (one-hot, orden de meses, etc.) → tabla `bank_features` o notebook
- Modelo (scikit-learn / XGBoost) entrenado sobre `bank_clean`
- API FastAPI opcional para carga y/o scoring
