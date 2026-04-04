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
PI_HOST_FALLBACK="${PI_HOST_FALLBACK:-}"
PI_REMOTE_ROOT="${PI_REMOTE_ROOT:-/srv/anime-data/appdata/rpi-anime}"
ACTION="${1:-status}"

run_remote() {
  local remote_cmd="$1"
  local -a ssh_cmd=(ssh)
  if [[ -t 0 && -t 1 ]]; then
    ssh_cmd+=("-t")
  fi

  if "${ssh_cmd[@]}" "${PI_HOST}" "${remote_cmd}"; then
    return 0
  fi
  if [[ -n "${PI_HOST_FALLBACK}" && "${PI_HOST_FALLBACK}" != "${PI_HOST}" ]]; then
    echo "Primary host failed, retrying via ${PI_HOST_FALLBACK}" >&2
    "${ssh_cmd[@]}" "${PI_HOST_FALLBACK}" "${remote_cmd}"
    return $?
  fi
  return 1
}

case "${ACTION}" in
  rebuild)
    run_remote "cd '${PI_REMOTE_ROOT}' && ./scripts/tailscale_rebuild_pi.sh"
    ;;
  start|stop|login|status)
    run_remote "cd '${PI_REMOTE_ROOT}' && ./scripts/tailscale_control_pi.sh '${ACTION}'"
    ;;
  *)
    echo "Usage: $0 {rebuild|start|stop|login|status}" >&2
    exit 1
    ;;
esac
