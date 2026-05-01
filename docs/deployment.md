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
findmnt --target /srv/anime-data
findmnt --target /srv/anime-collection
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
./scripts/install_mount_recovery_pi.sh
```

`install_mount_recovery_pi.sh` installs `rpi-anime-mount-recovery.timer`. It checks after boot and periodically while the system is running that:

- `/srv/anime-data` and `/srv/anime-collection` are mounted from the external disk, not the SD-card root filesystem
- running containers see those same external-disk bindings

If the host mount has recovered but containers are still bound to SD-card directories, the script restarts the Compose services so they rebind the correct paths. This also covers the case where the SSD disconnects during runtime and is later replugged: after USB detection and `mount /srv/anime-data` / `mount /srv/anime-collection` succeed, the next timer run repairs the container bindings. It cannot fix a physical USB detection failure; check power, cable, USB resets, and kernel logs first.

Manual checks:

```bash
sudo /usr/local/lib/rpi-anime-stack/recover_ops_stack_mounts.sh --repair
systemctl status rpi-anime-mount-recovery.timer --no-pager
journalctl -u rpi-anime-mount-recovery.service -n 80 --no-pager
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

## 6. SSD Remount Checks

If the external SSD disconnects while services are running, avoid letting containers continue writing. Recommended sequence:

```bash
cd /srv/anime-data/appdata/rpi-anime
docker compose --env-file deploy/.env -f deploy/compose.yaml stop
sudo umount /srv/anime-collection
sudo umount /srv/anime-data
sudo mount /srv/anime-data
sudo mount /srv/anime-collection
sudo /usr/local/lib/rpi-anime-stack/recover_ops_stack_mounts.sh --repair
```

If `mount` cannot find the UUID or `lsblk` / `lsusb` cannot see the SanDisk device, the failure is at the USB, power, cable, or device-detection layer and unmount/remount alone will not help. Useful checks:

```bash
vcgencmd get_throttled
journalctl -k --since "30 min ago" --no-pager | grep -Ei 'under-voltage|usb|uas|sd[a-z]|reset|disconnect|I/O error|exfat|ext4'
```
