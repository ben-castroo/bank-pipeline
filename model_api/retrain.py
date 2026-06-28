"""Reentrenamiento asíncrono.

- Un solo job a la vez (se valida contra la tabla retrain_jobs + un lock local).
- Corre en un hilo daemon; la UI recibe un job_id de inmediato.
- Al terminar: sube el modelo a Storage, hace hot swap en memoria y registra
  métricas/estado en la base.
"""
import threading
import traceback
import uuid

from . import db
from . import storage
from .training import train_on_sample
from .model_service import model_holder

_start_lock = threading.Lock()


class RetrainBusy(Exception):
    """Ya hay un reentrenamiento en curso."""


def start_retrain_job(sample_size: int) -> str:
    """Lanza el job en segundo plano. Devuelve job_id o lanza RetrainBusy."""
    with _start_lock:
        if db.running_job_exists():
            raise RetrainBusy()
        job_id = str(uuid.uuid4())
        db.create_job(job_id, sample_size)

    thread = threading.Thread(
        target=_run_job, args=(job_id, sample_size), daemon=True
    )
    thread.start()
    return job_id


def _run_job(job_id: str, sample_size: int) -> None:
    try:
        source = db.fetch_retrain_source()
        pipeline, metrics, used_n = train_on_sample(source, sample_size)
        metrics["sample_size_used"] = used_n

        version = storage.make_version()
        storage.upload_model(pipeline, version)

        model_holder.set(pipeline, version)   # hot swap atómico
        db.finish_job(job_id, version, metrics)
    except Exception:
        db.fail_job(job_id, traceback.format_exc())
