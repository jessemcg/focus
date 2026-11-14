"""Summary heading emphasis must not leak across paragraph boundaries."""
from types import SimpleNamespace

import pytest
import gi

gi.require_version('Gdk', '4.0')
gi.require_version('Gtk', '4.0')
from gi.repository import Gdk, Gtk

from focus.app import Focus
from focus.core import (
    SUMMARY_SOURCE_MOTIONS, SUMMARY_SOURCE_REPORTS,
    _extract_summary_emphasis_spans,
)
from focus.summary_editions import SummaryPageDisplay


@pytest.mark.parametrize('source', [SUMMARY_SOURCE_MOTIONS, SUMMARY_SOURCE_REPORTS])
@pytest.mark.parametrize('separator', ['\n', '\n\n', '\r\n', '\r\n\r\n'])
def test_paragraph_before_linked_heading_is_not_emphasized(source, separator):
    text = ('Her request rested on later developments.' + separator
            + '[August 17, 2030 - Request](page:42)')
    assert _extract_summary_emphasis_spans(text, source) == []


@pytest.mark.parametrize('source', [SUMMARY_SOURCE_MOTIONS, SUMMARY_SOURCE_REPORTS])
@pytest.mark.parametrize('space', [' ', '\t', '\u00a0'])
def test_same_line_legacy_entry_emphasis_is_preserved(source, space):
    text = f'Request to change order{space}[CT 42](page:42)\r\n'
    spans = _extract_summary_emphasis_spans(text, source)
    assert [text[a:b] for a, b in spans] == ['Request to change order']


@pytest.mark.parametrize('source', [SUMMARY_SOURCE_MOTIONS, SUMMARY_SOURCE_REPORTS])
def test_structured_gtk_keeps_only_quote_and_page_link_tags(source):
    paragraph = ('Her request rested on later developments. She reported steady progress '
                 'and requested further services.')
    heading = 'August 17, 2030 - Request'
    text = paragraph + '\n\n' + heading
    quote = 'steady progress'
    a = text.index(quote)
    h = text.index(heading)
    display = SummaryPageDisplay(text, ((a, a + len(quote), quote),),
                                 ((h, len(text), '42'),))
    color = Gdk.RGBA()
    color.parse('#334455')
    buffer = Gtk.TextBuffer()
    harness = SimpleNamespace(
        _summary_buffer=buffer, _summary_active_source=source,
        _summary_loaded_path=None, _summary_view=None, _summary_scroller=None,
        _summary_link_tags=[], _summary_link_tag_lookup={},
        _quotation_navigation_for_current=lambda: None,
        _resolve_ai_quote_color=lambda _view: color,
    )
    harness._ensure_summary_emphasis_tag = lambda b: Focus._ensure_summary_emphasis_tag(harness, b)
    harness._apply_structured_summary_emphasis = lambda d: Focus._apply_structured_summary_emphasis(harness, d)
    Focus._apply_structured_summary_page(harness, display)
    assert buffer.get_text(buffer.get_start_iter(), buffer.get_end_iter(), False) == text
    assert buffer.get_tag_table().lookup('summary-entry-emphasis') is None
    quote_tag, link_tag = harness._summary_link_tags
    assert harness._summary_link_tag_lookup == {
        quote_tag: ('phrase', quote), link_tag: ('page', '42'),
    }
    for offset in range(len(text)):
        it = buffer.get_iter_at_offset(offset)
        assert it.has_tag(quote_tag) == (a <= offset < a + len(quote))
        assert it.has_tag(link_tag) == (h <= offset < len(text))
