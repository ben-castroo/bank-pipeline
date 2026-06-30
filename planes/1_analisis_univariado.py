"""
Wrapper de entrada para el análisis univariado.
Autoría del análisis: Luis Muñoz.
Delega en ml/eda.py; ejecutar desde la raíz del repo:
    python planes/1_analisis_univariado.py
"""
from pathlib import Path
import sys
import os

BASE_DIR = Path(__file__).resolve().parent.parent   # bank-pipeline/
sys.path.insert(0, str(BASE_DIR))
os.chdir(BASE_DIR)

import pandas as pd
from ml import eda


def cargar_bank_clean():
    csv = Path("ml/data/bank_clean_export.csv")
    if csv.exists():
        df = pd.read_csv(csv)
        from model_api.features import BOOLEAN_FEATURES, TARGET
        for col in BOOLEAN_FEATURES + [TARGET]:
            if col in df.columns and df[col].dtype == object:
                df[col] = df[col].map({"True": True, "False": False})
        return df
    from model_api import db
    return db.fetch_retrain_source()


if __name__ == "__main__":
    df = cargar_bank_clean()
    df = df.drop(columns=[c for c in eda.COLUMNAS_EXCLUIR if c in df.columns])
    resumen = eda.analizar_numericas(df, "reports/univariado")
    eda.analizar_categoricas(df, "reports/univariado")
    print(resumen.to_string(index=False))
    print("Univariado OK")
