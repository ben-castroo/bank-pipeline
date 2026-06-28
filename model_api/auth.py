"""Autenticación simple por API key en header."""
from functools import wraps
from flask import request, jsonify

from . import config


def require_api_key(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        if not config.API_KEY:
            # Falla cerrada: si el servidor no tiene API_KEY configurada, no se sirve.
            return jsonify({"error": "Servidor sin API_KEY configurada"}), 500
        if request.headers.get(config.API_KEY_HEADER) != config.API_KEY:
            return jsonify({"error": "No autorizado"}), 401
        return fn(*args, **kwargs)
    return wrapper
