"""Tests for the storage manager."""

import os
import pytest
from storage_manager import StorageManager


@pytest.fixture
def sm(tmp_data):
    """Create a StorageManager for testing."""
    manager = StorageManager()
    return manager


class TestStorageInfo:
    """Test storage usage queries."""

    def test_get_usage_returns_dict(self, sm):
        usage = sm.get_usage()
        assert isinstance(usage, dict)
        # Should have at least root partition
        assert len(usage) > 0

    def test_partition_info_has_fields(self, sm):
        usage = sm.get_usage()
        for mount, info in usage.items():
            assert "total_bytes" in info
            assert "used_bytes" in info
            assert "free_bytes" in info
            assert "percent_used" in info
            assert "device" in info


class TestFileOperations:
    """Test sandboxed file operations."""

    def test_write_and_read(self, sm, tmp_path):
        # Patch allowed check for testing
        sm._check_access = lambda *a, **kw: None

        file_path = str(tmp_path / "test.txt")
        sm.write_file(file_path, "hello world")

        result = sm.read_file(file_path)
        assert result["content"] == "hello world"
        assert result["size_bytes"] > 0

    def test_list_files(self, sm, tmp_path):
        sm._check_access = lambda *a, **kw: None

        test_dir = tmp_path / "listtest"
        test_dir.mkdir()
        (test_dir / "a.txt").write_text("aaa")
        (test_dir / "b.txt").write_text("bbb")
        (test_dir / "subdir").mkdir()

        files = sm.list_files(str(test_dir))
        assert len(files) == 3
        names = [f["name"] for f in files]
        assert "a.txt" in names
        assert "b.txt" in names
        assert "subdir" in names

    def test_list_files_has_metadata(self, sm, tmp_path):
        sm._check_access = lambda *a, **kw: None
        (tmp_path / "file.txt").write_text("content")

        files = sm.list_files(str(tmp_path))
        f = files[0]
        assert "name" in f
        assert "path" in f
        assert "is_dir" in f
        assert "size_bytes" in f
        assert "modified" in f

    def test_delete_file(self, sm, tmp_path):
        sm._check_access = lambda *a, **kw: None
        file_path = tmp_path / "deleteme.txt"
        file_path.write_text("bye")

        sm.delete_file(str(file_path))
        assert not file_path.exists()

    def test_delete_directory(self, sm, tmp_path):
        sm._check_access = lambda *a, **kw: None
        dir_path = tmp_path / "mydir"
        dir_path.mkdir()
        (dir_path / "file.txt").write_text("inside")

        sm.delete_file(str(dir_path))
        assert not dir_path.exists()

    def test_read_nonexistent_raises(self, sm, tmp_path):
        sm._check_access = lambda *a, **kw: None
        with pytest.raises(FileNotFoundError):
            sm.read_file(str(tmp_path / "nope.txt"))

    def test_list_nonexistent_raises(self, sm, tmp_path):
        sm._check_access = lambda *a, **kw: None
        with pytest.raises(FileNotFoundError):
            sm.list_files(str(tmp_path / "nonexistent"))


class TestAccessControl:
    """Test sandboxed access control."""

    def test_blocks_system_paths(self, sm):
        with pytest.raises(PermissionError):
            sm._check_access(
                __import__("pathlib").Path("/etc/passwd"), app_id="myapp"
            )

    def test_blocks_proc(self, sm):
        with pytest.raises(PermissionError):
            sm._check_access(
                __import__("pathlib").Path("/proc/1/status"), app_id="myapp"
            )

    def test_blocks_sys(self, sm):
        with pytest.raises(PermissionError):
            sm._check_access(
                __import__("pathlib").Path("/sys/class"), app_id="myapp"
            )

    def test_app_can_access_own_data(self, sm):
        from pathlib import Path
        # Should NOT raise
        sm._check_access(
            Path("/var/lib/claude-os/apps/myapp/data/file.txt"),
            app_id="myapp",
        )

    def test_app_cant_access_other_app_data(self, sm):
        from pathlib import Path
        with pytest.raises(PermissionError):
            sm._check_access(
                Path("/var/lib/claude-os/apps/other-app/data/secrets.txt"),
                app_id="myapp",
            )
