#!/usr/bin/env bash
# Fase 5.2 — Mide latencia y cold start del servicio en Render.
#
# Uso:
#   export RENDER_URL=https://tu-servicio.onrender.com
#   export MODEL_API_KEY=tu-api-key
#   bash scripts/measure_cloud.sh | tee reports/perf_cloud_raw.txt
#
# Requiere: curl, jq (opcional para pretty-print)

set -euo pipefail

: "${RENDER_URL:?ERROR: define RENDER_URL antes de ejecutar}"
: "${MODEL_API_KEY:?ERROR: define MODEL_API_KEY antes de ejecutar}"

OUT_JSON="reports/perf_cloud.json"
HEALTH_URL="$RENDER_URL/health"
PREDICT_URL="$RENDER_URL/predict"

echo "================================================"
echo " BENCHMARK CLOUD — $RENDER_URL"
echo "================================================"
echo ""

# --- Cold start (primer request tras periodo de inactividad) ---
echo "== Cold start (esperar inactividad del servicio antes de ejecutar) =="
COLD=$(curl -o /dev/null -s -w "%{time_total}" "$HEALTH_URL")
echo "  cold: ${COLD}s"

# --- Warm requests (latencia estable) ---
echo ""
echo "== Warm requests — /health =="
WARM_TIMES=()
for i in 1 2 3 4 5; do
  T=$(curl -o /dev/null -s -w "%{time_total}" "$HEALTH_URL")
  echo "  warm[$i]: ${T}s"
  WARM_TIMES+=("$T")
done

# --- Predicción real con autenticación ---
echo ""
echo "== Latencia de predicción — POST /predict =="
PRED=$(curl -o /dev/null -s -w "%{time_total}" \
  -H "X-API-Key: $MODEL_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"raw_id": 1}' \
  "$PREDICT_URL")
echo "  predict: ${PRED}s"

# --- Calcular media de warm ---
WARM_SUM=0
for t in "${WARM_TIMES[@]}"; do
  WARM_SUM=$(echo "$WARM_SUM + $t" | bc)
done
WARM_MEAN=$(echo "scale=4; $WARM_SUM / ${#WARM_TIMES[@]}" | bc)

echo ""
echo "================================================"
echo " RESUMEN"
echo "================================================"
echo "  cold_start_s : $COLD"
echo "  warm_mean_s  : $WARM_MEAN"
echo "  predict_s    : $PRED"

# --- Guardar JSON ---
cat > "$OUT_JSON" <<EOF
{
  "render_url": "$RENDER_URL",
  "cold_start_s": $COLD,
  "warm_health_s": {
    "values": [$(IFS=,; echo "${WARM_TIMES[*]}")],
    "mean_s": $WARM_MEAN
  },
  "predict_s": $PRED,
  "notes": "cold_start medido con el servicio inactivo; warm tras 5 requests a /health"
}
EOF

echo ""
echo "Guardado: $OUT_JSON"
