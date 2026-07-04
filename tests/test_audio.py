import numpy as np
import pytest

from localflow.audio import _rms_level


class TestRmsLevel:
    def test_silence_is_zero(self):
        chunk = np.zeros((160, 1), dtype=np.float32)
        assert _rms_level(chunk) == 0.0

    def test_empty_chunk_is_zero(self):
        assert _rms_level(np.zeros((0, 1), dtype=np.float32)) == 0.0

    def test_louder_signal_gives_higher_level(self):
        quiet = np.full((160, 1), 0.01, dtype=np.float32)
        loud = np.full((160, 1), 0.05, dtype=np.float32)
        assert _rms_level(loud) > _rms_level(quiet)

    def test_clamped_to_one(self):
        chunk = np.full((160, 1), 1.0, dtype=np.float32)
        assert _rms_level(chunk) == 1.0

    def test_gain_scales_result(self):
        chunk = np.full((160, 1), 0.05, dtype=np.float32)
        assert _rms_level(chunk, gain=1.0) < _rms_level(chunk, gain=8.0)

    @pytest.mark.parametrize("gain", [1.0, 8.0, 20.0])
    def test_result_always_in_unit_range(self, gain):
        chunk = np.random.default_rng(0).uniform(-1, 1, size=(320, 1)).astype(np.float32)
        level = _rms_level(chunk, gain=gain)
        assert 0.0 <= level <= 1.0
