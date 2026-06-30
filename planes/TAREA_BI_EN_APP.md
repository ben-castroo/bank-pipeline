# TAREA (agente) — Página BI propia en el mismo web service (`/bi`)

**Repo:** `bank-pipeline` · **Rama:** `feat/form-prediccion`.
**Objetivo:** un dashboard de BI servido por la **misma app Flask**, en la **misma URL**
(`/bi`), sin Metabase ni segundo servicio. Lee las **vistas de Supabase que ya existen**
(`sql/views_bi.sql`) y las grafica con **Chart.js** (CDN). Cumple el apartado h
("Metabase/Power BI/Looker **o similar**") con una capa BI a medida integrada al deploy.

## Contexto técnico (verificado en el repo)

- `wsgi.py` ya monta dos apps con `DispatcherMiddleware`: ETL en `/`, modelo en `/model`.
  Agregamos una **tercera** en `/bi`.
- Datos en **Supabase** (`SUPABASE_DB_URL`): tablas `bank_clean`, `model_scores`,
  `model_metrics`, `model_confusion`, `model_comparison`, y vistas ya creadas:
  - `v_target_balance(deposit, n, pct)`
  - `v_sub_rate_by_job(job, total, tasa_pct)`
  - `v_sub_rate_by_education(education, total, tasa_pct)`
  - `v_sub_rate_by_month(month, tasa_pct)`
  - `v_score_distribution(bucket, n)`
  - `v_latest_model_metrics(*)` · `v_latest_model_comparison(run_id, model_name, f1, roc_auc)`
- `model_metrics` columnas: `run_id, created_at, model_name, duration_excluded, accuracy,
  precision, recall, f1, roc_auc, gini, n_train, n_test, si_pct`.
- `model_confusion(run_id, actual, predicted, n)`.

## Guardrails

1. **Usar `SUPABASE_DB_URL`** (donde viven las vistas), con engine **propio** y **lazy**
   (no romper el arranque combinado si la variable falta: solo `/bi` debe fallar, no el ETL
   ni el modelo).
2. **Datos agregados, sin PII** → la página `/bi` y sus datos son **públicos** (sin
   `X-API-Key`), para que el profe la abra en la demo sin login.
3. No tocar el ETL ni el modelo. `wsgi.py` solo **agrega** el montaje `/bi`.
4. `pool_pre_ping=True` (conexiones que duermen en el free tier).
5. Chart.js y Tailwind por **CDN**; armonizar el estilo con `etl/templates/dashboard.html`.
6. Si `model_metrics` está vacía → mensaje amable ("corre `load_metrics_to_db.py`").

## Archivos a crear / editar

```
bi_api/__init__.py            ← NUEVO (vacío)
bi_api/app.py                 ← NUEVO (rutas + lectura de Supabase)
bi_api/templates/bi.html      ← NUEVO (página con Chart.js)
wsgi.py                       ← EDITAR (montar /bi)
```

---

## Tarea 1 — `bi_api/__init__.py`
Vacío. **Aceptación:** existe.

## Tarea 2 — `bi_api/app.py`
```python
"""Dashboard BI servido por la misma app Flask (mismo web service en Render).
Lee las vistas/tablas de BI en Supabase y entrega JSON para Chart.js.
"""
import os
from flask import Flask, jsonify, render_template
from sqlalchemy import create_engine, text

app = Flask(__name__, template_folder="templates")

_engine = None
def get_engine():
    global _engine
    if _engine is None:
        url = os.getenv("SUPABASE_DB_URL")
        if not url:
            raise RuntimeError("SUPABASE_DB_URL no definida")
        _engine = create_engine(url, pool_pre_ping=True)
    return _engine

def _rows(sql, **params):
    with get_engine().connect() as cx:
        return [dict(r) for r in cx.execute(text(sql), params).mappings().all()]

@app.get("/")
def home():
    return render_template("bi.html")

@app.get("/data/summary")
def summary():
    try:
        metrics = _rows("SELECT * FROM v_latest_model_metrics")
        metrics = metrics[0] if metrics else {}
        run_id = metrics.get("run_id")
        confusion = _rows(
            "SELECT actual, predicted, n FROM model_confusion WHERE run_id = :r",
            r=run_id) if run_id else []
        return jsonify({
            "metrics": metrics,
            "confusion": confusion,
            "comparison": _rows("SELECT model_name, f1, roc_auc FROM v_latest_model_comparison"),
            "target_balance": _rows("SELECT deposit, n, pct FROM v_target_balance"),
            "rate_by_job": _rows("SELECT job, tasa_pct FROM v_sub_rate_by_job"),
            "rate_by_education": _rows("SELECT education, tasa_pct FROM v_sub_rate_by_education"),
            "rate_by_month": _rows("SELECT month, tasa_pct FROM v_sub_rate_by_month"),
            "score_distribution": _rows("SELECT bucket, n FROM v_score_distribution"),
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500
```

**Aceptación:** `GET /bi/data/summary` devuelve JSON con métricas, confusión, comparación y
las series de negocio. Si falta `SUPABASE_DB_URL` o las tablas, devuelve `{"error": ...}` 500
sin tumbar el resto del servicio.

## Tarea 3 — `wsgi.py` (montar /bi)
```python
from model_api.app import app as model_app          # (ya existe)
from bi_api.app import app as bi_app                 # NUEVO

application = DispatcherMiddleware(etl_app, {
    "/model": model_app,
    "/bi": bi_app,                                   # NUEVO
})
```
**Aceptación:** `/` (ETL), `/model/*` y `/bi` responden; el arranque no falla aunque
`SUPABASE_DB_URL` esté ausente (solo `/bi/data/*` fallaría).

## Tarea 4 — `bi_api/templates/bi.html`
Página con tarjetas de métricas + gráficos. Referencia (armonizar con el dashboard):
```html
<!doctype html><html lang="es"><head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>BI — Bank Marketing</title>
<script src="https://cdn.tailwindcss.com"></script>
<script src="https://cdn.jsdelivr.net/npm/chart.js@4"></script>
</head>
<body class="bg-slate-50 p-6">
  <h1 class="text-2xl font-bold mb-1">Dashboard BI — Predicción de depósitos</h1>
  <p id="status" class="text-sm text-slate-500 mb-6">Cargando…</p>

  <!-- Scorecards -->
  <div id="cards" class="grid grid-cols-2 md:grid-cols-6 gap-3 mb-6"></div>

  <div class="grid md:grid-cols-2 gap-6">
    <div class="bg-white rounded-xl p-4 shadow"><h2 class="font-semibold mb-2">Matriz de confusión</h2><div id="confusion"></div></div>
    <div class="bg-white rounded-xl p-4 shadow"><h2 class="font-semibold mb-2">Comparación de modelos (F1 / AUC)</h2><canvas id="chartCompare"></canvas></div>
    <div class="bg-white rounded-xl p-4 shadow"><h2 class="font-semibold mb-2">Balance del target</h2><canvas id="chartBalance"></canvas></div>
    <div class="bg-white rounded-xl p-4 shadow"><h2 class="font-semibold mb-2">Tasa de suscripción por oficio</h2><canvas id="chartJob"></canvas></div>
    <div class="bg-white rounded-xl p-4 shadow"><h2 class="font-semibold mb-2">Tasa por educación</h2><canvas id="chartEdu"></canvas></div>
    <div class="bg-white rounded-xl p-4 shadow"><h2 class="font-semibold mb-2">Distribución de probabilidades (model_scores)</h2><canvas id="chartScore"></canvas></div>
  </div>

<script>
const PCT = ['accuracy','precision','recall','f1','roc_auc','gini'];
function card(label, val){ return `<div class="bg-white rounded-xl p-3 shadow text-center">
  <div class="text-xs text-slate-500 uppercase">${label}</div>
  <div class="text-xl font-bold">${val}</div></div>`; }

async function load(){
  const st = document.getElementById('status');
  let d;
  try { d = await fetch('/bi/data/summary').then(r=>r.json()); }
  catch(e){ st.textContent = 'No se pudo cargar.'; return; }
  if (d.error || !d.metrics || !d.metrics.run_id){
    st.textContent = 'Sin métricas. Corre ml/load_metrics_to_db.py para poblar model_metrics.';
    return;
  }
  st.textContent = `Modelo ${d.metrics.model_name} · ${d.metrics.n_test} casos de test`;

  // scorecards
  document.getElementById('cards').innerHTML =
    PCT.map(k => card(k, Number(d.metrics[k]).toFixed(4))).join('');

  // matriz de confusión (2x2)
  const cm = {}; d.confusion.forEach(c => cm[`${c.actual}_${c.predicted}`]=c.n);
  document.getElementById('confusion').innerHTML = `
    <table class="text-sm w-full text-center">
      <tr><td></td><th>Pred NO</th><th>Pred SÍ</th></tr>
      <tr><th>Real NO</th><td class="bg-green-50">${cm['no_no']??0}</td><td class="bg-red-50">${cm['no_si']??0}</td></tr>
      <tr><th>Real SÍ</th><td class="bg-red-50">${cm['si_no']??0}</td><td class="bg-green-50">${cm['si_si']??0}</td></tr>
    </table>`;

  const bar = (id, labels, data, label) => new Chart(document.getElementById(id),
    { type:'bar', data:{ labels, datasets:[{ label, data }] },
      options:{ plugins:{legend:{display:false}}, responsive:true } });

  new Chart(document.getElementById('chartCompare'), { type:'bar',
    data:{ labels: d.comparison.map(c=>c.model_name),
      datasets:[ {label:'F1', data:d.comparison.map(c=>c.f1)},
                 {label:'AUC', data:d.comparison.map(c=>c.roc_auc)} ] } });

  new Chart(document.getElementById('chartBalance'), { type:'doughnut',
    data:{ labels:d.target_balance.map(t=> t.deposit ? 'Sí' : 'No'),
           datasets:[{ data:d.target_balance.map(t=>t.n) }] } });

  bar('chartJob', d.rate_by_job.map(r=>r.job), d.rate_by_job.map(r=>r.tasa_pct), 'Tasa %');
  bar('chartEdu', d.rate_by_education.map(r=>r.education), d.rate_by_education.map(r=>r.tasa_pct), 'Tasa %');
  bar('chartScore', d.score_distribution.map(s=>s.bucket), d.score_distribution.map(s=>s.n), 'n');
}
load();
</script>
</body></html>
```
**Aceptación:** `/bi` muestra las 6 scorecards, la matriz de confusión 2×2, y los gráficos
de comparación, balance, tasa por oficio/educación y distribución de scores.

---

## Criterio de aceptación GLOBAL

- `https://TU-APP.onrender.com/bi` (misma URL del servicio) muestra el dashboard, **sin
  login** y **sin segundo servicio**.
- Lee de Supabase vía `SUPABASE_DB_URL` (las vistas/tablas ya creadas).
- ETL (`/`) y modelo (`/model`) siguen funcionando igual.
- Con `model_metrics` vacía, muestra el mensaje para correr `load_metrics_to_db.py`.
- El gráfico de distribución de scores se llena a medida que se hacen predicciones
  (botón "Predecir pendientes" del panel del modelo).

## Prerrequisitos y cómo probar

1. En Supabase ya deben estar: las vistas (`sql/views_bi.sql`) y las tablas de métricas
   pobladas (`python ml/load_metrics_to_db.py`).
2. `SUPABASE_DB_URL` definida (local y en Render — es la misma que usa el modelo).
3. Local: `python wsgi.py` → abrir `http://localhost:8000/bi`.
4. En Render: confirmar que **despliega esta rama**, hacer deploy, abrir `.../bi`.
5. Verificar que `requirements.txt` (raíz) ya trae `flask`, `sqlalchemy`, `psycopg2-binary`
   (lo usa el modelo) → no deberían faltar dependencias.

## Qué desbloquea

- Apartado h del informe e indicador 3 (integración BI) con **evidencia desplegada**.
- La demo "pipeline → modelo → panel de métricas" queda en **una sola URL**, sin cold
  start de Metabase ni RAM extra.
