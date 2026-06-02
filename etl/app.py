"""
Web Service para Render: ejecuta el ETL al arrancar
y expone endpoints para monitoreo y ejecución manual.
"""
import logging
import os
import threading
from collections import deque
from datetime import datetime
from zoneinfo import ZoneInfo

from flask import Flask, jsonify, render_template
from sqlalchemy import text

from process_data import TZ_NAME, get_engine, log, main as run_etl

app = Flask(__name__)
_tz = ZoneInfo(TZ_NAME)

_status = {"state": "pending", "last_run": None, "error": None, "timezone": TZ_NAME}


# ---------------------------------------------------------------------------
# Captura de logs en memoria
# ---------------------------------------------------------------------------
class _LogCapture(logging.Handler):
    def __init__(self, maxlen: int = 300):
        super().__init__()
        self._records: deque = deque(maxlen=maxlen)

    def emit(self, record: logging.LogRecord) -> None:
        self._records.appendleft({
            "time": datetime.fromtimestamp(record.created, tz=_tz).strftime("%Y-%m-%dT%H:%M:%S %Z"),
            "level": record.levelname,
            "message": record.getMessage(),
        })

    def get_logs(self) -> list:
        return list(self._records)


_log_capture = _LogCapture()
log.addHandler(_log_capture)


def _run_etl_background() -> None:
    _status["state"] = "running"
    _status["last_run"] = datetime.now(_tz).isoformat()
    _status["error"] = None
    log.info("ETL disparado desde Web Service (tz=%s)", TZ_NAME)
    try:
        run_etl()
        _status["state"] = "success"
        log.info("ETL completado con éxito.")
    except Exception as exc:
        _status["state"] = "error"
        _status["error"] = str(exc)
        log.error("ETL falló: %s", exc)


def _serialize_row(row: dict) -> dict:
    result = {}
    for k, v in row.items():
        if hasattr(v, "isoformat"):
            result[k] = v.isoformat()
        else:
            result[k] = v
    return result


# ---------------------------------------------------------------------------
# Rutas
# ---------------------------------------------------------------------------
@app.get("/")
def dashboard():
    return render_template("dashboard.html")


@app.get("/health")
def health():
    return jsonify({"status": "ok", "etl": _status}), 200


@app.get("/logs")
def get_logs():
    return jsonify(_log_capture.get_logs()), 200


@app.post("/run")
def trigger():
    if _status["state"] == "running":
        return jsonify({"message": "ETL ya en ejecución"}), 409
    threading.Thread(target=_run_etl_background, daemon=True).start()
    return jsonify({"message": "ETL iniciado"}), 202


@app.get("/report")
def report():
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


@app.get("/data/raw")
def data_raw():
    try:
        engine = get_engine()
        with engine.connect() as conn:
            rows = conn.execute(text(
                "SELECT * FROM bank_raw ORDER BY id DESC LIMIT 50"
            )).mappings().all()
        return jsonify([_serialize_row(dict(r)) for r in rows]), 200
    except Exception as exc:
        return jsonify({"error": str(exc)}), 500


@app.get("/data/clean")
def data_clean():
    try:
        engine = get_engine()
        with engine.connect() as conn:
            rows = conn.execute(text(
                "SELECT * FROM bank_clean ORDER BY id DESC LIMIT 50"
            )).mappings().all()
        return jsonify([_serialize_row(dict(r)) for r in rows]), 200
    except Exception as exc:
        return jsonify({"error": str(exc)}), 500


if __name__ == "__main__":
    threading.Thread(target=_run_etl_background, daemon=True).start()
    port = int(os.environ.get("PORT", 8000))
    app.run(host="0.0.0.0", port=port)

