"""Always-on-top animated waveform indicator for recording/processing state.

Uses Tkinter (Python's stdlib GUI toolkit, no extra dependency needed) so
you can see LocalFlow is listening without keeping a console window in
view. A single smooth, filled waveform shape floats at the bottom-center of
the screen: teal while recording, tracking your live mic volume with a
scrolling amplitude trace; amber while transcribing, with a gentle idle
pulse; invisible the rest of the time.
"""

from __future__ import annotations

import math
import queue

WAVE_POINTS = 48

_COLORS = {
    "recording": "#4fd1c5",
    "processing": "#f5a623",
}
# Background/key color: made transparent on Windows so only the waveform is
# visible, floating over whatever's on screen. Falls back to a faint solid
# background on platforms without -transparentcolor support.
_KEY_COLOR = "#010101"

# Smoothing: quick to rise when you start talking, slower to fall afterwards,
# like a real VU meter -- this is what makes the trace look alive rather
# than jittery or, if too slow, flat.
_ATTACK = 0.55
_RELEASE = 0.12
_IDLE_FLOOR = 0.035


def _clamp01(value: float) -> float:
    return max(0.0, min(1.0, value))


class Overlay:
    """Thread-safe: show_recording()/show_processing()/hide()/push_level()
    may be called from any thread. run() builds the window and blocks in
    Tkinter's mainloop, so it must be called from the main thread.
    """

    def __init__(self, width: int = 340, height: int = 90, bottom_margin: int = 70) -> None:
        self.width = width
        self.height = height
        self.bottom_margin = bottom_margin
        self._queue: "queue.Queue[tuple[str, object]]" = queue.Queue()
        self._root = None
        self._canvas = None
        self._poly_id = None
        self._state = "idle"
        self._level = 0.0
        self._smoothed = 0.0
        self._history = [0.0] * WAVE_POINTS
        self._phase = 0.0

    # -- public, thread-safe API --------------------------------------------

    def show_recording(self) -> None:
        self._queue.put(("state", "recording"))

    def show_processing(self) -> None:
        self._queue.put(("state", "processing"))

    def hide(self) -> None:
        self._queue.put(("state", "idle"))

    def push_level(self, level: float) -> None:
        """Report the current mic input level (0..1) from the audio thread."""
        self._queue.put(("level", _clamp01(level)))

    # -- pure animation logic (unit-testable without a real Tk window) -----

    def _drain_queue(self) -> None:
        try:
            while True:
                kind, value = self._queue.get_nowait()
                if kind == "state":
                    self._set_state(value)
                elif kind == "level":
                    self._level = value
        except queue.Empty:
            pass

    def _set_state(self, state: str) -> None:
        if state == self._state:
            return
        self._state = state
        if self._root is None:
            return
        if state == "idle":
            self._root.withdraw()
        else:
            self._root.deiconify()
            self._root.lift()
            self._root.attributes("-topmost", True)

    def _heights(self) -> list[float]:
        """Amplitude in [0, 1] for each point of the current animation frame."""
        if self._state == "recording":
            target = max(_IDLE_FLOOR, self._level)
            rate = _ATTACK if target > self._smoothed else _RELEASE
            self._smoothed += (target - self._smoothed) * rate
            self._history.append(_clamp01(self._smoothed))
            self._history.pop(0)
            return list(self._history)
        if self._state == "processing":
            return [
                0.15 + 0.35 * (0.5 + 0.5 * math.sin(self._phase + i * 0.35))
                for i in range(WAVE_POINTS)
            ]
        return [0.0] * WAVE_POINTS

    # -- Tk-dependent rendering ----------------------------------------------

    def _redraw(self) -> None:
        color = _COLORS.get(self._state, _COLORS["recording"])
        heights = self._heights()
        n = len(heights)
        mid_y = self.height / 2
        step = self.width / (n - 1)
        usable_half = self.height / 2 - 6

        coords: list[float] = []
        for i, h in enumerate(heights):
            coords.extend((i * step, mid_y - max(2.0, h * usable_half)))
        for i, h in enumerate(reversed(heights)):
            coords.extend(((n - 1 - i) * step, mid_y + max(2.0, h * usable_half)))

        if self._poly_id is None:
            self._poly_id = self._canvas.create_polygon(
                coords, smooth=True, splinesteps=16, fill=color, outline=""
            )
        else:
            self._canvas.coords(self._poly_id, *coords)
            self._canvas.itemconfig(self._poly_id, fill=color)

    def _tick(self) -> None:
        self._drain_queue()
        if self._state != "idle":
            self._phase += 0.2
            self._redraw()
        # Re-arming every ~33ms also lets Ctrl+C interrupt the mainloop
        # promptly, since Tkinter otherwise never yields to the interpreter.
        self._root.after(33, self._tick)

    def run(self) -> None:
        """Build the window and block in Tkinter's mainloop."""
        import tkinter as tk  # lazy: not present on headless/minimal Python installs

        root = tk.Tk()
        root.overrideredirect(True)
        root.attributes("-topmost", True)
        root.configure(bg=_KEY_COLOR)
        try:
            root.attributes("-transparentcolor", _KEY_COLOR)
        except tk.TclError:
            try:
                root.attributes("-alpha", 0.9)
            except tk.TclError:
                pass

        screen_w = root.winfo_screenwidth()
        screen_h = root.winfo_screenheight()
        x = (screen_w - self.width) // 2
        y = screen_h - self.height - self.bottom_margin
        root.geometry(f"{self.width}x{self.height}+{x}+{y}")

        canvas = tk.Canvas(
            root, width=self.width, height=self.height, bg=_KEY_COLOR, highlightthickness=0
        )
        canvas.pack(fill="both", expand=True)

        self._root = root
        self._canvas = canvas
        root.withdraw()
        root.after(33, self._tick)
        root.mainloop()

    def stop(self) -> None:
        if self._root is not None:
            self._root.after(0, self._root.destroy)
