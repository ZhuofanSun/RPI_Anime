#!/usr/bin/env bash

set -euo pipefail

if [[ "${EUID}" -eq 0 ]]; then
  echo "Run this script as the normal user, not root."
  exit 1
fi

USERNAME="$(id -un)"
USERGROUP="$(id -gn)"

echo "[1/6] Installing Docker repository prerequisites"
sudo apt-get update
sudo apt-get install -y ca-certificates curl
sudo install -m 0755 -d /etc/apt/keyrings
sudo curl -fsSL https://download.docker.com/linux/debian/gpg -o /etc/apt/keyrings/docker.asc
sudo chmod a+r /etc/apt/keyrings/docker.asc

echo "[2/6] Configuring Docker apt repository"
sudo tee /etc/apt/sources.list.d/docker.sources >/dev/null <<EOF
Types: deb
URIs: https://download.docker.com/linux/debian
Suites: $(. /etc/os-release && echo "$VERSION_CODENAME")
Components: stable
Signed-By: /etc/apt/keyrings/docker.asc
EOF

echo "[3/6] Installing Docker Engine and Compose plugin"
sudo apt-get update
sudo apt-get install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin

echo "[4/6] Enabling Docker service"
sudo systemctl enable --now docker

echo "[5/6] Preparing runtime directories"
sudo mkdir -p /srv/anime-data/appdata
sudo mkdir -p /srv/anime-data/appdata/jellyfin/config
sudo mkdir -p /srv/anime-data/appdata/jellyfin/cache
sudo mkdir -p /srv/anime-data/appdata/jellyfin/fonts
sudo mkdir -p /srv/anime-data/appdata/ops-ui
sudo mkdir -p /srv/anime-data/appdata/qbittorrent/config
sudo mkdir -p /srv/anime-data/appdata/autobangumi/config
sudo mkdir -p /srv/anime-data/appdata/autobangumi/data
sudo mkdir -p /srv/anime-data/appdata/rpi-anime
sudo mkdir -p /srv/anime-data/downloads
sudo mkdir -p /srv/anime-data/library/seasonal
sudo mkdir -p /srv/anime-data/processing/incoming
sudo mkdir -p /srv/anime-data/processing/working
sudo mkdir -p /srv/anime-data/processing/failed
sudo mkdir -p /srv/anime-data/processing/manual_review
sudo mkdir -p /srv/anime-data/cache
sudo chown -R "${USERNAME}:${USERGROUP}" /srv/anime-data/appdata
sudo chown -R "${USERNAME}:${USERGROUP}" /srv/anime-data/downloads
sudo chown -R "${USERNAME}:${USERGROUP}" /srv/anime-data/library
sudo chown -R "${USERNAME}:${USERGROUP}" /srv/anime-data/processing
sudo chown -R "${USERNAME}:${USERGROUP}" /srv/anime-data/cache

echo "[6/6] Granting docker group access to ${USERNAME}"
sudo usermod -aG docker "${USERNAME}"

echo
echo "Bootstrap complete."
echo "Open a new login session before using docker without sudo."
echo "Verification commands:"
echo "  docker --version"
echo "  docker compose version"
echo "  docker run hello-world"
