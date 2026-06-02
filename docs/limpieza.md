# Limpieza, normalización y validaciones — Bank Pipeline ETL

Documento de referencia: qué hace cada paso, qué valores acepta y por qué se tomó esa decisión.

---

## 0. Validación de estructura

**Qué hace:** Comprueba que el archivo tenga exactamente las 17 columnas esperadas, ni más ni menos.

**Columnas requeridas:**
`age`, `job`, `marital`, `education`, `default`, `balance`, `housing`, `loan`, `contact`, `day`, `month`, `duration`, `campaign`, `pdays`, `previous`, `poutcome`, `deposit`

**Por qué:** El pipeline mapea cada columna a un tipo y a reglas de negocio específicas. Una columna renombrada o un archivo de otra fuente con diferente esquema pasaría las validaciones siguientes produciendo resultados incorrectos sin ningún aviso. Fallar temprano con un mensaje claro evita corrupción silenciosa de datos.

**Resultado si falla:** El ETL se detiene. No se escribe nada en la base de datos.

---

## 1. Deduplicación

**Qué hace:** Elimina filas completamente idénticas (todos los campos iguales). Se conserva la primera aparición (`keep='first'`). Las copias adicionales se registran en `etl_rejected` con motivo `duplicado`.

**Por qué:** Filas duplicadas inflan artificialmente las métricas de campaña y sesgan los modelos de clasificación. Un cliente que aparece dos veces en el dataset se contaría el doble en el análisis de conversión. El criterio "todas las columnas iguales" es conservador: si un mismo cliente fue contactado en dos ocasiones distintas, los campos `day`, `duration` o `campaign` serán diferentes y la fila se conserva.

---

## 2. Normalización de texto

**Columnas afectadas:** `job`, `marital`, `education`, `default_credit`, `housing`, `loan`, `contact`, `month`, `poutcome`, `deposit`

**Transformaciones aplicadas:**

| Transformación | Ejemplo antes | Ejemplo después |
|---|---|---|
| Eliminar espacios (`strip`) | `" yes "` | `"yes"` |
| Minúsculas (`lower`) | `"Married"` / `"MARRIED"` | `"married"` |
| Vacío o `NaN` → `"unknown"` | `""` / `NaN` | `"unknown"` |

**Por qué:** Los archivos CSV generados por herramientas externas (Excel, CRMs, exportaciones manuales) producen variaciones de capitalización y espaciado que son semánticamente equivalentes pero técnicamente distintas. Sin esta normalización, `"Married"` y `"married"` serían dos categorías diferentes, ambas rechazarían la validación de categorías del paso 5 aunque el valor sea correcto. El mapeo de `NaN`/vacío a `"unknown"` evita perder filas por campos de texto no rellenos cuando ese campo no es crítico para el análisis.

**Registro:** Si el valor de una celda cambió, se guarda un evento `normalizado` en `etl_row_logs` con el valor antes y después, para trazabilidad completa.

---

## 3. Conversión numérica

**Columnas afectadas:** `age`, `balance`, `day`, `duration`, `campaign`, `pdays`, `previous`

**Método:** `pd.to_numeric(errors="coerce")` — si el valor no puede convertirse a número, se reemplaza por `NaN`.

**Por qué:** Los archivos CSV almacenan todo como texto. Sin conversión explícita, operaciones como `age >= 18` comparan cadenas (`"9" > "18"` en orden lexicográfico) produciendo resultados incorrectos. El modo `errors="coerce"` convierte valores no numéricos (p.ej. `"N/A"`, `"?"`, texto libre) en `NaN` en lugar de lanzar un error, permitiendo que el pipeline continúe y que esas filas sean detectadas y descartadas en el paso de nulos críticos con un motivo claro.

---

## 4. Filtros de rango numérico

**Qué hace:** Descarta filas donde un campo numérico tiene un valor imposible o fuera del dominio del negocio.

| Campo | Rango válido | Justificación |
|---|---|---|
| `age` | 18 – 100 | Edad mínima legal para productos bancarios en Portugal (mercado del dataset). Valores < 18 indican error de captura; > 100 son biológicamente improbables. |
| `day` | 1 – 31 | Días del calendario. Valores fuera de este rango no corresponden a ninguna fecha real. |
| `duration` | ≥ 0 | Duración de llamada en segundos. No puede ser negativa. Cero indica que la llamada no se realizó o fue inmediata (registro igualmente válido para análisis). |
| `campaign` | ≥ 1 | Número de veces que se contactó al cliente en esta campaña. Si está en el dataset, fue contactado al menos una vez. |
| `previous` | ≥ 0 | Contactos en campañas anteriores. Cero es válido (cliente nuevo). |
| `pdays` | ≥ −1 | Días desde el último contacto anterior. −1 es el valor convencional del dataset para "nunca fue contactado antes". Cualquier valor menor es un error. |

**Resultado si falla:** Fila descartada → `etl_rejected` con motivo `fuera_de_rango`.

---

## 5. Conversión de columnas binarias (yes/no → booleano)

**Columnas:** `default_credit`, `housing`, `loan`, `deposit`

**Mapeo:** `"yes"` → `True`, `"no"` → `False`. Cualquier otro valor → `NULL`.

**Por qué:** Las columnas binarias del dataset fuente usan literales de texto `"yes"`/`"no"`. Almacenarlas como booleanos en PostgreSQL ocupa menos espacio, permite índices más eficientes y evita ambigüedades semánticas. Un valor que no sea `yes` ni `no` es un dato corrupto o de codificación desconocida; se convierte a `NULL` y se registra como `binario_invalido` en `etl_row_logs`. Si esa columna es crítica (como `deposit`, la variable objetivo), la fila será descartada en el paso siguiente.

---

## 6. Filtros de categoría

**Qué hace:** Descarta filas donde un campo categórico tiene un valor no reconocido.

### `marital` — Estado civil

| Valor | Significado |
|---|---|
| `married` | Casado/a |
| `single` | Soltero/a |
| `divorced` | Divorciado/a o viudo/a |

**Por qué:** Son los tres estados civiles del dataset UCI Bank Marketing. Cualquier otro valor indica un error de ingesta o una categoría de una fuente diferente incompatible con el modelo.

---

### `education` — Nivel educativo

| Valor | Significado |
|---|---|
| `primary` | Educación primaria |
| `secondary` | Educación secundaria |
| `tertiary` | Educación universitaria o superior |
| `unknown` | No informado |

**Por qué:** `unknown` se admite como valor legítimo porque el dato puede no estar disponible sin que eso invalide el registro.

---

### `contact` — Medio de contacto

| Valor | Significado |
|---|---|
| `cellular` | Teléfono móvil |
| `telephone` | Teléfono fijo |
| `unknown` | No registrado |

**Por qué:** Son los únicos canales de contacto del estudio. Un valor diferente (p.ej. `"email"`) indicaría que el archivo no pertenece a esta campaña.

---

### `poutcome` — Resultado de campaña anterior

| Valor | Significado |
|---|---|
| `success` | El cliente suscribió en la campaña anterior |
| `failure` | No suscribió |
| `other` | Resultado distinto o indeterminado |
| `unknown` | No hubo campaña anterior o no se registró |

**Por qué:** `unknown` es frecuente y legítimo (muchos clientes son nuevos). Cualquier otro valor es una categoría no definida en el esquema de la campaña.

---

### `job` — Ocupación

| Valores permitidos |
|---|
| `admin.`, `blue-collar`, `entrepreneur`, `housemaid`, `management`, `retired`, `self-employed`, `services`, `student`, `technician`, `unemployed`, `unknown` |

**Por qué:** Son las 12 categorías de ocupación del dataset UCI. El punto en `admin.` es parte del valor original y debe preservarse tal cual. `unknown` es válido para empleados cuya ocupación no fue registrada.

---

**Resultado si falla:** Fila descartada → `etl_rejected` con motivo `categoria_invalida`.

---

## 7. Eliminación de nulos críticos

**Columnas críticas:** `age`, `balance`, `day`, `duration`, `campaign`, `pdays`, `previous`, `deposit`

**Por qué son críticas:**
- `deposit` es la **variable objetivo** (target). Sin ella, la fila no aporta valor al análisis predictivo.
- `age`, `balance`, `duration`, `campaign`, `pdays`, `previous` son las **features numéricas principales**. Un registro con cualquiera de ellas vacía es prácticamente inutilizable para entrenamiento o análisis.
- `day` es necesario para reconstruir la fecha de contacto.

Las columnas de texto (`job`, `marital`, etc.) no son críticas porque ya fueron normalizadas a `"unknown"` en el paso 2, lo que es un valor válido y útil para el modelo.

**Resultado si falla:** Fila descartada → `etl_rejected` con motivo `nulo_critico`.

---

## Resumen del flujo
