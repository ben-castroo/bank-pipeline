# Sección e.g — Seguridad y Marco Legal
*(Esqueleto para el informe — el equipo redacta y verifica vigencia a la fecha de defensa)*

---

## 1. Datos personales en el proyecto

El dataset `bank_clean` contiene información de clientes bancarios procesada para
segmentar campañas de marketing. Las columnas se clasifican en:

- **Cuasi-identificadores:** `age` — no identifica por sí sola, pero puede
  contribuir a re-identificación en combinación.
- **Financieros:** `balance`, `housing`, `loan`, `default_credit` — revelan
  situación económica.
- **Conductuales:** historial de contactos de campaña (`campaign`, `pdays`,
  `previous`, `poutcome`, `month`, `day`, `contact`).
- **Target comercial:** `deposit` — resultado de la suscripción, dato sensible
  en contexto de scoring crediticio.
- **Sin PII directa:** el dataset **no contiene** nombre, RUT, email ni
  número de teléfono (ver principio de minimización, §3).

---

## 2. Marco legal chileno aplicable

### 2.1 Ley 19.628 (vigente)
> *[HUMANO: confirmar que sigue vigente o si ha sido derogada por 21.719 al momento de la defensa]*

La Ley 19.628 sobre Protección de la Vida Privada establece los principios
fundamentales aplicados a este proyecto:

| Principio | Aplicación concreta en el proyecto |
|---|---|
| **Consentimiento** | Los datos provienen de campañas bancarias donde el cliente fue contactado; el dataset es anónimo/histórico. Uso: investigación académica. |
| **Finalidad** | Finalidad declarada y acotada: segmentación de campañas de marketing (priorización de contactos). No se usa para otros fines. |
| **Seguridad** | TLS en tránsito (Render), credenciales en variables de entorno, API protegida por `X-API-Key`, roles diferenciados. |
| **Acceso limitado** | Solo Analista BI, Operador ETL y Desarrollador acceden; ver matriz de roles en `reports/security_audit.md`. |

### 2.2 Ley 21.719 (Reforma 2024 — enfoque GDPR)
> *[HUMANO: verificar estado de vigencia plena — estimada hacia fines de 2026 —
> y confirmar si la Agencia de Protección de Datos ya está operativa]*

La Ley 21.719 moderniza el marco chileno alineándolo con el GDPR europeo e introduce:

- **Agencia de Protección de Datos Personales** — organismo autónomo de fiscalización.
- **Derechos del titular:** acceso, rectificación, supresión ("derecho al olvido"),
  oposición y portabilidad.
- **Multas:** hasta 20.000 UTM (~CLP 1.300M) por infracción grave.
- **Evaluación de impacto** (DPIA) para tratamientos de alto riesgo.

> *[HUMANO: redactar cómo el proyecto se alinea o qué adaptaciones requeriría
> si el dataset contuviera PII real bajo 21.719]*

---

## 3. Principios aplicados al proyecto

| Principio | Medida concreta |
|---|---|
| **Minimización** | No se incluyen nombre, RUT, email ni teléfono en `bank_clean`. La columna `id` es una clave interna artificial. |
| **Seguridad técnica** | TLS automático en Render; secretos en variables de entorno (nunca en código); `.env` en `.gitignore`. |
| **Control de acceso** | API con `X-API-Key`; Metabase con credenciales propias; rol Analista BI solo con lectura de vistas. |
| **Trazabilidad** | Tabla `etl_reports` registra cada corrida del ETL. Tabla `model_scores` registra cada predicción con `raw_id` y versión del modelo. |
| **Finalidad acotada** | El modelo predice `deposit` para priorizar contactos de campaña — única finalidad declarada. |

---

## 4. Decisiones automatizadas y perfilamiento

El modelo RandomForest asigna a cada cliente una **probabilidad de suscripción**
(`prob_deposit`) y una **etiqueta de predicción** (`pred_deposit`). Esto constituye
**perfilamiento automatizado** en el sentido de la Ley 21.719:

> *"Toda forma de tratamiento automatizado de datos personales destinada a evaluar
> aspectos de la personalidad de una persona natural, en particular para analizar o
> predecir su situación económica, rendimiento, preferencias o comportamiento."*

### Implicancias:
- **Transparencia:** el cliente debería ser informado de que su historial se usa
  para segmentarlo comercialmente.
- **Derecho a no quedar sujeto a decisiones exclusivamente automatizadas:** bajo
  21.719, el titular puede oponerse a que una decisión con efectos jurídicos o
  significativos dependa solo del modelo. En este proyecto, la predicción **orienta**
  al agente de campaña, no reemplaza la decisión humana.
- **Limitación de uso:** el score no debe usarse para denegar crédito ni para
  decisiones con efectos adversos directos sin revisión humana.

> *[HUMANO: describir el flujo real de decisión: ¿el agente ve el score y decide
> contactar o no? ¿Hay revisión humana? Detallar para la defensa del indicador #9]*

---

## 5. Mayor riesgo identificado

La **`SUPABASE_SERVICE_KEY`** (`service_role`) otorga acceso total a la base de
datos sin restricción de Row Level Security. Si se filtra:

1. Un actor malicioso puede leer, modificar o eliminar toda la tabla `bank_clean`.
2. Puede insertar predicciones falsas en `model_scores`.
3. Puede eliminar registros de auditoría.

**Medida actual:** la clave se almacena como variable de entorno en Render (Secrets)
y nunca en el código fuente. **Acción si se compromete:** rotar inmediatamente desde
Supabase → Settings → API → Regenerate service_role key.

---

## 6. Conclusión

> *[HUMANO: párrafo de cierre de 4–5 líneas que sintetice la postura de seguridad
> del proyecto, qué principios de 19.628 y 21.719 se cumplen, y qué quedaría
> pendiente en un escenario de producción real con datos de clientes reales]*
