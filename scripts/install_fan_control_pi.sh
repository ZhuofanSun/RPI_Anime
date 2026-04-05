#!/usr/bin/env bash

set -euo pipefail

if [[ "${EUID}" -eq 0 ]]; then
  echo "Run this script as the normal user, not root."
  exit 1
fi

PROJECT_ROOT="/srv/anime-data/appdata/rpi-anime"
INSTALL_ROOT="/usr/local/lib/rpi-anime-fan"
SERVICE_NAME="anime-fan-control.service"
SERVICE_SOURCE="${PROJECT_ROOT}/deploy/systemd/${SERVICE_NAME}"
SERVICE_TARGET="/etc/systemd/system/${SERVICE_NAME}"
SCRIPT_SOURCE="${PROJECT_ROOT}/scripts/fan_control.py"
CONFIG_SOURCE="${PROJECT_ROOT}/deploy/fan_control.toml"

echo "[1/4] Installing fan control runtime dependencies"
sudo apt-get update
sudo apt-get install -y pigpio-tools python3-pigpio

echo "[2/4] Enabling pigpio daemon"
sudo systemctl enable --now pigpiod

echo "[3/4] Installing fan control files"
sudo install -d -m 0755 "${INSTALL_ROOT}"
sudo install -m 0755 "${SCRIPT_SOURCE}" "${INSTALL_ROOT}/fan_control.py"
sudo install -m 0644 "${CONFIG_SOURCE}" "${INSTALL_ROOT}/fan_control.toml"

echo "[4/4] Installing and enabling systemd unit"
sudo cp "${SERVICE_SOURCE}" "${SERVICE_TARGET}"
sudo systemctl daemon-reload
sudo systemctl reset-failed "${SERVICE_NAME}" || true
sudo systemctl enable --now "${SERVICE_NAME}"

echo
echo "Fan control installed."
echo "Verification commands:"
echo "  systemctl status ${SERVICE_NAME} --no-pager"
echo "  journalctl -u ${SERVICE_NAME} -f"
