"""Entrena el MODELO BASE que se hornea en la imagen Docker.

Se corre UNA vez, en local, antes de construir la imagen. Genera:
    artifacts/base_model.joblib   (pipeline completo)
    artifacts/model_card.json     (algoritmo, métricas, fecha)

Lee desde bank_clean (necesita SUPABASE_DB_URL / SUPABASE_URL) o, si pasas
--csv ruta.csv, desde un CSV exportado del dashboard.

Uso:
    python train_base_model.py                 # desde la BD, muestra por defecto
    python train_base_model.py --sample 10000
    python train_base_model.py --csv data/bank_clean_export.csv --full
"""
import argparse
import json
import os
from datetime import datetime, timezone

import joblib
import pandas as pd

from . import config
from .training import train_on_sample


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--csv", help="Ruta a un CSV de bank_clean (opcional)")
    parser.add_argument("--sample", type=int, default=config.DEFAULT_SAMPLE_SIZE)
    parser.add_argument("--full", action="store_true", help="Usar todo el dataset")
    args = parser.parse_args()

    if args.csv:
        df = pd.read_csv(args.csv)
    else:
        from . import db
        df = db.fetch_retrain_source()

    sample_size = len(df) if args.full else args.sample
    pipeline, metrics, used_n = train_on_sample(df, sample_size)

    os.makedirs(config.ARTIFACTS_DIR, exist_ok=True)
    joblib.dump(pipeline, config.BASE_MODEL_PATH)

    card = {
        "model_version": "base",
        "algorithm": "RandomForestClassifier (sklearn Pipeline)",
        "trained_at": datetime.now(timezone.utc).isoformat(),
        "sample_size_used": used_n,
        "metrics": metrics,
        "note": "Modelo base horneado. Se reemplaza por reentrenamientos en Storage.",
    }
    with open(config.BASE_CARD_PATH, "w") as fh:
        json.dump(card, fh, indent=2)

    print(f"[OK] Modelo base guardado en {config.BASE_MODEL_PATH}")
    print(f"[OK] Metricas: {json.dumps(metrics, indent=2)}")


if __name__ == "__main__":
    main()
