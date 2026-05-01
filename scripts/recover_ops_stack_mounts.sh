#!/usr/bin/env bash

set -euo pipefail

PROJECT_ROOT="${RPI_ANIME_PROJECT_ROOT:-/srv/anime-data/appdata/rpi-anime}"
ANIME_DATA_ROOT="${RPI_ANIME_DATA_ROOT:-/srv/anime-data}"
ANIME_COLLECTION_ROOT="${RPI_ANIME_COLLECTION_ROOT:-/srv/anime-collection}"
WAIT_SECONDS=180
POLL_SECONDS=5
REPAIR=false

COMPOSE_SERVICES=(homepage jellyfin qbittorrent autobangumi glances postprocessor)
CONTAINER_CHECKS=(
  "homepage:/srv/anime-data:data"
  "homepage:/srv/anime-collection:collection"
  "jellyfin:/config:data"
  "jellyfin:/media/seasonal:data"
  "jellyfin:/media/collection:collection"
  "qbittorrent:/config:data"
  "qbittorrent:/downloads:data"
  "qbittorrent:/library/seasonal:data"
  "autobangumi:/app/data:data"
  "autobangumi:/downloads:data"
  "autobangumi:/library/seasonal:data"
  "anime-postprocessor:/srv/anime-data:data"
  "anime-postprocessor:/srv/anime-collection:collection"
)

usage() {
  cat <<EOF
Usage: $(basename "$0") [--repair] [--wait-seconds N] [--poll-seconds N] [--project-root PATH]

Checks that the RPI Anime storage roots are mounted from the external disk and
that running containers see those external-disk bindings. With --repair, the
script attempts fstab mounts and restarts the Compose services when container
bindings still point at the root filesystem.
EOF
}

log() {
  printf '[rpi-anime-mount-recovery] %s\n' "$*"
}

while [[ "$#" -gt 0 ]]; do
  case "$1" in
    --repair)
      REPAIR=true
      shift
      ;;
    --wait-seconds)
      WAIT_SECONDS="$2"
      shift 2
      ;;
    --poll-seconds)
      POLL_SECONDS="$2"
      shift 2
      ;;
    --project-root)
      PROJECT_ROOT="$2"
      shift 2
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      usage >&2
      exit 2
      ;;
  esac
done

LOCK_FILE="${RPI_ANIME_RECOVERY_LOCK_FILE:-/run/rpi-anime-mount-recovery.lock}"
if [[ ! -w "$(dirname "${LOCK_FILE}")" ]]; then
  LOCK_FILE="/tmp/rpi-anime-mount-recovery.${UID}.lock"
fi
exec 9>"${LOCK_FILE}"
if ! flock -n 9; then
  log "Another recovery check is already running; exiting."
  exit 0
fi

load_deploy_env() {
  local env_file="${PROJECT_ROOT}/deploy/.env"
  if [[ -f "${env_file}" ]]; then
    set -a
    # shellcheck disable=SC1090
    source "${env_file}"
    set +a
    ANIME_DATA_ROOT="${RPI_ANIME_DATA_ROOT:-${ANIME_DATA_ROOT:-/srv/anime-data}}"
    ANIME_COLLECTION_ROOT="${RPI_ANIME_COLLECTION_ROOT:-${ANIME_COLLECTION_ROOT:-/srv/anime-collection}}"
  fi
}

root_source() {
  findmnt -n -o SOURCE --target / 2>/dev/null || true
}

mount_source() {
  local target="$1"
  findmnt -n -o SOURCE --target "${target}" 2>/dev/null || true
}

is_external_mount() {
  local target="$1"
  local root
  local live

  root="$(root_source)"
  live="$(mount_source "${target}")"
  [[ -n "${live}" ]] || return 1
  mountpoint -q "${target}" || return 1
  [[ "${live}" != "${root}" ]]
}

attempt_mount() {
  local target="$1"
  if [[ "${REPAIR}" != true ]]; then
    return 0
  fi
  if [[ "${EUID}" -ne 0 ]]; then
    log "Cannot mount ${target}: --repair needs root."
    return 0
  fi
  mount "${target}" >/dev/null 2>&1 || true
}

wait_for_external_mount() {
  local target="$1"
  local deadline=$((SECONDS + WAIT_SECONDS))

  while (( SECONDS <= deadline )); do
    if is_external_mount "${target}"; then
      log "${target} is mounted from $(mount_source "${target}")."
      return 0
    fi
    attempt_mount "${target}"
    if is_external_mount "${target}"; then
      log "${target} is mounted from $(mount_source "${target}")."
      return 0
    fi
    sleep "${POLL_SECONDS}"
  done

  log "${target} is not mounted from an external disk after ${WAIT_SECONDS}s."
  return 10
}

container_is_running() {
  local container="$1"
  [[ "$(docker inspect --format '{{.State.Running}}' "${container}" 2>/dev/null || true)" == "true" ]]
}

container_path_source() {
  local container="$1"
  local path="$2"

  docker exec "${container}" sh -lc "df -P '${path}' 2>/dev/null | awk 'NR==2 { print \$1 }'" 2>/dev/null || true
}

container_bindings_need_restart() {
  local data_source="$1"
  local collection_source="$2"
  local needs_restart=false
  local any_container=false
  local item

  for item in "${CONTAINER_CHECKS[@]}"; do
    IFS=: read -r container path expected_root <<<"${item}"
    if ! container_is_running "${container}"; then
      continue
    fi
    any_container=true

    local expected_source="${data_source}"
    if [[ "${expected_root}" == "collection" ]]; then
      expected_source="${collection_source}"
    fi

    local live_source
    live_source="$(container_path_source "${container}" "${path}")"
    if [[ "${live_source}" != "${expected_source}" ]]; then
      log "${container}:${path} sees ${live_source:-<missing>} but host expects ${expected_source}."
      needs_restart=true
    fi
  done

  if [[ "${any_container}" != true ]]; then
    log "No target containers are running; Compose will be brought up after mount checks."
    return 0
  fi

  [[ "${needs_restart}" == true ]]
}

compose_cmd() {
  docker compose --env-file deploy/.env -f deploy/compose.yaml "$@"
}

main() {
  load_deploy_env
  wait_for_external_mount "${ANIME_DATA_ROOT}"
  load_deploy_env
  wait_for_external_mount "${ANIME_COLLECTION_ROOT}"

  local data_source
  local collection_source
  data_source="$(mount_source "${ANIME_DATA_ROOT}")"
  collection_source="$(mount_source "${ANIME_COLLECTION_ROOT}")"

  if [[ ! -f "${PROJECT_ROOT}/deploy/compose.yaml" ]]; then
    log "Compose file is missing at ${PROJECT_ROOT}/deploy/compose.yaml."
    return 11
  fi

  cd "${PROJECT_ROOT}"

  if ! docker info >/dev/null 2>&1; then
    log "Docker is not available."
    return 12
  fi

  if ! docker compose --env-file deploy/.env -f deploy/compose.yaml ps -q >/dev/null 2>&1; then
    log "Compose project is not readable."
    return 13
  fi

  if [[ -z "$(docker compose --env-file deploy/.env -f deploy/compose.yaml ps -q 2>/dev/null)" ]]; then
    if [[ "${REPAIR}" == true ]]; then
      log "Starting Compose services after storage mounts became available."
      compose_cmd up -d --no-build "${COMPOSE_SERVICES[@]}"
    else
      log "Compose services are not running."
      return 14
    fi
  elif container_bindings_need_restart "${data_source}" "${collection_source}"; then
    if [[ "${REPAIR}" == true ]]; then
      log "Restarting Compose services to rebind external storage."
      docker compose --env-file deploy/.env -f deploy/compose.yaml restart "${COMPOSE_SERVICES[@]}"
    else
      log "Container storage bindings need repair."
      return 15
    fi
  else
    log "Container storage bindings already match host mounts."
  fi
}

main "$@"
