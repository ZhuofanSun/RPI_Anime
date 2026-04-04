#!/usr/bin/env bash

set -euo pipefail

SOCKET_PATH="${TAILSCALE_SOCKET:-/var/run/tailscale/tailscaled.sock}"
ACTION="${1:-status}"

api() {
  sudo curl --fail --silent --show-error \
    --unix-socket "${SOCKET_PATH}" \
    -H 'Sec-Tailscale: localapi' \
    "$@"
}

patch_want_running() {
  local want_running="$1"
  api \
    -H 'Content-Type: application/json' \
    -X PATCH \
    http://local-tailscaled.sock/localapi/v0/prefs \
    -d "{\"WantRunning\":${want_running},\"WantRunningSet\":true}" >/dev/null
}

print_status_json() {
  sudo tailscale status --json
}

case "${ACTION}" in
  start|up)
    patch_want_running true
    if ! api -H 'Content-Type: application/json' -X POST http://local-tailscaled.sock/localapi/v0/start -d '{}' >/dev/null; then
      echo "Failed to start Tailscale backend."
      echo "If the error mentions _machinekey or tailscaled.state, run:"
      echo "  ./scripts/tailscale_rebuild_pi.sh"
      exit 1
    fi
    sleep 1
    print_status_json
    echo
    echo "If BackendState is NeedsLogin, finish auth in this SSH session with:"
    echo "  sudo tailscale login"
    ;;
  stop|down)
    patch_want_running false
    sleep 1
    print_status_json
    ;;
  login)
    sudo tailscale login
    ;;
  status)
    print_status_json
    ;;
  *)
    echo "Usage: $0 {start|stop|login|status}" >&2
    exit 1
    ;;
esac
