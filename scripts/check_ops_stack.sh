#!/usr/bin/env bash

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
DEPLOY_ENV="${DEPLOY_ENV:-${PROJECT_ROOT}/deploy/.env}"

if [[ -f "${DEPLOY_ENV}" ]]; then
  set -a
  # shellcheck disable=SC1090
  source "${DEPLOY_ENV}"
  set +a
fi

OPS_HOST="${OPS_HOST:-${HOMEPAGE_BASE_HOST:-sunzhuofan.local}}"
OPS_PORT="${OPS_PORT:-${HOMEPAGE_PORT:-3000}}"
OPS_BASE_URL="${OPS_BASE_URL:-http://${OPS_HOST}:${OPS_PORT}}"

health_json="$(curl -fsS "${OPS_BASE_URL}/healthz")"
overview_json="$(curl -fsS "${OPS_BASE_URL}/api/overview")"

python3 - "${health_json}" "${overview_json}" <<'EOF'
import json
import sys

health = json.loads(sys.argv[1])
overview = json.loads(sys.argv[2])

if health.get("ok") is not True:
    raise SystemExit("healthz did not return ok=true")

diagnostics = overview.get("diagnostics") or []
if diagnostics:
    raise SystemExit(f"overview diagnostics are not empty: {len(diagnostics)}")

days = ((overview.get("weekly_schedule") or {}).get("days") or [])
if len(days) != 7:
    raise SystemExit(f"weekly_schedule.days expected 7, got {len(days)}")

print("OK: healthz and overview diagnostics passed")
EOF
