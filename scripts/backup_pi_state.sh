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
ANIME_APPDATA_ROOT="${ANIME_APPDATA_ROOT:-/srv/anime-data/appdata}"
BACKUP_DEST_ROOT="${BACKUP_DEST_ROOT:-${PROJECT_ROOT}/backups}"
STAMP="$(date +%Y%m%d-%H%M%S)"
BACKUP_NAME="${BACKUP_NAME:-rpi-anime-state-${STAMP}.tar.gz}"
DEST_PATH="${BACKUP_DEST_ROOT%/}/${BACKUP_NAME}"

mkdir -p "${BACKUP_DEST_ROOT}"

ssh "${PI_HOST}" bash -s -- "${ANIME_APPDATA_ROOT}" "${PI_REMOTE_ROOT}" > "${DEST_PATH}" <<'EOF'
set -euo pipefail

appdata_root="$1"
project_root="$2"
candidates=(
  "${appdata_root}/jellyfin"
  "${appdata_root}/qbittorrent"
  "${appdata_root}/autobangumi"
  "${appdata_root}/ops-ui"
  "${project_root}/deploy/.env"
  "${project_root}/deploy/title_mappings.toml"
)

existing=()
for path in "${candidates[@]}"; do
  if [[ -e "${path}" ]]; then
    existing+=("${path#/}")
  fi
done

if [[ "${#existing[@]}" -eq 0 ]]; then
  echo "No backup targets found on remote host." >&2
  exit 1
fi

tar --warning=no-file-changed -czf - -C / "${existing[@]}"
EOF

echo "Backup written to ${DEST_PATH}"
