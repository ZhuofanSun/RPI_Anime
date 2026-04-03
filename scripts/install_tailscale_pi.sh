#!/usr/bin/env bash

set -euo pipefail

if [[ "${EUID}" -eq 0 ]]; then
  echo "Run this script as the normal user, not root."
  exit 1
fi

echo "[1/2] Installing Tailscale using the official install script"
curl -fsSL https://tailscale.com/install.sh | sh

echo "[2/2] Enabling tailscaled"
sudo systemctl enable --now tailscaled

echo
echo "Tailscale installed."
echo "Next step:"
echo "  sudo tailscale up"
echo
echo "After login, verify with:"
echo "  tailscale ip -4"
echo "  tailscale status"
