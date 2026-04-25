# Deployment Notes

[简体中文](./deployment.zh-Hans.md)

These notes keep the operational details out of the main README while preserving the current Raspberry Pi workflow.

## 1. Prepare the Raspberry Pi

Use a Raspberry Pi running 64-bit Raspberry Pi OS and prepare these mount points:

- `/srv/anime-data`
- `/srv/anime-collection`

Storage notes:

- These paths should resolve to the intended external volumes, not empty directories on the root filesystem.
- `./scripts/sync_to_pi.sh` refuses to sync if either mount target is configured in `/etc/fstab` but has fallen back to `/`, which protects the SD card from accidental writes.
- Useful checks on the Pi:

```bash
lsblk -o NAME,MODEL,SIZE,FSTYPE,MOUNTPOINTS,LABEL,UUID
findmnt /srv/anime-data /srv/anime-collection
df -h /srv/anime-data /srv/anime-collection
```

- If a SanDisk `Extreme 55AE` repeatedly drops off the Pi under UAS, add `usb-storage.quirks=0781:55ae:u` to `/boot/firmware/cmdline.txt` and reboot.

Then bootstrap Docker and the default runtime directories:

```bash
./scripts/bootstrap_pi.sh
```

Optional host-side setup:

```bash
./scripts/install_tailscale_pi.sh
./scripts/install_fan_control_pi.sh
```

## 2. Create local deployment config

Create `deploy/.env` locally and fill in at least:

- `PI_HOST`
- `PI_REMOTE_USER`
- `PI_REMOTE_ROOT`
- `TZ`
- `JELLYFIN_PLAYBACK_USER_ID`
- `JELLYFIN_PLAYBACK_ACCESS_TOKEN`
- `QBITTORRENT_USERNAME`
- `QBITTORRENT_PASSWORD`
- `AUTOBANGUMI_USERNAME`
- `AUTOBANGUMI_PASSWORD`

For this project, the stable Jellyfin setup is:

- keep a single Jellyfin user for your own devices and watch-state truth
- give `ops_ui` a dedicated long-lived token for that same user via `JELLYFIN_PLAYBACK_USER_ID` and `JELLYFIN_PLAYBACK_ACCESS_TOKEN`
- avoid relying on `Users/AuthenticateByName` for every playback bootstrap, because a broken password-auth path in Jellyfin can take mobile playback down even when token auth still works

## 3. Sync the repository to the Pi

```bash
./scripts/sync_to_pi.sh
```

This copies the main repo to `${PI_REMOTE_ROOT}`, syncs `deploy/.env` separately, and does **not** sync `RPI_Anime_APP/`.

Current sync semantics:

- if `services/ops_ui/src/` changes, the script restarts `homepage`
- if `services/postprocessor/src/` changes, the script rebuilds and relaunches `postprocessor`
- if `deploy/compose.yaml`, service build inputs, or `deploy/.env` change, the script reconciles the remote compose stack
- if `${PI_REMOTE_ROOT}/RPI_Anime_APP` already exists on the Pi, the script refuses to continue so the APP repo does not get mixed into the backend deploy tree

## 4. Build and start services

```bash
./scripts/remote_up.sh
```

This still provides an explicit full-stack rebuild path when you want to force the entire compose stack to refresh.

## 5. Verify the deployment

Typical checks:

```bash
curl http://<ops-host>:3000/healthz
curl http://<ops-host>:3000/api/overview
```

For later updates, start with:

```bash
./scripts/sync_to_pi.sh
```

Use `./scripts/remote_up.sh` when you explicitly want a full-stack rebuild.
