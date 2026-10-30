#!/usr/bin/env bash
# Falla si aparece algo con forma de credencial en archivos versionados.
# Complementa a gitleaks en CI; corre también local en scripts/check.sh.
set -euo pipefail
cd "$(dirname "$0")/.."
patterns='AIza[0-9A-Za-z_-]{35}|1//0[0-9A-Za-z_-]{30,}|GOCSPX-[0-9A-Za-z_-]{20,}|ya29\.[0-9A-Za-z_-]{20,}'
if git ls-files -z | xargs -0 grep -nEI "$patterns" -- 2>/dev/null; then
  echo "check_secrets: posible credencial en el repo (arriba)." >&2
  exit 1
fi
echo "check_secrets: ok"
