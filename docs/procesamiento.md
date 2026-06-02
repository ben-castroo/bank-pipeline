# Documentación del procesamiento ETL — Bank Pipeline

## Arquitectura general

```
Archivo CSV/Excel
      │
      ▼
  read_source()          ← lectura y normalización de nombres de columnas
      │
      ▼
  validate_structure()   ← verificación de columnas esperadas
      │
  ┌───┴────────────────────────────────────┐
  │                                        │
  ▼                                        ▼
load_raw()                           clean_data()
(Render PG → bank_raw)                    │
                                     ┌────┴─────────────────────┐
                                     │  Pipeline de limpieza     │
                                     └────────────────────────── ┘
                                          │
                              ┌───────────┼────────────┐
                              ▼           ▼            ▼
                       load_clean_    load_rejected  load_row_logs
                       supabase()    (Render PG)    (Render PG)
                       (Supabase →
                        bank_clean)
                              │
                              ▼
                         write_report()
                         (Render PG → etl_reports)
```

---

## Bases de datos

| BD | Tablas | Función |
|----|--------|---------|
| **Render PostgreSQL** | `bank_raw` | Datos originales sin modificar |
| **Render PostgreSQL** | `etl_reports` | Métricas de calidad de cada ejecución |
| **Render PostgreSQL** | `etl_rejected` | Filas descartadas con motivo |
| **Render PostgreSQL** | `etl_row_logs` | Log granular por fila (correcciones) |
| **Supabase** | `bank_clean` | Datos procesados y listos para consumo |

---

## Variables de entorno requeridas

| Variable | Descripción |
|----------|-------------|
| `DATABASE_URL` | URL de conexión a Render PostgreSQL (se configura automáticamente si el servicio está enlazado) |
| `SUPABASE_URL` | URL del connection pooler de Supabase (puerto 6543). Formato: `postgresql://postgres.[REF]:[PASS]@aws-0-[region].pooler.supabase.com:6543/postgres` |
| `TZ` | Zona horaria para timestamps (opcional, por defecto `UTC`). Ejemplo: `America/Mexico_City` |
| `DATA_FILE` | Ruta al archivo a procesar (lo setea el Web Service automáticamente al recibir un upload) |

---

## Descripción de cada función en `process_data.py`

### Configuración y constantes

#### `TZ_NAME`, `_tz`, `_TZFormatter`
Configuración de zona horaria. `TZ_NAME` lee la variable de entorno `TZ` (por defecto `UTC`).  
`_TZFormatter` es un formateador de logging que añade la zona horaria configurada a cada mensaje de log.

#### `EXPECTED_COLUMNS`
Lista de 17 columnas que debe tener el archivo fuente. Si falta alguna o hay columnas extra, el ETL falla con error descriptivo.

#### `TEXT_COLUMNS`, `NUMERIC_COLUMNS`, `BINARY_COLUMNS`
Clasificación de columnas por tipo de dato para aplicar las transformaciones correctas.

#### `VALID_MARITAL`, `VALID_EDUCATION`, `VALID_CONTACT`, `VALID_POUTCOME`, `VALID_JOBS`
Conjuntos de valores permitidos para columnas categóricas. Cualquier valor fuera de estos conjuntos produce el rechazo de la fila.

---

### Conexiones a base de datos

#### `get_engine() → Engine`
Retorna un engine SQLAlchemy hacia **Render PostgreSQL**.  
Prioriza la variable `DATABASE_URL` (Render la setea automáticamente si el PG está enlazado al servicio).  
Si no está definida, usa las variables individuales `DB_USER`, `DB_PASSWORD`, `DB_HOST`, `DB_PORT`, `DB_NAME`.  
Siempre fuerza `sslmode=require`.

#### `get_supabase_engine() → Engine | None`
Retorna un engine SQLAlchemy hacia **Supabase** usando `SUPABASE_URL`.  
Si la variable no está definida, retorna `None` y el ETL omite la carga a Supabase sin fallar.  
⚠️ Usar el URL del **connection pooler** (puerto 6543), no el de conexión directa, para evitar problemas de IPv6 en Render free tier.

---

### Creación de tablas

#### `create_tables(engine)`
Crea en Render PostgreSQL, solo si no existen (`CREATE TABLE IF NOT EXISTS`):
- `bank_raw` — datos originales como texto
- `etl_reports` — métricas de calidad por ejecución
- `etl_rejected` — filas descartadas durante la limpieza
- `etl_row_logs` — log granular de eventos por fila

#### `create_tables_supabase(engine)`
Crea en Supabase, solo si no existe:
- `bank_clean` — datos limpios con índice en columna `deposit`

---

### Lectura y validación

#### `resolve_data_file() → Path`
Determina qué archivo procesar. Orden de prioridad:
1. Variable de entorno `DATA_FILE` (seteada por el Web Service al recibir un upload)
2. `/data/bank.csv` o variantes xlsx/xls (fallback para ejecución local)

Lanza `FileNotFoundError` si no encuentra ningún archivo.

#### `read_source(path) → DataFrame`
Lee el archivo fuente (CSV o Excel). Normaliza los nombres de columna: minúsculas y sin espacios.

#### `validate_structure(df)`
Verifica que el DataFrame tenga exactamente las 17 columnas esperadas.  
Lanza `ValueError` indicando qué columnas faltan o sobran.

---

### Carga de datos crudos

#### `load_raw(df, engine)`
Carga los datos originales (sin transformar) en `bank_raw` de Render PG.  
- Renombra `default` → `default_credit`
- Convierte todas las columnas a texto (`astype(str)`)
- Añade timestamp `loaded_at` con la zona horaria configurada
- **Reemplaza** la tabla completa en cada ejecución (`TRUNCATE` + `INSERT`)

---

### Pipeline de limpieza

#### `_row_to_dict(row) → dict`
Función auxiliar. Convierte una fila de pandas a un diccionario JSON-serializable, manejando tipos numpy y valores NaN.

#### `clean_data(df) → (DataFrame, dict, list, list)`
Función principal de limpieza. Retorna cuatro objetos:
1. `df` — DataFrame limpio listo para cargar
2. `stats` — diccionario con métricas de calidad
3. `rejected` — lista de filas descartadas con motivo
4. `row_logs` — lista de eventos granulares por fila

**Pasos en orden:**

| # | Paso | Qué hace | Qué registra |
|---|------|----------|--------------|
| 1 | **Deduplicación** | `df.duplicated(keep='first')` — mantiene la **primera** copia de cada fila duplicada, descarta el resto | Las copias eliminadas → `rejected` con `reason="duplicado"` |
| 2 | **Normalización de texto** | Para columnas categóricas: strip, lower, vacíos/nan → `"unknown"` | Si el valor cambia → `row_logs` con `event="normalizado"` y detalle del cambio |
| 3 | **Conversión numérica** | `pd.to_numeric(errors="coerce")` — valores no numéricos → NaN | — |
| 4 | **Filtros de rango** | Elimina filas fuera de: `age`∈[18,100], `day`∈[1,31], `duration≥0`, `campaign≥1`, `previous≥0`, `pdays≥−1` | Filas eliminadas → `rejected` con `reason="fuera_de_rango"` |
| 5 | **Conversión binaria** | `{"yes": True, "no": False}` en columnas yes/no | Si el valor no era yes/no → `row_logs` con `event="binario_invalido"` y NULL resultante |
| 6 | **Filtros de categoría** | Elimina filas con valores no permitidos en `marital`, `education`, `contact`, `poutcome`, `job` | Filas eliminadas → `rejected` con `reason="categoria_invalida"` |
| 7 | **Nulos críticos** | Elimina filas con NaN en: `age`, `balance`, `day`, `duration`, `campaign`, `pdays`, `previous`, `deposit` | Filas eliminadas → `rejected` con `reason="nulo_critico"` |
| 8 | **Registro final** | Cada fila que sobrevivió → `row_logs` con `event="aceptado"`. Cada fila en `rejected` → `row_logs` con `event="rechazado"` | Visibilidad completa de qué pasó con cada fila |

> **Nota sobre duplicados:** `keep='first'` significa que si una fila aparece 3 veces, la primera se conserva (y puede ser `aceptado` si pasa los demás filtros), y las otras 2 se marcan como `rechazado` con motivo `duplicado`.

---

### Carga de datos limpios

#### `load_clean_supabase(df, engine)`
Carga el DataFrame limpio en `bank_clean` de Supabase.
- Añade timestamp `processed_at` con la zona horaria configurada
- **Reemplaza** el contenido completo en cada ejecución

> `bank_clean` de Render PG fue eliminada. Supabase es el único destino de datos limpios.

---

### Carga de metadatos del ETL

#### `load_rejected(rejected, engine)`
Inserta todas las filas descartadas en `etl_rejected` de Render PG.  
Los datos originales de cada fila se almacenan como JSONB en `original_data`.  
La tabla se trunca al inicio de cada ejecución (siempre refleja la última corrida).

#### `load_row_logs(row_logs, engine)`
Inserta todos los eventos granulares en `etl_row_logs` de Render PG.  
Usa inserción en lote (executemany vía SQLAlchemy).  
La tabla se trunca al inicio de cada ejecución.

#### `write_report(stats, source_file, engine)`
Genera el reporte de calidad y lo persiste en `etl_reports` de Render PG (columna `payload` JSONB).  
También intenta escribirlo en `/reports/quality_report.json` (efímero en Render, útil en local).

**Métricas incluidas:**

| Métrica | Descripción |
|---------|-------------|
| `registros_iniciales` | Total de filas en el archivo fuente |
| `duplicados_eliminados` | Filas descartadas por ser copias exactas |
| `filas_fuera_de_rango` | Filas descartadas por valores numéricos inválidos |
| `filas_categoria_invalida` | Filas descartadas por categorías no permitidas |
| `filas_con_nulos_criticos` | Filas descartadas por nulos en campos obligatorios |
| `registros_finales` | Filas que pasaron todos los filtros y fueron cargadas |
| `nulos_por_columna` | Conteo de nulos por columna en el dataset limpio |

---

### Función principal

#### `main()`
Orquesta el pipeline completo en este orden:
1. Leer archivo fuente y validar estructura
2. Conectar a Render PG y crear tablas si no existen
3. Cargar datos crudos en `bank_raw`
4. Ejecutar `clean_data()` y loguear métricas
5. Cargar rechazados en `etl_rejected`
6. Cargar logs granulares en `etl_row_logs`
7. Si `SUPABASE_URL` está definida: crear tabla en Supabase y cargar datos limpios
8. Escribir reporte de calidad

Si `SUPABASE_URL` no está definida, el paso 7 se omite con un log informativo y el ETL no falla.
