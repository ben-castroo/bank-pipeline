# IMPLEMENTACIÓN — Fase 2: Notebook canónico de EDA + modelo

**Proyecto:** `bank-pipeline` · **Objetivo:** construir el **único** notebook que
produce TODOS los números y figuras del apartado e del informe, del dashboard BI y
de la defensa de métricas (#8, 30%). Reutiliza `model_api` para que análisis ==
producción.

> Documento para ejecutarse con un agente de código (Claude Code / Cursor). Tareas en
> orden, con **criterio de aceptación**. No avanzar hasta cumplirlo.

---

## Contexto (estado verificado del repo)

- `model_api/features.py` define las columnas del modelo y **excluye `duration`**
  (fuga de datos). `select_features(df)` devuelve solo `FEATURE_COLUMNS`.
  - `NUMERIC_FEATURES = [age, balance, day, campaign, pdays, previous]` (sin duration)
  - `NOMINAL_FEATURES = [job, marital, education, contact, poutcome, month]`
  - `BOOLEAN_FEATURES = [default_credit, housing, loan]`
  - `TARGET = "deposit"`
- `model_api/training.py` expone `train_on_sample(df, sample_size)`, `build_pipeline()`
  (ColumnTransformer + RandomForest `class_weight='balanced'`) y `_gini(auc)`.
- **Dataset definitivo: la versión balanceada de ~11.000 filas** ya cargada en
  `bank_clean` (Supabase). Balance del target ~50/50 → confirmar con el conteo real.
- El modelo titular es **RandomForest SIN `duration`**. `duration` aparece solo en el
  EDA con la advertencia de fuga.

## Guardrails (no romper)

1. **No modificar `model_api`** salvo —opcional— extraer un helper `build_preprocessor()`
   sin alterar la firma de `build_pipeline()` (ver Tarea 7). Si se evita, el notebook
   reconstruye el preprocesador desde las constantes de `features.py`.
2. **El modelo titular usa `select_features()`** → queda sin `duration` automáticamente.
3. **Dataset balanceado (~50/50):** NO argumentar desbalance. Reportar el balance real;
   `accuracy` es válido; documentar que `class_weight='balanced'` tiene efecto mínimo
   aquí pero se conserva por paridad con producción. **Nada de SMOTE.**
4. **`random_state=42`** en todo (split, modelos). Reproducible: "Restart & Run All".
5. **Sin credenciales en el notebook.** Conexión por variable de entorno o CSV local.
   Todas las salidas a `reports/` (figuras + JSON).
6. **11k es chico → entrenar sobre TODO el dataset** (no muestrear).

## Archivos a crear

```
ml/
├── analisis_eda_modelo.ipynb     ← el notebook canónico
└── data/
    └── bank_clean_export.csv      ← export de bank_clean (fuente reproducible)
reports/
├── figures/                       ← histogramas, barras, heatmap, ROC, confusión, importancia
├── model_metrics.json             ← consumido por el dashboard y el informe
└── eda_summary.md                 ← resumen de números para quien redacta el apartado e
```

---

## Tarea 0 — Preparación de entorno y datos

- Desde la raíz del repo, instalar dependencias de gráficos (las de ML ya están):
  ```bash
  pip install matplotlib seaborn
  ```
- Poblar la fuente de datos (elegir UNA):
  - **CSV (recomendado, reproducible en la defensa):** exportar `bank_clean` a
    `ml/data/bank_clean_export.csv` (desde el dashboard o `\copy` por SQL).
  - **DB en vivo:** definir `SUPABASE_URL` y leer con `model_api.db`.

**Criterio de aceptación:** existe `ml/data/bank_clean_export.csv` (o `SUPABASE_URL`
está seteada) y este comando corre sin error desde la raíz:
```bash
python -c "from model_api.features import FEATURE_COLUMNS, select_features; print(len(FEATURE_COLUMNS), 'features')"
```

---

## Tarea 1 — Celda 0: imports, rutas y reuso de `model_api`

```python
import json, os
from pathlib import Path
import numpy as np, pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
from sklearn.model_selection import train_test_split
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (confusion_matrix, accuracy_score, precision_score,
                             recall_score, f1_score, roc_auc_score, roc_curve)

from model_api.features import (NUMERIC_FEATURES, NOMINAL_FEATURES, BOOLEAN_FEATURES,
                                FEATURE_COLUMNS, TARGET, select_features)
from model_api.training import build_pipeline, _gini

RANDOM_STATE = 42
REPORTS = Path("reports"); FIGS = REPORTS / "figures"
FIGS.mkdir(parents=True, exist_ok=True)
# columnas para EDA (incluyen duration, que NO va al modelo):
EDA_NUMERIC = NUMERIC_FEATURES + ["duration"]
EDA_CATEGORICAL = NOMINAL_FEATURES + BOOLEAN_FEATURES
```

**Criterio de aceptación:** la celda importa sin error; imprime `FEATURE_COLUMNS` (15
columnas, sin `duration`).

---

## Tarea 2 — Celda 1: carga de datos (DB o CSV)

```python
def cargar_bank_clean():
    csv = Path("ml/data/bank_clean_export.csv")
    if csv.exists():
        df = pd.read_csv(csv)
    else:
        from model_api import db
        df = db.fetch_retrain_source()
    # normalizar booleanas a True/False si vienen como texto/0-1
    return df

df = cargar_bank_clean()
print("Filas:", len(df))
```

**Criterio de aceptación:** `df` carga; `len(df)` ≈ 11.000; están las 17 columnas + `id`.

---

## Tarea 3 — Celda 2: análisis de calidad de datos (apartado e.calidad)

Calcular y guardar para el informe:
- `df.shape`, `df.dtypes`, nulos por columna (`df.isna().sum()`).
- Para numéricas (incl. `duration`): media, mediana, moda, std, **p25/p50/p75**, min, max.
- **Balance del target** (clave — reemplaza los "88/12" del informe):
  ```python
  balance = df[TARGET].value_counts(dropna=False)
  balance_pct = df[TARGET].value_counts(normalize=True).mul(100).round(1)
  print(balance, balance_pct, sep="\n")
  ```
- Nota redactable: "no se imputa en modelado porque el ETL ya hizo dropna en columnas
  críticas; `unknown` se mantiene como categoría válida".

**Criterio de aceptación:** se imprime tabla descriptiva con percentiles y el **balance
real** del target; esos números quedan disponibles para `eda_summary.md`.

---

## Tarea 4 — Celda 3: análisis univariado (apartado e.univariado)

- Histogramas: `age`, `balance`, `duration` → `reports/figures/hist_*.png`.
- Barras de frecuencia: `job`, `education` → `reports/figures/bar_*.png`.
- Barra del target `deposit` mostrando el balance → `reports/figures/target_balance.png`.

**Criterio de aceptación:** existen los `.png` de histogramas, barras y balance del target.

---

## Tarea 5 — Celda 4: bivariado + matriz de correlación (apartado e.bivariado)

- Numéricas por grupo de `deposit`: `df.groupby(TARGET)[EDA_NUMERIC].agg(['mean','median','std'])`.
- **Matriz de correlación** (numéricas incl. `duration` + `deposit` como 0/1):
  ```python
  num = df[EDA_NUMERIC].copy()
  num["deposit"] = df[TARGET].astype(int)
  corr = num.corr(numeric_only=True)
  sns.heatmap(corr, annot=True, fmt=".2f", cmap="coolwarm"); plt.tight_layout()
  plt.savefig(FIGS / "correlacion.png"); plt.close()
  ```
- **Puente de `duration`** (texto redactable): es la variable de mayor asociación con
  el target, PERO se excluye del modelo por fuga (solo se conoce post-llamada).

**Criterio de aceptación:** existe `correlacion.png`; queda anotada la correlación de
`duration` con `deposit` y la justificación de exclusión.

---

## Tarea 6 — Celda 5: bivariado categórico

- Para cada `EDA_CATEGORICAL`: `pd.crosstab(df[col], df[TARGET], normalize='index')*100`.
- Barras de tasa de suscripción por `job`, `education`, `poutcome`, `month` →
  `reports/figures/biv_*.png`.

**Criterio de aceptación:** existen las figuras de tasa por segmento.

---

## Tarea 7 — Celda 6: partición + preprocesamiento (apartado e.partición/preproc)

```python
data = df.dropna(subset=[TARGET]).copy()
y = data[TARGET].astype(int)
X = select_features(data)          # <- sin duration, paridad con producción
X_tr, X_te, y_tr, y_te = train_test_split(
    X, y, test_size=0.2, stratify=y, random_state=RANDOM_STATE)
```

Para comparar modelos sobre el **mismo preprocesamiento de producción**, elegir A o B:
- **A (preferida, sin tocar model_api):** reconstruir el `ColumnTransformer` desde las
  constantes de `features.py` (numéricas → imputer+scaler; nominales → OneHot
  `handle_unknown='ignore'`; booleanas → passthrough/imputer), **espejando lo que hace
  `training.build_pipeline`**. Antes de escribirlo, el agente **abre `training.py` y
  copia exactamente la definición del preprocesador** para no divergir.
- **B (opcional):** refactor mínimo no-rompedor en `training.py`: extraer
  `build_preprocessor()` y que `build_pipeline(clf=None)` lo use; el notebook lo importa.
  Si se hace, `python -m py_compile model_api/training.py` debe pasar y `build_pipeline()`
  seguir devolviendo el RF por defecto.

**Criterio de aceptación:** `X` no contiene `duration`; el split es estratificado;
el preprocesador del notebook coincide con el de `training.py` (mismas columnas/encoding).

---

## Tarea 8 — Celda 7: comparación de algoritmos (apartado e.modelo)

Entrenar y comparar sobre el mismo preprocesador y el mismo split:
- LogisticRegression (`max_iter=1000`, `class_weight='balanced'`) — baseline interpretable.
- RandomForest (vía `build_pipeline()` de producción) — candidato fuerte.
- (Opcional) XGBoost si está instalado.

Tabla comparativa con `f1` y `roc_auc` en test. Justificar la elección de **RandomForest**
(mejor F1/AUC, mejor recall en la clase positiva, alineado al objetivo de negocio).

**Criterio de aceptación:** existe la tabla comparativa LogReg vs RF (vs XGB) con F1 y AUC;
queda escrita la justificación de por qué RF.

---

## Tarea 9 — Celda 8: modelo titular + métricas (apartado e.métricas)

```python
pipe = build_pipeline()            # RF de producción, sin duration
pipe.fit(X_tr, y_tr)
proba = pipe.predict_proba(X_te)[:, 1]
pred = (proba >= 0.5).astype(int)
cm = confusion_matrix(y_te, pred)            # [[tn, fp],[fn, tp]]
auc = roc_auc_score(y_te, proba)
metrics = {
    "accuracy":  round(float(accuracy_score(y_te, pred)), 4),
    "precision": round(float(precision_score(y_te, pred)), 4),
    "recall":    round(float(recall_score(y_te, pred)), 4),
    "f1":        round(float(f1_score(y_te, pred)), 4),
    "roc_auc":   round(float(auc), 4),
    "gini":      round(float(_gini(auc)), 4),
}
```

**Criterio de aceptación:** se obtienen las 6 métricas + matriz de confusión, **sobre el
modelo sin `duration`** (AUC realista, NO el ~0,89–0,95 que da con duration).

---

## Tarea 10 — Celda 9: figuras de métricas

- **Curva ROC** (`roc_curve` + AUC) → `reports/figures/roc.png`.
- **Matriz de confusión** (heatmap con TN/FP/FN/TP etiquetados) → `reports/figures/confusion.png`.
- **Importancia de variables** del RF (mapeando `get_feature_names_out` del preprocesador
  a `feature_importances_`) → `reports/figures/importancia.png`.

**Criterio de aceptación:** existen `roc.png`, `confusion.png`, `importancia.png`.

---

## Tarea 11 — Celda 10: exportar artefactos para informe y dashboard

`reports/model_metrics.json` con este esquema (lo consume el dashboard y el informe):
```json
{
  "dataset": {"source": "bank_clean", "n_rows": 0, "target": "deposit",
              "balance": {"si": 0, "no": 0, "si_pct": 0.0}},
  "split": {"test_size": 0.2, "stratified": true, "random_state": 42,
            "n_train": 0, "n_test": 0},
  "model": {"name": "RandomForestClassifier", "duration_excluded": true,
            "class_weight": "balanced", "n_estimators": 200},
  "metrics": {"accuracy": 0, "precision": 0, "recall": 0, "f1": 0, "roc_auc": 0, "gini": 0},
  "confusion_matrix": {"tn": 0, "fp": 0, "fn": 0, "tp": 0},
  "model_comparison": [
    {"model": "LogisticRegression", "f1": 0, "roc_auc": 0},
    {"model": "RandomForest",       "f1": 0, "roc_auc": 0}
  ]
}
```
Y un `reports/eda_summary.md` con: balance real del target, descriptivos con percentiles,
hallazgos del bivariado y la nota de `duration`. Es el insumo directo del apartado e.

**Criterio de aceptación:** existen `model_metrics.json` (con `duration_excluded: true`
y el balance real) y `eda_summary.md`.

---

## Criterio de aceptación GLOBAL de la Fase 2

- "Restart & Run All" corre el notebook de principio a fin **sin error**.
- En `reports/` están: `model_metrics.json`, `eda_summary.md` y todas las figuras
  (histogramas, barras, balance del target, correlación, ROC, confusión, importancia).
- Las métricas titulares son del modelo **sin `duration`**.
- El JSON trae el **balance real** del target (para corregir los "88/12" del informe).

## Limitaciones conocidas (para el informe / defensa)

- Dataset balanceado (~50/50): accuracy es informativo; `class_weight='balanced'` tiene
  efecto mínimo (se conserva por paridad con producción); no se usa SMOTE.
- `duration` queda fuera del modelo por fuga; aparece solo en EDA.
- 11k filas: se entrena sobre el total (sin muestreo); métricas pueden variar algo entre
  corridas si no se fija `random_state` (está fijado en 42).

## Qué desbloquea esta fase

- Apartado **e** del informe (números y figuras reales).
- Tabla/vista `model_metrics` del **dashboard BI** (Fase 3).
- La defensa de **métricas (#8, 30%)**: cada integrante explica matriz de confusión,
  por qué RF, por qué sin `duration`, qué es el Gini, y por qué recall importa.
