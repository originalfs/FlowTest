"""Global hotkey handling with press *and* release edges, so push-to-talk works.

pynput's GlobalHotKeys only fires on activation, so we track the pressed-key
set ourselves: when every key of the combo is down we fire on_activate; when
any of them is released while active we fire on_deactivate.
"""

from __future__ import annotations

from typing import Callable

MODIFIER_ALIASES = {
    "ctrl": "ctrl",
    "control": "ctrl",
    "alt": "alt",
    "option": "alt",
    "opt": "alt",
    "shift": "shift",
    "cmd": "cmd",
    "command": "cmd",
    "super": "cmd",
    "win": "cmd",
    "meta": "cmd",
}

SPECIAL_KEYS = {
    "space",
    "tab",
    "enter",
    "esc",
    "escape",
    "backspace",
    "delete",
    "home",
    "end",
    "insert",
    "caps_lock",
} | {f"f{i}" for i in range(1, 25)}


def parse_combo(combo: str) -> list[str]:
    """Parse "ctrl+alt+space" into normalized key names. Raises on unknown keys."""
    parts = [p.strip().lower() for p in combo.split("+")]
    if not parts or any(not p for p in parts):
        raise ValueError(f"invalid hotkey combo: {combo!r}")
    keys: list[str] = []
    for part in parts:
        if part in MODIFIER_ALIASES:
            keys.append(MODIFIER_ALIASES[part])
        elif part in SPECIAL_KEYS:
            keys.append("escape" if part == "esc" else part)
        elif len(part) == 1:
            keys.append(part)
        else:
            raise ValueError(f"unknown key {part!r} in hotkey combo {combo!r}")
    if len(set(keys)) != len(keys):
        raise ValueError(f"duplicate keys in hotkey combo: {combo!r}")
    return keys


class HotkeyListener:
    """Fires on_activate when the combo is fully pressed, on_deactivate on release."""

    def __init__(
        self,
        combo: str,
        on_activate: Callable[[], None],
        on_deactivate: Callable[[], None],
    ) -> None:
        self.keys = set(parse_combo(combo))
        self.on_activate = on_activate
        self.on_deactivate = on_deactivate
        self._pressed: set[str] = set()
        self._active = False
        self._listener = None

    @staticmethod
    def _normalize(key) -> str | None:
        """Map a pynput key event to our normalized key names."""
        from pynput import keyboard

        if isinstance(key, keyboard.KeyCode):
            return key.char.lower() if key.char else None
        name = key.name  # e.g. "ctrl_l", "alt_gr", "space", "f5"
        for mod in ("ctrl", "alt", "shift", "cmd"):
            if name == mod or name.startswith(mod + "_"):
                return mod
        return name

    def _on_press(self, key) -> None:
        name = self._normalize(key)
        if name in self.keys:
            self._pressed.add(name)
            if not self._active and self._pressed == self.keys:
                self._active = True
                self.on_activate()

    def _on_release(self, key) -> None:
        name = self._normalize(key)
        if name in self.keys:
            self._pressed.discard(name)
            if self._active:
                self._active = False
                self.on_deactivate()

    def run(self) -> None:
        """Block, listening for the hotkey until the process exits."""
        from pynput import keyboard  # lazy: needs a display server

        with keyboard.Listener(
            on_press=self._on_press, on_release=self._on_release
        ) as listener:
            self._listener = listener
            listener.join()

    def stop(self) -> None:
        if self._listener is not None:
            self._listener.stop()
