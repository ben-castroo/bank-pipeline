#!/usr/bin/env bash
# Fase 4.1 — Escaneo de secretos en archivos versionados
# Uso: bash scripts/audit_secrets.sh  (desde la raíz del repo)
# Resultado: imprime hallazgos; redirigir a reports/security_audit.md si se desea.

set -euo pipefail

echo "========================================"
echo " AUDITORÍA DE SECRETOS — bank-pipeline"
echo "========================================"
echo ""

echo "== 1. Secretos en archivos versionados =="
git ls-files | xargs grep -nEi \
  "(service_role|supabase.*(key|url)|api[_-]?key|secret|passw)" 2>/dev/null \
  | grep -v -E "(\.md:|\.md\.example|example|placeholder|os\.environ|getenv|#|\.env\.example)" \
  || echo "  [OK] Sin secretos reales detectados."

echo ""
echo "== 2. ¿.env está ignorado por git? =="
if grep -qE "(^|/)\.env" .gitignore; then
  echo "  [OK] .env figura en .gitignore"
else
  echo "  [CRITICO] .env NO está en .gitignore — agregar inmediatamente"
fi

echo ""
echo "== 3. ¿Archivos .env están sin versionar? =="
if git ls-files --error-unmatch model_api/.env 2>/dev/null; then
  echo "  [CRITICO] model_api/.env está versionado — eliminar con git rm --cached"
else
  echo "  [OK] model_api/.env no está en el repositorio"
fi

echo ""
echo "== 4. Archivos con potencial de secreto (revisar manualmente) =="
git ls-files | grep -E "\.(env|cfg|ini|json|yaml|yml)$" \
  | grep -v -E "(example|template|docker-compose|render\.yaml|model_card)" \
  || echo "  (ninguno)"

echo ""
echo "Auditoría completada."
