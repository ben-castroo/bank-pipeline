"""Construcción del pipeline y entrenamiento sobre una muestra.

El pipeline COMPLETO (preprocesamiento + clasificador) se serializa junto,
de modo que la predicción nunca reimplementa la limpieza -> sin train/serve skew.
"""
import numpy as np
from sklearn.compose import ColumnTransformer
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler, OneHotEncoder
from sklearn.impute import SimpleImputer
from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import train_test_split
from sklearn.metrics import (
    accuracy_score, precision_score, recall_score, f1_score, roc_auc_score,
)

from . import config
from .features import (
    NUMERIC_FEATURES, NOMINAL_FEATURES, BOOLEAN_FEATURES, TARGET, select_features,
)


def build_pipeline() -> Pipeline:
    numeric = Pipeline([
        ("imputer", SimpleImputer(strategy="median")),
        ("scaler", StandardScaler()),
    ])
    nominal = Pipeline([
        ("imputer", SimpleImputer(strategy="most_frequent")),
        ("onehot", OneHotEncoder(handle_unknown="ignore")),
    ])
    boolean = Pipeline([
        ("imputer", SimpleImputer(strategy="most_frequent")),
    ])
    pre = ColumnTransformer([
        ("num", numeric, NUMERIC_FEATURES),
        ("nom", nominal, NOMINAL_FEATURES),
        ("bool", boolean, BOOLEAN_FEATURES),
    ])
    # class_weight='balanced' maneja el desbalance sin resampling (más liviano).
    clf = RandomForestClassifier(
        n_estimators=200,
        class_weight="balanced",
        random_state=config.RANDOM_STATE,
        n_jobs=-1,
    )
    return Pipeline([("pre", pre), ("clf", clf)])


def _gini(auc: float) -> float:
    return 2 * auc - 1


def train_on_sample(df, sample_size: int, random_state: int = config.RANDOM_STATE):
    """Entrena el pipeline sobre una muestra estratificada de `df`.

    Devuelve (pipeline, metrics, used_n).
    """
    data = df.dropna(subset=[TARGET]).copy()
    data[TARGET] = data[TARGET].map({True: 1, False: 0}).astype(int)

    used_n = min(sample_size, len(data))
    if used_n < len(data):
        data, _ = train_test_split(
            data, train_size=used_n, stratify=data[TARGET],
            random_state=random_state,
        )

    X = select_features(data)
    y = data[TARGET]

    X_tr, X_te, y_tr, y_te = train_test_split(
        X, y, test_size=0.2, stratify=y, random_state=random_state,
    )

    pipeline = build_pipeline()
    pipeline.fit(X_tr, y_tr)

    proba = pipeline.predict_proba(X_te)[:, 1]
    pred = (proba >= 0.5).astype(int)
    auc = roc_auc_score(y_te, proba)
    metrics = {
        "accuracy": round(float(accuracy_score(y_te, pred)), 4),
        "precision": round(float(precision_score(y_te, pred, zero_division=0)), 4),
        "recall": round(float(recall_score(y_te, pred, zero_division=0)), 4),
        "f1": round(float(f1_score(y_te, pred, zero_division=0)), 4),
        "roc_auc": round(float(auc), 4),
        "gini": round(float(_gini(auc)), 4),
        "n_train": int(len(X_tr)),
        "n_test": int(len(X_te)),
    }
    return pipeline, metrics, used_n
