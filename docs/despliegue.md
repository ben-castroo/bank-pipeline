# Guía de despliegue — Bank Pipeline

## Prerequisitos
- Cuenta en [Render](https://render.com) (plan gratuito es suficiente)
- Cuenta en [Supabase](https://supabase.com) (plan gratuito es suficiente)
- Repositorio en GitHub con el código del proyecto

---

## 1. Supabase — Base de datos de datos limpios

### 1.1 Crear proyecto
1. Ir a [supabase.com](https://supabase.com) → **New project**
2. Elegir organización, nombre del proyecto, contraseña (guardarla) y región más cercana
3. Esperar a que el proyecto se inicialice (~2 minutos)

### 1.2 Obtener la URL de conexión (pooler)
> ⚠️ Usar el **connection pooler** (puerto 6543), NO la conexión directa. Render free tier no soporta IPv6 que usa el puerto directo.

1. En el panel de Supabase → **Project Settings** → **Database**
2. Sección **Connection pooling** → modo **Transaction**
3. Copiar la URI que tiene el formato:
   ```
   postgresql://postgres.[REF]:[PASSWORD]@aws-0-[region].pooler.supabase.com:6543/postgres
   ```
4. Guardar esta URL — será `SUPABASE_URL` en Render

> La tabla `bank_clean` se crea automáticamente la primera vez que el ETL se ejecuta.

---

## 2. Render — PostgreSQL (metadatos del ETL)

### 2.1 Crear base de datos PostgreSQL
1. En el dashboard de Render → **New** → **PostgreSQL**
2. Configurar:
   - **Name:** `bank-pipeline-db` (o cualquier nombre)
   - **Region:** la más cercana
   - **Plan:** Free
3. Click en **Create Database**
4. Una vez creada, anotar la **Internal Database URL** (solo accesible desde servicios del mismo account en Render)

> Las tablas (`bank_raw`, `etl_reports`, `etl_rejected`, `etl_row_logs`) se crean automáticamente al arrancar el servicio.

---

## 3. Render — Web Service

### 3.1 Crear el servicio
1. En el dashboard de Render → **New** → **Web Service**
2. Conectar el repositorio de GitHub (autorizar Render si es la primera vez)
3. Seleccionar el repositorio `bank-pipeline`

### 3.2 Configurar el servicio
| Campo | Valor |
|-------|-------|
| **Name** | `bank-pipeline` (o cualquier nombre) |
| **Region** | La misma que la BD de Render |
| **Branch** | `main` |
| **Root Directory** | `gestion_ia/bank-pipeline` |
| **Runtime** | **Docker** |
| **Instance Type** | Free |

> El Dockerfile está en `etl/Dockerfile` dentro del Root Directory. Render lo detecta automáticamente.

### 3.3 Variables de entorno
En la sección **Environment** del Web Service, agregar:

| Variable | Valor | Descripción |
|----------|-------|-------------|
| `DATABASE_URL` | *(enlazar la BD de Render — ver paso 3.4)* | Conexión a Render PostgreSQL |
| `SUPABASE_URL` | `postgresql://postgres.[REF]:[PASS]@aws-0-[region].pooler.supabase.com:6543/postgres` | Conexión a Supabase (pooler) |
| `TZ` | `America/Mexico_City` *(o la zona horaria deseada)* | Timestamps en logs. Opcional, defecto: `UTC` |

### 3.4 Enlazar la base de datos de Render
En lugar de copiar la URL manualmente, usar la integración nativa:
1. En el Web Service → **Environment** → **Add from Database**
2. Seleccionar la BD de PostgreSQL creada en el paso 2
3. Esto crea automáticamente la variable `DATABASE_URL` con la URL interna

### 3.5 Deploy
1. Click en **Create Web Service**
2. Render construye la imagen Docker y despliega
3. Verificar en los logs que aparezca:
   ```
   Tablas verificadas/creadas en Render PostgreSQL.
   * Running on http://0.0.0.0:[PORT]
   ```

---

## 4. Verificar el despliegue

1. Abrir la URL del Web Service (ej. `https://bank-pipeline.onrender.com`)
2. El dashboard debe cargarse con el estado **pendiente** o **éxito** si el ETL ya corrió
3. Subir un archivo CSV desde el botón de upload
4. Click en **▶ Ejecutar ETL**
5. Verificar en la pestaña **Logs** que el pipeline complete sin errores
6. Verificar en **Datos limpios** que los registros aparezcan (vienen de Supabase)

---

## 5. Auto-deploy

Cada `git push` a `main` dispara un nuevo deploy automáticamente en Render.  
Para desactivarlo: Web Service → **Settings** → **Auto-Deploy** → Off.

---

## Estructura de archivos relevantes para el despliegue

```
bank-pipeline/
├── etl/
│   ├── Dockerfile          ← imagen del Web Service
│   ├── requirements.txt    ← dependencias Python
│   ├── db.py               ← conexiones y DDL
│   ├── process_data.py     ← lógica ETL
│   ├── app.py              ← Flask Web Service
│   └── templates/
│       └── dashboard.html  ← interfaz web
└── data/
    └── bank.csv            ← archivo de datos (se sube desde el dashboard)
```

---

## Solución de problemas comunes

| Error | Causa | Solución |
|-------|-------|---------|
| `ModuleNotFoundError: No module named 'db'` | `db.py` no copiado en Dockerfile | Verificar que `COPY etl/db.py .` esté en el Dockerfile |
| `CERTIFICATE_VERIFY_FAILED` | SSL en Supabase | Usar el URL del pooler (puerto 6543) con `sslmode=require` |
| `connection refused` a Supabase | Usando IPv6 (puerto 5432 directo) | Cambiar al URL del connection pooler (puerto 6543) |
| `No hay archivo cargado` | ETL se dispara sin CSV | Subir un archivo desde el dashboard antes de ejecutar |
| Dashboard vacío en "Datos limpios" | `SUPABASE_URL` no configurada | Agregar la variable en Render → Environment |
