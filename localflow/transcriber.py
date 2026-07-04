"""Local speech-to-text via faster-whisper (CTranslate2 Whisper).

The model file is downloaded once from Hugging Face on first use and cached
locally; transcription itself runs entirely offline. Pre-download with
`localflow download` if you want to go fully offline before first dictation.
"""

from __future__ import annotations

import sys

# CTranslate2 defers loading CUDA shared libraries until the first inference
# call, so a missing cuBLAS/cuDNN DLL (common on Windows when the nvidia-*
# pip packages aren't on PATH) surfaces here, not in WhisperModel(). We detect
# that specific failure and fall back to CPU rather than crash the session.
_CUDA_LIBRARY_MARKERS = ("cublas", "cudnn", "nvrtc")


def _looks_like_missing_cuda_library(exc: Exception) -> bool:
    message = str(exc).lower()
    if not any(marker in message for marker in _CUDA_LIBRARY_MARKERS):
        return False
    return "not found" in message or "cannot be loaded" in message


class Transcriber:
    def __init__(
        self,
        model: str = "base",
        device: str = "auto",
        compute_type: str = "auto",
        language: str | None = None,
    ) -> None:
        self.model_name = model
        self.device = device
        self.compute_type = compute_type
        self.language = language
        self._model = None
        self._fell_back_to_cpu = False

    def load(self) -> None:
        """Load the model into memory (lazy; called automatically on first use)."""
        if self._model is not None:
            return
        from faster_whisper import WhisperModel  # lazy: heavy import

        self._model = WhisperModel(
            self.model_name,
            device=self.device,
            compute_type=self.compute_type,
        )

    def _reload_on_cpu(self) -> None:
        from faster_whisper import WhisperModel  # lazy: heavy import

        print(
            "warning: GPU acceleration unavailable (a CUDA library failed to load); "
            "falling back to CPU for this session. See the README for how to fix "
            "the GPU setup permanently.",
            file=sys.stderr,
        )
        self.device = "cpu"
        self.compute_type = "int8"
        self._model = WhisperModel(
            self.model_name,
            device=self.device,
            compute_type=self.compute_type,
        )
        self._fell_back_to_cpu = True

    def _run(self, audio) -> str:
        segments, _info = self._model.transcribe(
            audio,
            language=self.language,
            vad_filter=True,
            beam_size=5,
        )
        return " ".join(seg.text.strip() for seg in segments).strip()

    def transcribe(self, audio) -> str:
        """Transcribe a 16 kHz mono float32 numpy array (or a path to an audio file)."""
        self.load()
        try:
            return self._run(audio)
        except RuntimeError as exc:
            if self._fell_back_to_cpu or not _looks_like_missing_cuda_library(exc):
                raise
            self._reload_on_cpu()
            return self._run(audio)
