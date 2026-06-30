# Auditoría de Seguridad — bank-pipeline
**Fecha:** 2026-06-29 · **Auditor:** agente (Fase 4) · **Rama:** feat/fase3-4-5

---

## 1. Escaneo de secretos en archivos versionados

**Comando ejecutado:** `git ls-files | xargs grep -nEi "(service_role|supabase.*(key|url)|api[_-]?key|secret|passw)"`

**Resultado:** todos los matches corresponden a:
- Documentación de referencia (`.md`) con placeholders: `[PASSWORD]`, `eyJ...service_role...`, `un-token-secreto`.
- Archivos de ejemplo (`model_api/.env.example`) con valores de plantilla, **no reales**.
- Referencias a nombres de variable (`os.environ`, `getenv`) sin valores embebidos.
- Configuración de desarrollo local (`docker-compose.yml` con `postgres:postgres`).

**Conclusión: cero secretos reales detectados en archivos versionados.**

### `.env` en `.gitignore`
- `[OK]` `.env` figura en `.gitignore` → el archivo con credenciales reales nunca se versiona.

---

## 2. Verificación de autenticación de endpoints

Lectura de `model_api/app.py` + `model_api/auth.py`:

| Endpoint | Método | ¿Requiere X-API-Key? | Observación |
|---|---|---|---|
| `/health` | GET | **No** | Público intencional — solo devuelve estado y versión del modelo |
| `/model-info` | GET | **Sí** (`@require_api_key`) | Info del modelo en producción |
| `/predict` | POST | **Sí** (`@require_api_key`) | Predicción individual |
| `/predict/batch` | POST | **Sí** (`@require_api_key`) | Predicción en lote |
| `/retrain` | POST | **Sí** (`@require_api_key`) | Lanza reentrenamiento — crítico |
| `/retrain/status/<job_id>` | GET | **Sí** (`@require_api_key`) | Estado del job |

**Mecanismo (`auth.py`):**
- Si `API_KEY` no está configurada en el servidor → responde 500 (falla cerrada — no sirve sin clave).
- Si el header `X-API-Key` no coincide → responde 401.
- Ningún endpoint sensible está desprotegido.

**Conclusión: autenticación correcta. Ningún endpoint de predicción o reentrenamiento es accesible sin clave.**

---

## 3. Inventario de datos sensibles

### Clasificación de columnas de `bank_clean`

| Categoría | Columnas | Nivel de sensibilidad |
|---|---|---|
| **Cuasi-identificador** | `age` | Medio (no identifica sola, pero en combinación sí) |
| **Financiero** | `balance`, `housing`, `loan`, `default_credit` | Alto |
| **Conductual / campaña** | `contact`, `month`, `day`, `campaign`, `pdays`, `previous`, `poutcome` | Medio |
| **Laboral** | `job`, `marital`, `education` | Medio |
| **Target comercial** | `deposit` (resultado de suscripción) | Alto |
| **Sin PII directa** | — | El dataset **no contiene** nombre, RUT, email ni teléfono |

**Nota de minimización:** el dataset original no incluye identificadores directos (nombre, RUT). La columna `id` es una clave interna artificial, no un RUT ni DNI.

---

## 4. Matriz de roles

| Rol | Acceso | Privilegio | Riesgo |
|---|---|---|---|
| **Desarrollador** | Repo, `.env` local, despliegue | Alto (código completo) | Medio — acceso controlado por repositorio |
| **Operador ETL** | Ejecutar pipeline / dashboard ETL | Medio | Bajo — solo ejecuta, no modifica código |
| **Analista BI** | Solo lectura `bank_clean` + vistas en Metabase | Bajo | Bajo — sin acceso a tablas de scores o jobs |
| **Consumidor API** | `POST /predict`, `POST /predict/batch` con `X-API-Key` | Acotado por clave | Bajo — solo predicción, no puede entrenar ni leer DB |
| **Admin Supabase** | `service_role` key = máximo privilegio en toda la BD | **Crítico** | **Crítico** — puede leer, escribir y eliminar cualquier tabla; rotar si se expone |

### Riesgo más crítico
La `SUPABASE_SERVICE_KEY` (`service_role`) otorga acceso total sin restricción de Row Level Security (RLS). Si se expone (commit, log, slack), **rotar inmediatamente** desde el dashboard de Supabase → Settings → API.

---

## 5. Hallazgos y recomendaciones

| # | Hallazgo | Criticidad | Estado | Acción |
|---|---|---|---|---|
| 1 | `.env` no está versionado | — | ✅ Correcto | Mantener |
| 2 | Todos los endpoints sensibles requieren `X-API-Key` | — | ✅ Correcto | Mantener |
| 3 | `docker-compose.yml` usa `postgres:postgres` (dev) | Bajo | ✅ Aceptable | Solo para desarrollo local, no producción |
| 4 | `model_api/.env.example` con valores de plantilla visibles | Bajo | ✅ Intencional | Es un ejemplo; los valores reales están en `.env` (ignorado) |
| 5 | `service_role` key en variable de entorno de Render | Crítico | ✅ Correcto (en Render secrets) | No versionar; rotar periódicamente |
| 6 | Sin rate-limiting en la API | Medio | ⚠ Pendiente | Considerar para producción con tráfico real |
| 7 | Sin HTTPS explícito en código (depende de Render/proxy) | Bajo | ✅ Render provee TLS | Documentar que el TLS es responsabilidad del hosting |

**Resumen:** La postura de seguridad del proyecto es adecuada para un entorno académico/demo. Los riesgos identificados son de nivel bajo-medio y están documentados. El riesgo más crítico es la `service_role` key, que debe mantenerse fuera del código y rotar si se compromete.
