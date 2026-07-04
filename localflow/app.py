"""Orchestrator: hotkey -> record -> transcribe -> clean -> inject -> history."""

from __future__ import annotations

import sys
import threading
import time

from . import history
from .audio import Recorder
from .cleanup import clean
from .config import Config
from .hotkey import HotkeyListener
from .inject import inject_text
from .transcriber import Transcriber

try:
    import tkinter  # noqa: F401

    _OVERLAY_SUPPORTED = True
except ImportError:
    _OVERLAY_SUPPORTED = False


class App:
    def __init__(self, cfg: Config) -> None:
        self.cfg = cfg
        self.overlay = None
        self.recorder = Recorder(
            sample_rate=cfg.sample_rate,
            on_level=lambda level: self.overlay.push_level(level) if self.overlay else None,
        )
        self.transcriber = Transcriber(
            model=cfg.model,
            device=cfg.device,
            compute_type=cfg.compute_type,
            language=cfg.language,
        )
        self._started_at = 0.0
        self._busy = threading.Lock()

    # -- hotkey edges ------------------------------------------------------

    def _on_activate(self) -> None:
        if self.cfg.mode == "toggle" and self.recorder.recording:
            self._finish()
            return
        self._start()

    def _on_deactivate(self) -> None:
        if self.cfg.mode == "push_to_talk" and self.recorder.recording:
            self._finish()

    # -- pipeline ----------------------------------------------------------

    def _start(self) -> None:
        self.recorder.start()
        self._started_at = time.monotonic()
        if self.overlay is not None:
            self.overlay.show_recording()
        print("● recording... (release to transcribe)" if self.cfg.mode == "push_to_talk"
              else "● recording... (press hotkey again to stop)", flush=True)

    def _finish(self) -> None:
        audio = self.recorder.stop()
        duration = time.monotonic() - self._started_at
        # Process off the hotkey listener thread so new dictations aren't blocked.
        threading.Thread(
            target=self._process, args=(audio, duration), daemon=True
        ).start()

    def _process(self, audio, duration: float) -> None:
        if len(audio) < self.cfg.sample_rate // 10:  # < 0.1s: accidental tap
            print("(too short, ignored)", flush=True)
            if self.overlay is not None:
                self.overlay.hide()
            return
        with self._busy:
            try:
                if self.overlay is not None:
                    self.overlay.show_processing()
                raw = self.transcriber.transcribe(audio)
                if not raw:
                    print("(no speech detected)", flush=True)
                    return
                text = clean(
                    raw,
                    remove_filler_words=self.cfg.remove_fillers,
                    dictionary=self.cfg.dictionary,
                    capitalize=self.cfg.capitalize_sentences,
                )
                inject_text(text, method=self.cfg.injection)
                print(f"→ {text}", flush=True)
                if self.cfg.save_history:
                    history.record(raw=raw, cleaned=text, duration_seconds=duration)
            finally:
                if self.overlay is not None:
                    self.overlay.hide()

    # -- entry point -------------------------------------------------------

    def run(self) -> None:
        print(f"LocalFlow — private local dictation (model: {self.cfg.model})")
        print("Loading Whisper model...", flush=True)
        self.transcriber.load()
        mode_hint = "hold" if self.cfg.mode == "push_to_talk" else "press"
        print(f"Ready. {mode_hint.capitalize()} {self.cfg.hotkey} to dictate. Ctrl+C to quit.")
        listener = HotkeyListener(
            self.cfg.hotkey,
            on_activate=self._on_activate,
            on_deactivate=self._on_deactivate,
        )

        if not (self.cfg.show_overlay and _OVERLAY_SUPPORTED):
            if self.cfg.show_overlay:
                print("(visual overlay needs Tkinter, which isn't installed; skipping)")
            self._run_listener(listener)
            return

        from .overlay import Overlay

        self.overlay = Overlay()
        threading.Thread(target=self._run_listener, args=(listener,), daemon=True).start()
        try:
            self.overlay.run()
        except KeyboardInterrupt:
            print("\nbye")
            sys.exit(0)

    def _run_listener(self, listener: HotkeyListener) -> None:
        try:
            listener.run()
        except KeyboardInterrupt:
            print("\nbye")
            sys.exit(0)
