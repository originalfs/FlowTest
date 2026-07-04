import math
import queue

import pytest

from localflow.overlay import WAVE_POINTS, Overlay, _clamp01, _hex_to_rgb, _lerp_color


class TestClamp:
    @pytest.mark.parametrize(
        "value,expected", [(-1, 0.0), (0, 0.0), (0.5, 0.5), (1, 1.0), (2, 1.0)]
    )
    def test_clamp01(self, value, expected):
        assert _clamp01(value) == expected


class TestColorHelpers:
    def test_hex_to_rgb(self):
        assert _hex_to_rgb("#22d3ee") == (0x22, 0xD3, 0xEE)

    def test_hex_to_rgb_without_hash(self):
        assert _hex_to_rgb("6366f1") == (0x63, 0x66, 0xF1)

    def test_lerp_at_endpoints(self):
        c1, c2 = (0, 0, 0), (255, 200, 100)
        assert _lerp_color(c1, c2, 0.0) == c1
        assert _lerp_color(c1, c2, 1.0) == c2

    def test_lerp_midpoint(self):
        assert _lerp_color((0, 0, 0), (200, 100, 50), 0.5) == (100, 50, 25)

    def test_lerp_clamps_t(self):
        c1, c2 = (0, 0, 0), (100, 100, 100)
        assert _lerp_color(c1, c2, -1) == c1
        assert _lerp_color(c1, c2, 2) == c2


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
        assert o._heights() == [0.0] * WAVE_POINTS

    def test_recording_length_matches_wave_points(self):
        o = Overlay()
        o._state = "recording"
        o._level = 0.5
        assert len(o._heights()) == WAVE_POINTS

    def test_recording_rises_toward_loud_level(self):
        o = Overlay()
        o._state = "recording"
        o._level = 0.9
        for _ in range(30):
            heights = o._heights()
        assert heights[-1] == pytest.approx(0.9, abs=0.02)

    def test_recording_has_a_silence_floor_not_flat_zero(self):
        o = Overlay()
        o._state = "recording"
        o._level = 0.0
        for _ in range(30):
            heights = o._heights()
        assert heights[-1] > 0.0

    def test_recording_scrolls_history(self):
        o = Overlay()
        o._state = "recording"
        o._level = 0.0
        for _ in range(30):
            o._heights()
        o._level = 1.0
        first = o._heights()
        second = o._heights()
        # A rising level should push the trailing edge of the trace up over
        # successive frames rather than jumping or staying static.
        assert second[-1] > first[-1]

    def test_processing_oscillates_with_phase(self):
        o = Overlay()
        o._state = "processing"
        o._phase = 0.0
        expected0 = 0.15 + 0.35 * (0.5 + 0.5 * math.sin(0.0))
        assert o._heights()[0] == pytest.approx(expected0)

        o._phase = 1.0
        expected1 = 0.15 + 0.35 * (0.5 + 0.5 * math.sin(1.0))
        assert o._heights()[0] == pytest.approx(expected1)

    def test_processing_heights_stay_in_range(self):
        o = Overlay()
        o._state = "processing"
        for phase_step in range(20):
            o._phase = phase_step * 0.3
            assert all(0.0 <= h <= 1.0 for h in o._heights())
