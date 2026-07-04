import pytest

from localflow.transcriber import Transcriber, _looks_like_missing_cuda_library


class TestLooksLikeMissingCudaLibrary:
    @pytest.mark.parametrize(
        "message",
        [
            "Library cublas64_12.dll is not found or cannot be loaded",
            "Library cudnn64_9.dll is not found or cannot be loaded",
            "libcublas.so.12: cannot be loaded",
            "NVRTC library not found",
        ],
    )
    def test_detects_missing_cuda_library(self, message):
        assert _looks_like_missing_cuda_library(RuntimeError(message))

    @pytest.mark.parametrize(
        "message",
        [
            "CUDA out of memory",
            "some unrelated failure",
            "",
        ],
    )
    def test_ignores_unrelated_errors(self, message):
        assert not _looks_like_missing_cuda_library(RuntimeError(message))


class FakeModel:
    """Stands in for faster_whisper.WhisperModel."""

    def __init__(self, fail_times: int = 0, error: Exception | None = None):
        self.fail_times = fail_times
        self.error = error or RuntimeError(
            "Library cublas64_12.dll is not found or cannot be loaded"
        )
        self.calls = 0

    def transcribe(self, audio, **kwargs):
        self.calls += 1
        if self.calls <= self.fail_times:
            raise self.error

        class Seg:
            def __init__(self, text):
                self.text = text

        return [Seg("hello"), Seg("world")], object()


class TestTranscribeFallback:
    def _make(self, fake_model) -> Transcriber:
        t = Transcriber(device="cuda")
        t._model = fake_model
        return t

    def test_succeeds_without_error(self):
        t = self._make(FakeModel(fail_times=0))
        assert t.transcribe("audio") == "hello world"
        assert not t._fell_back_to_cpu

    def test_falls_back_to_cpu_on_cuda_library_error(self, monkeypatch):
        first = FakeModel(fail_times=1)
        t = self._make(first)

        replacement = FakeModel(fail_times=0)
        monkeypatch.setattr(
            Transcriber,
            "_reload_on_cpu",
            lambda self: (setattr(self, "_model", replacement), setattr(self, "_fell_back_to_cpu", True)),
        )

        assert t.transcribe("audio") == "hello world"
        assert t._fell_back_to_cpu

    def test_does_not_retry_twice(self, monkeypatch):
        model = FakeModel(fail_times=99)
        t = self._make(model)
        t._fell_back_to_cpu = True  # simulate already having fallen back once

        with pytest.raises(RuntimeError):
            t.transcribe("audio")

    def test_reraises_unrelated_errors(self):
        model = FakeModel(fail_times=1, error=RuntimeError("disk full"))
        t = self._make(model)

        with pytest.raises(RuntimeError, match="disk full"):
            t.transcribe("audio")
