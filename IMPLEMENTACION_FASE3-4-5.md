# IMPLEMENTACIÓN — Fases 3, 4 y 5

**Proyecto:** `bank-pipeline`. Documento para ejecutarse con un agente de código
(Claude Code / Cursor) corriendo **en tu máquina** (tiene red hacia Render/Supabase).
Cada fase marca **[AGENTE]** (código verificable) y **[HUMANO]** (GUI, capturas,
redacción) para no confundir responsabilidades.

**Prerrequisitos comunes (variables de entorno locales):**
`SUPABASE_DB_URL` (cadena postgres de Supabase), `MODEL_API_KEY` (la `X-API-Key`),
`RENDER_URL` (URL pública del servicio). Insumo de Fase 2: `reports/model_metrics.json`.

---

# FASE 3 — Dashboard BI (apartado e.h, demo, indicador 6 = 5%)

**Objetivo:** un dashboard con los **resultados clave del entrenamiento** + KPIs del
ETL, accesible por URL para la demo.
**[AGENTE]** crea las tablas/vistas SQL y el cargador de métricas en Supabase.
**[HUMANO]** conecta Metabase a Supabase y arma las tarjetas siguiendo el runbook.

### Archivos a crear
```
ml/load_metrics_to_db.py        ← carga reports/model_metrics.json a Supabase
sql/views_bi.sql                ← vistas analíticas sobre bank_clean / model_scores
docs/METABASE_RUNBOOK.md        ← pasos de GUI para el humano
```

### Tarea 3.1 [AGENTE] — Tablas de métricas + cargador
Crear 3 tablas pequeñas en Supabase y un script que las puebla desde el JSON de Fase 2:
```python
# ml/load_metrics_to_db.py
import json, os, datetime as dt
from pathlib import Path
from sqlalchemy import create_engine, text

m = json.loads(Path("reports/model_metrics.json").read_text())
run_id = dt.datetime.utcnow().strftime("%Y%m%d_%H%M%S")
eng = create_engine(os.environ["SUPABASE_DB_URL"])
with eng.begin() as cx:
    cx.execute(text("""CREATE TABLE IF NOT EXISTS model_metrics(
        run_id text PRIMARY KEY, created_at timestamptz DEFAULT now(),
        model_name text, duration_excluded bool,
        accuracy numeric, precision numeric, recall numeric, f1 numeric,
        roc_auc numeric, gini numeric, n_train int, n_test int, si_pct numeric)"""))
    cx.execute(text("""CREATE TABLE IF NOT EXISTS model_confusion(
        run_id text, actual text, predicted text, n int)"""))
    cx.execute(text("""CREATE TABLE IF NOT EXISTS model_comparison(
        run_id text, model_name text, f1 numeric, roc_auc numeric)"""))
    me = m["metrics"]; cm = m["confusion_matrix"]
    cx.execute(text("""INSERT INTO model_metrics VALUES (:r, now(), :mn, :de,
        :acc,:pre,:rec,:f1,:auc,:gini,:ntr,:nte,:sp)
        ON CONFLICT (run_id) DO NOTHING"""), dict(
        r=run_id, mn=m["model"]["name"], de=m["model"]["duration_excluded"],
        acc=me["accuracy"], pre=me["precision"], rec=me["recall"], f1=me["f1"],
        auc=me["roc_auc"], gini=me["gini"], ntr=m["split"]["n_train"],
        nte=m["split"]["n_test"], sp=m["dataset"]["balance"]["si_pct"]))
    for a,p,n in [("no","no",cm["tn"]),("no","si",cm["fp"]),
                  ("si","no",cm["fn"]),("si","si",cm["tp"])]:
        cx.execute(text("INSERT INTO model_confusion VALUES (:r,:a,:p,:n)"),
                   dict(r=run_id,a=a,p=p,n=n))
    for c in m["model_comparison"]:
        cx.execute(text("INSERT INTO model_comparison VALUES (:r,:mn,:f1,:auc)"),
                   dict(r=run_id, mn=c["model"], f1=c["f1"], auc=c["roc_auc"]))
print("cargado run_id:", run_id)
```
**Aceptación:** `python ml/load_metrics_to_db.py` corre sin error; `SELECT * FROM
model_metrics` devuelve la fila con los números reales (sin duration).

### Tarea 3.2 [AGENTE] — Vistas analíticas sobre bank_clean / model_scores
```sql
-- sql/views_bi.sql  (deposit es boolean en bank_clean)
CREATE OR REPLACE VIEW v_target_balance AS
SELECT deposit, COUNT(*) n,
       ROUND(100.0*COUNT(*)/SUM(COUNT(*)) OVER(),1) pct
FROM bank_clean GROUP BY deposit;

CREATE OR REPLACE VIEW v_sub_rate_by_job AS
SELECT job, COUNT(*) total,
       ROUND(100.0*AVG((deposit)::int),1) tasa_pct
FROM bank_clean GROUP BY job ORDER BY tasa_pct DESC;

CREATE OR REPLACE VIEW v_sub_rate_by_education AS
SELECT education, COUNT(*) total,
       ROUND(100.0*AVG((deposit)::int),1) tasa_pct
FROM bank_clean GROUP BY education ORDER BY tasa_pct DESC;

CREATE OR REPLACE VIEW v_sub_rate_by_month AS
SELECT month, ROUND(100.0*AVG((deposit)::int),1) tasa_pct
FROM bank_clean GROUP BY month;

-- ajustar 'prob_deposit' al nombre real de la columna de probabilidad en model_scores
CREATE OR REPLACE VIEW v_score_distribution AS
SELECT width_bucket(prob_deposit,0,1,10) bucket, COUNT(*) n
FROM model_scores GROUP BY 1 ORDER BY 1;
```
**Aceptación:** las vistas se crean sin error; cada `SELECT * FROM v_...` devuelve filas.

### Tarea 3.3 [HUMANO] — Metabase (runbook que escribe el agente en docs/)
1. Metabase → Admin → Databases → agregar Supabase (host/puerto/db/usuario/clave).
2. Crear *Questions* (una por tarjeta):
   - Scorecards: accuracy, recall, F1, ROC-AUC, Gini (de `model_metrics`).
   - Matriz de confusión: tabla pivote de `model_confusion` (actual × predicted).
   - Comparación de modelos: barras de `model_comparison` (F1, AUC por modelo).
   - Balance del target: dona de `v_target_balance`.
   - Tasa de suscripción por job / education / month (barras).
   - Distribución de probabilidades: histograma de `v_score_distribution`.
3. Armar el dashboard, ordenar las tarjetas, **obtener URL pública/compartible** para la demo.
**Aceptación:** dashboard con ≥6 tarjetas + URL accesible; muestra métricas del modelo
y al menos una vista de negocio (tasa por segmento).

### Qué desbloquea
Apartado e.h del informe, la demo (b.c) y evidencia para el indicador 3 (integración BI).

---

# FASE 4 — Seguridad + ley (apartado e.g, indicador 2 = 3%, pregunta #9 = 30%)

**Realidad:** ~30% es auditoría de código (agente) y ~70% es análisis/redacción
(humano). El agente **audita y arma el inventario**; el humano **escribe el análisis
legal** y lo verifica.

### Archivos a crear
```
scripts/audit_secrets.sh        ← escaneo de secretos en el repo
reports/security_audit.md       ← resultado de la auditoría (lo llena el agente)
docs/SEGURIDAD_SECCION.md        ← esqueleto de la sección de seguridad (humano redacta)
```

### Tarea 4.1 [AGENTE] — Escaneo de secretos y de `.gitignore`
```bash
# scripts/audit_secrets.sh
echo "== secretos en archivos versionados =="
git ls-files | xargs grep -nEi \
  "(service_role|supabase.*(key|url)|api[_-]?key|secret|passw)" 2>/dev/null \
  | grep -v -E "(\.md:|example|placeholder|os\.environ|getenv)"
echo "== .env ignorado? =="
grep -nE "(^|/)\.env" .gitignore || echo "FALTA .env en .gitignore"
```
**Aceptación:** `reports/security_audit.md` registra el resultado; **cero** secretos
reales en archivos versionados; `.env` está en `.gitignore`. Si aparece algo, listarlo
como hallazgo crítico a remediar (rotar la clave).

### Tarea 4.2 [AGENTE] — Verificar autenticación de la API
Leer las rutas de `model_api` y confirmar que **todos** los endpoints de predicción y
reentrenamiento exigen `X-API-Key`. Listar en `security_audit.md` cada endpoint y si
está protegido (sí/no). Marcar `/model/health` como público intencional.
**Aceptación:** tabla endpoint → auth en el audit; ningún endpoint sensible sin clave.

### Tarea 4.3 [AGENTE] — Inventario de datos sensibles + matriz de roles
Generar, a partir del esquema de `bank_clean`, una clasificación de columnas:
- **Identificación/PII:** age (cuasi-identificador) — el dataset no trae nombre/rut.
- **Financiero:** balance, housing, loan, default_credit.
- **Conductual/campaña:** contact, month, day, campaign, pdays, previous, poutcome.
- **Target:** deposit (resultado comercial).
Y la **matriz de roles** (incluyendo lo nuevo del Parcial 3):

| Rol | Acceso | Privilegio |
|---|---|---|
| Desarrollador | repo, `.env` local | alto (código) |
| Operador ETL | ejecutar pipeline/dashboard | medio |
| Analista BI | solo lectura `bank_clean`/vistas | bajo |
| Consumidor API | `/model/predict` con `X-API-Key` | acotado por clave |
| Admin Supabase | **`service_role` key** (máximo privilegio) | crítico |

**Aceptación:** `security_audit.md` incluye inventario clasificado + matriz de roles
con el consumidor de API y la `service_role` marcada como riesgo crítico.

### Tarea 4.4 [HUMANO + agente borrador] — Sección legal (esqueleto en docs/)
El agente deja el esqueleto con encabezados y andamiaje; el humano redacta y **verifica
la vigencia actual**:
- **Ley 19.628** (vigente): consentimiento, finalidad, seguridad, acceso limitado.
- **Ley 21.719** (reforma 2024, enfoque tipo GDPR): Agencia de Protección de Datos,
  derechos del titular (acceso, rectificación, supresión, oposición, portabilidad),
  multas hasta 20.000 UTM, vigencia plena hacia fines de 2026. → **confirmar estado
  vigente a la fecha de la defensa.**
- **Principios aplicados al proyecto:** finalidad (segmentar campañas), minimización
  (sin nombre/RUT), seguridad (TLS, secrets, clave de API), acceso por rol.
- **Decisiones automatizadas / perfilamiento:** el modelo puntúa clientes para
  priorizarlos comercialmente → es exactamente lo que regula la ley tipo GDPR; mencionar
  transparencia y derecho a no quedar sujeto solo a decisiones automatizadas.
**Aceptación:** el esqueleto nombra **19.628 y 21.719**, incluye perfilamiento y vincula
cada principio a una medida concreta del proyecto (no genérico).

### Qué desbloquea
Apartado e.g, indicador 2 (3%) y la defensa #9 (30%): cada integrante explica datos
sensibles, roles, 19.628 vs 21.719, perfilamiento y el mayor riesgo (`service_role`).

---

# FASE 5 — Rendimiento en nube (apartado e.f, indicador 3 = 3%)

**Objetivo:** números reales local vs Render + logs + cold start.
**[AGENTE]** escribe los scripts de benchmark y el gráfico.
**[HUMANO]** dispara las corridas en Render y captura logs/pantallas.

### Archivos a crear
```
scripts/benchmark_etl.py        ← cronometra el ETL local por etapa
scripts/measure_cloud.sh        ← mide latencia y cold start contra Render
scripts/plot_perf.py            ← gráfico local vs nube
reports/perf_local.json, reports/perf_cloud.json
reports/figures/perf_local_vs_cloud.png
reports/perf_summary.md
```

### Tarea 5.1 [AGENTE] — Benchmark local del ETL
Script que corre el transform/load del ETL sobre el CSV N veces (p.ej. 5), mide cada
etapa con `time.perf_counter()`, y guarda media/desv en `reports/perf_local.json`
(extract, transform, load, total).
**Aceptación:** `perf_local.json` con tiempos por etapa (números, no placeholders).

### Tarea 5.2 [AGENTE] — Latencia y cold start en Render
```bash
# scripts/measure_cloud.sh
echo "== cold start (primer request tras inactividad) =="
curl -o /dev/null -s -w "cold: %{time_total}s\n" "$RENDER_URL/model/health"
for i in 1 2 3 4 5; do
  curl -o /dev/null -s -w "warm: %{time_total}s\n" "$RENDER_URL/model/health"
done
# predicción real (medir latencia con auth):
curl -o /dev/null -s -w "predict: %{time_total}s\n" \
  -H "X-API-Key: $MODEL_API_KEY" -H "Content-Type: application/json" \
  -d '{"raw_id": 1}' "$RENDER_URL/model/predict"
```
Guardar los tiempos en `reports/perf_cloud.json`.
**Aceptación:** `perf_cloud.json` con cold start + latencia warm + latencia de
predicción reales.

### Tarea 5.3 [AGENTE] — Gráfico comparativo
`scripts/plot_perf.py` lee ambos JSON y genera barras local vs nube →
`reports/figures/perf_local_vs_cloud.png`, y un `reports/perf_summary.md` de 1 plana.
**Aceptación:** existe el PNG y el resumen con la interpretación (ej. "el cold start del
free tier agrega ~Xs en la primera petición; en caliente la predicción responde en ~Yms").

### Tarea 5.4 [HUMANO] — Capturar logs de Render
Desde el panel de Render: descargar/capturar los logs de un despliegue y de una corrida
de ETL + una predicción. Guardar las imágenes para el Anexo de rendimiento.
**Aceptación:** ≥2 capturas de logs reales adjuntas al informe (deploy + request).

### Qué desbloquea
Apartado e.f, indicador 3 (integración nube), y material para "limitaciones" (cold
start, RAM del free tier, worker único) que también suma en la presentación (#7, 10%).

---

## Orden sugerido de ejecución

1. **Fase 3.1–3.2** (agente, rápido) → carga métricas + vistas. Luego **3.3** (humano, Metabase).
2. **Fase 5.1–5.3** (agente) en paralelo → benchmark + gráfico. Luego **5.4** (humano, logs).
3. **Fase 4.1–4.3** (agente) → auditoría e inventario. Luego **4.4** (humano, redacción legal).

Las tres alimentan la Fase 6 (redacción del informe a 10–12 págs) y la defensa: la 3
arma la demo, la 4 cubre el 30% de seguridad, y la 5 da los números de rendimiento y
nutre la sección de limitaciones.
