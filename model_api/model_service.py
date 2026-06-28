"""Modelo en memoria con recarga en caliente (hot swap).

Un único holder protegido por lock guarda el pipeline activo y su versión.
Cuando un reentrenamiento termina, reemplazamos el pipeline de forma atómica
sin reiniciar el proceso.
"""
import threading
import joblib

from . import config
from . import storage
from .features import select_features


class ModelHolder:
    def __init__(self):
        self._lock = threading.RLock()
        self._pipeline = None
        self._version = None

    def set(self, pipeline, version: str):
        with self._lock:
            self._pipeline = pipeline
            self._version = version

    def get(self):
        with self._lock:
            return self._pipeline, self._version

    @property
    def loaded(self) -> bool:
        with self._lock:
            return self._pipeline is not None


model_holder = ModelHolder()


def load_initial_model() -> tuple[str, str]:
    """Carga el último modelo de Storage; si no hay, usa el base horneado.

    Devuelve (version, source) donde source ∈ {"storage", "base"}.
    """
    try:
        pipeline, version = storage.download_latest_model()
        model_holder.set(pipeline, version)
        return version, "storage"
    except Exception:
        pipeline = joblib.load(config.BASE_MODEL_PATH)
        model_holder.set(pipeline, "base")
        return "base", "base"


def predict_df(df, threshold: float):
    """Predice sobre un DataFrame ya proveniente de bank_clean.

    Devuelve (probas, preds, version) como listas / valores nativos de Python.
    """
    pipeline, version = model_holder.get()
    if pipeline is None:
        raise RuntimeError("No hay modelo cargado.")
    X = select_features(df)
    probas = pipeline.predict_proba(X)[:, 1]
    preds = probas >= threshold
    return [float(p) for p in probas], [bool(b) for b in preds], version
