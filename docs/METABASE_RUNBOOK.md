# Metabase Runbook — Dashboard BI bank-pipeline

**Prerrequisito:** haber ejecutado `python ml/load_metrics_to_db.py` (tablas
`model_metrics`, `model_confusion`, `model_comparison` pobladas) y aplicado
`sql/views_bi.sql` en Supabase.

---

## Paso 1 — Conectar Metabase a Supabase

1. Ir a **Admin → Databases → Add a database**.
2. Tipo: **PostgreSQL**.
3. Completar los campos con los datos de Supabase (conexión pooler, puerto 6543):

| Campo | Valor |
|---|---|
| Display name | `Supabase bank-pipeline` |
| Host | `aws-0-[region].pooler.supabase.com` |
| Port | `6543` |
| Database name | `postgres` |
| Username | `postgres.[REF]` |
| Password | `[tu contraseña de Supabase]` |
| SSL | activar "Use a secure connection (SSL)" |

4. Clic en **Save**. Esperar que la conexión sea exitosa.

---

## Paso 2 — Tarjetas de métricas del modelo (Scorecards)

Para cada métrica, crear una **Question → Simple question → model_metrics
(vista latest)** o directamente con SQL:

| Tarjeta | Query sugerida |
|---|---|
| Accuracy | `SELECT accuracy FROM v_latest_model_metrics` |
| Recall | `SELECT recall FROM v_latest_model_metrics` |
| F1-Score | `SELECT f1 FROM v_latest_model_metrics` |
| ROC-AUC | `SELECT roc_auc FROM v_latest_model_metrics` |
| Gini | `SELECT gini FROM v_latest_model_metrics` |
| Balance sí (%) | `SELECT si_pct FROM v_latest_model_metrics` |

Visualización recomendada: **Number** (Metabase scorecard).

---

## Paso 3 — Matriz de confusión

1. New Question → Native query:
```sql
SELECT actual AS "Real", predicted AS "Predicho", n AS "N"
FROM model_confusion mc
JOIN (SELECT run_id FROM model_metrics ORDER BY created_at DESC LIMIT 1) r
    ON mc.run_id = r.run_id
ORDER BY actual, predicted;
```
2. Visualización: **Table** o **Pivot Table** (filas = Real, columnas = Predicho).

---

## Paso 4 — Comparación de modelos

1. New Question → Native query:
```sql
SELECT model_name AS "Modelo", f1 AS "F1", roc_auc AS "ROC-AUC"
FROM v_latest_model_comparison;
```
2. Visualización: **Bar chart** (agrupado, eje X = Modelo).

---

## Paso 5 — Balance del target (dona)

1. New Question → `v_target_balance`.
2. Visualización: **Pie chart** o **Row chart** (depósito sí/no, pct).

---

## Paso 6 — Tasa de suscripción por segmentos

Crear una tarjeta por cada vista:

| Vista | Tarjeta |
|---|---|
| `v_sub_rate_by_job` | Tasa por ocupación (bar, ordenado por tasa_pct) |
| `v_sub_rate_by_education` | Tasa por educación (bar) |
| `v_sub_rate_by_month` | Tasa mensual (line o bar) |

---

## Paso 7 — Distribución de probabilidades del modelo

1. New Question → `v_score_distribution`.
2. Visualización: **Bar chart** (eje X = bucket 1–10, eje Y = n).
3. Título sugerido: "Distribución de scores del modelo (deciles de probabilidad)".

---

## Paso 8 — Armar el dashboard

1. **New → Dashboard** → título: `Dashboard BI — bank-pipeline`.
2. Agregar tarjetas en este orden sugerido:
   - Fila 1: Scorecards (Accuracy, Recall, F1, ROC-AUC, Gini, Balance sí%)
   - Fila 2: Comparación de modelos | Matriz de confusión
   - Fila 3: Balance del target (dona) | Distribución de scores
   - Fila 4–5: Tasas por job, education, month
3. Redimensionar tarjetas arrastrando las esquinas.

---

## Paso 9 — Obtener URL pública para la demo

1. Abrir el dashboard terminado.
2. Clic en el icono de compartir (🔗) en la esquina superior derecha.
3. Activar **"Enable sharing"**.
4. Copiar la URL pública generada.
5. Verificar que la URL es accesible en incógnito (sin sesión de Metabase).

**Criterio de aceptación:** dashboard con ≥ 6 tarjetas accesible vía URL pública.

---

## Referencia de tablas/vistas

| Nombre | Descripción |
|---|---|
| `model_metrics` | Métricas de cada run de entrenamiento |
| `model_confusion` | Matriz de confusión por run |
| `model_comparison` | Comparación algoritmos por run |
| `v_target_balance` | Balance sí/no en bank_clean |
| `v_sub_rate_by_job` | Tasa de suscripción por ocupación |
| `v_sub_rate_by_education` | Tasa por nivel educativo |
| `v_sub_rate_by_month` | Tasa por mes de campaña |
| `v_score_distribution` | Histograma de probabilidades del modelo |
| `v_latest_model_metrics` | Métricas del run más reciente |
| `v_latest_model_comparison` | Comparación del run más reciente |
