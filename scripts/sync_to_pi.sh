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

PI_HOST="${PI_HOST:-sunzhuofan@raspberrypi.local}"
PI_REMOTE_ROOT="${PI_REMOTE_ROOT:-/srv/anime-data/appdata/rpi-anime}"
PI_REMOTE_USER="${PI_REMOTE_USER:-${PI_HOST%@*}}"
COMPOSE_CMD="docker compose --env-file deploy/.env -f deploy/compose.yaml"

RSYNC_ARGS=(
  -az
  --delete
  --exclude '.git/'
  --exclude '.venv/'
  --exclude '.superpowers/'
  --exclude '__pycache__/'
  --exclude '*.pyc'
  --exclude '.DS_Store'
  --exclude 'backups/'
  --exclude 'docs/superpowers/'
  --exclude 'docs/*_new_*.png'
  --exclude 'deploy/.env'
)

ssh "${PI_HOST}" "sudo mkdir -p '${PI_REMOTE_ROOT}' && sudo chown -R '${PI_REMOTE_USER}:${PI_REMOTE_USER}' '${PI_REMOTE_ROOT}'"

SYNC_PREVIEW="$(
  rsync "${RSYNC_ARGS[@]}" --dry-run --itemize-changes \
    "${PROJECT_ROOT}/" \
    "${PI_HOST}:${PI_REMOTE_ROOT}/"
)"

restart_homepage=false
restart_postprocessor=false
warn_rebuild=false

if grep -Eq '(^|[[:space:]])services/ops_ui/src/' <<<"${SYNC_PREVIEW}"; then
  restart_homepage=true
fi

if grep -Eq '(^|[[:space:]])services/postprocessor/src/' <<<"${SYNC_PREVIEW}"; then
  restart_postprocessor=true
fi

if grep -Eq '(^|[[:space:]])(deploy/compose\.yaml|services/ops_ui/Dockerfile|services/ops_ui/pyproject\.toml|services/postprocessor/Dockerfile|services/postprocessor/pyproject\.toml)' <<<"${SYNC_PREVIEW}"; then
  warn_rebuild=true
fi

rsync "${RSYNC_ARGS[@]}" --itemize-changes \
  "${PROJECT_ROOT}/" \
  "${PI_HOST}:${PI_REMOTE_ROOT}/"

if [[ -f "${DEPLOY_ENV}" ]]; then
  rsync -az "${DEPLOY_ENV}" "${PI_HOST}:${PI_REMOTE_ROOT}/deploy/.env"
fi

if [[ "${restart_homepage}" == true || "${restart_postprocessor}" == true ]]; then
  remote_restart_commands=()
  remote_restart_commands+=("cd '${PI_REMOTE_ROOT}'")
  if [[ "${restart_postprocessor}" == true ]]; then
    remote_restart_commands+=("${COMPOSE_CMD} restart postprocessor")
  fi
  if [[ "${restart_homepage}" == true ]]; then
    remote_restart_commands+=("${COMPOSE_CMD} restart homepage")
  fi
  ssh "${PI_HOST}" "$(printf '%s\n' "${remote_restart_commands[@]}")"
fi

echo "Synced ${PROJECT_ROOT} -> ${PI_HOST}:${PI_REMOTE_ROOT}"

if [[ "${restart_postprocessor}" == true ]]; then
  echo "Restarted remote postprocessor to load synced source changes."
fi

if [[ "${restart_homepage}" == true ]]; then
  echo "Restarted remote homepage to load synced source changes."
fi

if [[ "${warn_rebuild}" == true ]]; then
  echo "Detected compose/image/dependency changes. Run ./scripts/remote_up.sh to rebuild services."
fi
