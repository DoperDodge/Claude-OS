"""Tests for the notification manager."""

import asyncio
import json
import pytest
from notification_manager import NotificationManager, Priority


@pytest.fixture
def nm(tmp_data, monkeypatch):
    """Create a NotificationManager with temp storage."""
    monkeypatch.setenv("CLAUDE_OS_DATA", str(tmp_data))
    # Patch the module-level constant
    import notification_manager
    notification_manager.NOTIFICATIONS_DIR = tmp_data / "notifications"
    manager = NotificationManager()
    return manager


class TestPostNotification:
    """Test posting notifications."""

    @pytest.mark.asyncio
    async def test_post_basic(self, nm):
        result = await nm.post("test-app", "Hello", "World")
        assert result["app_id"] == "test-app"
        assert result["title"] == "Hello"
        assert result["body"] == "World"
        assert result["id"]

    @pytest.mark.asyncio
    async def test_post_with_priority(self, nm):
        result = await nm.post("app", "Urgent!", "Fix now", priority="urgent")
        assert result["priority"] == "urgent"

    @pytest.mark.asyncio
    async def test_post_increments_count(self, nm):
        await nm.post("app", "One", "")
        await nm.post("app", "Two", "")
        await nm.post("app", "Three", "")
        assert len(nm.get_all()) == 3

    @pytest.mark.asyncio
    async def test_post_with_actions(self, nm):
        actions = [{"action_id": "reply", "label": "Reply"}]
        result = await nm.post("app", "Message", "Hi", actions=actions)
        assert len(result["actions"]) == 1
        assert result["actions"][0]["label"] == "Reply"


class TestQueryNotifications:
    """Test querying notifications."""

    @pytest.mark.asyncio
    async def test_get_all(self, nm):
        await nm.post("app1", "A", "")
        await nm.post("app2", "B", "")
        all_notifs = nm.get_all()
        assert len(all_notifs) == 2

    @pytest.mark.asyncio
    async def test_get_unread(self, nm):
        await nm.post("app", "A", "")
        result = await nm.post("app", "B", "")
        await nm.mark_read(result["id"])

        unread = nm.get_unread()
        assert len(unread) == 1
        assert unread[0]["title"] == "A"

    @pytest.mark.asyncio
    async def test_get_by_app(self, nm):
        await nm.post("app1", "A", "")
        await nm.post("app2", "B", "")
        await nm.post("app1", "C", "")

        app1_notifs = nm.get_by_app("app1")
        assert len(app1_notifs) == 2

    @pytest.mark.asyncio
    async def test_get_summary(self, nm):
        await nm.post("app1", "A", "", priority="urgent")
        await nm.post("app2", "B", "", priority="normal")
        await nm.post("app1", "C", "", priority="high")

        summary = nm.get_summary()
        assert summary["total_unread"] == 3
        assert summary["urgent_count"] == 1
        assert summary["high_count"] == 1
        assert "app1" in summary["by_app"]
        assert "app2" in summary["by_app"]


class TestNotificationActions:
    """Test marking read, dismissing, etc."""

    @pytest.mark.asyncio
    async def test_mark_read(self, nm):
        result = await nm.post("app", "Test", "")
        await nm.mark_read(result["id"])

        unread = nm.get_unread()
        assert len(unread) == 0

    @pytest.mark.asyncio
    async def test_dismiss(self, nm):
        result = await nm.post("app", "Test", "")
        await nm.dismiss(result["id"])

        all_notifs = nm.get_all(include_dismissed=False)
        assert len(all_notifs) == 0

    @pytest.mark.asyncio
    async def test_dismiss_all(self, nm):
        await nm.post("app", "A", "")
        await nm.post("app", "B", "")
        await nm.post("app", "C", "")

        result = await nm.dismiss_all()
        assert result["dismissed_count"] == 3
        assert len(nm.get_all()) == 0

    @pytest.mark.asyncio
    async def test_dismiss_all_by_app(self, nm):
        await nm.post("app1", "A", "")
        await nm.post("app2", "B", "")

        await nm.dismiss_all(app_id="app1")
        remaining = nm.get_all()
        assert len(remaining) == 1
        assert remaining[0]["app_id"] == "app2"

    @pytest.mark.asyncio
    async def test_mark_all_read(self, nm):
        await nm.post("app", "A", "")
        await nm.post("app", "B", "")

        result = await nm.mark_all_read()
        assert result["marked_read_count"] == 2
        assert len(nm.get_unread()) == 0

    @pytest.mark.asyncio
    async def test_mark_read_nonexistent_raises(self, nm):
        with pytest.raises(ValueError):
            await nm.mark_read("nonexistent-id")


class TestDND:
    """Test Do Not Disturb mode."""

    def test_set_dnd(self, nm):
        result = nm.set_dnd(True)
        assert result["do_not_disturb"] is True
        assert nm.do_not_disturb is True

    def test_disable_dnd(self, nm):
        nm.set_dnd(True)
        nm.set_dnd(False)
        assert nm.do_not_disturb is False


class TestNotificationLimits:
    """Test enforcement of notification limits."""

    @pytest.mark.asyncio
    async def test_per_app_limit(self, nm):
        nm.MAX_PER_APP = 5
        for i in range(10):
            await nm.post("app", f"Notif {i}", "")

        app_notifs = nm.get_by_app("app")
        assert len(app_notifs) <= 5

    @pytest.mark.asyncio
    async def test_global_limit(self, nm):
        nm.MAX_NOTIFICATIONS = 10
        for i in range(20):
            await nm.post(f"app{i}", f"Notif {i}", "")

        assert len(nm.notifications) <= 10
