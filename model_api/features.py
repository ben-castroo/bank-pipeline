"""Definición de features y selección de columnas.

Este módulo es la ÚNICA fuente de verdad sobre qué columnas usa el modelo y
cómo se preparan. Tanto el entrenamiento como la predicción lo usan, de modo
que es imposible que diverjan (train/serve skew).

`duration` se excluye a propósito: solo se conoce DESPUÉS de la llamada y
filtra el resultado (data leakage).
"""
import pandas as pd

NUMERIC_FEATURES = ["age", "balance", "day", "campaign", "pdays", "previous"]
NOMINAL_FEATURES = ["job", "marital", "education", "contact", "poutcome", "month"]
BOOLEAN_FEATURES = ["default_credit", "housing", "loan"]

FEATURE_COLUMNS = NUMERIC_FEATURES + NOMINAL_FEATURES + BOOLEAN_FEATURES
TARGET = "deposit"


def select_features(df: pd.DataFrame) -> pd.DataFrame:
    """Devuelve solo las columnas de features, en el orden esperado por el
    pipeline, con las booleanas convertidas a numérico (0.0/1.0/NaN).

    Se usa tanto en entrenamiento como en predicción.
    """
    X = df.copy()
    for col in BOOLEAN_FEATURES:
        if col in X.columns:
            # bool/None -> float; los NaN los imputa el ColumnTransformer
            X[col] = X[col].map({True: 1.0, False: 0.0})
    missing = [c for c in FEATURE_COLUMNS if c not in X.columns]
    if missing:
        raise ValueError(f"Faltan columnas requeridas para predecir: {missing}")
    return X[FEATURE_COLUMNS]
