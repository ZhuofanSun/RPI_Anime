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

    for relative_path in ["README.md", "README.zh-Hans.md"]:
        text = _read_text(relative_path)
        for label, url in expected_links.items():
            assert f"[{label}]({url})" in text
        assert "./docs/dash1.png" in text
        assert "./docs/dash2.png" in text
        assert "_new_" not in text


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
    assert "--exclude 'docs/superpowers/'" in sync_script
    assert "--exclude 'docs/*_new_*.png'" in sync_script
