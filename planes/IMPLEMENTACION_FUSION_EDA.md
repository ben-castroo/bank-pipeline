# IMPLEMENTACIÓN — Fusión del EDA (scripts de Luis + notebook canónico)

**Proyecto:** `bank-pipeline`. **Objetivo:** unir lo mejor de ambos: el análisis
univariado/bivariado de **Luis Muñoz** (`1_analisis_univariado.py`,
`2_analisis_bivariado.py`) pasa a ser el **módulo oficial de EDA** que el notebook
canónico importa. Se preserva su autoría, su estructura y sus entry points; se corrigen
tres detalles para que todo lea el mismo dataset de 11k.

> Para ejecutarse con agente de código (Cursor/Claude Code) o por el propio Luis.

---

## Principio de la fusión

- **EDA descriptivo = código de Luis** (es el más completo y sistemático). Se refactoriza
  a `ml/eda.py` con funciones importables, **sin perder su lógica**.
- **Modelo = notebook** (partición, preprocesamiento reusando `model_api`, métricas).
- **Una sola carga de datos:** el `df` se carga una vez y se pasa a las funciones de EDA
  y al modelo. Así EDA y modelo describen exactamente los mismos datos.

## Guardrails

1. **No descartar la lógica de Luis.** `ml/eda.py` es su análisis, reorganizado. Mantener
   sus nombres de función (`analizar_numericas`/`analizar_categoricas`) y su enfoque.
   Atribución en el encabezado del módulo y en la sección del notebook.
2. **`ml/eda.py` no carga datos ni importa el `db` del ETL.** Recibe el `df` como
   argumento (funciones puras). Esto resuelve la inconsistencia de fuente de datos.
3. **`duration` se incluye solo en EDA** (describir y justificar su exclusión). El lado
   del modelo no cambia: sigue usando `select_features()` (sin duration).
4. **Rutas relativas** bajo `reports/` (nada de `/reports/...` absolutas).
5. **Reusar las columnas de `model_api.features`** para no divergir.

## Archivos

```
ml/
├── eda.py                      ← NUEVO: módulo de EDA (autoría: Luis Muñoz)
├── __init__.py                 ← NUEVO: vacío, para importar `from ml import eda`
└── analisis_eda_modelo.ipynb   ← se reemplaza la sección EDA por llamadas a eda.py
1_analisis_univariado.py        ← pasa a ser wrapper que llama a ml/eda.py
2_analisis_bivariado.py         ← pasa a ser wrapper que llama a ml/eda.py
reports/univariado/  reports/bivariado/  reports/figures/   ← salidas
```

---

## Tarea 1 — Crear `ml/__init__.py` (vacío)

Para poder importar `from ml import eda` corriendo desde la raíz del repo.
**Aceptación:** existe `ml/__init__.py`.

---

## Tarea 2 — Crear `ml/eda.py` (refactor del código de Luis)

```python
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

EDA_NUMERICAS   = NUMERIC_FEATURES + ["duration"]      # duration SOLO para EDA
EDA_CATEGORICAS = NOMINAL_FEATURES + BOOLEAN_FEATURES
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
        pct  = pd.crosstab(df[c], df[target], normalize="index") * 100   # tasa por categoría
        freq.to_csv(out / f"{c}_vs_{target}.csv")
        pct.to_csv(out / f"{c}_vs_{target}_porcentaje.csv")
        # opcional recomendado: graficar la tasa (pct) en vez de la frecuencia
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
```

**Aceptación:** `python -c "from ml import eda; print(eda.EDA_NUMERICAS)"` corre desde la
raíz sin error e incluye `duration`; el módulo **no** importa el `db` del ETL.

---

## Tarea 3 — Integrar en el notebook (sección atribuida a Luis)

Reemplazar las celdas de EDA del notebook (las que hacían histogramas/bivariado a mano)
por esta sección, usando el `df` ya cargado en la celda de carga:

```python
# === Análisis univariado y bivariado — Luis Muñoz ===
from ml import eda

UNI  = "reports/univariado"
BIV  = "reports/bivariado"
FIGS = "reports/figures"

resumen_num = eda.analizar_numericas(df, UNI)      # incluye percentiles
display(resumen_num)
eda.analizar_categoricas(df, UNI)                  # incluye balance de deposit
eda.bivariado_numericas(df, BIV, FIGS)
eda.bivariado_categoricas(df, BIV, FIGS)
corr = eda.matriz_correlacion(df, FIGS)            # heatmap incl. duration
display(corr)
# Nota: duration aparece aquí (EDA) pero se EXCLUYE del modelo por fuga de datos.
```

Mantener intactas las celdas del **modelo** (partición, preprocesamiento, comparación,
métricas) del `IMPLEMENTACION_FASE2`.

**Aceptación:** "Restart & Run All" corre completo; se generan
`reports/univariado/univariado_numericas.csv` (con `p25/p50/p75`), los CSV por categoría,
los CSV bivariados (frecuencia y porcentaje), las figuras y `reports/figures/correlacion.png`.

---

## Tarea 4 — Convertir los scripts de Luis en wrappers (preservar entry points)

Para que `python 1_analisis_univariado.py` siga funcionando standalone y nada se rompa,
cada script carga el `df` y delega en `ml/eda.py`:

```python
# 1_analisis_univariado.py
from pathlib import Path
import pandas as pd
from ml import eda

def cargar_bank_clean():
    csv = Path("ml/data/bank_clean_export.csv")
    if csv.exists():
        return pd.read_csv(csv)
    from model_api import db
    return db.fetch_retrain_source()

if __name__ == "__main__":
    df = cargar_bank_clean()
    df = df.drop(columns=[c for c in eda.COLUMNAS_EXCLUIR if c in df.columns])
    eda.analizar_numericas(df, "reports/univariado")
    eda.analizar_categoricas(df, "reports/univariado")
    print("Univariado OK")
```
(Análogo para `2_analisis_bivariado.py` con `bivariado_numericas` / `bivariado_categoricas`
/ `matriz_correlacion`.)

**Aceptación:** ambos scripts corren standalone desde la raíz y producen los mismos CSV
y figuras que el notebook; usan la **misma** fuente de datos que el modelo.

---

## Criterio de aceptación GLOBAL

- `ml/eda.py` existe, está **atribuido a Luis**, y reúsa columnas de `model_api.features`.
- El notebook usa `eda.py` para todo el univariado/bivariado + correlación, en una
  sección con su nombre.
- Hay **una sola carga de datos** (un `df`) compartida por EDA y modelo → mismo dataset 11k.
- `duration` aparece solo en EDA; el modelo sigue sin `duration`.
- Los scripts originales de Luis siguen funcionando (como wrappers).
- Salidas en `reports/univariado`, `reports/bivariado`, `reports/figures` (rutas relativas).

## Qué resuelve y qué desbloquea

- Cierra dos inconsistencias del registro: **rutas absolutas** y **fuente de datos del EDA**.
- Le da a Luis **propiedad clara** de la sección univariado/bivariado del informe y de su
  parte de la defensa.
- Suma lo que faltaba al código (percentiles + matriz de correlación) sin rehacer su
  trabajo.
- Deja el apartado e con el EDA y el modelo coherentes y sobre el mismo snapshot.
