"""Tests for the Bridge API permission system."""

import json
import pytest
from permissions import PermissionManager


@pytest.fixture
def pm(tmp_config):
    """Create a PermissionManager with a temp config path."""
    manager = PermissionManager(tmp_config / "permissions.json")
    manager.load()
    return manager


class TestPermissionDefaults:
    """Test that default permissions are sensible."""

    def test_safe_actions_granted_by_default(self, pm):
        assert pm.check("wifi.connect") is True
        assert pm.check("wifi.scan") is True
        assert pm.check("system.info") is True
        assert pm.check("system.battery") is True
        assert pm.check("audio.volume") is True

    def test_dangerous_actions_denied_by_default(self, pm):
        assert pm.check("power.shutdown") is False
        assert pm.check("power.reboot") is False
        assert pm.check("files.read") is False
        assert pm.check("files.write") is False
        assert pm.check("camera.access") is False
        assert pm.check("location.access") is False
        assert pm.check("messages.read") is False

    def test_unknown_permission_denied(self, pm):
        assert pm.check("totally.made.up") is False


class TestPermissionGrant:
    """Test granting and revoking permissions."""

    def test_grant_permission(self, pm):
        assert pm.check("power.shutdown") is False
        pm.grant("power.shutdown")
        assert pm.check("power.shutdown") is True

    def test_revoke_permission(self, pm):
        assert pm.check("wifi.connect") is True
        pm.revoke("wifi.connect")
        assert pm.check("wifi.connect") is False

    def test_grant_unknown_returns_false(self, pm):
        assert pm.grant("nonexistent.perm") is False

    def test_revoke_unknown_returns_false(self, pm):
        assert pm.revoke("nonexistent.perm") is False


class TestPermissionPersistence:
    """Test that permissions survive save/load cycles."""

    def test_save_and_reload(self, tmp_config):
        config_path = tmp_config / "permissions.json"

        # Grant a permission and save
        pm1 = PermissionManager(config_path)
        pm1.load()
        pm1.grant("power.shutdown")

        # Load in a new instance
        pm2 = PermissionManager(config_path)
        pm2.load()
        assert pm2.check("power.shutdown") is True

    def test_revoke_persists(self, tmp_config):
        config_path = tmp_config / "permissions.json"

        pm1 = PermissionManager(config_path)
        pm1.load()
        pm1.revoke("wifi.connect")

        pm2 = PermissionManager(config_path)
        pm2.load()
        assert pm2.check("wifi.connect") is False


class TestPermissionList:
    """Test listing permissions."""

    def test_list_all_returns_categories(self, pm):
        result = pm.list_all()
        assert "wifi" in result
        assert "power" in result
        assert "audio" in result
        assert "system" in result

    def test_list_all_entries_have_fields(self, pm):
        result = pm.list_all()
        for category, entries in result.items():
            for entry in entries:
                assert "permission" in entry
                assert "granted" in entry
                assert "description" in entry
