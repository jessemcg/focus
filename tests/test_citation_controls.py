from dataclasses import replace
from unittest.mock import Mock

import pytest

from focus.app import Focus
from focus.core import TranscriptPageIndex, TranscriptPageLabel
from focus.citation_extent import resolve_citation_extent


def _label(file_page: int, citation_label: str) -> TranscriptPageLabel:
    citation_prefix, page_number = citation_label.split()
    return TranscriptPageLabel(
        file_page=file_page, transcript_page_number=int(page_number),
        citation_prefix=citation_prefix, citation_label=citation_label,
        citation_key=citation_label.lower(), record_type="reporter_transcript",
        series_id=citation_prefix.lower(), series_description=citation_prefix,
        status="official",
    )


class CitationHarness:
    _insert_page_citation_range_in_prose_or_clipboard = Focus._insert_page_citation_range_in_prose_or_clipboard
    _on_current_page_citation_clicked = Focus._on_current_page_citation_clicked
    _citation_additional_pages = Focus._citation_additional_pages
    _clear_citation_extent = Focus._clear_citation_extent
    _resolve_citation_extent = Focus._resolve_citation_extent
    _set_citation_extent = Focus._set_citation_extent
    _commit_citation_count = Focus._commit_citation_count
    _on_citation_count_activate = Focus._on_citation_count_activate
    _on_citation_step_clicked = Focus._on_citation_step_clicked
    _on_citation_end_here_clicked = Focus._on_citation_end_here_clicked
    _sync_citation_buttons = Focus._sync_citation_buttons

    def __init__(self):
        self.pages = list(range(41, 46))
        self.current_page = 41
        self._transcript_page_index = TranscriptPageIndex(
            {i: _label(i, f"RT {i + 4}") for i in self.pages}, {}, {}
        )
        self._page_citation_range_start = None
        self._page_citation_range_end = None
        self._citation_count_entry = Mock()
        self._citation_count_entry.get_text.side_effect = lambda: self.count_text
        self._citation_count_entry.set_text.side_effect = self._set_count_text
        self.count_text = "+0"
        for name in ("_current_page_citation_button", "_citation_less_button",
                     "_citation_more_button", "_citation_preview_label", "_citation_end_here_button"):
            setattr(self, name, Mock())
        self._citation_end_here_button.has_focus.return_value = False
        self._send_text_to_prose_record_citations_action = Mock(return_value=True)
        self._copy_text_to_clipboard = Mock(return_value=True)
        self._transient_toast = Mock()
        self._insert_current_page_citation_in_prose_or_clipboard = Mock(return_value=True)

    def _set_count_text(self, text):
        self.count_text = text

    def _current_page_number(self):
        return self.current_page if self.pages else None

    def _current_transcript_page_label(self):
        return self._transcript_page_index.by_file_page.get(self._current_page_number())


def test_primary_at_zero_inserts_current_page_once():
    app = CitationHarness()
    app._on_current_page_citation_clicked(None)
    app._insert_current_page_citation_in_prose_or_clipboard.assert_called_once()
    app._send_text_to_prose_record_citations_action.assert_not_called()


def test_two_plus_clicks_anchor_through_navigation_then_cite_and_reset():
    app = CitationHarness()
    app._on_citation_step_clicked(None, 1)
    app._on_citation_step_clicked(None, 1)
    assert app.count_text == "+2"
    app.current_page = 45
    app._sync_citation_buttons()
    assert app.count_text == "+2"
    app._citation_preview_label.set_label.assert_called_with("RT 45–47")
    app._citation_end_here_button.set_visible.assert_called_with(True)
    description = app._current_page_citation_button.set_tooltip_text.call_args.args[0]
    assert "RT 45–47" in description and "3 pages" in description
    app._on_current_page_citation_clicked(None)
    app._send_text_to_prose_record_citations_action.assert_called_once_with("(RT 45–47.)")
    app._insert_current_page_citation_in_prose_or_clipboard.assert_not_called()
    assert app.count_text == "+0"
    assert app._page_citation_range_start is None
    assert app._page_citation_range_end is None


def test_end_here_sets_endpoint_not_anchor_then_minus_to_zero_cancels():
    app = CitationHarness()
    app._set_citation_extent(1)
    app.current_page = 44
    app._on_citation_end_here_clicked(None)
    assert app._page_citation_range_start.file_page == 41
    assert app._page_citation_range_end.file_page == 44
    assert app.count_text == "+3"
    app.current_page = 45
    for _ in range(3):
        app._on_citation_step_clicked(None, -1)
    assert app._page_citation_range_start is None
    app._on_current_page_citation_clicked(None)
    app._insert_current_page_citation_in_prose_or_clipboard.assert_called_once()


def test_end_here_can_shorten_range_and_rejects_page_before_start():
    app = CitationHarness()
    app.current_page = 42
    app._set_citation_extent(3)
    app.current_page = 43
    app._on_citation_end_here_clicked(None)
    assert app.count_text == "+1"
    app.current_page = 41
    app._sync_citation_buttons()
    app._citation_end_here_button.set_sensitive.assert_called_with(False)
    app._on_citation_end_here_clicked(None)
    assert app.count_text == "+1"
    app._transient_toast.assert_called_once()


@pytest.mark.parametrize("text", ["-1", "oops", "1.5", "999999"])
def test_invalid_typed_count_preserves_extent_and_does_not_send(text):
    app = CitationHarness()
    app._set_citation_extent(1)
    app.count_text = text
    app._on_current_page_citation_clicked(None)
    assert app.count_text == "+1"
    app._send_text_to_prose_record_citations_action.assert_not_called()
    app._transient_toast.assert_called_once()


def test_edit_count_commits_on_enter_and_on_cite():
    app = CitationHarness()
    app.count_text = "2"
    app._on_citation_count_activate(None)
    assert app.count_text == "+2"
    app.count_text = "3"
    app._on_current_page_citation_clicked(None)
    app._send_text_to_prose_record_citations_action.assert_called_once_with("(RT 45–48.)")


@pytest.mark.parametrize("clipboard_ok", [False, True])
def test_delivery_fallback_only_clears_after_success(clipboard_ok):
    app = CitationHarness()
    app._set_citation_extent(2)
    app._send_text_to_prose_record_citations_action.return_value = False
    app._copy_text_to_clipboard.return_value = clipboard_ok
    app._on_current_page_citation_clicked(None)
    app._copy_text_to_clipboard.assert_called_once_with("(RT 45–47.)")
    assert (app._page_citation_range_start is None) == clipboard_ok
    assert app.count_text == ("+0" if clipboard_ok else "+2")


def test_typed_zero_cancels_and_preview_is_hidden_at_rest():
    app = CitationHarness()
    app._set_citation_extent(2)
    app.current_page = 44
    app.count_text = "0"
    app._on_citation_count_activate(None)
    assert app._page_citation_range_start is None
    assert app.count_text == "+0"
    app._citation_preview_label.set_visible.assert_called_with(False)
    app._send_text_to_prose_record_citations_action.assert_not_called()


def test_end_here_is_hidden_back_at_anchor_without_cancelling_range():
    app = CitationHarness()
    app._set_citation_extent(2)
    app.current_page = 44
    app._sync_citation_buttons()
    app._citation_end_here_button.set_visible.assert_called_with(True)
    app.current_page = 41
    app._sync_citation_buttons()
    app._citation_end_here_button.set_visible.assert_called_with(False)
    assert app.count_text == "+2"


def test_no_pages_disables_all_citation_controls():
    app = CitationHarness()
    app.pages = []
    app._sync_citation_buttons()
    for button in (app._current_page_citation_button, app._citation_count_entry,
                   app._citation_more_button, app._citation_less_button):
        button.set_sensitive.assert_called_with(False)
    app._citation_preview_label.set_visible.assert_called_with(False)
    app._citation_end_here_button.set_visible.assert_called_with(False)


def test_end_of_record_disables_plus_with_explanation():
    app = CitationHarness()
    app.current_page = 45
    app._sync_citation_buttons()
    app._citation_more_button.set_sensitive.assert_called_with(False)
    assert app._citation_more_button.set_tooltip_text.call_args.args[0]


def test_existing_two_press_range_shortcut_remains_start_then_current_end():
    app = CitationHarness()
    assert app._insert_page_citation_range_in_prose_or_clipboard()
    app._send_text_to_prose_record_citations_action.assert_not_called()
    assert app._page_citation_range_start.file_page == 41
    app.current_page = 44
    app._sync_citation_buttons()
    assert app._insert_page_citation_range_in_prose_or_clipboard()
    app._send_text_to_prose_record_citations_action.assert_called_once_with("(RT 45–48.)")
    assert app._page_citation_range_start is None
    assert app._page_citation_range_end is None


def test_invalid_shortcut_range_retains_anchor():
    app = CitationHarness()
    app._insert_page_citation_range_in_prose_or_clipboard()
    app.current_page = 44
    app._transcript_page_index.by_file_page[44] = _label(44, "CT 48")
    assert not app._insert_page_citation_range_in_prose_or_clipboard()
    assert app._page_citation_range_start.file_page == 41
    app._transient_toast.assert_called_once()


@pytest.mark.parametrize("break_kind", ["missing_file", "missing_label", "prefix", "series", "restart"])
def test_extent_checks_intermediate_pages_not_just_endpoints(break_kind):
    app = CitationHarness()
    index = app._transcript_page_index
    if break_kind == "missing_file":
        app.pages.remove(42)
    elif break_kind == "missing_label":
        del index.by_file_page[42]
    elif break_kind == "prefix":
        index.by_file_page[42] = _label(42, "CT 46")
    elif break_kind == "series":
        index.by_file_page[42] = replace(index.by_file_page[42], series_id="another-volume")
    else:
        index.by_file_page[42] = _label(42, "RT 1")
    with pytest.raises(ValueError):
        resolve_citation_extent(index.by_file_page[41], 2, app.pages, index)
    assert not app._set_citation_extent(2)
    assert app._page_citation_range_start is None
