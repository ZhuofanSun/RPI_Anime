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

ssh "${PI_HOST}" "
  cd '${PI_REMOTE_ROOT}'
  if ! docker image inspect deploy-homepage:latest >/dev/null 2>&1; then
    docker compose --env-file deploy/.env -f deploy/compose.yaml build homepage
  fi
  docker compose --env-file deploy/.env -f deploy/compose.yaml up -d --build postprocessor
  docker compose --env-file deploy/.env -f deploy/compose.yaml up -d --no-build
  docker compose --env-file deploy/.env -f deploy/compose.yaml restart homepage
"
