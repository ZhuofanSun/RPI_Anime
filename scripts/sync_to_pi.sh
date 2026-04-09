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

ssh "${PI_HOST}" "sudo mkdir -p '${PI_REMOTE_ROOT}' && sudo chown -R '${PI_REMOTE_USER}:${PI_REMOTE_USER}' '${PI_REMOTE_ROOT}'"

rsync -az --delete \
  --exclude '.git/' \
  --exclude '.venv/' \
  --exclude '.superpowers/' \
  --exclude '__pycache__/' \
  --exclude '*.pyc' \
  --exclude '.DS_Store' \
  --exclude 'backups/' \
  --exclude 'docs/superpowers/' \
  --exclude 'docs/*_new_*.png' \
  --exclude 'deploy/.env' \
  "${PROJECT_ROOT}/" \
  "${PI_HOST}:${PI_REMOTE_ROOT}/"

if [[ -f "${DEPLOY_ENV}" ]]; then
  rsync -az "${DEPLOY_ENV}" "${PI_HOST}:${PI_REMOTE_ROOT}/deploy/.env"
fi

echo "Synced ${PROJECT_ROOT} -> ${PI_HOST}:${PI_REMOTE_ROOT}"
