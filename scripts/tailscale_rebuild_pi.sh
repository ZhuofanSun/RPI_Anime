#!/usr/bin/env bash

set -euo pipefail

if [[ "${EUID}" -eq 0 ]]; then
  echo "Run this script as the normal user, not root."
  exit 1
fi

TS_DIR="/var/lib/tailscale"
STAMP="$(date +%Y%m%d-%H%M%S)"
BACKUP_DIR="/var/lib/tailscale-backup-${STAMP}"

echo "[1/5] Stopping tailscaled"
sudo systemctl stop tailscaled

echo "[2/5] Backing up ${TS_DIR} -> ${BACKUP_DIR}"
sudo mkdir -p "${BACKUP_DIR}"
if [[ -d "${TS_DIR}" ]]; then
  sudo cp -a "${TS_DIR}"/. "${BACKUP_DIR}"/ 2>/dev/null || true
  sudo rm -rf "${TS_DIR}"
fi

echo "[3/5] Recreating fresh ${TS_DIR}"
sudo install -d -m 700 -o root -g root "${TS_DIR}"

echo "[4/5] Starting tailscaled"
sudo systemctl start tailscaled
sleep 2
sudo systemctl is-active tailscaled

echo "[5/5] Current Tailscale status"
sudo tailscale status --json

echo
echo "Rebuild finished."
echo "Backup kept at:"
echo "  ${BACKUP_DIR}"
echo
echo "Next step:"
echo "  ./scripts/tailscale_control_pi.sh start"
echo
echo "If status becomes NeedsLogin, finish auth with:"
echo "  sudo tailscale login"
