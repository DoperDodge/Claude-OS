"""Tests for the accessibility manager."""

import json
import pytest
from accessibility import AccessibilityManager, AccessibilitySettings

import accessibility


@pytest.fixture
def a11y(tmp_config, monkeypatch):
    """Create an AccessibilityManager with temp config."""
    monkeypatch.setenv("CLAUDE_OS_CONFIG", str(tmp_config))
    accessibility.A11Y_CONFIG = tmp_config / "accessibility.json"
    accessibility.CONFIG_DIR = tmp_config
    manager = AccessibilityManager()
    return manager


class TestDefaults:
    """Test default accessibility settings."""

    def test_defaults_off(self, a11y):
        s = a11y.settings
        assert s.large_text is False
        assert s.high_contrast is False
        assert s.screen_reader is False
        assert s.voice_only_mode is False
        assert s.text_scale == 1.0

    def test_defaults_on(self, a11y):
        s = a11y.settings
        assert s.haptic_feedback is True


class TestSettingsUpdate:
    """Test updating settings."""

    @pytest.mark.asyncio
    async def test_update_single(self, a11y):
        result = await a11y.update_settings({"large_text": True})
        assert result["display"]["large_text"] is True
        assert a11y.settings.large_text is True

    @pytest.mark.asyncio
    async def test_update_multiple(self, a11y):
        await a11y.update_settings({
            "high_contrast": True,
            "text_scale": 2.0,
            "mono_audio": True,
        })
        assert a11y.settings.high_contrast is True
        assert a11y.settings.text_scale == 2.0
        assert a11y.settings.mono_audio is True

    @pytest.mark.asyncio
    async def test_unknown_setting_ignored(self, a11y):
        # Should not raise
        await a11y.update_settings({"fake_setting": True})


class TestQuickModes:
    """Test quick-enable modes."""

    @pytest.mark.asyncio
    async def test_enable_screen_reader(self, a11y):
        result = await a11y.enable_screen_reader()
        assert result["screen_reader"] is True
        assert a11y.settings.auto_read_responses is True

    @pytest.mark.asyncio
    async def test_enable_voice_only(self, a11y):
        result = await a11y.enable_voice_only_mode()
        assert result["voice_only_mode"] is True
        assert a11y.settings.screen_reader is True
        assert a11y.settings.verbose_descriptions is True

    @pytest.mark.asyncio
    async def test_enable_high_contrast(self, a11y):
        result = await a11y.enable_high_contrast()
        assert result["high_contrast"] is True
        assert a11y.settings.reduce_transparency is True

    @pytest.mark.asyncio
    async def test_set_text_scale(self, a11y):
        result = await a11y.set_text_scale(2.5)
        assert result["text_scale"] == 2.5
        assert result["large_text"] is True

    @pytest.mark.asyncio
    async def test_text_scale_clamped(self, a11y):
        result = await a11y.set_text_scale(10.0)
        assert result["text_scale"] == 3.0

        result = await a11y.set_text_scale(0.1)
        assert result["text_scale"] == 0.5

    @pytest.mark.asyncio
    async def test_set_color_correction(self, a11y):
        result = await a11y.set_color_correction("deuteranomaly")
        assert result["color_correction"] == "deuteranomaly"

    @pytest.mark.asyncio
    async def test_invalid_color_correction(self, a11y):
        with pytest.raises(ValueError):
            await a11y.set_color_correction("invalid_mode")


class TestClaudePromptModifiers:
    """Test Claude system prompt adjustments."""

    def test_no_modifiers_by_default(self, a11y):
        assert a11y.get_claude_prompt_modifiers() == ""

    def test_simple_language_modifier(self, a11y):
        a11y.settings.simple_language = True
        mods = a11y.get_claude_prompt_modifiers()
        assert "simple" in mods.lower()

    def test_verbose_modifier(self, a11y):
        a11y.settings.verbose_descriptions = True
        mods = a11y.get_claude_prompt_modifiers()
        assert "descriptive" in mods.lower()

    def test_voice_only_modifier(self, a11y):
        a11y.settings.voice_only_mode = True
        mods = a11y.get_claude_prompt_modifiers()
        assert "voice-only" in mods.lower()


class TestPersistence:
    """Test save/load of settings."""

    @pytest.mark.asyncio
    async def test_save_and_load(self, a11y, tmp_config):
        await a11y.update_settings({"high_contrast": True, "text_scale": 1.8})

        a11y2 = AccessibilityManager()
        accessibility.A11Y_CONFIG = tmp_config / "accessibility.json"
        a11y2.load()

        assert a11y2.settings.high_contrast is True
        assert a11y2.settings.text_scale == 1.8

    def test_get_settings_structure(self, a11y):
        settings = a11y.get_settings()
        assert "display" in settings
        assert "audio" in settings
        assert "input" in settings
        assert "claude" in settings
