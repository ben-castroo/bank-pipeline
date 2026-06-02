"""
Web Service para Render: ejecuta el ETL al arrancar
y expone endpoints para monitoreo y ejecución manual.
"""
import os
import threading
from datetime import datetime, timezone

from flask import Flask, jsonify

from process_data import get_engine, main as run_etl

app = Flask(__name__)

_status = {"state": "pending", "last_run": None, "error": None}


def _run_etl_background():
    _status["state"] = "running"
    _status["last_run"] = datetime.now(timezone.utc).isoformat()
    try:
        run_etl()
        _status["state"] = "success"
    except Exception as exc:
        _status["state"] = "error"
        _status["error"] = str(exc)
        raise


@app.get("/health")
def health():
    return jsonify({"status": "ok", "etl": _status}), 200


@app.post("/run")
def trigger():
    if _status["state"] == "running":
        return jsonify({"message": "ETL ya en ejecución"}), 409
    t = threading.Thread(target=_run_etl_background, daemon=True)
    t.start()
    return jsonify({"message": "ETL iniciado"}), 202


@app.get("/report")
def report():
    """Devuelve el último quality report guardado en PostgreSQL."""
    from sqlalchemy import text
    try:
        engine = get_engine()
        with engine.connect() as conn:
            row = conn.execute(text(
                "SELECT payload FROM etl_reports ORDER BY generated_at DESC LIMIT 1"
            )).fetchone()
        if row is None:
            return jsonify({"error": "No hay reportes aún"}), 404
        return jsonify(row[0]), 200
    except Exception as exc:
        return jsonify({"error": str(exc)}), 500


if __name__ == "__main__":
    # Ejecuta el ETL automáticamente al arrancar el servicio
    threading.Thread(target=_run_etl_background, daemon=True).start()

    port = int(os.environ.get("PORT", 8000))
    app.run(host="0.0.0.0", port=port)
