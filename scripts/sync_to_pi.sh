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
ANIME_DATA_ROOT="${ANIME_DATA_ROOT:-/srv/anime-data}"
ANIME_COLLECTION_ROOT="${ANIME_COLLECTION_ROOT:-/srv/anime-collection}"
COMPOSE_CMD="docker compose --env-file deploy/.env -f deploy/compose.yaml"

RSYNC_ARGS=(
  -az
  --delete
  --exclude '.git/'
  --exclude '.venv/'
  --exclude '.superpowers/'
  --exclude '.worktrees/'
  --exclude 'RPI_Anime_APP/'
  --exclude 'tmp/'
  --exclude '.pytest_cache/'
  --exclude '__pycache__/'
  --exclude '*.pyc'
  --exclude '.DS_Store'
  --exclude 'backups/'
  --exclude 'docs/superpowers/'
  --exclude 'docs/*_new_*.png'
  --exclude 'deploy/.env'
)

if ! remote_mount_guard_output="$(
  ssh "${PI_HOST}" "bash -s -- '${ANIME_DATA_ROOT}' '${ANIME_COLLECTION_ROOT}'" <<'EOF'
set -euo pipefail

root_source="$(findmnt -n -o SOURCE --target / 2>/dev/null || true)"

check_target() {
  local target="$1"
  local fstab_source=""
  local live_source=""
  fstab_source="$(findmnt -s -n -o SOURCE --target "$target" 2>/dev/null || true)"
  if [[ -z "${fstab_source}" ]]; then
    return 0
  fi
  live_source="$(findmnt -n -o SOURCE --target "$target" 2>/dev/null || true)"
  if [[ -z "${live_source}" || "${live_source}" == "${root_source}" ]]; then
    echo "Refusing to sync because ${target} mount has fallen back to the root filesystem. Expected ${fstab_source}, saw ${live_source:-<unmounted>}."
    exit 12
  fi
}

check_target "$1"
check_target "$2"
EOF
)"; then
  echo "${remote_mount_guard_output}" >&2
  exit 1
fi

ssh "${PI_HOST}" "sudo mkdir -p '${PI_REMOTE_ROOT}' && sudo chown -R '${PI_REMOTE_USER}:${PI_REMOTE_USER}' '${PI_REMOTE_ROOT}'"

if ! remote_app_repo_guard_output="$(
  ssh "${PI_HOST}" "bash -s -- '${PI_REMOTE_ROOT}'" <<'EOF'
set -euo pipefail

if [[ -e "$1/RPI_Anime_APP" ]]; then
  echo "Refusing to sync because $1/RPI_Anime_APP already exists on the Raspberry Pi. The APP repository must stay outside the backend deploy tree."
  exit 13
fi
EOF
)"; then
  echo "${remote_app_repo_guard_output}" >&2
  exit 1
fi

SYNC_PREVIEW="$(
  rsync "${RSYNC_ARGS[@]}" --dry-run --itemize-changes \
    "${PROJECT_ROOT}/" \
    "${PI_HOST}:${PI_REMOTE_ROOT}/"
)"

restart_homepage=false
build_homepage=false
build_postprocessor=false
reconcile_stack=false
deploy_env_changed=false

if grep -Eq '(^|[[:space:]])services/ops_ui/src/' <<<"${SYNC_PREVIEW}"; then
  restart_homepage=true
fi

if grep -Eq '(^|[[:space:]])services/ops_ui/(Dockerfile|pyproject\.toml)' <<<"${SYNC_PREVIEW}"; then
  build_homepage=true
fi

if grep -Eq '(^|[[:space:]])services/postprocessor/src/' <<<"${SYNC_PREVIEW}"; then
  build_postprocessor=true
fi

if grep -Eq '(^|[[:space:]])services/postprocessor/(Dockerfile|pyproject\.toml)' <<<"${SYNC_PREVIEW}"; then
  build_postprocessor=true
fi

if grep -Eq '(^|[[:space:]])deploy/compose\.yaml' <<<"${SYNC_PREVIEW}"; then
  reconcile_stack=true
fi

if [[ -f "${DEPLOY_ENV}" ]]; then
  DEPLOY_ENV_SYNC_PREVIEW="$(
    rsync -az --dry-run --itemize-changes \
      "${DEPLOY_ENV}" \
      "${PI_HOST}:${PI_REMOTE_ROOT}/deploy/.env"
  )"
  if [[ -n "${DEPLOY_ENV_SYNC_PREVIEW}" ]]; then
    deploy_env_changed=true
    reconcile_stack=true
  fi
fi

rsync "${RSYNC_ARGS[@]}" --itemize-changes \
  "${PROJECT_ROOT}/" \
  "${PI_HOST}:${PI_REMOTE_ROOT}/"

if [[ -f "${DEPLOY_ENV}" ]]; then
  rsync -az "${DEPLOY_ENV}" "${PI_HOST}:${PI_REMOTE_ROOT}/deploy/.env"
fi

remote_runtime_commands=()
remote_runtime_commands+=("set -euo pipefail")
remote_runtime_commands+=("cd '${PI_REMOTE_ROOT}'")

changed_services=()

if [[ "${build_homepage}" == true ]]; then
  remote_runtime_commands+=("${COMPOSE_CMD} build homepage")
  changed_services+=("homepage")
fi

if [[ "${build_postprocessor}" == true ]]; then
  remote_runtime_commands+=("${COMPOSE_CMD} build postprocessor")
  changed_services+=("postprocessor")
fi

if [[ "${reconcile_stack}" == true ]]; then
  remote_runtime_commands+=("${COMPOSE_CMD} up -d --no-build")
elif [[ "${#changed_services[@]}" -gt 0 ]]; then
  remote_runtime_commands+=("${COMPOSE_CMD} up -d --no-build ${changed_services[*]}")
fi

if [[ "${restart_homepage}" == true && "${build_homepage}" == false ]]; then
  remote_runtime_commands+=("${COMPOSE_CMD} restart homepage")
fi

if [[ "${#remote_runtime_commands[@]}" -gt 2 ]]; then
  ssh "${PI_HOST}" "$(printf '%s\n' "${remote_runtime_commands[@]}")"
fi

echo "Synced ${PROJECT_ROOT} -> ${PI_HOST}:${PI_REMOTE_ROOT}"

if [[ "${build_postprocessor}" == true ]]; then
  echo "Rebuilt and relaunched remote postprocessor because its runtime comes from the image, not a source bind mount."
fi

if [[ "${build_homepage}" == true ]]; then
  echo "Rebuilt and relaunched remote homepage because its image inputs changed."
elif [[ "${restart_homepage}" == true ]]; then
  echo "Restarted remote homepage to load synced source changes."
fi

if [[ "${reconcile_stack}" == true ]]; then
  echo "Reconciled the remote compose stack because runtime config changed."
fi

if [[ "${deploy_env_changed}" == true ]]; then
  echo "Applied updated deploy/.env on the Raspberry Pi."
fi
