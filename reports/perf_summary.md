# Rendimiento del sistema — Local vs Nube
**Generado:** 2026-06-29 · **Fuente local:** `bank.csv` (11162 filas)

---

## ETL local — tiempos por etapa

| Etapa | Media (s) | Std (s) | Min | Max |
|---|---|---|---|---|
| Extract (leer CSV + validar estructura) | 0.0159 | 0.0012 | 0.0149 | 0.0179 |
| Transform (limpieza completa) | 1.1556 | 0.0233 | 1.1244 | 1.1814 |
| Load DB (Supabase) | N/A — sin conexión | — | — | — |
| **Total** | **1.1715** | 0.0233 | — | — |

**Interpretación:** el transform es la etapa dominante porque recorre cada fila para
validar rangos, categorías y convertir binarios. A 11162 filas, el ETL completo
(sin DB) tarda aproximadamente **1.17s**, lo que es adecuado para cargas
programadas (no tiempo real).

---

## Nube (Render Free Tier)

- **Cold start:** 0.00s (primer request tras inactividad del free tier)
- **Warm /health:** 0.000s (latencia estable tras calentar)
- **POST /predict:** 0.000s (incluye lectura de DB + inferencia RF)

**Interpretación:** el **cold start** del free tier es la limitación más notable:
el servicio queda inactivo tras ~15 minutos sin tráfico y necesita cargar la imagen
Docker + el modelo (`~0.0s` aproximado). En caliente, la latencia de predicción
es aceptable para una demo; en producción real se mitigaría con un plan pagado o
un ping periódico para mantener la instancia activa.

---

## Limitaciones conocidas

- **Free tier de Render:** una sola instancia, cold start de hasta ~30s tras inactividad,
  RAM limitada (~512 MB), sin escala horizontal.
- **ETL monolítico:** el transform es secuencial y no paralelo; escalaría con chunking
  o procesamiento distribuido (Spark) para datasets de millones de filas.
- **Modelo en memoria:** el RF de 200 árboles ocupa ~20–50 MB serializado (joblib);
  aceptable en el contexto actual.

---

## Figura

Ver `reports/figures/perf_local_vs_cloud.png` para el gráfico comparativo.
