#!/usr/bin/env bash

set -euo pipefail

if [[ "${EUID}" -eq 0 ]]; then
  echo "Run this script as the normal user, not root."
  exit 1
fi

PROJECT_ROOT="/srv/anime-data/appdata/rpi-anime"
INSTALL_ROOT="/usr/local/lib/rpi-anime-stack"
SCRIPT_NAME="recover_ops_stack_mounts.sh"
SERVICE_NAME="rpi-anime-mount-recovery.service"
TIMER_NAME="rpi-anime-mount-recovery.timer"

echo "[1/3] Installing mount recovery script"
sudo install -d -m 0755 "${INSTALL_ROOT}"
sudo install -m 0755 "${PROJECT_ROOT}/scripts/${SCRIPT_NAME}" "${INSTALL_ROOT}/${SCRIPT_NAME}"

echo "[2/3] Installing systemd units"
sudo cp "${PROJECT_ROOT}/deploy/systemd/${SERVICE_NAME}" "/etc/systemd/system/${SERVICE_NAME}"
sudo cp "${PROJECT_ROOT}/deploy/systemd/${TIMER_NAME}" "/etc/systemd/system/${TIMER_NAME}"
sudo systemctl daemon-reload
sudo systemctl reset-failed "${SERVICE_NAME}" "${TIMER_NAME}" || true

echo "[3/3] Enabling periodic recovery"
sudo systemctl enable --now "${TIMER_NAME}"
sudo systemctl start "${SERVICE_NAME}"

echo
echo "Mount recovery installed."
echo "Verification commands:"
echo "  systemctl status ${TIMER_NAME} --no-pager"
echo "  systemctl status ${SERVICE_NAME} --no-pager"
echo "  journalctl -u ${SERVICE_NAME} -n 80 --no-pager"
