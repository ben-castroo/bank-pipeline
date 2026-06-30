"""API de predicción del modelo de depósito a plazo.

Endpoints:
  GET  /health                     -> estado del servicio (sin auth)
  GET  /model-info                 -> versión + métricas del modelo activo
  POST /predict                    -> predice un raw_id
  POST /predict/batch              -> predice una lista de raw_ids
  POST /retrain                    -> lanza reentrenamiento asíncrono (job)
  GET  /retrain/status/<job_id>    -> estado de un job

Todos los endpoints, salvo /health, requieren el header X-API-Key.
"""
import json
from flask import Flask, request, jsonify

from . import config
from . import db
from .auth import require_api_key
from .model_service import load_initial_model, model_holder, predict_df
from .retrain import start_retrain_job, RetrainBusy

app = Flask(__name__)

# --- Inicialización: tablas + modelo ----------------------------------------
# Resiliente: si falla, NO tumba el proceso (importante al ir combinado con el
# dashboard del ETL). Las rutas de predicción responden 503 hasta que el
# modelo esté disponible.
try:
    db.init_tables()
except Exception as exc:  # noqa: BLE001
    app.logger.warning(f"No se pudieron inicializar las tablas del modelo: {exc}")

try:
    _version, _source = load_initial_model()
    app.logger.info(f"Modelo inicial cargado: version={_version} (fuente={_source})")
except Exception as exc:  # noqa: BLE001
    app.logger.warning(
        f"No se pudo cargar el modelo al arrancar: {exc}. "
        "Las rutas de predicción responderán 503 hasta que exista un modelo."
    )


# --- Helpers ----------------------------------------------------------------
def _resolve_threshold(payload: dict) -> float:
    thr = payload.get("threshold", config.DEFAULT_THRESHOLD)
    try:
        thr = float(thr)
    except (TypeError, ValueError):
        raise ValueError("threshold debe ser numérico")
    if not 0.0 <= thr <= 1.0:
        raise ValueError("threshold debe estar entre 0 y 1")
    return thr


def _score_ids(ids: list, threshold: float):
    """Busca en bank_clean, predice, persiste en model_scores y arma la respuesta."""
    rows = db.fetch_clean_rows(ids)
    if rows.empty:
        return None, []

    found_ids = rows[config.CLEAN_ID_COLUMN].tolist()
    probas, preds, version = predict_df(rows, threshold)

    score_rows, results = [], []
    for rid, prob, pred in zip(found_ids, probas, preds):
        score_rows.append({"raw_id": int(rid), "prob": prob, "pred": pred,
                           "thr": threshold, "ver": version})
        results.append({
            "raw_id": int(rid),
            "prob_deposit": round(prob, 6),
            "pred_deposit": pred,
            "model_version": version,
        })
    db.insert_scores(score_rows)

    missing = [i for i in ids if i not in found_ids]
    return results, missing


# --- Endpoints --------------------------------------------------------------
@app.get("/health")
def health():
    _, version = model_holder.get()
    return jsonify({
        "status": "ok",
        "model_loaded": model_holder.loaded,
        "model_version": version,
    })


@app.get("/model-info")
@require_api_key
def model_info():
    _, version = model_holder.get()
    metrics = None
    if version and version != "base":
        metrics = db.get_metrics_for_version(version)
    if metrics is None:
        # métricas del modelo base horneado (si existe el card)
        try:
            with open(config.BASE_CARD_PATH) as fh:
                metrics = json.load(fh).get("metrics")
        except FileNotFoundError:
            metrics = None
    return jsonify({
        "model_version": version,
        "algorithm": "RandomForestClassifier (sklearn Pipeline)",
        "metrics": metrics,
    })


@app.post("/predict")
@require_api_key
def predict():
    if not model_holder.loaded:
        return jsonify({"error": "Modelo no disponible todavía"}), 503
    payload = request.get_json(silent=True) or {}
    if "raw_id" not in payload:
        return jsonify({"error": "Falta 'raw_id'"}), 400
    try:
        threshold = _resolve_threshold(payload)
    except ValueError as e:
        return jsonify({"error": str(e)}), 400

    results, _ = _score_ids([payload["raw_id"]], threshold)
    if not results:
        return jsonify({"error": "raw_id no encontrado en bank_clean"}), 404
    return jsonify({**results[0], "threshold": threshold})


@app.post("/predict/batch")
@require_api_key
def predict_batch():
    if not model_holder.loaded:
        return jsonify({"error": "Modelo no disponible todavía"}), 503
    payload = request.get_json(silent=True) or {}
    ids = payload.get("raw_ids")
    if not isinstance(ids, list) or not ids:
        return jsonify({"error": "Falta 'raw_ids' (lista no vacía)"}), 400
    try:
        threshold = _resolve_threshold(payload)
    except ValueError as e:
        return jsonify({"error": str(e)}), 400

    results, missing = _score_ids(ids, threshold)
    return jsonify({
        "threshold": threshold,
        "count": len(results or []),
        "predictions": results or [],
        "not_found": missing,
    })


@app.get("/predict/pending/count")
@require_api_key
def predict_pending_count():
    return jsonify({"pending": db.count_pending()})


@app.post("/predict/pending")
@require_api_key
def predict_pending():
    if not model_holder.loaded:
        return jsonify({"error": "Modelo no disponible todavía"}), 503
    payload = request.get_json(silent=True) or {}
    try:
        threshold = _resolve_threshold(payload)
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    limit = payload.get("limit", 2000)
    try:
        limit = int(limit)
    except (TypeError, ValueError):
        return jsonify({"error": "limit debe ser entero"}), 400

    ids = db.fetch_pending_ids(limit)
    if not ids:
        return jsonify({"scored": 0, "remaining": 0, "threshold": threshold})
    results, _ = _score_ids(ids, threshold)
    return jsonify({
        "scored": len(results or []),
        "remaining": db.count_pending(),
        "threshold": threshold,
    })


@app.post("/retrain")
@require_api_key
def retrain():
    payload = request.get_json(silent=True) or {}
    sample_size = payload.get("sample_size", config.DEFAULT_SAMPLE_SIZE)
    try:
        sample_size = int(sample_size)
    except (TypeError, ValueError):
        return jsonify({"error": "sample_size debe ser entero"}), 400
    if sample_size < config.MIN_SAMPLE_SIZE:
        return jsonify({"error": f"sample_size mínimo es {config.MIN_SAMPLE_SIZE}"}), 400

    try:
        job_id = start_retrain_job(sample_size)
    except RetrainBusy:
        return jsonify({"error": "Ya hay un reentrenamiento en curso"}), 409

    return jsonify({
        "job_id": job_id,
        "status": "running",
        "sample_size": sample_size,
    }), 202


@app.get("/retrain/status/<job_id>")
@require_api_key
def retrain_status(job_id):
    job = db.get_job(job_id)
    if not job:
        return jsonify({"error": "job_id no encontrado"}), 404
    # serializa timestamps
    for k in ("started_at", "finished_at"):
        if job.get(k) is not None:
            job[k] = job[k].isoformat()
    return jsonify(job)


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8000, debug=True)
