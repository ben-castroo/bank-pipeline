# Resumen de validaciones y limpieza — Bank Pipeline ETL

## Columnas esperadas (17)

| Columna | Tipo tras limpieza | Descripción |
|---------|-------------------|-------------|
| `age` | INTEGER | Edad del cliente |
| `job` | VARCHAR | Ocupación |
| `marital` | VARCHAR | Estado civil |
| `education` | VARCHAR | Nivel educativo |
| `default` | BOOLEAN | ¿Tiene crédito en mora? |
| `balance` | INTEGER | Saldo en cuenta |
| `housing` | BOOLEAN | ¿Tiene hipoteca? |
| `loan` | BOOLEAN | ¿Tiene préstamo personal? |
| `contact` | VARCHAR | Medio de contacto |
| `day` | INTEGER | Día del último contacto |
| `month` | VARCHAR | Mes del último contacto |
| `duration` | INTEGER | Duración de la última llamada (seg) |
| `campaign` | INTEGER | Nº de contactos en esta campaña |
| `pdays` | INTEGER | Días desde el contacto anterior (−1 = nunca) |
| `previous` | INTEGER | Nº de contactos en campañas anteriores |
| `poutcome` | VARCHAR | Resultado de campaña anterior |
| `deposit` | BOOLEAN | ¿Suscribió depósito a plazo? (objetivo) |

---

## Pasos de validación y limpieza (en orden de ejecución)

### 1. Validación de estructura
**Cuándo:** Antes de cualquier procesamiento.  
**Qué verifica:** Que el archivo tenga exactamente las 17 columnas esperadas.  
**Resultado si falla:** El ETL se detiene con error inmediato indicando qué columnas faltan o sobran.  
**Archivo de prueba:** `data/bank_estructura_test.csv` (columnas renombradas al español → activa este error).

---

### 2. Deduplicación
**Criterio:** Fila completamente idéntica en todas las columnas (`keep='first'`).  
**Resultado:** La primera aparición se conserva; las copias adicionales se marcan como `rechazado` con motivo `duplicado`.

---

### 3. Normalización de texto
**Columnas afectadas:** `job`, `marital`, `education`, `default_credit`, `housing`, `loan`, `contact`, `month`, `poutcome`, `deposit`.  
**Transformaciones:**
- Eliminar espacios al inicio/final (`strip`)
- Convertir a minúsculas (`lower`)
- Vacíos y `NaN` → `"unknown"`

**Registro:** Si el valor cambió, se guarda en `etl_row_logs` con `event = normalizado`.

---

### 4. Conversión numérica
**Columnas afectadas:** `age`, `balance`, `day`, `duration`, `campaign`, `pdays`, `previous`.  
**Método:** `pd.to_numeric(errors="coerce")` — valores no numéricos se convierten en `NaN` (se detectarán como nulo crítico en el paso 7).

---

### 5. Filtros de rango numérico
| Columna | Rango válido |
|---------|-------------|
| `age` | 18 – 100 |
| `day` | 1 – 31 |
| `duration` | ≥ 0 |
| `campaign` | ≥ 1 |
| `previous` | ≥ 0 |
| `pdays` | ≥ −1 |

**Resultado si falla:** Fila descartada → `rejected` con motivo `fuera_de_rango`.

---

### 6. Conversión de columnas binarias (yes/no → booleano)
**Columnas:** `default_credit`, `housing`, `loan`, `deposit`.  
**Mapeo:** `"yes"` → `True`, `"no"` → `False`.  
**Si el valor no es yes/no:** Se convierte a `NULL` y se registra en `etl_row_logs` con `event = binario_invalido`. La fila puede continuar (el NULL se descartará en el paso 7 si la columna es crítica).

---

### 7. Filtros de categoría
| Columna | Valores permitidos |
|---------|-------------------|
| `marital` | `married`, `single`, `divorced` |
| `education` | `primary`, `secondary`, `tertiary`, `unknown` |
| `contact` | `cellular`, `telephone`, `unknown` |
| `poutcome` | `success`, `failure`, `other`, `unknown` |
| `job` | `admin.`, `unknown`, `unemployed`, `management`, `housemaid`, `entrepreneur`, `student`, `blue-collar`, `self-employed`, `retired`, `technician`, `services` |

**Resultado si falla:** Fila descartada → `rejected` con motivo `categoria_invalida`.

---

### 8. Eliminación de nulos críticos
**Columnas críticas:** `age`, `balance`, `day`, `duration`, `campaign`, `pdays`, `previous`, `deposit`.  
**Resultado si falla:** Fila descartada → `rejected` con motivo `nulo_critico`.

---

## Destino de los datos

| Resultado | Destino | Tabla |
|-----------|---------|-------|
| Datos originales sin modificar | Render PostgreSQL | `bank_raw` |
| Filas que pasaron todos los filtros | Supabase | `bank_clean` |
| Filas descartadas con motivo | Render PostgreSQL | `etl_rejected` |
| Log granular por fila (correcciones + aceptados + rechazados) | Render PostgreSQL | `etl_row_logs` |
| Métricas de cada ejecución | Render PostgreSQL | `etl_reports` |

---

## Métricas del reporte de calidad

- `registros_iniciales` — Filas en el archivo fuente
- `duplicados_eliminados` — Copias exactas descartadas
- `filas_fuera_de_rango` — Filas con valores numéricos inválidos
- `filas_categoria_invalida` — Filas con categorías no permitidas
- `filas_con_nulos_criticos` — Filas con campos obligatorios vacíos
- `registros_finales` — Filas cargadas en `bank_clean`
