"""Microphone capture. Records 16 kHz mono float32, the format Whisper expects."""

from __future__ import annotations

import math
import threading
from typing import Callable

# Typical speech RMS on a float32 mic stream is roughly 0.01-0.1 -- too small
# a range for a linear gain to look lively. A sqrt (roughly perceptual/dB-like)
# mapping spreads normal speaking volume across most of 0..1 instead of
# hugging the bottom of the range, which is what made the waveform look flat.
_LEVEL_GAIN = 3.2


def _rms_level(chunk, gain: float = _LEVEL_GAIN) -> float:
    """Root-mean-square amplitude of an audio chunk, scaled and clamped to [0, 1]."""
    import numpy as np

    if chunk.size == 0:
        return 0.0
    rms = float(np.sqrt(np.mean(np.square(chunk, dtype="float64"))))
    return max(0.0, min(1.0, math.sqrt(rms) * gain))


class Recorder:
    """Start/stop microphone recording; returns the captured audio as a numpy array."""

    def __init__(
        self,
        sample_rate: int = 16000,
        on_level: Callable[[float], None] | None = None,
    ) -> None:
        self.sample_rate = sample_rate
        self.on_level = on_level
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
            if self.on_level is not None:
                self.on_level(_rms_level(indata))

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
