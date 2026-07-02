"""Microphone capture. Records 16 kHz mono float32, the format Whisper expects."""

from __future__ import annotations

import threading


class Recorder:
    """Start/stop microphone recording; returns the captured audio as a numpy array."""

    def __init__(self, sample_rate: int = 16000) -> None:
        self.sample_rate = sample_rate
        self._frames: list = []
        self._stream = None
        self._lock = threading.Lock()

    @property
    def recording(self) -> bool:
        return self._stream is not None

    def start(self) -> None:
        if self._stream is not None:
            return
        import sounddevice as sd  # lazy: needs PortAudio, not present on CI boxes

        self._frames = []

        def callback(indata, frames, time_info, status) -> None:
            with self._lock:
                self._frames.append(indata.copy())

        self._stream = sd.InputStream(
            samplerate=self.sample_rate,
            channels=1,
            dtype="float32",
            callback=callback,
        )
        self._stream.start()

    def stop(self):
        """Stop recording and return mono float32 audio (may be empty)."""
        import numpy as np

        stream, self._stream = self._stream, None
        if stream is not None:
            stream.stop()
            stream.close()
        with self._lock:
            frames, self._frames = self._frames, []
        if not frames:
            return np.zeros(0, dtype=np.float32)
        return np.concatenate(frames).flatten()
