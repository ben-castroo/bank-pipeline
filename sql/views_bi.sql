-- Fase 3.2 — Vistas analíticas sobre bank_clean / model_scores
-- Ejecutar en Supabase SQL Editor o mediante psql con SUPABASE_DB_URL.
-- deposit es boolean en bank_clean.

-- Balance del target (dona / scorecard)
CREATE OR REPLACE VIEW v_target_balance AS
SELECT
    deposit,
    COUNT(*) AS n,
    ROUND(100.0 * COUNT(*) / SUM(COUNT(*)) OVER (), 1) AS pct
FROM bank_clean
GROUP BY deposit;

-- Tasa de suscripción por job (barras)
CREATE OR REPLACE VIEW v_sub_rate_by_job AS
SELECT
    job,
    COUNT(*) AS total,
    ROUND(100.0 * AVG((deposit)::int), 1) AS tasa_pct
FROM bank_clean
GROUP BY job
ORDER BY tasa_pct DESC;

-- Tasa de suscripción por education (barras)
CREATE OR REPLACE VIEW v_sub_rate_by_education AS
SELECT
    education,
    COUNT(*) AS total,
    ROUND(100.0 * AVG((deposit)::int), 1) AS tasa_pct
FROM bank_clean
GROUP BY education
ORDER BY tasa_pct DESC;

-- Tasa de suscripción por mes (barras o línea)
CREATE OR REPLACE VIEW v_sub_rate_by_month AS
SELECT
    month,
    ROUND(100.0 * AVG((deposit)::int), 1) AS tasa_pct
FROM bank_clean
GROUP BY month;

-- Distribución de scores del modelo (histograma de probabilidades)
-- prob_deposit: columna de probabilidad en model_scores
CREATE OR REPLACE VIEW v_score_distribution AS
SELECT
    width_bucket(prob_deposit, 0, 1, 10) AS bucket,
    COUNT(*) AS n
FROM model_scores
GROUP BY 1
ORDER BY 1;

-- Métricas del último run del modelo (scorecard)
CREATE OR REPLACE VIEW v_latest_model_metrics AS
SELECT *
FROM model_metrics
ORDER BY created_at DESC
LIMIT 1;

-- Comparación de modelos del último run
CREATE OR REPLACE VIEW v_latest_model_comparison AS
SELECT mc.*
FROM model_comparison mc
JOIN (SELECT run_id FROM model_metrics ORDER BY created_at DESC LIMIT 1) latest
    ON mc.run_id = latest.run_id
ORDER BY f1 DESC;
