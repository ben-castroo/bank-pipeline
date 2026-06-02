"""
Web Service para Render: ejecuta el ETL al arrancar
y expone endpoints para monitoreo y ejecución manual.
"""
import logging
import os
import threading
from collections import deque
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from flask import Flask, jsonify, render_template, request
from sqlalchemy import text

from process_data import TZ_NAME, get_engine, log, main as run_etl

app = Flask(__name__)
_tz = ZoneInfo(TZ_NAME)

_status = {"state": "pending", "last_run": None, "error": None, "timezone": TZ_NAME}

_UPLOAD_PATH = Path("/tmp/uploaded_bank.csv")


def _active_file() -> str | None:
    """Devuelve la ruta del archivo subido, o None si no hay ninguno."""
    # Busca cualquier extensión soportada
    for ext in (".csv", ".xlsx", ".xls"):
        candidate = _UPLOAD_PATH.with_suffix(ext)
        if candidate.exists():
            return str(candidate)
    return None


_ALLOWED_EXT = {".csv", ".xlsx", ".xls"}


def _safe_ext(filename: str) -> str | None:
    ext = Path(filename).suffix.lower()
    return ext if ext in _ALLOWED_EXT else None


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
    file_path = _active_file()
    if file_path is None:
        _status["state"] = "error"
        _status["error"] = "No hay archivo cargado. Sube un CSV desde el dashboard."
        log.error("ETL cancelado: no hay archivo cargado.")
        return
    os.environ["DATA_FILE"] = file_path
    log.info("ETL disparado desde Web Service (tz=%s) · archivo: %s", TZ_NAME, file_path)
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


@app.get("/logs/granular")
def get_granular_logs():
    try:
        engine = get_engine()
        with engine.connect() as conn:
            total = conn.execute(text("SELECT COUNT(*) FROM etl_row_logs")).scalar() or 0
            rows = conn.execute(text(
                "SELECT row_index, event, detail, snapshot, run_at "
                "FROM etl_row_logs "
                "ORDER BY CASE event "
                "  WHEN 'rechazado' THEN 0 "
                "  WHEN 'normalizado' THEN 1 "
                "  WHEN 'binario_invalido' THEN 1 "
                "  ELSE 2 END, row_index "
                "LIMIT 2000"
            )).mappings().all()
        result = []
        for r in rows:
            entry = {
                "row_index": r["row_index"],
                "event": r["event"],
                "detail": r["detail"],
                "run_at": r["run_at"].isoformat() if r["run_at"] else None,
            }
            if r["snapshot"]:
                entry["snapshot"] = r["snapshot"]
            result.append(entry)
        return jsonify({"total": total, "shown": len(result), "rows": result}), 200
    except Exception as exc:
        return jsonify({"error": str(exc)}), 500


@app.post("/run")
def trigger():
    if _status["state"] == "running":
        return jsonify({"message": "ETL ya en ejecución"}), 409
    threading.Thread(target=_run_etl_background, daemon=True).start()
    return jsonify({"message": "ETL iniciado"}), 202


@app.get("/current-file")
def current_file():
    path = _active_file()
    if path is None:
        return jsonify({"file": None, "source": "ninguno", "bytes": 0}), 200
    size = Path(path).stat().st_size
    return jsonify({"file": Path(path).name, "source": "subido", "bytes": size}), 200


@app.post("/upload")
def upload():
    if "file" not in request.files:
        return jsonify({"error": "No se recibió ningún archivo"}), 400
    f = request.files["file"]
    if not f.filename:
        return jsonify({"error": "Nombre de archivo vacío"}), 400
    ext = _safe_ext(f.filename)
    if ext is None:
        return jsonify({"error": "Solo se permiten archivos .csv, .xlsx o .xls"}), 415
    dest = _UPLOAD_PATH.with_suffix(ext)
    f.save(dest)
    # Si cambió extensión, eliminar el anterior
    if dest != _UPLOAD_PATH and _UPLOAD_PATH.exists():
        _UPLOAD_PATH.unlink(missing_ok=True)
    log.info("Archivo subido: %s (%d bytes)", dest.name, dest.stat().st_size)
    return jsonify({"message": f"Archivo {dest.name} recibido", "file": dest.name}), 200


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
        from process_data import get_supabase_engine
        engine = get_supabase_engine()
        if engine is None:
            return jsonify({"error": "SUPABASE_URL no configurada"}), 503
        with engine.connect() as conn:
            rows = conn.execute(text(
                "SELECT * FROM bank_clean ORDER BY id DESC LIMIT 50"
            )).mappings().all()
        return jsonify([_serialize_row(dict(r)) for r in rows]), 200
    except Exception as exc:
        return jsonify({"error": str(exc)}), 500


@app.get("/data/rejected")
def data_rejected():
    try:
        engine = get_engine()
        with engine.connect() as conn:
            rows = conn.execute(text(
                "SELECT row_index, reason, original_data "
                "FROM etl_rejected ORDER BY id LIMIT 500"
            )).mappings().all()
        result = []
        for r in rows:
            entry = {"row_index": r["row_index"], "reason": r["reason"]}
            if r["original_data"]:
                entry.update(r["original_data"])
            result.append(entry)
        return jsonify(result), 200
    except Exception as exc:
        return jsonify({"error": str(exc)}), 500


@app.post("/truncate")
def truncate_tables():
    """Vacía las tablas de datos en Render PG y Supabase."""
    from process_data import get_supabase_engine
    results = {}

    # ── Render PostgreSQL (metadatos: raw, reports, rejected, row_logs) ──────────
    try:
        engine = get_engine()
        with engine.begin() as conn:
            conn.execute(text(
                "TRUNCATE TABLE bank_raw, etl_reports, etl_rejected, etl_row_logs RESTART IDENTITY CASCADE"
            ))
        results["render"] = "ok"
        log.warning("Tablas vaciadas en Render PG: bank_raw, etl_reports, etl_rejected, etl_row_logs")
    except Exception as exc:
        results["render"] = str(exc)
        log.error("Error al vaciar tablas en Render PG: %s", exc)

    # ── Supabase (opcional) ──────────────────────────────────────────────────
    supa_engine = get_supabase_engine()
    if supa_engine is not None:
        try:
            with supa_engine.begin() as conn:
                conn.execute(text(
                    "TRUNCATE TABLE bank_clean RESTART IDENTITY CASCADE"
                ))
            results["supabase"] = "ok"
            log.warning("Tabla bank_clean vaciada en Supabase")
        except Exception as exc:
            results["supabase"] = str(exc)
            log.error("Error al vaciar tabla en Supabase: %s", exc)
    else:
        results["supabase"] = "no configurado"

    return jsonify(results), 200


if __name__ == "__main__":
    threading.Thread(target=_run_etl_background, daemon=True).start()
    port = int(os.environ.get("PORT", 8000))
    app.run(host="0.0.0.0", port=port)

