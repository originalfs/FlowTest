"""Always-on-top visual indicator for recording/processing state.

Uses Tkinter (Python's stdlib GUI toolkit, no extra dependency needed) so
you can see LocalFlow is listening without keeping a console window in
view. A small borderless pill appears in the corner of the screen while
recording or processing, and disappears the rest of the time.
"""

from __future__ import annotations

import queue

_COLORS = {
    "recording": "#e5484d",
    "processing": "#f5a623",
}
_LABELS = {
    "recording": "● Recording...",
    "processing": "● Processing...",
}


class Overlay:
    """Thread-safe: show_recording()/show_processing()/hide() may be called
    from any thread; run() builds the window and blocks in Tkinter's
    mainloop, so it must be called from the main thread.
    """

    def __init__(self, width: int = 190, height: int = 40, margin: int = 20) -> None:
        self.width = width
        self.height = height
        self.margin = margin
        self._queue: "queue.Queue[str]" = queue.Queue()
        self._root = None
        self._label = None

    def show_recording(self) -> None:
        self._queue.put("recording")

    def show_processing(self) -> None:
        self._queue.put("processing")

    def hide(self) -> None:
        self._queue.put("idle")

    def _apply(self, state: str) -> None:
        if state == "idle":
            self._root.withdraw()
            return
        self._label.config(text=_LABELS[state], bg=_COLORS[state])
        self._root.configure(bg=_COLORS[state])
        self._root.deiconify()
        self._root.lift()
        self._root.attributes("-topmost", True)

    def _poll(self) -> None:
        try:
            while True:
                self._apply(self._queue.get_nowait())
        except queue.Empty:
            pass
        # Re-arming every 50ms also lets Ctrl+C interrupt the mainloop
        # promptly, since Tkinter otherwise never yields to the interpreter.
        self._root.after(50, self._poll)

    def run(self) -> None:
        """Build the window and block in Tkinter's mainloop."""
        import tkinter as tk  # lazy: not present on headless/minimal Python installs

        root = tk.Tk()
        root.overrideredirect(True)
        root.attributes("-topmost", True)
        try:
            root.attributes("-alpha", 0.92)
        except tk.TclError:
            pass
        screen_w = root.winfo_screenwidth()
        root.geometry(
            f"{self.width}x{self.height}+{screen_w - self.width - self.margin}+{self.margin}"
        )

        label = tk.Label(root, font=("Segoe UI", 12, "bold"), fg="white")
        label.pack(expand=True, fill="both")

        self._root = root
        self._label = label
        root.withdraw()
        root.after(50, self._poll)
        root.mainloop()

    def stop(self) -> None:
        if self._root is not None:
            self._root.after(0, self._root.destroy)
