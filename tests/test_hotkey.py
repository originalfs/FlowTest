import pytest

from localflow.hotkey import HotkeyListener, parse_combo


class TestParseCombo:
    def test_basic(self):
        assert parse_combo("ctrl+alt+space") == ["ctrl", "alt", "space"]

    def test_aliases(self):
        assert parse_combo("Control+Option+Command") == ["ctrl", "alt", "cmd"]
        assert parse_combo("win+z") == ["cmd", "z"]

    def test_single_key(self):
        assert parse_combo("f9") == ["f9"]

    def test_whitespace_and_case(self):
        assert parse_combo(" CTRL + Shift + A ") == ["ctrl", "shift", "a"]

    @pytest.mark.parametrize("bad", ["", "ctrl+", "ctrl+bogus", "ctrl+ctrl+a"])
    def test_invalid(self, bad):
        with pytest.raises(ValueError):
            parse_combo(bad)


class FakeKey:
    """Stands in for pynput.keyboard.Key: has .name, is not a KeyCode."""

    def __init__(self, name: str):
        self.name = name


class FakeKeyCode:
    def __init__(self, char):
        self.char = char


def make_listener(combo="ctrl+space"):
    events = []
    listener = HotkeyListener(
        combo,
        on_activate=lambda: events.append("on"),
        on_deactivate=lambda: events.append("off"),
    )
    return listener, events


class TestEdges:
    """Drive _on_press/_on_release with normalization stubbed to identity-by-name."""

    @pytest.fixture(autouse=True)
    def _patch_normalize(self, monkeypatch):
        monkeypatch.setattr(
            HotkeyListener,
            "_normalize",
            staticmethod(lambda key: key.name),
        )

    def test_push_to_talk_cycle(self):
        listener, events = make_listener()
        listener._on_press(FakeKey("ctrl"))
        assert events == []
        listener._on_press(FakeKey("space"))
        assert events == ["on"]
        listener._on_release(FakeKey("space"))
        assert events == ["on", "off"]

    def test_repeat_presses_do_not_refire(self):
        listener, events = make_listener()
        listener._on_press(FakeKey("ctrl"))
        listener._on_press(FakeKey("space"))
        listener._on_press(FakeKey("space"))  # OS key-repeat
        assert events == ["on"]

    def test_unrelated_keys_ignored(self):
        listener, events = make_listener()
        listener._on_press(FakeKey("ctrl"))
        listener._on_press(FakeKey("x"))
        listener._on_release(FakeKey("x"))
        assert events == []

    def test_reactivation_after_release(self):
        listener, events = make_listener()
        for _ in range(2):
            listener._on_press(FakeKey("ctrl"))
            listener._on_press(FakeKey("space"))
            listener._on_release(FakeKey("space"))
            listener._on_release(FakeKey("ctrl"))
        assert events == ["on", "off", "on", "off"]
