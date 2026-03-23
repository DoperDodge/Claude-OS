"""
Shared test fixtures for Claude-OS tests.
"""

import json
import os
import sys
import tempfile
from pathlib import Path

import pytest

# Add all source directories to path so tests can import modules
PROJECT_ROOT = Path(__file__).parent.parent

sys.path.insert(0, str(PROJECT_ROOT / "system" / "bridge"))
sys.path.insert(0, str(PROJECT_ROOT / "system" / "bridge" / "services"))
sys.path.insert(0, str(PROJECT_ROOT / "system" / "wifi-manager"))
sys.path.insert(0, str(PROJECT_ROOT / "system" / "storage-manager"))
sys.path.insert(0, str(PROJECT_ROOT / "system" / "app-manager"))
sys.path.insert(0, str(PROJECT_ROOT / "system" / "notifications"))
sys.path.insert(0, str(PROJECT_ROOT / "system" / "security"))
sys.path.insert(0, str(PROJECT_ROOT / "system" / "ota"))
sys.path.insert(0, str(PROJECT_ROOT / "system" / "crash-reporter"))
sys.path.insert(0, str(PROJECT_ROOT / "system" / "battery-optimizer"))
sys.path.insert(0, str(PROJECT_ROOT / "system" / "accessibility"))
sys.path.insert(0, str(PROJECT_ROOT / "system" / "onboarding"))
sys.path.insert(0, str(PROJECT_ROOT / "ui" / "compositor"))
sys.path.insert(0, str(PROJECT_ROOT / "ui" / "display"))
sys.path.insert(0, str(PROJECT_ROOT / "ui" / "keyboard"))
sys.path.insert(0, str(PROJECT_ROOT / "ui" / "statusbar"))
sys.path.insert(0, str(PROJECT_ROOT / "claude-app"))
sys.path.insert(0, str(PROJECT_ROOT / "claude-app" / "chat"))
sys.path.insert(0, str(PROJECT_ROOT / "claude-app" / "voice"))
sys.path.insert(0, str(PROJECT_ROOT / "claude-app" / "tools"))


@pytest.fixture
def tmp_dir(tmp_path):
    """Provide a temporary directory for tests."""
    return tmp_path


@pytest.fixture
def tmp_config(tmp_path):
    """Provide a temporary config directory."""
    config_dir = tmp_path / "config"
    config_dir.mkdir()
    return config_dir


@pytest.fixture
def tmp_data(tmp_path):
    """Provide a temporary data directory."""
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    return data_dir
