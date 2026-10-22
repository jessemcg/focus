"""Two-click range controls share validation with the public citation actions."""
from dataclasses import replace
from unittest.mock import Mock

import pytest

from focus.app import Focus
from focus.core import (TranscriptPageIndex, TranscriptPageLabel,
                        format_page_citation_range_for_clipboard)
from focus.citation_extent import resolve_citation_extent, resolve_citation_range


def _label(file_page: int, citation_label: str) -> TranscriptPageLabel:
    citation_prefix, page_number = citation_label.rsplit(" ", 1)
    return TranscriptPageLabel(
        file_page=file_page, transcript_page_number=int(page_number),
        citation_prefix=citation_prefix, citation_label=citation_label,
        citation_key=citation_label.lower(), record_type="reporter_transcript",
        series_id=citation_prefix.lower(), series_description=citation_prefix,
        status="official",
    )


class CitationHarness:
    for _name in (
        "_insert_page_citation_range_in_prose_or_clipboard",
        "_insert_current_page_citation_in_prose_or_clipboard", "_deliver_citation",
        "_on_current_page_citation_clicked", "_on_citation_range_clicked",
        "_on_citation_cancel_clicked", "_clear_citation_extent",
        "_resolve_current_citation_range", "_sync_citation_buttons",
        "_current_page_citation_for_clipboard",
    ):
        locals()[_name] = getattr(Focus, _name)

    def __init__(self):
        self.pages = list(range(41, 46))
        self.current_page = 41
        self._transcript_page_index = TranscriptPageIndex(
            {i: _label(i, f"RT {i + 4}") for i in self.pages}, {}, {}
        )
        self._page_citation_range_start = None
        for name in ("_current_page_citation_button", "_citation_range_button",
                     "_citation_range_label", "_citation_cancel_button"):
            setattr(self, name, Mock())
        self._citation_cancel_button.is_focus.return_value = False
        self._send_text_to_prose_record_citations_action = Mock(return_value=True)
        self._copy_text_to_clipboard = Mock(return_value=True)
        self._transient_toast = Mock()

    def _current_page_number(self):
        return self.current_page if self.pages else None

    def _current_transcript_page_label(self):
        return self._transcript_page_index.by_file_page.get(self._current_page_number())

    def start(self):
        assert self._insert_page_citation_range_in_prose_or_clipboard()
        self._copy_text_to_clipboard.assert_not_called()
        self._send_text_to_prose_record_citations_action.assert_not_called()


def test_one_explicit_page_click_delivers_once_without_starting_range():
    app = CitationHarness()
    app._on_current_page_citation_clicked(None)
    app._copy_text_to_clipboard.assert_called_once_with("(RT 45.)")
    app._send_text_to_prose_record_citations_action.assert_called_once_with("(RT 45.)")
    assert app._page_citation_range_start is None


def test_one_click_current_page_independent_of_pending_range():
    app = CitationHarness()
    app.start()
    app.current_page = 44
    app._on_current_page_citation_clicked(None)
    app._copy_text_to_clipboard.assert_called_once_with("(RT 48.)")
    app._send_text_to_prose_record_citations_action.assert_called_once_with("(RT 48.)")
    assert app._page_citation_range_start.file_page == 41


@pytest.mark.parametrize("start,end", [(41, 44), (44, 41), (41, 41)])
@pytest.mark.parametrize("button", [True, False])
def test_start_complete_normalizes_both_directions_and_same_page(start, end, button):
    app = CitationHarness()
    app.current_page = start
    app.start()
    app.current_page = end
    app._sync_citation_buttons()
    expected = "(RT 45.)" if start == end else "(RT 45–48.)"
    app._citation_range_label.set_label.assert_called_with(f"Cite {expected[1:-2]}")
    if button:
        app._on_citation_range_clicked(None)
    else:
        assert app._insert_page_citation_range_in_prose_or_clipboard()
    app._copy_text_to_clipboard.assert_called_once_with(expected)
    app._send_text_to_prose_record_citations_action.assert_called_once_with(expected)
    assert app._page_citation_range_start is None
    app._current_page_citation_button.set_visible.assert_called_with(True)
    app._citation_cancel_button.set_visible.assert_called_with(False)


def test_live_preview_shortens_crosses_anchor_and_returns_without_delivery_or_focus_theft():
    app = CitationHarness()
    app.current_page = 43
    app.start()
    for page, preview in [(45, "47–49"), (44, "47–48"), (43, "47"),
                          (41, "45–47"), (43, "47")]:
        app.current_page = page
        app._sync_citation_buttons()
        app._citation_range_label.set_label.assert_called_with(f"Cite RT {preview}")
        assert app._page_citation_range_start.file_page == 43
    app._copy_text_to_clipboard.assert_not_called()
    app._send_text_to_prose_record_citations_action.assert_not_called()
    app._citation_range_button.grab_focus.assert_not_called()
    description = app._citation_range_button.set_tooltip_text.call_args.args[0]
    assert "(RT 47.)" in description and "1 page" in description
    assert "Anchored at RT 47" in description and "Click to cite" in description


def test_cancel_only_clears_anchor_and_returns_focus_if_cancel_was_focused():
    app = CitationHarness()
    app.start()
    app.current_page = 44
    app._citation_cancel_button.is_focus.return_value = True
    app._on_citation_cancel_clicked(None)
    assert app._page_citation_range_start is None and app.current_page == 44
    app._copy_text_to_clipboard.assert_not_called()
    app._send_text_to_prose_record_citations_action.assert_not_called()
    app._citation_range_button.grab_focus.assert_called_once()


@pytest.mark.parametrize("copied,sent,message", [
    (True, True, "Citation copied and sent to Prose."),
    (True, False, "Citation copied."),
    (False, True, "Sent to Prose; clipboard unavailable."),
    (False, False, "Citation not delivered: clipboard and Prose are unavailable."),
])
def test_independent_delivery_routes_and_range_retention(copied, sent, message):
    app = CitationHarness()
    app.start()
    app.current_page = 43
    order = []
    app._copy_text_to_clipboard.side_effect = lambda text: order.append("copy") or copied
    app._send_text_to_prose_record_citations_action.side_effect = lambda text: order.append("prose") or sent
    assert app._insert_page_citation_range_in_prose_or_clipboard() == (copied or sent)
    assert order == ["copy", "prose"]
    assert (app._page_citation_range_start is None) == (copied or sent)
    app._transient_toast.assert_called_with(message)


@pytest.mark.parametrize("route", ["_copy_text_to_clipboard", "_send_text_to_prose_record_citations_action"])
def test_delivery_exception_does_not_prevent_other_route(route):
    app = CitationHarness()
    app.start()
    getattr(app, route).side_effect = RuntimeError("unavailable")
    assert app._insert_page_citation_range_in_prose_or_clipboard()
    app._copy_text_to_clipboard.assert_called_once()
    app._send_text_to_prose_record_citations_action.assert_called_once()


@pytest.mark.parametrize("break_kind", ["missing_file", "missing_label", "prefix", "series",
                                        "record_type", "restart", "gap"])
@pytest.mark.parametrize("backward", [False, True])
def test_interior_validation_shared_by_preview_button_and_shortcut(break_kind, backward):
    app = CitationHarness()
    app.current_page = 43 if backward else 41
    app.start()
    index = app._transcript_page_index
    original = index.by_file_page[42]
    if break_kind == "missing_file":
        app.pages.remove(42)
    elif break_kind == "missing_label":
        del index.by_file_page[42]
    elif break_kind == "prefix":
        index.by_file_page[42] = _label(42, "CT 46")
    elif break_kind in ("series", "record_type"):
        field = "series_id" if break_kind == "series" else "record_type"
        index.by_file_page[42] = replace(original, **{field: "other"})
    else:
        index.by_file_page[42] = _label(42, "RT 1" if break_kind == "restart" else "RT 99")
    app.current_page = 41 if backward else 43
    app._sync_citation_buttons()
    app._citation_range_button.set_sensitive.assert_called_with(False)
    anchor = app._page_citation_range_start
    app._citation_range_label.set_label.assert_called_with(f"From {anchor.citation_label}…")
    assert not app._insert_page_citation_range_in_prose_or_clipboard()
    assert app._page_citation_range_start is anchor
    app._copy_text_to_clipboard.assert_not_called()
    with pytest.raises(ValueError):
        resolve_citation_range(anchor, app._current_transcript_page_label(), app.pages, index)
    # Returning to the anchor restores completion, no restart needed.
    app.current_page = anchor.file_page
    app._sync_citation_buttons()
    app._citation_range_button.set_sensitive.assert_called_with(True)
    app._citation_cancel_button.set_visible.assert_called_with(True)


@pytest.mark.parametrize("which", ["anchor", "endpoint"])
@pytest.mark.parametrize("change", ["removed_file", "removed_label", "identity"])
def test_stale_endpoints_rejected_even_at_zero_extent(which, change):
    app = CitationHarness()
    index = app._transcript_page_index
    anchor, endpoint = index.by_file_page[41], index.by_file_page[43]
    page = anchor.file_page if which == "anchor" else endpoint.file_page
    if change == "removed_file":
        app.pages.remove(page)
    elif change == "removed_label":
        del index.by_file_page[page]
    else:
        index.by_file_page[page] = replace(index.by_file_page[page], citation_label="RT 999")
    with pytest.raises(ValueError):
        resolve_citation_range(anchor, endpoint, app.pages, index)
    stale = anchor if which == "anchor" else endpoint
    with pytest.raises(ValueError):
        resolve_citation_extent(stale, 0, app.pages, index)


def test_cross_series_matching_prefix_and_direct_formatter_reversal():
    app = CitationHarness()
    lo, hi = app._transcript_page_index.by_file_page[41], app._transcript_page_index.by_file_page[43]
    assert not format_page_citation_range_for_clipboard(hi, lo).valid
    index = app._transcript_page_index
    index.by_file_page[43] = replace(hi, series_id="different")
    with pytest.raises(ValueError, match="series"):
        resolve_citation_range(lo, index.by_file_page[43], app.pages, index)


@pytest.mark.parametrize("empty", [False, True])
def test_unmapped_and_empty_records_never_fabricate_citations(empty):
    app = CitationHarness()
    if empty:
        app.pages = []
    else:
        app._transcript_page_index.by_file_page.clear()
    app._sync_citation_buttons()
    app._current_page_citation_button.set_sensitive.assert_called_with(False)
    app._citation_range_button.set_sensitive.assert_called_with(False)
    assert not app._insert_current_page_citation_in_prose_or_clipboard()
    assert not app._insert_page_citation_range_in_prose_or_clipboard()
    app._copy_text_to_clipboard.assert_not_called()


def test_completion_revalidates_instead_of_delivering_stale_preview():
    app = CitationHarness()
    app.start()
    app.current_page = 44
    app._sync_citation_buttons()
    del app._transcript_page_index.by_file_page[42]
    assert not app._insert_page_citation_range_in_prose_or_clipboard()
    app._copy_text_to_clipboard.assert_not_called()
    app._citation_range_button.set_sensitive.assert_called_with(False)


@pytest.mark.parametrize("field", ["citation_prefix", "citation_label", "series_id", "record_type"])
def test_incomplete_anchor_metadata_disables_start_without_disabling_valid_page_formatter(field):
    app = CitationHarness()
    index = app._transcript_page_index
    index.by_file_page[41] = replace(index.by_file_page[41], **{field: ""})
    app._sync_citation_buttons()
    app._citation_range_button.set_sensitive.assert_called_with(False)
    assert not app._insert_page_citation_range_in_prose_or_clipboard()
    app._copy_text_to_clipboard.assert_not_called()


def test_missing_interior_citation_identity_is_rejected():
    app = CitationHarness()
    index = app._transcript_page_index
    index.by_file_page[42] = replace(index.by_file_page[42], citation_label="")
    with pytest.raises(ValueError, match="no transcript citation"):
        resolve_citation_range(index.by_file_page[41], index.by_file_page[43], app.pages, index)


def test_long_volume_labels_keep_complete_accessible_citation_and_delivery():
    app = CitationHarness()
    index = app._transcript_page_index
    for page, label in index.by_file_page.copy().items():
        index.by_file_page[page] = replace(label, citation_prefix="12345 RT",
                                          citation_label=f"12345 RT {98724 + page}",
                                          transcript_page_number=98724 + page)
    app.start()
    app.current_page = 43
    app._sync_citation_buttons()
    app._citation_range_label.set_label.assert_called_with("Cite RT 98765–98767")
    properties, values = app._citation_range_button.update_property.call_args.args
    assert values[0] == "Cite 12345 RT 98765–98767"
    assert "(12345 RT 98765–98767.)" in values[1]
    assert app._insert_page_citation_range_in_prose_or_clipboard()
    app._copy_text_to_clipboard.assert_called_once_with("(12345 RT 98765–98767.)")


def test_clipboard_set_exception_is_a_failure(monkeypatch):
    from focus import app as module
    display = Mock()
    display.get_clipboard.return_value.set.side_effect = RuntimeError("closed")
    monkeypatch.setattr(module.Gdk.Display, "get_default", lambda: display)
    assert not Focus._copy_text_to_clipboard(CitationHarness(), "(RT 45.)")
    display.get_primary_clipboard.assert_not_called()
