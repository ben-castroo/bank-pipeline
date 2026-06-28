"""Entrypoint combinado: ETL (dashboard) + API del modelo en UN solo web service.

Render sirve un único proceso en un único puerto, así que montamos las dos
apps Flask con DispatcherMiddleware:

    /            -> dashboard del ETL  (/, /health, /run, /upload, /data/*, ...)
    /model/...   -> API del modelo     (/model/predict, /model/retrain, ...)

El ETL queda intacto: usa imports planos (from db import ...), así que añadimos
su carpeta al path y lo importamos tal cual. La API del modelo es un paquete
con imports relativos, por lo que su propio db.py NO colisiona con el del ETL.
"""
import os
import sys

from werkzeug.middleware.dispatcher import DispatcherMiddleware

# --- ETL (sin modificar): su carpeta va al path para importarlo plano --------
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "etl"))
import app as _etl_module            # noqa: E402  -> etl/app.py
etl_app = _etl_module.app

# --- API del modelo (paquete con imports relativos) --------------------------
from model_api.app import app as model_app   # noqa: E402

# --- App combinada -----------------------------------------------------------
application = DispatcherMiddleware(etl_app, {"/model": model_app})


if __name__ == "__main__":
    from werkzeug.serving import run_simple
    port = int(os.getenv("PORT", "8000"))
    run_simple("0.0.0.0", port, application, use_reloader=False)
