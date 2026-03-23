"""
Tests for Phase 5 — App Framework & Window Management.

Covers: window manager, recent apps, system apps (settings, file manager,
terminal, contacts), and package manager.
"""

import json
import os
import tarfile
import tempfile
import time
import pytest

from theme import Colors, Typography
from widget import Widget, Event, EventType, Align, Direction


# --- Window Manager ---

from window_manager import WindowManager, Window, WindowState


class TestWindowManager:
    def test_create(self):
        wm = WindowManager()
        assert wm.window_count == 0
        assert wm.foreground_id is None

    def test_create_window(self):
        wm = WindowManager()
        w = wm.create_window("app1", "App 1")
        assert wm.window_count == 1
        assert w.app_id == "app1"
        assert w.name == "App 1"

    def test_create_duplicate_returns_existing(self):
        wm = WindowManager()
        w1 = wm.create_window("app1", "App 1")
        w2 = wm.create_window("app1", "App 1 Again")
        assert w1 is w2

    def test_focus_window(self):
        wm = WindowManager()
        wm.create_window("app1", "App 1")
        wm.focus_window("app1")
        assert wm.foreground_id == "app1"
        assert wm.foreground_window.state == WindowState.FOREGROUND

    def test_focus_backgrounds_previous(self):
        wm = WindowManager()
        wm.create_window("app1", "App 1")
        wm.create_window("app2", "App 2")
        wm.focus_window("app1")
        wm.focus_window("app2")
        assert wm.get_window("app1").state == WindowState.BACKGROUND
        assert wm.get_window("app2").state == WindowState.FOREGROUND

    def test_focus_nonexistent_returns_false(self):
        wm = WindowManager()
        assert wm.focus_window("nonexistent") is False

    def test_destroy_window(self):
        wm = WindowManager()
        wm.create_window("app1", "App 1")
        wm.destroy_window("app1")
        assert wm.window_count == 0

    def test_destroy_foreground_switches(self):
        wm = WindowManager()
        wm.create_window("app1", "App 1")
        wm.create_window("app2", "App 2")
        wm.focus_window("app1")
        wm.focus_window("app2")
        wm.destroy_window("app2")
        assert wm.foreground_id == "app1"

    def test_switch_to_previous(self):
        wm = WindowManager()
        wm.create_window("app1", "App 1")
        wm.create_window("app2", "App 2")
        wm.focus_window("app1")
        wm.focus_window("app2")
        prev = wm.switch_to_previous()
        assert prev == "app1"
        assert wm.foreground_id == "app1"

    def test_switch_to_previous_no_history(self):
        wm = WindowManager()
        wm.create_window("app1", "App 1")
        wm.focus_window("app1")
        assert wm.switch_to_previous() is None

    def test_go_home(self):
        wm = WindowManager()
        wm.create_window("claude-chat", "Claude")
        wm.create_window("settings", "Settings")
        wm.focus_window("settings")
        wm.go_home()
        assert wm.foreground_id == "claude-chat"

    def test_recent_order(self):
        wm = WindowManager()
        wm.create_window("a", "A")
        wm.create_window("b", "B")
        wm.create_window("c", "C")
        wm.focus_window("a")
        wm.focus_window("b")
        wm.focus_window("c")
        recent = wm.get_recent_windows()
        assert [w.app_id for w in recent] == ["c", "b", "a"]

    def test_foreground_widget(self):
        wm = WindowManager()
        widget = Widget()
        wm.create_window("app1", "App 1", widget=widget)
        wm.focus_window("app1")
        assert wm.foreground_widget is widget

    def test_capture_thumbnail(self):
        wm = WindowManager()
        wm.create_window("app1", "App 1")
        thumb = bytearray(100)
        wm.capture_thumbnail("app1", thumb, 10, 10)
        w = wm.get_window("app1")
        assert w.thumbnail is thumb
        assert w.thumb_width == 10

    def test_callbacks(self):
        changes = []
        wm = WindowManager()
        wm.create_window("a", "A")
        wm.create_window("b", "B")
        wm.focus_window("a")
        wm.set_callbacks(on_foreground_change=lambda old, new: changes.append((old, new)))
        wm.focus_window("b")
        assert len(changes) == 1
        assert changes[0] == ("a", "b")

    def test_get_status(self):
        wm = WindowManager()
        wm.create_window("app1", "App 1")
        wm.focus_window("app1")
        status = wm.get_status()
        assert status["foreground"] == "app1"
        assert "app1" in status["windows"]


# --- Recent Apps View ---

from recent_apps import RecentAppsView, AppCard


class TestRecentAppsView:
    def test_create(self):
        rv = RecentAppsView()
        assert rv.card_count == 0

    def test_set_recent_apps(self):
        rv = RecentAppsView()
        rv.set_recent_apps([
            {"app_id": "a", "name": "App A"},
            {"app_id": "b", "name": "App B"},
        ])
        assert rv.card_count == 2

    def test_show_hide(self):
        rv = RecentAppsView()
        rv.show()
        assert rv.is_visible is True
        rv.hide()
        assert rv.is_visible is False

    def test_select_callback(self):
        selected = []
        rv = RecentAppsView(on_select=lambda id: selected.append(id))
        rv.set_recent_apps([{"app_id": "a", "name": "A"}])
        # Manually trigger selection
        rv._cards[0]._select()
        assert "a" in selected

    def test_empty_state(self):
        rv = RecentAppsView()
        rv.set_recent_apps([])
        assert rv.card_count == 0


class TestAppCard:
    def test_create(self):
        card = AppCard("test", "Test App")
        assert card.app_id == "test"
        size = card.measure(200, 300)
        assert size.width == AppCard.CARD_WIDTH
        assert size.height == AppCard.CARD_HEIGHT

    def test_close_swipe(self):
        closed = []
        card = AppCard("test", "Test", on_close=lambda id: closed.append(id))
        card.layout(0, 0, 140, 200)
        card._handle_event(EventType.TOUCH_DOWN, 70, 150, 0)
        card._handle_event(EventType.TOUCH_UP, 70, 50, 0)  # 100px up
        assert "test" in closed


# --- Settings App ---

from settings_app import SettingsApp, SettingsSection, SettingItem, SettingRow


class TestSettingsApp:
    def test_create(self):
        sa = SettingsApp()
        assert sa.section_count == 4
        assert sa.setting_count > 0

    def test_get_setting(self):
        sa = SettingsApp()
        assert sa.get_setting("os_version") == "Claude-OS 0.1.0"

    def test_set_setting(self):
        sa = SettingsApp()
        sa.set_setting("brightness", "50%")
        assert sa.get_setting("brightness") == "50%"

    def test_toggle_setting(self):
        sa = SettingsApp()
        assert sa.get_setting("dark_mode") == "On"
        # Find the actual item in the data model and toggle it
        actual_item = None
        for section in sa._sections:
            for item in section.items:
                if item.key == "dark_mode":
                    actual_item = item
                    break
        sa._on_item_tap(actual_item)
        assert sa.get_setting("dark_mode") == "Off"

    def test_setting_change_callback(self):
        changes = []
        sa = SettingsApp(on_setting_change=lambda k, v: changes.append((k, v)))
        sa._on_item_tap(SettingItem("wifi_enabled", "WiFi", "On", "toggle"))
        assert len(changes) == 1

    def test_draw(self):
        sa = SettingsApp()
        sa.layout(0, 0, 320, 480)
        buf = bytearray(320 * 480 * 4)
        sa.draw(buf, 320, 480)
        has_content = any(buf[i] > 0 for i in range(0, len(buf)))
        assert has_content


# --- File Manager App ---

from file_manager_app import FileManagerApp, FileEntry


class TestFileManagerApp:
    def test_create(self):
        fm = FileManagerApp(root_path="/tmp")
        assert fm.current_path == "/tmp"

    def test_set_entries(self):
        fm = FileManagerApp(root_path="/test")
        fm.set_entries([
            FileEntry("docs", "/test/docs", is_dir=True),
            FileEntry("readme.txt", "/test/readme.txt", is_dir=False, size=1024),
        ])
        assert fm.entry_count == 2

    def test_navigate(self):
        fm = FileManagerApp(root_path="/test")
        fm.navigate("/test/subdir")
        assert fm.current_path == "/test/subdir"

    def test_go_back(self):
        fm = FileManagerApp(root_path="/test")
        fm.navigate("/test/subdir")
        fm.go_back()
        assert fm.current_path == "/test"

    def test_go_back_no_history(self):
        fm = FileManagerApp(root_path="/test")
        fm.go_back()  # Should not crash
        assert fm.current_path == "/test"

    def test_go_home(self):
        fm = FileManagerApp(root_path="/home")
        fm.navigate("/home/subdir")
        fm.go_home()
        assert fm.current_path == "/home"

    def test_file_size_display(self):
        e = FileEntry("big.bin", "/big.bin", is_dir=False, size=1536)
        assert "1.5 KB" in e.size_str

        e = FileEntry("huge.bin", "/huge.bin", is_dir=False, size=2 * 1024 * 1024)
        assert "2.0 MB" in e.size_str

    def test_file_type_icon(self):
        assert FileEntry("test.py", "/test.py", False).type_icon == "#"
        assert FileEntry("photo.jpg", "/photo.jpg", False).type_icon == "I"
        assert FileEntry("docs", "/docs", True).type_icon == "D"

    def test_draw(self):
        fm = FileManagerApp(root_path="/test")
        fm.set_entries([
            FileEntry("file.txt", "/test/file.txt", is_dir=False, size=100),
        ])
        fm.layout(0, 0, 320, 480)
        buf = bytearray(320 * 480 * 4)
        fm.draw(buf, 320, 480)
        has_content = any(buf[i] > 0 for i in range(0, len(buf)))
        assert has_content


# --- Terminal App ---

from terminal_app import TerminalApp


class TestTerminalApp:
    def test_create(self):
        term = TerminalApp()
        assert term.line_count > 0  # Welcome messages

    def test_type_char(self):
        term = TerminalApp()
        term.type_char("h")
        term.type_char("i")
        assert term.input_text == "hi"

    def test_backspace(self):
        term = TerminalApp()
        term.type_char("a")
        term.type_char("b")
        term.type_char("BACKSPACE")
        assert term.input_text == "a"

    def test_submit_help(self):
        term = TerminalApp()
        term._input_text = "help"
        term.submit()
        assert term.input_text == ""
        assert term.line_count > 3  # Help output

    def test_submit_clear(self):
        term = TerminalApp()
        term._input_text = "clear"
        term.submit()
        assert term.line_count == 0

    def test_submit_pwd(self):
        term = TerminalApp()
        term._input_text = "pwd"
        initial_count = term.line_count
        term.submit()
        assert term.line_count > initial_count

    def test_unknown_command(self):
        term = TerminalApp()
        term._input_text = "nonexistent_cmd"
        term.submit()
        # Should have error output
        has_error = any("not found" in line.text for line in term._lines)
        assert has_error

    def test_command_callback(self):
        results = []
        term = TerminalApp(on_command=lambda cmd: f"ran: {cmd}")
        term._input_text = "custom"
        term.submit()
        has_result = any("ran: custom" in line.text for line in term._lines)
        assert has_result

    def test_write_output(self):
        term = TerminalApp()
        initial = term.line_count
        term.write("hello\nworld")
        assert term.line_count == initial + 2

    def test_command_history(self):
        term = TerminalApp()
        term._input_text = "help"
        term.submit()
        term._input_text = "pwd"
        term.submit()
        assert term.command_history == ["help", "pwd"]

    def test_draw(self):
        term = TerminalApp()
        term.layout(0, 0, 320, 480)
        buf = bytearray(320 * 480 * 4)
        term.draw(buf, 320, 480)
        has_content = any(buf[i] > 0 for i in range(0, len(buf)))
        assert has_content


# --- Contacts App ---

from contacts_app import ContactsApp, Contact


class TestContactsApp:
    def test_create(self):
        ca = ContactsApp()
        assert ca.contact_count == 5  # Default contacts

    def test_add_contact(self):
        ca = ContactsApp()
        ca.add_contact(Contact("Frank", "+1 555-0106"))
        assert ca.contact_count == 6

    def test_remove_contact(self):
        ca = ContactsApp()
        ca.remove_contact("Alice")
        assert ca.contact_count == 4
        assert ca.find_contact("Alice") is None

    def test_find_contact(self):
        ca = ContactsApp()
        c = ca.find_contact("Claude")
        assert c is not None
        assert c.phone == "+1 555-0103"

    def test_call_callback(self):
        calls = []
        ca = ContactsApp(on_call=lambda num: calls.append(num))
        ca._on_contact_tap(Contact("Test", "+1 555-9999"))
        assert "+1 555-9999" in calls

    def test_contact_avatar_auto(self):
        c = Contact("Bob")
        assert c.avatar_char == "B"

    def test_draw(self):
        ca = ContactsApp()
        ca.layout(0, 0, 320, 480)
        buf = bytearray(320 * 480 * 4)
        ca.draw(buf, 320, 480)
        has_content = any(buf[i] > 0 for i in range(0, len(buf)))
        assert has_content


# --- Package Manager ---

from package_manager import PackageManager, PackageInfo, PackageError


class TestPackageManager:
    @pytest.fixture
    def pm(self, tmp_path):
        apps = tmp_path / "apps"
        data = tmp_path / "data"
        apps.mkdir()
        data.mkdir()
        return PackageManager(apps_dir=apps, data_dir=data)

    @pytest.fixture
    def sample_cpk(self, tmp_path):
        """Create a valid .cpk package file."""
        pkg_dir = tmp_path / "pkg_build"
        pkg_dir.mkdir()

        manifest = {
            "app_id": "test-app",
            "name": "Test App",
            "exec": "python3 main.py",
            "version": "1.0.0",
            "author": "Test",
            "description": "A test app",
            "permissions": ["network"],
        }
        (pkg_dir / "manifest.json").write_text(json.dumps(manifest))
        (pkg_dir / "main.py").write_text("print('hello')")

        cpk_path = tmp_path / "test-app.cpk"
        with tarfile.open(str(cpk_path), "w:gz") as tar:
            tar.add(str(pkg_dir / "manifest.json"), "manifest.json")
            tar.add(str(pkg_dir / "main.py"), "main.py")

        return str(cpk_path)

    def test_empty_installed(self, pm):
        assert pm.installed_count == 0

    def test_verify_valid_package(self, pm, sample_cpk):
        info = pm.verify(sample_cpk)
        assert info.app_id == "test-app"
        assert info.name == "Test App"
        assert info.version == "1.0.0"

    def test_verify_missing_file(self, pm):
        with pytest.raises(PackageError, match="not found"):
            pm.verify("/nonexistent.cpk")

    def test_verify_missing_manifest(self, pm, tmp_path):
        # Create a tarball without manifest
        cpk = tmp_path / "bad.cpk"
        with tarfile.open(str(cpk), "w:gz") as tar:
            f = tmp_path / "random.txt"
            f.write_text("no manifest")
            tar.add(str(f), "random.txt")

        with pytest.raises(PackageError, match="Missing manifest"):
            pm.verify(str(cpk))

    def test_install(self, pm, sample_cpk):
        info = pm.install(sample_cpk)
        assert info.app_id == "test-app"
        assert pm.is_installed("test-app")
        assert pm.installed_count == 1

        # Check files were extracted
        assert (pm.apps_dir / "test-app" / "manifest.json").exists()
        assert (pm.apps_dir / "test-app" / "main.py").exists()

    def test_install_duplicate_fails(self, pm, sample_cpk):
        pm.install(sample_cpk)
        with pytest.raises(PackageError, match="Already installed"):
            pm.install(sample_cpk)

    def test_install_force(self, pm, sample_cpk):
        pm.install(sample_cpk)
        info = pm.install(sample_cpk, force=True)
        assert info.app_id == "test-app"

    def test_uninstall(self, pm, sample_cpk):
        pm.install(sample_cpk)
        pm.uninstall("test-app")
        assert not pm.is_installed("test-app")
        assert pm.installed_count == 0
        assert not (pm.apps_dir / "test-app").exists()

    def test_uninstall_not_installed(self, pm):
        with pytest.raises(PackageError, match="Not installed"):
            pm.uninstall("nonexistent")

    def test_uninstall_keep_data(self, pm, sample_cpk):
        pm.install(sample_cpk)
        # Create some data
        data_dir = pm.data_dir / "test-app" / "data"
        data_dir.mkdir(parents=True, exist_ok=True)
        (data_dir / "save.json").write_text("{}")

        pm.uninstall("test-app", keep_data=True)
        assert not pm.is_installed("test-app")
        assert (data_dir / "save.json").exists()

    def test_get_info(self, pm, sample_cpk):
        pm.install(sample_cpk)
        info = pm.get_info("test-app")
        assert info.name == "Test App"
        assert "network" in info.permissions

    def test_list_installed(self, pm, sample_cpk):
        pm.install(sample_cpk)
        installed = pm.list_installed()
        assert len(installed) == 1
        assert installed[0].app_id == "test-app"

    def test_load_installed_from_disk(self, pm, sample_cpk):
        pm.install(sample_cpk)
        # Create a new PackageManager pointing at the same dir
        pm2 = PackageManager(apps_dir=pm.apps_dir, data_dir=pm.data_dir)
        assert pm2.is_installed("test-app")

    def test_verify_path_traversal_blocked(self, pm, tmp_path):
        """Packages with .. paths should be rejected."""
        pkg_dir = tmp_path / "evil_build"
        pkg_dir.mkdir()
        manifest = {"app_id": "evil", "name": "Evil", "exec": "evil"}
        (pkg_dir / "manifest.json").write_text(json.dumps(manifest))

        cpk = tmp_path / "evil.cpk"
        with tarfile.open(str(cpk), "w:gz") as tar:
            tar.add(str(pkg_dir / "manifest.json"), "manifest.json")
            # Add a file with path traversal
            evil_file = pkg_dir / "evil.txt"
            evil_file.write_text("gotcha")
            tar.add(str(evil_file), "../../../etc/evil.txt")

        with pytest.raises(PackageError, match="Unsafe path"):
            pm.verify(str(cpk))
