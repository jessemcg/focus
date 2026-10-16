"""Runner-owned minute labels are bold presentation, never phrase-search links."""
from types import SimpleNamespace
from pathlib import Path

from gi.repository import Gtk, Gdk, Pango
from focus.app import Focus
from focus.core import (
    SUMMARY_SOURCE_MINUTES, SUMMARY_SOURCE_HEARING, SUMMARY_SOURCE_REPORTS,
    _extract_summary_emphasis_spans,
)
from focus.summary_editions import (
    SummaryPageDisplay, SummaryEdition, SummaryEditionPage, SummaryEditionLink,
    SummaryEditionQuote, emphasis_match_text, render_page_display, search_pages,
    with_paragraph_spacing, with_paragraph_spacing_mapped,
)

TEXT = ('May 7, 2030 — Motion\n'
        'Appearances: Applicant present.\n'
        'Orders: The request was denied, but it may be renewed.\n'
        'Next: Review June 4.\n')


def test_only_exact_minute_label_prefixes_are_emphasized():
    spans = _extract_summary_emphasis_spans(TEXT, SUMMARY_SOURCE_MINUTES)
    assert [TEXT[start:end] for start, end in spans] == ['Appearances:', 'Orders:', 'Next:']
    assert _extract_summary_emphasis_spans('Orders:No space\nThe Orders: were changed.\n- Orders: old\n', SUMMARY_SOURCE_MINUTES) == []
    for source in (None, SUMMARY_SOURCE_HEARING, SUMMARY_SOURCE_REPORTS):
        assert _extract_summary_emphasis_spans(TEXT, source) == []


def test_structured_display_offsets_remain_exact_with_links_and_spacing():
    # Real v2 path does not parse Markdown. Prefix styling changes no text,
    # phrase-search span or record-page link offset.
    text = TEXT.replace('\n', '\n\n')
    start = text.index('Review')
    display = SummaryPageDisplay(text, (), ((start, start + len('Review'), '9'),))
    match_text, offsets = emphasis_match_text(display)
    spans = _extract_summary_emphasis_spans(match_text, SUMMARY_SOURCE_MINUTES)
    assert [display.text[offsets[a]:offsets[b]] for a, b in spans] == ['Appearances:', 'Orders:', 'Next:']
    assert display.text == text
    assert display.phrase_spans == ()
    assert display.page_link_spans == ((start, start + 6, '9'),)


def test_minute_entries_have_one_blank_line_between_but_no_internal_blanks():
    other = ('June 4, 2030 — Administrative review\n'
             'Appearances: Not established.\nOrders: No substantive orders recorded.\nNext: Not stated.')
    raw = TEXT.rstrip() + '\n' + other  # Actual PDF block boundaries, not canonical TXT gaps.
    expected = TEXT.rstrip() + '\n\n' + other
    for value in (raw, '\n\n' + raw.replace('\n', '\n\n\n') + '\n'):
        display, offsets = with_paragraph_spacing_mapped(value, minute_entries=True)
        assert display == expected
        assert with_paragraph_spacing(value, minute_entries=True) == expected
        assert offsets == sorted(offsets)
        assert display[0] != '\n' and display[-1] != '\n'
    # Hearing/report defaults and old paragraph-shaped minutes are untouched.
    assert with_paragraph_spacing(raw) == raw.replace('\n', '\n\n')
    old = 'First historical paragraph.\nSecond historical paragraph.'
    assert with_paragraph_spacing(old, minute_entries=True) == with_paragraph_spacing(old)
    # No blank line is inserted at paper-page edges, even for a split entry.
    assert with_paragraph_spacing('\nOrders: Decision.\nNext: Not stated.\n', minute_entries=True) == 'Orders: Decision.\nNext: Not stated.'


def test_structured_minute_spacing_preserves_quote_link_and_search_offsets():
    other = 'June 4, 2030 — Review\nAppearances: Not established.\nOrders: No substantive orders recorded.\nNext: Not stated.'
    raw = TEXT.rstrip() + '\n' + other
    q = 'request was denied'; q_start = raw.index(q)
    link = 'Review June 4.'; link_start = raw.index(link)
    page = SummaryEditionPage(1, raw, 1, 9,
                             (SummaryEditionLink(link, 9, link_start, link_start + len(link)),),
                             (SummaryEditionQuote(q, q, q_start, q_start + len(q)),))
    edition = SummaryEdition('minutes', Path('/fictional'), Path('/fictional/minutes.txt'), 'a'*64,
                             Path('/fictional/minutes.pdf'), 'b'*64, (page,), 'recordprep-summary-letter-v3', 2)
    display = render_page_display(edition, 1)
    assert display.text == TEXT.rstrip() + '\n\n' + other
    for start, end, phrase in display.phrase_spans:
        assert display.text[start:end] == phrase == q
    for start, end, target in display.page_link_spans:
        assert display.text[start:end] == link and target == '9'
    matches = search_pages(edition, link, render=lambda e, p: render_page_display(e, p).text)
    assert matches == [(1, display.text.index(link), display.text.index(link) + len(link))]
    match_text, offsets = emphasis_match_text(display)
    spans = _extract_summary_emphasis_spans(match_text, SUMMARY_SOURCE_MINUTES)
    assert [display.text[offsets[a]:offsets[b]] for a,b in spans] == ['Appearances:', 'Orders:', 'Next:'] * 2


def test_real_gtk_structured_and_continuous_paths_make_labels_bold_not_links():
    color = Gdk.RGBA()
    color.parse('#334455')
    buffer = Gtk.TextBuffer()
    harness = SimpleNamespace(
        _summary_buffer=buffer, _summary_active_source=SUMMARY_SOURCE_MINUTES,
        _summary_loaded_path=None, _summary_view=None, _summary_scroller=None,
        _summary_link_tags=[], _summary_link_tag_lookup={},
        _resolve_ai_quote_color=lambda _view: color,
    )
    harness._ensure_summary_emphasis_tag = lambda buf: Focus._ensure_summary_emphasis_tag(harness, buf)
    harness._apply_structured_summary_emphasis = lambda display: Focus._apply_structured_summary_emphasis(harness, display)
    display = SummaryPageDisplay(TEXT)
    Focus._apply_structured_summary_page(harness, display)
    tag = buffer.get_tag_table().lookup('summary-entry-emphasis')
    assert tag.get_property('weight') == Pango.Weight.MEDIUM
    assert tag.get_property('scale') == 1.0
    assert tag.get_property('foreground-rgba').equal(color)
    for start, end in _extract_summary_emphasis_spans(TEXT, SUMMARY_SOURCE_MINUTES):
        assert buffer.get_iter_at_offset(start).has_tag(tag)
        assert not buffer.get_iter_at_offset(end).has_tag(tag)
    assert buffer.get_text(buffer.get_start_iter(), buffer.get_end_iter(), False) == TEXT
    assert harness._summary_link_tag_lookup == {}
    assert harness._summary_link_tags == []
    # Legacy continuous summaries call this same matcher through their
    # established offset maps; no input mutation or Markdown fake links.
    buffer.set_text(TEXT)
    identity = list(range(len(TEXT) + 1))
    harness._map_markdown_offset = lambda offset, mapping: Focus._map_markdown_offset(harness, offset, mapping)
    Focus._apply_summary_emphasis(harness, TEXT, SUMMARY_SOURCE_MINUTES, buffer, identity, identity)
    for start, _end in _extract_summary_emphasis_spans(TEXT, SUMMARY_SOURCE_MINUTES):
        assert buffer.get_iter_at_offset(start).has_tag(tag)
