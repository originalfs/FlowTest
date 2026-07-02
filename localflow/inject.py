"""Insert text at the cursor of whatever app has focus.

Two strategies:
- "type": simulate keystrokes (works everywhere, slower for long text)
- "paste": put text on the clipboard, press Ctrl/Cmd+V, restore the clipboard
"""

from __future__ import annotations

import sys
import time


def inject_text(text: str, method: str = "type") -> None:
    if not text:
        return
    if method == "paste":
        _inject_paste(text)
    else:
        _inject_type(text)


def _inject_type(text: str) -> None:
    from pynput.keyboard import Controller  # lazy: needs a display server

    Controller().type(text)


def _inject_paste(text: str) -> None:
    import pyperclip  # lazy
    from pynput.keyboard import Controller, Key  # lazy

    keyboard = Controller()
    try:
        previous = pyperclip.paste()
    except Exception:
        previous = None

    pyperclip.copy(text)
    modifier = Key.cmd if sys.platform == "darwin" else Key.ctrl
    with keyboard.pressed(modifier):
        keyboard.press("v")
        keyboard.release("v")

    if previous is not None:
        # Give the focused app a moment to read the clipboard before restoring.
        time.sleep(0.3)
        pyperclip.copy(previous)
