"""Local speech-to-text via faster-whisper (CTranslate2 Whisper).

The model file is downloaded once from Hugging Face on first use and cached
locally; transcription itself runs entirely offline. Pre-download with
`localflow download` if you want to go fully offline before first dictation.
"""

from __future__ import annotations


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

    def transcribe(self, audio) -> str:
        """Transcribe a 16 kHz mono float32 numpy array (or a path to an audio file)."""
        self.load()
        segments, _info = self._model.transcribe(
            audio,
            language=self.language,
            vad_filter=True,
            beam_size=5,
        )
        return " ".join(seg.text.strip() for seg in segments).strip()
