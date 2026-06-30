"""Dashboard BI servido por la misma app Flask (mismo web service en Render).

Lee las vistas/tablas de BI en Supabase (sql/views_bi.sql) y entrega JSON
para que el frontend (Chart.js) las grafique. No requiere auth: solo expone
datos agregados (sin PII), pensado para que se abra sin login en la demo.
"""
import os

from flask import Flask, jsonify, render_template
from sqlalchemy import create_engine, text

app = Flask(__name__, template_folder="templates")

# Engine propio y lazy: si SUPABASE_DB_URL falta, solo /bi/data/* falla,
# no tumba el arranque combinado (ETL + modelo) en wsgi.py.
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
    except Exception as e:  # noqa: BLE001
        return jsonify({"error": str(e)}), 500


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8000, debug=True)
