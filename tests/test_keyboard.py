"""Tests for the on-screen keyboard."""

import pytest
from keyboard import OnScreenKeyboard, KeyboardLayer, LAYOUTS


@pytest.fixture
def kb():
    """Create a keyboard instance."""
    k = OnScreenKeyboard()
    k.show()
    return k


class TestKeyboardLayers:
    """Test layer switching."""

    def test_starts_lowercase(self, kb):
        assert kb.layer == KeyboardLayer.LOWERCASE

    def test_all_layouts_exist(self):
        assert KeyboardLayer.LOWERCASE in LAYOUTS
        assert KeyboardLayer.UPPERCASE in LAYOUTS
        assert KeyboardLayer.NUMBERS in LAYOUTS
        assert KeyboardLayer.SYMBOLS in LAYOUTS

    def test_all_layouts_have_4_rows(self):
        for layer, layout in LAYOUTS.items():
            assert len(layout) == 4, f"{layer.name} has {len(layout)} rows"

    def test_get_current_layout(self, kb):
        layout = kb.get_current_layout()
        assert len(layout) == 4
        # First key of QWERTY row 1 should be 'q'
        assert layout[0][0].label == "q"


class TestKeyPresses:
    """Test key press handling."""

    def test_character_key(self, kb):
        pressed = []
        kb.set_key_handler(on_key=lambda c: pressed.append(c))

        kb._press_key(LAYOUTS[KeyboardLayer.LOWERCASE][0][0])  # 'q'
        assert pressed == ["q"]

    def test_shift_toggles_uppercase(self, kb):
        # Find shift key
        shift = LAYOUTS[KeyboardLayer.LOWERCASE][2][0]
        kb._handle_special(shift)
        assert kb.layer == KeyboardLayer.UPPERCASE

        # Shift again goes back
        shift_upper = LAYOUTS[KeyboardLayer.UPPERCASE][2][0]
        kb._handle_special(shift_upper)
        assert kb.layer == KeyboardLayer.LOWERCASE

    def test_auto_lowercase_after_char(self, kb):
        # Switch to uppercase
        kb.layer = KeyboardLayer.UPPERCASE
        pressed = []
        kb.set_key_handler(on_key=lambda c: pressed.append(c))

        # Type a character
        kb._press_key(LAYOUTS[KeyboardLayer.UPPERCASE][0][0])  # 'Q'
        assert pressed == ["Q"]
        assert kb.layer == KeyboardLayer.LOWERCASE

    def test_numbers_layer(self, kb):
        # Find the "123" key
        num_key = LAYOUTS[KeyboardLayer.LOWERCASE][3][0]
        kb._handle_special(num_key)
        assert kb.layer == KeyboardLayer.NUMBERS

    def test_backspace(self, kb):
        specials = []
        kb.set_key_handler(
            on_key=lambda c: None,
            on_special=lambda c: specials.append(c),
        )

        backspace = LAYOUTS[KeyboardLayer.LOWERCASE][2][-1]
        kb._handle_special(backspace)
        assert specials == ["backspace"]

    def test_enter(self, kb):
        specials = []
        kb.set_key_handler(
            on_key=lambda c: None,
            on_special=lambda c: specials.append(c),
        )

        enter = LAYOUTS[KeyboardLayer.LOWERCASE][3][-1]
        kb._handle_special(enter)
        assert specials == ["enter"]


class TestHitTest:
    """Test touch-to-key mapping."""

    def test_hit_first_key(self, kb):
        # First key 'q' should be in the top-left area
        key = kb._hit_test(10, 10)
        assert key is not None
        assert key.label == "q"

    def test_hit_test_out_of_bounds(self, kb):
        key = kb._hit_test(0, 9999)
        assert key is None

    def test_hit_test_negative(self, kb):
        key = kb._hit_test(-10, -10)
        assert key is None


class TestShowHide:
    """Test visibility toggling."""

    def test_show(self):
        kb = OnScreenKeyboard()
        assert kb.visible is False
        kb.show()
        assert kb.visible is True

    def test_hide(self, kb):
        kb.hide()
        assert kb.visible is False

    def test_touch_ignored_when_hidden(self):
        kb = OnScreenKeyboard()
        pressed = []
        kb.set_key_handler(on_key=lambda c: pressed.append(c))
        kb.handle_touch(100, 100, "down")
        assert pressed == []


class TestSuggestions:
    """Test predictive text suggestions."""

    def test_update_suggestions(self, kb):
        kb.update_suggestions(["hello", "help", "hey"])
        assert kb.suggestions == ["hello", "help", "hey"]

    def test_suggestions_max_3(self, kb):
        kb.update_suggestions(["a", "b", "c", "d", "e"])
        assert len(kb.suggestions) == 3

    def test_suggestion_tap(self, kb):
        suggestions_received = []
        kb.set_key_handler(
            on_key=lambda c: None,
            on_suggestion=lambda s: suggestions_received.append(s),
        )
        kb.update_suggestions(["hello", "help"])
        kb._handle_suggestion_tap(100)  # Should hit first suggestion
        assert len(suggestions_received) == 1


class TestRenderData:
    """Test render data generation."""

    def test_render_data_structure(self, kb):
        data = kb.get_render_data()
        assert data["visible"] is True
        assert data["height"] == 300
        assert data["layer"] == "LOWERCASE"
        assert len(data["rows"]) == 4

    def test_render_data_key_format(self, kb):
        data = kb.get_render_data()
        key = data["rows"][0][0]
        assert "label" in key
        assert "code" in key
        assert "width" in key
        assert "special" in key
