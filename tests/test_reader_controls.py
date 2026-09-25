"""Image controller coverage without accessing case data."""
from unittest.mock import Mock

import pytest

from focus.app import Focus


class ImageHarness:
    _set_show_image = Focus._set_show_image
    _sync_show_image_action = Focus._sync_show_image_action
    _sync_image_return_button = Focus._sync_image_return_button
    _show_image_update_visible = Focus._show_image_update_visible
    _on_back_to_text_clicked = Focus._on_back_to_text_clicked

    def __init__(self):
        self.pages = [1]
        self.current_index = 0
        self._show_image = False
        self._show_image_action = None
        self._back_to_text_button = Mock()
        self._back_to_text_button.has_focus.return_value = False
        self._content_stack = Mock()
        self._load_image_for_page = Mock(return_value=True)
        self._clear_image_view = Mock()
        self._refresh_search_highlighted_button = Mock()
        self._transient_toast = Mock()
        self.scroller = Mock()
        self.textview = Mock()


def test_image_return_is_explicit_and_restores_focus_without_scrolling():
    harness = ImageHarness()
    assert harness._set_show_image(True)
    harness._back_to_text_button.set_visible.assert_called_with(True)
    harness._content_stack.set_visible_child_name.assert_called_with("image")
    harness._back_to_text_button.has_focus.return_value = True
    harness.scroller.get_vadjustment().get_value.return_value = 120
    harness._on_back_to_text_clicked(None)
    harness._back_to_text_button.set_visible.assert_called_with(False)
    harness._content_stack.set_visible_child_name.assert_called_with("text")
    harness.textview.grab_focus.assert_called_once()
    harness.scroller.get_vadjustment().set_value.assert_called_with(120)
    harness._on_back_to_text_clicked(None)
    assert not harness._show_image


@pytest.mark.parametrize("initial_image", [False, True])
def test_failed_image_load_returns_to_text(initial_image):
    harness = ImageHarness()
    harness._show_image = initial_image
    harness._load_image_for_page.return_value = False
    assert not harness._set_show_image(True)
    assert not harness._show_image
    harness._back_to_text_button.set_visible.assert_called_with(False)
    harness._content_stack.set_visible_child_name.assert_called_with("text")


def test_image_without_pages_stays_hidden():
    harness = ImageHarness()
    harness.pages = []
    assert not harness._set_show_image(True)
    harness._back_to_text_button.set_visible.assert_called_with(False)
