"""Always-on-top dictation indicator: a compact frosted-glass pill.

Modeled on how Wispr Flow, Muesli, and WisprType actually do this (compact
capsule anchored bottom-center, dark glass panel, glowing accent waveform)
rather than a bare colored shape floating in space -- the panel is what
makes it read as a deliberate app widget instead of an abstract blob.

Each frame is composed with Pillow at supersampled resolution (plain
Tkinter canvas can't do gradients, blur, or anti-aliasing): a drop shadow,
a dark rounded-rect glass panel with a subtle outline, and inside it a
smooth mirrored waveform filled with a color gradient whose glow bleeds
softly beyond the panel edge. Teal/indigo while recording (tracking your
live mic volume), amber/red while transcribing (a gentle idle pulse),
invisible the rest of the time.
"""

from __future__ import annotations

import math
import queue

WAVE_POINTS = 64
SUPERSAMPLE = 2

# Left-to-right gradient endpoints per state, for the waveform accent.
_GRADIENTS = {
    "recording": ("#22d3ee", "#818cf8"),
    "processing": ("#fbbf24", "#f87171"),
}
_PANEL_COLOR = "#17161f"
_PANEL_OUTLINE = "#3a3846"
# Chroma-key color made transparent on Windows via -transparentcolor; picked
# far from every hue above so anti-aliased edges never misfire.
_KEY_COLOR = "#fe00fe"

# Smoothing: quick to rise when you start talking, slower to fall afterwards,
# like a real VU meter -- this is what makes the trace look alive rather
# than jittery or, if too slow, flat.
_ATTACK = 0.55
_RELEASE = 0.12
_IDLE_FLOOR = 0.035


def _clamp01(value: float) -> float:
    return max(0.0, min(1.0, value))


def _hex_to_rgb(color: str) -> tuple[int, int, int]:
    color = color.lstrip("#")
    return tuple(int(color[i : i + 2], 16) for i in (0, 2, 4))


def _lerp_color(c1: tuple[int, int, int], c2: tuple[int, int, int], t: float) -> tuple[int, int, int]:
    t = _clamp01(t)
    return tuple(round(c1[i] + (c2[i] - c1[i]) * t) for i in range(3))


class Overlay:
    """Thread-safe: show_recording()/show_processing()/hide()/push_level()
    may be called from any thread. run() builds the window and blocks in
    Tkinter's mainloop, so it must be called from the main thread.
    """

    def __init__(
        self,
        width: int = 320,
        height: int = 150,
        bottom_margin: int = 90,
        pill_width: int = 220,
        pill_height: int = 60,
    ) -> None:
        self.width = width
        self.height = height
        self.bottom_margin = bottom_margin
        self.pill_width = pill_width
        self.pill_height = pill_height
        self._queue: "queue.Queue[tuple[str, object]]" = queue.Queue()
        self._root = None
        self._canvas = None
        self._image_id = None
        self._photo = None  # keep a reference: Tkinter won't hold one for you
        self._gradient_cache: dict[tuple, "object"] = {}
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

    # -- pure animation logic (unit-testable without Tk or Pillow) ----------

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

    # -- Pillow-rendered frame -----------------------------------------------

    def _gradient_image(self, state: str, w: int, h: int):
        """A full-frame left-to-right gradient image, cached per state/size."""
        cache_key = (state, w, h)
        cached = self._gradient_cache.get(cache_key)
        if cached is not None:
            return cached

        import numpy as np
        from PIL import Image

        top_hex, bottom_hex = _GRADIENTS.get(state, _GRADIENTS["recording"])
        top_rgb, bottom_rgb = _hex_to_rgb(top_hex), _hex_to_rgb(bottom_hex)
        t = np.linspace(0.0, 1.0, w)
        row = (np.outer(1 - t, top_rgb) + np.outer(t, bottom_rgb)).astype("uint8")
        array = np.broadcast_to(row, (h, w, 3))
        image = Image.fromarray(array, mode="RGB")
        self._gradient_cache.clear()  # only one state is ever rendered at a time
        self._gradient_cache[cache_key] = image
        return image

    def _wave_mask(self, w: int, h: int, box: tuple[float, float, float, float]):
        """Full-frame (w, h) alpha mask of the waveform, confined to `box`
        (left, top, right, bottom) so it stays inside the glass panel and
        never crosses into the pill's rounded end-caps.
        """
        from PIL import Image, ImageDraw

        left, top, right, bottom = box
        heights = self._heights()
        n = len(heights)
        mid_y = (top + bottom) / 2
        span = right - left
        step = span / (n - 1)
        usable_half = (bottom - top) / 2

        top_pts = []
        bottom_pts = []
        for i, amp in enumerate(heights):
            x = left + i * step
            half = max(1.5 * SUPERSAMPLE, amp * usable_half)
            top_pts.append((x, mid_y - half))
            bottom_pts.append((x, mid_y + half))
        polygon = top_pts + list(reversed(bottom_pts))

        mask = Image.new("L", (w, h), 0)
        ImageDraw.Draw(mask).polygon(polygon, fill=255)
        return mask

    def _render_frame(self):
        """Compose one frame: shadow, glass pill, glow, waveform."""
        from PIL import Image, ImageDraw, ImageFilter

        s = SUPERSAMPLE
        w, h = self.width * s, self.height * s
        pw, ph = self.pill_width * s, self.pill_height * s
        radius = ph / 2
        key_rgb = _hex_to_rgb(_KEY_COLOR)

        px0 = (w - pw) / 2
        py0 = (h - ph) / 2 - 6 * s
        px1, py1 = px0 + pw, py0 + ph
        pill_box = (px0, py0, px1, py1)

        base = Image.new("RGB", (w, h), key_rgb)

        # -- drop shadow: soft, offset down, fading into the transparent key --
        shadow_mask = Image.new("L", (w, h), 0)
        shadow_offset = 8 * s
        ImageDraw.Draw(shadow_mask).rounded_rectangle(
            (px0, py0 + shadow_offset, px1, py1 + shadow_offset), radius=radius, fill=140
        )
        shadow_mask = shadow_mask.filter(ImageFilter.GaussianBlur(radius=12 * s))
        base = Image.composite(Image.new("RGB", (w, h), (0, 0, 0)), base, shadow_mask)

        # -- waveform glow: unclipped, so it softly bleeds past the panel edge --
        wave_box = (px0 + radius, py0 + 10 * s, px1 - radius, py1 - 10 * s)
        wave_mask = self._wave_mask(w, h, wave_box)
        gradient = self._gradient_image(self._state, w, h)
        glow_mask = wave_mask.filter(ImageFilter.GaussianBlur(radius=9 * s)).point(
            lambda p: int(p * 0.9)
        )
        base = Image.composite(gradient, base, glow_mask)

        # -- glass panel: dark rounded pill with a subtle outline --
        panel_mask = Image.new("L", (w, h), 0)
        ImageDraw.Draw(panel_mask).rounded_rectangle(pill_box, radius=radius, fill=255)
        base = Image.composite(Image.new("RGB", (w, h), _hex_to_rgb(_PANEL_COLOR)), base, panel_mask)

        outline = Image.new("L", (w, h), 0)
        ImageDraw.Draw(outline).rounded_rectangle(
            pill_box, radius=radius, outline=255, width=max(1, round(1.5 * s))
        )
        base = Image.composite(Image.new("RGB", (w, h), _hex_to_rgb(_PANEL_OUTLINE)), base, outline)

        # -- waveform, sharp, clipped inside the panel --
        base = Image.composite(gradient, base, wave_mask)

        return base.resize((self.width, self.height), Image.LANCZOS)

    def _redraw(self) -> None:
        from PIL import ImageTk

        frame = self._render_frame()
        self._photo = ImageTk.PhotoImage(frame)
        if self._image_id is None:
            self._image_id = self._canvas.create_image(0, 0, anchor="nw", image=self._photo)
        else:
            self._canvas.itemconfig(self._image_id, image=self._photo)

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
                root.attributes("-alpha", 0.92)
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
