"""
ml/eda.py — Análisis univariado y bivariado.
Autoría del análisis: Luis Muñoz.
Refactor a módulo importable, basado en 1_analisis_univariado.py y
2_analisis_bivariado.py. Las funciones reciben el DataFrame ya cargado.
"""
from pathlib import Path
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns

# Reusar las columnas de producción para no divergir. EDA incluye duration.
from model_api.features import (NUMERIC_FEATURES, NOMINAL_FEATURES,
                                BOOLEAN_FEATURES, TARGET)

EDA_NUMERICAS    = NUMERIC_FEATURES + ["duration"]      # duration SOLO para EDA
EDA_CATEGORICAS  = NOMINAL_FEATURES + BOOLEAN_FEATURES
COLUMNAS_EXCLUIR = ["id", "raw_id", "processed_at"]


# ---------- UNIVARIADO (de Luis; se le agregan percentiles) ----------
def analizar_numericas(df, out_dir, cols=EDA_NUMERICAS):
    out = Path(out_dir); out.mkdir(parents=True, exist_ok=True)
    filas = []
    for c in cols:
        s = df[c]; q = s.quantile([.25, .5, .75])
        filas.append({
            "variable": c, "cantidad": int(s.count()),
            "media": float(s.mean()), "mediana": float(s.median()),
            "moda": s.mode().iloc[0] if not s.mode().empty else None,
            "desv_std": float(s.std()),
            "p25": float(q.loc[.25]), "p50": float(q.loc[.5]), "p75": float(q.loc[.75]),
            "minimo": float(s.min()), "maximo": float(s.max()),
        })
    resumen = pd.DataFrame(filas)
    resumen.to_csv(out / "univariado_numericas.csv", index=False)
    return resumen


def analizar_categoricas(df, out_dir, cols=None):
    out = Path(out_dir); out.mkdir(parents=True, exist_ok=True)
    cols = cols or (EDA_CATEGORICAS + [TARGET])   # incluye deposit (balance del target)
    tablas = {}
    for c in cols:
        t = df[c].value_counts(dropna=False).reset_index()
        t.columns = [c, "frecuencia"]
        t["porcentaje"] = (t["frecuencia"] / len(df)) * 100
        t.to_csv(out / f"univariado_{c}.csv", index=False)
        tablas[c] = t
    return tablas


# ---------- BIVARIADO (de Luis; mismas salidas) ----------
def bivariado_numericas(df, out_dir, figs_dir, cols=EDA_NUMERICAS, target=TARGET):
    out = Path(out_dir); out.mkdir(parents=True, exist_ok=True)
    figs = Path(figs_dir); figs.mkdir(parents=True, exist_ok=True)
    for c in cols:
        resumen = (df.groupby(target)[c]
                     .agg(["count", "mean", "median", "min", "max", "std"]).reset_index())
        resumen.to_csv(out / f"{c}_vs_{target}.csv", index=False)
        resumen.plot(kind="bar", x=target, y="mean", legend=False)
        plt.title(f"Media de {c} según {target}"); plt.xlabel(target)
        plt.ylabel(f"Media de {c}"); plt.tight_layout()
        plt.savefig(figs / f"{c}_vs_{target}.png"); plt.close()


def bivariado_categoricas(df, out_dir, figs_dir, cols=EDA_CATEGORICAS, target=TARGET):
    out = Path(out_dir); out.mkdir(parents=True, exist_ok=True)
    figs = Path(figs_dir); figs.mkdir(parents=True, exist_ok=True)
    for c in cols:
        freq = pd.crosstab(df[c], df[target])
        pct  = pd.crosstab(df[c], df[target], normalize="index") * 100
        freq.to_csv(out / f"{c}_vs_{target}.csv")
        pct.to_csv(out / f"{c}_vs_{target}_porcentaje.csv")
        freq.plot(kind="bar")
        plt.title(f"{c} según {target}"); plt.xlabel(c); plt.ylabel("Frecuencia")
        plt.tight_layout(); plt.savefig(figs / f"{c}_vs_{target}.png"); plt.close()


# ---------- NUEVO: matriz de correlación (lo que faltaba) ----------
def matriz_correlacion(df, figs_dir, cols=EDA_NUMERICAS, target=TARGET):
    figs = Path(figs_dir); figs.mkdir(parents=True, exist_ok=True)
    num = df[cols].copy(); num[target] = df[target].astype(int)
    corr = num.corr(numeric_only=True)
    plt.figure(figsize=(9, 7))
    sns.heatmap(corr, annot=True, fmt=".2f", cmap="coolwarm")
    plt.tight_layout(); plt.savefig(figs / "correlacion.png"); plt.close()
    return corr
