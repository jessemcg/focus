"""Navigation callbacks: no case files, GUI activation or delivery."""
from types import SimpleNamespace
from unittest.mock import Mock

from focus.app import Focus
from gi.repository import Gtk


def test_primary_click_advances_once():
    app = SimpleNamespace(_go_next=Mock(), _go_prev=Mock())
    Focus._on_right_scroll_zone_clicked(app, None)
    app._go_next.assert_called_once_with()
    app._go_prev.assert_not_called()


def test_secondary_click_claims_sequence_and_goes_back_once_per_press():
    app = SimpleNamespace(_go_next=Mock(), _go_prev=Mock())
    gesture = Mock()
    for count in (1, 2):
        Focus._on_right_scroll_zone_right_pressed(app, gesture, count, 10, 20)
    assert app._go_prev.call_count == 2
    assert gesture.set_state.call_count == 2
    gesture.set_state.assert_called_with(Gtk.EventSequenceState.CLAIMED)
    app._go_next.assert_not_called()


def test_wheel_directions_and_zero_are_unchanged():
    app = SimpleNamespace(_go_next=Mock(), _go_prev=Mock())
    assert Focus._on_right_scroll_zone_scroll(app, None, 0, 1)
    assert Focus._on_right_scroll_zone_scroll(app, None, 0, -1)
    assert not Focus._on_right_scroll_zone_scroll(app, None, 1, 0)
    app._go_next.assert_called_once_with()
    app._go_prev.assert_called_once_with()
