import math
import queue

import pytest

from localflow.overlay import BAR_COUNT, Overlay, _clamp01


class TestClamp:
    @pytest.mark.parametrize(
        "value,expected", [(-1, 0.0), (0, 0.0), (0.5, 0.5), (1, 1.0), (2, 1.0)]
    )
    def test_clamp01(self, value, expected):
        assert _clamp01(value) == expected


class TestQueueing:
    """show_*/hide/push_level only push onto the internal queue -- no Tk needed."""

    def test_show_recording_queues_state(self):
        o = Overlay()
        o.show_recording()
        assert o._queue.get_nowait() == ("state", "recording")

    def test_show_processing_queues_state(self):
        o = Overlay()
        o.show_processing()
        assert o._queue.get_nowait() == ("state", "processing")

    def test_hide_queues_idle(self):
        o = Overlay()
        o.hide()
        assert o._queue.get_nowait() == ("state", "idle")

    def test_push_level_queues_clamped_value(self):
        o = Overlay()
        o.push_level(1.7)
        assert o._queue.get_nowait() == ("level", 1.0)

    def test_empty_initially(self):
        o = Overlay()
        with pytest.raises(queue.Empty):
            o._queue.get_nowait()


class FakeWidget:
    """Duck-types just enough of the Tkinter API for _set_state() to run."""

    def __init__(self):
        self.calls: list[str] = []

    def withdraw(self):
        self.calls.append("withdraw")

    def deiconify(self):
        self.calls.append("deiconify")

    def lift(self):
        self.calls.append("lift")

    def attributes(self, *args, **kwargs):
        self.calls.append("attributes")


class TestDrainQueue:
    def test_state_change_hides_and_shows(self):
        o = Overlay()
        o._root = FakeWidget()
        o.show_recording()
        o._drain_queue()
        assert o._state == "recording"
        assert "deiconify" in o._root.calls

        o.hide()
        o._drain_queue()
        assert o._state == "idle"
        assert "withdraw" in o._root.calls

    def test_repeated_same_state_is_a_noop(self):
        o = Overlay()
        o._root = FakeWidget()
        o.show_recording()
        o._drain_queue()
        o._root.calls.clear()
        o.show_recording()
        o._drain_queue()
        assert o._root.calls == []

    def test_level_updates_stored_level(self):
        o = Overlay()
        o._root = FakeWidget()
        o.push_level(0.42)
        o._drain_queue()
        assert o._level == 0.42


class TestHeights:
    def test_idle_is_all_zero(self):
        o = Overlay()
        o._state = "idle"
        assert o._heights() == [0.0] * BAR_COUNT

    def test_recording_reacts_to_level(self, monkeypatch):
        monkeypatch.setattr("random.uniform", lambda a, b: 1.0)
        o = Overlay()
        o._state = "recording"
        o._level = 0.5
        heights = o._heights()
        assert len(heights) == BAR_COUNT
        assert all(h == pytest.approx(0.5) for h in heights)

    def test_recording_has_a_silence_floor(self, monkeypatch):
        monkeypatch.setattr("random.uniform", lambda a, b: 1.0)
        o = Overlay()
        o._state = "recording"
        o._level = 0.0
        assert all(h == pytest.approx(0.08) for h in o._heights())

    def test_processing_oscillates_with_phase(self):
        o = Overlay()
        o._state = "processing"
        o._phase = 0.0
        expected0 = 0.15 + 0.5 * (0.5 + 0.5 * math.sin(0.0))
        assert o._heights()[0] == pytest.approx(expected0)

        o._phase = 1.0
        expected1 = 0.15 + 0.5 * (0.5 + 0.5 * math.sin(1.0))
        assert o._heights()[0] == pytest.approx(expected1)

    def test_processing_heights_stay_in_range(self):
        o = Overlay()
        o._state = "processing"
        for phase_step in range(20):
            o._phase = phase_step * 0.3
            assert all(0.0 <= h <= 1.0 for h in o._heights())
