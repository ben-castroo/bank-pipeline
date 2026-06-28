"""Persistencia del artefacto del modelo en Supabase Storage (vía REST).

Usamos la API REST directa de Storage (con `requests`) en vez de un cliente
pesado, para mantener el contenedor liviano y el comportamiento transparente.

Convención de nombres de objeto:
    {MODEL_PREFIX}/model-{version}.joblib   (version = timestamp UTC)
La "última versión" se determina listando el prefijo y tomando el nombre
mayor (los timestamps ISO ordenan correctamente como texto).
"""
import io
import joblib
import requests
from datetime import datetime, timezone

from . import config


def make_version() -> str:
    """Versión basada en timestamp UTC, ej. 2025-06-28T15:30:00Z."""
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _headers(extra: dict | None = None) -> dict:
    h = {"Authorization": f"Bearer {config.SUPABASE_SERVICE_KEY}"}
    if extra:
        h.update(extra)
    return h


def _object_path(version: str) -> str:
    return f"{config.MODEL_PREFIX}/model-{version}.joblib"


def upload_model(pipeline, version: str) -> str:
    """Serializa el pipeline y lo sube a Storage. Devuelve la ruta del objeto."""
    buf = io.BytesIO()
    joblib.dump(pipeline, buf)
    buf.seek(0)
    path = _object_path(version)
    url = f"{config.SUPABASE_PROJECT_URL}/storage/v1/object/{config.MODEL_BUCKET}/{path}"
    resp = requests.post(
        url,
        headers=_headers({"Content-Type": "application/octet-stream", "x-upsert": "true"}),
        data=buf.read(),
        timeout=60,
    )
    resp.raise_for_status()
    return path


def _list_versions() -> list[str]:
    url = f"{config.SUPABASE_PROJECT_URL}/storage/v1/object/list/{config.MODEL_BUCKET}"
    resp = requests.post(
        url,
        headers=_headers({"Content-Type": "application/json"}),
        json={"prefix": f"{config.MODEL_PREFIX}/", "limit": 1000,
              "sortBy": {"column": "name", "order": "desc"}},
        timeout=30,
    )
    resp.raise_for_status()
    names = [obj["name"] for obj in resp.json() if obj.get("name", "").startswith("model-")]
    return sorted(names, reverse=True)


def download_latest_model():
    """Descarga el modelo más reciente desde Storage.

    Devuelve (pipeline, version) o lanza una excepción si no hay ninguno.
    """
    versions = _list_versions()
    if not versions:
        raise FileNotFoundError("No hay modelos en Storage todavía.")
    latest_name = versions[0]                       # ej. model-2025-06-28T15:30:00Z.joblib
    version = latest_name.replace("model-", "").replace(".joblib", "")
    path = f"{config.MODEL_PREFIX}/{latest_name}"
    url = f"{config.SUPABASE_PROJECT_URL}/storage/v1/object/{config.MODEL_BUCKET}/{path}"
    resp = requests.get(url, headers=_headers(), timeout=60)
    resp.raise_for_status()
    pipeline = joblib.load(io.BytesIO(resp.content))
    return pipeline, version
