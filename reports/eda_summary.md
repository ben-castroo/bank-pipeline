# EDA Summary — bank-pipeline Fase 2

## 1. Dataset
- **Filas:** 11162  
- **Target:** `deposit`  
- **Balance:** 47.4% sí / 52.6% no — dataset balanceado (~50/50), no aplicar SMOTE.  

## 2. Calidad de datos
- Sin valores nulos en columnas críticas (ETL ya hizo `dropna`).  
- `unknown` se conserva como categoría válida.  

## 3. Estadísticas descriptivas (numéricas)
|       |        age |   balance |         day |    campaign |      pdays |     previous |   duration |
|:------|-----------:|----------:|------------:|------------:|-----------:|-------------:|-----------:|
| count | 11162      |  11162    | 11162       | 11162       | 11162      | 11162        |  11162     |
| mean  |    41.2319 |   1528.54 |    15.658   |     2.50842 |    51.3304 |     0.832557 |    371.994 |
| std   |    11.9134 |   3225.41 |     8.42074 |     2.72208 |   108.758  |     2.29201  |    347.128 |
| min   |    18      |  -6847    |     1       |     1       |    -1      |     0        |      2     |
| 25%   |    32      |    122    |     8       |     1       |    -1      |     0        |    138     |
| 50%   |    39      |    550    |    15       |     2       |    -1      |     0        |    255     |
| 75%   |    49      |   1708    |    22       |     3       |    20.75   |     1        |    496     |
| max   |    95      |  81204    |    31       |    63       |   854      |    58        |   3881     |

## 4. Bivariado numérico por deposit
|   deposit |   ('age', 'mean') |   ('age', 'median') |   ('balance', 'mean') |   ('balance', 'median') |   ('day', 'mean') |   ('day', 'median') |   ('campaign', 'mean') |   ('campaign', 'median') |   ('pdays', 'mean') |   ('pdays', 'median') |   ('previous', 'mean') |   ('previous', 'median') |   ('duration', 'mean') |   ('duration', 'median') |
|----------:|------------------:|--------------------:|----------------------:|------------------------:|------------------:|--------------------:|-----------------------:|-------------------------:|--------------------:|----------------------:|-----------------------:|-------------------------:|-----------------------:|-------------------------:|
|         0 |             40.84 |                  39 |               1280.23 |                     414 |             16.11 |                  16 |                   2.84 |                        2 |               35.69 |                    -1 |                   0.53 |                        0 |                 223.13 |                      163 |
|         1 |             41.67 |                  38 |               1804.27 |                     733 |             15.16 |                  15 |                   2.14 |                        2 |               68.7  |                    -1 |                   1.17 |                        0 |                 537.29 |                      426 |

## 5. Variable `duration` (nota de fuga)
- Correlación `duration` ↔ `deposit`: **0.452** (la más alta del dataset).  
- **Excluida del modelo** por fuga de datos: solo se conoce post-llamada.  
- Aparece en EDA únicamente como referencia.  

## 6. Modelo titular
- **Algoritmo:** RandomForestClassifier (200 árboles, class_weight=balanced).  
- **Features:** 15 columnas (sin `duration`).  
- **Accuracy:**  0.7282  
- **Precision:** 0.7464  
- **Recall:**    0.6456  
- **F1:**        0.6923  
- **ROC-AUC:**   0.7803  
- **Gini:**      0.5606  

## 7. Limitaciones conocidas
- Dataset balanceado (~50/50): accuracy es informativo; class_weight=balanced tiene efecto mínimo.  
- 11k filas: entrenado sobre el total (sin muestreo).  
- Reproducible: random_state=42 en todo.  
