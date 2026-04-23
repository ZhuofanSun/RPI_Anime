from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[3]


def _read_text(relative_path: str) -> str:
    return (REPO_ROOT / relative_path).read_text(encoding="utf-8")


def test_readmes_link_core_services_to_official_github_repositories():
    expected_links = {
        "AutoBangumi": "https://github.com/EstrellaXD/Auto_Bangumi",
        "qBittorrent": "https://github.com/qbittorrent/qBittorrent",
        "Jellyfin": "https://github.com/jellyfin/jellyfin",
        "Tailscale": "https://github.com/tailscale/tailscale",
    }
    expected_snapshots = {
        "README.md": ["./docs/dash1_new_en.png", "./docs/dash2_new_en.png"],
        "README.zh-Hans.md": ["./docs/dash1_new_zh.png", "./docs/dash2_new_zh.png"],
    }

    for relative_path in ["README.md", "README.zh-Hans.md"]:
        text = _read_text(relative_path)
        for label, url in expected_links.items():
            assert f"[{label}]({url})" in text
        for snapshot_path in expected_snapshots[relative_path]:
            assert snapshot_path in text


def test_compose_pins_external_service_images_instead_of_latest_tags():
    compose_text = _read_text("deploy/compose.yaml")

    assert "nicolargo/glances@sha256:" in compose_text
    assert "ghcr.io/jellyfin/jellyfin@sha256:" in compose_text
    assert "lscr.io/linuxserver/qbittorrent@sha256:" in compose_text
    assert "ghcr.io/estrellaxd/auto_bangumi@sha256:" in compose_text
    assert ":latest" not in compose_text
    assert ":latest-full" not in compose_text


def test_deploy_scripts_split_ui_only_and_full_stack_paths():
    ui_script = _read_text("scripts/remote_up_ui.sh")
    stack_script = _read_text("scripts/remote_up_stack.sh")
    compat_script = _read_text("scripts/remote_up.sh")

    assert "up -d --build homepage" in ui_script
    assert "up -d --build postprocessor" not in ui_script

    assert "up -d --build postprocessor" in stack_script
    assert "up -d --no-build" in stack_script

    assert "remote_up_stack.sh" in compat_script


def test_backup_and_healthcheck_scripts_cover_critical_runtime_state():
    backup_script = _read_text("scripts/backup_pi_state.sh")
    healthcheck_script = _read_text("scripts/check_ops_stack.sh")

    for expected_path in [
        "/jellyfin",
        "/qbittorrent",
        "/autobangumi",
        "/deploy/.env",
        "/deploy/title_mappings.toml",
    ]:
        assert expected_path in backup_script
    assert "--warning=no-file-changed" in backup_script

    assert "/healthz" in healthcheck_script
    assert "/api/overview" in healthcheck_script
    assert "diagnostics" in healthcheck_script


def test_sync_script_excludes_local_only_artifacts_from_remote_sync():
    sync_script = _read_text("scripts/sync_to_pi.sh")

    assert "--exclude 'backups/'" in sync_script
    assert "--exclude '.superpowers/'" in sync_script
    assert "--exclude '.worktrees/'" in sync_script
    assert "--exclude 'RPI_Anime_APP/'" in sync_script
    assert "--exclude 'tmp/'" in sync_script
    assert "--exclude '.pytest_cache/'" in sync_script
    assert "--exclude 'docs/superpowers/'" in sync_script
    assert "--exclude 'docs/*_new_*.png'" in sync_script


def test_sync_script_reloads_live_source_and_image_based_services_after_sync():
    sync_script = _read_text("scripts/sync_to_pi.sh")

    assert "--itemize-changes" in sync_script
    assert "restart homepage" in sync_script
    assert "build postprocessor" in sync_script
    assert 'changed_services+=("postprocessor")' in sync_script
    assert 'up -d --no-build ${changed_services[*]}' in sync_script


def test_sync_script_refuses_to_sync_when_remote_app_repo_is_present():
    sync_script = _read_text("scripts/sync_to_pi.sh")

    assert "RPI_Anime_APP already exists on the Raspberry Pi" in sync_script
    assert "APP repository must stay outside the backend deploy tree" in sync_script


def test_sync_script_reconciles_remote_stack_when_runtime_config_changes():
    sync_script = _read_text("scripts/sync_to_pi.sh")

    assert "deploy/compose.yaml" in sync_script
    assert 'services/ops_ui/(Dockerfile|pyproject\\.toml)' in sync_script
    assert 'services/postprocessor/(Dockerfile|pyproject\\.toml)' in sync_script
    assert "deploy/.env" in sync_script
    assert "build homepage" in sync_script
    assert "up -d --no-build" in sync_script


def test_sync_script_refuses_to_sync_into_rootfs_when_fstab_mount_is_missing():
    sync_script = _read_text("scripts/sync_to_pi.sh")

    assert "findmnt -s -n -o SOURCE --target" in sync_script
    assert "findmnt -n -o SOURCE --target /" in sync_script
    assert "Refusing to sync because" in sync_script
    assert "mount has fallen back to the root filesystem" in sync_script


def test_bootstrap_script_prepares_shared_ops_ui_state_directory():
    bootstrap_script = _read_text("scripts/bootstrap_pi.sh")

    assert "/srv/anime-data/appdata/ops-ui" in bootstrap_script
    assert "/srv/anime-data/appdata/jellyfin/fonts" in bootstrap_script
