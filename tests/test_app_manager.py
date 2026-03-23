"""Tests for the app lifecycle manager."""

import json
import pytest
from pathlib import Path
from app_manager import AppManager, AppManifest, AppState


@pytest.fixture
def manifest_dir(tmp_path):
    """Create a temp directory with test app manifests."""
    import app_manager
    app_manager.APPS_DIR = tmp_path / "apps"
    app_manager.APP_DATA_BASE = tmp_path / "data"
    app_manager.APPS_DIR.mkdir()
    app_manager.APP_DATA_BASE.mkdir()

    # Create a test app manifest
    app_dir = app_manager.APPS_DIR / "test-app"
    app_dir.mkdir()
    manifest = {
        "app_id": "test-app",
        "name": "Test App",
        "exec": "python3 -c 'import time; time.sleep(3600)'",
        "category": "utility",
        "autostart": False,
        "restart_on_crash": False,
        "max_memory_mb": 128,
        "permissions": [],
    }
    (app_dir / "manifest.json").write_text(json.dumps(manifest))

    return tmp_path


@pytest.fixture
def am(manifest_dir):
    """Create an AppManager with test manifests."""
    manager = AppManager()
    manager._load_manifests()
    return manager


class TestManifestLoading:
    """Test app manifest loading."""

    def test_load_manifests(self, am):
        assert "test-app" in am.manifests
        assert am.manifests["test-app"].name == "Test App"

    def test_manifest_fields(self, am):
        m = am.manifests["test-app"]
        assert m.app_id == "test-app"
        assert m.category == "utility"
        assert m.max_memory_mb == 128
        assert m.autostart is False

    def test_list_installed(self, am):
        installed = am.list_installed()
        assert len(installed) == 1
        assert installed[0]["app_id"] == "test-app"
        assert installed[0]["name"] == "Test App"
        assert installed[0]["running"] is False

    def test_invalid_manifest_skipped(self, manifest_dir):
        import app_manager
        bad_dir = app_manager.APPS_DIR / "bad-app"
        bad_dir.mkdir()
        (bad_dir / "manifest.json").write_text("not valid json{{{")

        manager = AppManager()
        manager._load_manifests()
        assert "bad-app" not in manager.manifests


class TestAppLifecycle:
    """Test app launch/kill operations."""

    @pytest.mark.asyncio
    async def test_launch_app(self, am):
        result = await am.launch("test-app")
        assert result["status"] == "launched"
        assert result["pid"] > 0
        assert "test-app" in am.apps
        assert am.apps["test-app"].state == AppState.RUNNING

        # Cleanup
        await am.kill("test-app")

    @pytest.mark.asyncio
    async def test_launch_unknown_raises(self, am):
        with pytest.raises(ValueError, match="Unknown app"):
            await am.launch("nonexistent-app")

    @pytest.mark.asyncio
    async def test_launch_already_running(self, am):
        await am.launch("test-app")
        result = await am.launch("test-app")
        assert result["status"] == "already_running"
        await am.kill("test-app")

    @pytest.mark.asyncio
    async def test_kill_app(self, am):
        await am.launch("test-app")
        result = await am.kill("test-app")
        assert result["status"] == "killed"
        assert "test-app" not in am.apps

    @pytest.mark.asyncio
    async def test_kill_unknown_raises(self, am):
        with pytest.raises(ValueError):
            await am.kill("nonexistent")

    @pytest.mark.asyncio
    async def test_list_running(self, am):
        await am.launch("test-app")
        running = am.list_running()
        assert len(running) == 1
        assert running[0]["app_id"] == "test-app"
        assert running[0]["state"] == "running"
        await am.kill("test-app")

    @pytest.mark.asyncio
    async def test_get_app_info(self, am):
        info = am.get_app_info("test-app")
        assert info["app_id"] == "test-app"
        assert info["name"] == "Test App"
        assert info["installed"] is True

    @pytest.mark.asyncio
    async def test_suspend_resume(self, am):
        await am.launch("test-app")

        result = await am.suspend("test-app")
        assert result["status"] == "suspended"
        assert am.apps["test-app"].state == AppState.SUSPENDED

        result = await am.resume("test-app")
        assert result["status"] == "resumed"
        assert am.apps["test-app"].state == AppState.RUNNING

        await am.kill("test-app")
