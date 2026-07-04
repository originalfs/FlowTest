import queue

import pytest

from localflow.overlay import _COLORS, _LABELS, Overlay


class TestQueueing:
    """show_*/hide only push onto the internal queue -- no Tkinter needed."""

    def test_show_recording_queues_state(self):
        o = Overlay()
        o.show_recording()
        assert o._queue.get_nowait() == "recording"

    def test_show_processing_queues_state(self):
        o = Overlay()
        o.show_processing()
        assert o._queue.get_nowait() == "processing"

    def test_hide_queues_idle(self):
        o = Overlay()
        o.hide()
        assert o._queue.get_nowait() == "idle"

    def test_empty_initially(self):
        o = Overlay()
        with pytest.raises(queue.Empty):
            o._queue.get_nowait()

    def test_preserves_order(self):
        o = Overlay()
        o.show_recording()
        o.show_processing()
        o.hide()
        assert [o._queue.get_nowait() for _ in range(3)] == [
            "recording",
            "processing",
            "idle",
        ]


class FakeWidget:
    """Duck-types just enough of the Tkinter API for _apply() to run."""

    def __init__(self):
        self.calls: list[str] = []
        self.config_kwargs: dict | None = None

    def config(self, **kwargs):
        self.config_kwargs = kwargs

    def configure(self, **kwargs):
        self.config_kwargs = kwargs

    def withdraw(self):
        self.calls.append("withdraw")

    def deiconify(self):
        self.calls.append("deiconify")

    def lift(self):
        self.calls.append("lift")

    def attributes(self, *args, **kwargs):
        self.calls.append("attributes")


class TestApply:
    def _make(self) -> Overlay:
        o = Overlay()
        o._root = FakeWidget()
        o._label = FakeWidget()
        return o

    def test_idle_withdraws_without_touching_label(self):
        o = self._make()
        o._apply("idle")
        assert o._root.calls == ["withdraw"]
        assert o._label.config_kwargs is None

    def test_recording_sets_color_and_shows(self):
        o = self._make()
        o._apply("recording")
        assert o._label.config_kwargs == {
            "text": _LABELS["recording"],
            "bg": _COLORS["recording"],
        }
        assert "deiconify" in o._root.calls
        assert "lift" in o._root.calls

    def test_processing_sets_color_and_shows(self):
        o = self._make()
        o._apply("processing")
        assert o._label.config_kwargs == {
            "text": _LABELS["processing"],
            "bg": _COLORS["processing"],
        }
        assert "deiconify" in o._root.calls
