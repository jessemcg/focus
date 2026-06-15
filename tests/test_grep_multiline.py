import re
import shutil
import threading
from types import SimpleNamespace

import pytest

from focus import (
    Focus,
    MAX_BREAKS,
    TranscriptPageIndex,
    TranscriptPageLabel,
    _render_markdown_text,
    append_page_citation_to_selected_text,
    build_grep_match_order,
    build_pattern,
    format_current_page_citation_for_clipboard,
    format_grep_status_text,
    normalize_text_for_search_with_map,
    preprocess_phrase,
    split_span_at_line_breaks,
)


def test_grep_pattern_matches_phrase_across_blank_line() -> None:
    regex = re.compile(
        build_pattern(preprocess_phrase("issue still is placement"), MAX_BREAKS),
        re.IGNORECASE | re.DOTALL,
    )

    match = regex.search("my issue still\n\nis placement, probably")

    assert match is not None
    assert match.group(0) == "issue still\n\nis placement"


def test_multiline_match_maps_full_display_span() -> None:
    content = (
        "Just a few issues. My client, at first, did\n"
        "not understand that she was not able to have an\n"
    )
    regex = re.compile(
        build_pattern(preprocess_phrase("did not understand"), MAX_BREAKS),
        re.IGNORECASE | re.DOTALL,
    )
    normalized, norm_to_orig = normalize_text_for_search_with_map(content)

    match = regex.search(normalized)

    assert match is not None
    mapped = Focus._map_normalized_span_to_original(
        None,
        norm_to_orig,
        match.start(),
        match.end(),
        len(content),
    )
    assert mapped is not None
    assert content[mapped[0] : mapped[1]] == "did\nnot understand"

    display_text = f"0041\n\n{content}"
    rendered_text, _markdown_spans, orig_to_clean = _render_markdown_text(display_text)
    display_span = (mapped[0] + len("0041\n\n"), mapped[1] + len("0041\n\n"))

    class Mapper:
        _map_markdown_offset = Focus._map_markdown_offset
        _map_markdown_spans = Focus._map_markdown_spans

    highlight_span = Mapper()._map_markdown_spans([display_span], orig_to_clean)

    assert highlight_span == [display_span]
    start, end = highlight_span[0]
    assert rendered_text[start:end] == "did\nnot understand"


def test_multiline_highlight_span_splits_into_visible_line_segments() -> None:
    text = "before did\nnot understand after"
    start = text.index("did")
    end = text.index(" after")

    spans = split_span_at_line_breaks(text, start, end)

    assert [text[start:end] for start, end in spans] == ["did", "not understand"]


def test_grep_match_order_flattens_hits_across_matching_pages() -> None:
    grep_hits = {
        41: [(0, 5), (10, 15)],
        55: [(3, 8)],
        60: [(2, 2)],
    }

    order = build_grep_match_order(grep_hits, [41, 55, 60])

    assert order == [(41, 0), (41, 1), (55, 0)]


def test_grep_status_text_reports_global_hit_position() -> None:
    match_order = [(41, 0), (41, 1), (55, 0)]

    assert format_grep_status_text(match_order, 2) == "Search: hit 3/3"


def _label(file_page: int, citation_label: str) -> TranscriptPageLabel:
    return TranscriptPageLabel(
        file_page=file_page,
        transcript_page_number=file_page,
        citation_prefix=citation_label.split(maxsplit=1)[0],
        citation_label=citation_label,
        citation_key=citation_label.replace(" ", ":"),
        record_type="",
        series_id="",
        series_description="",
        status="selected",
    )


def test_current_page_citation_formats_page_label() -> None:
    index = TranscriptPageIndex(
        by_file_page={41: _label(41, "RT 45")},
        by_transcript_number={},
        by_citation_key={},
    )

    citation = format_current_page_citation_for_clipboard(41, index)

    assert citation == "(RT 45.)"


def test_current_page_citation_preserves_existing_period() -> None:
    index = TranscriptPageIndex(
        by_file_page={12: _label(12, "2CT 454.")},
        by_transcript_number={},
        by_citation_key={},
    )

    citation = format_current_page_citation_for_clipboard(12, index)

    assert citation == "(2CT 454.)"


def test_current_page_citation_skips_pages_without_citation_metadata() -> None:
    index = TranscriptPageIndex(
        by_file_page={55: _label(55, "RT 23")},
        by_transcript_number={},
        by_citation_key={},
    )

    citation = format_current_page_citation_for_clipboard(41, index)

    assert citation == ""


def test_append_page_citation_to_selected_text_matches_collapsed_whitespace() -> None:
    index = TranscriptPageIndex(
        by_file_page={41: _label(41, "RT 45")},
        by_transcript_number={},
        by_citation_key={},
    )

    updated = append_page_citation_to_selected_text(
        "The child was detained at the hearing.",
        "The child was detained\nat the hearing.",
        41,
        index,
    )

    assert updated == "The child was detained at the hearing. (RT 45.)"


def test_append_page_citation_to_selected_text_skips_non_focus_selection() -> None:
    index = TranscriptPageIndex(
        by_file_page={41: _label(41, "RT 45")},
        by_transcript_number={},
        by_citation_key={},
    )

    updated = append_page_citation_to_selected_text(
        "Text selected from another app.",
        "The Focus transcript selection.",
        41,
        index,
    )

    assert updated == "Text selected from another app."


def test_append_page_citation_to_selected_text_skips_missing_citation_metadata() -> None:
    index = TranscriptPageIndex(
        by_file_page={},
        by_transcript_number={},
        by_citation_key={},
    )

    updated = append_page_citation_to_selected_text(
        "The child was detained.",
        "The child was detained.",
        41,
        index,
    )

    assert updated == "The child was detained."


def test_append_page_citation_to_selected_text_does_not_duplicate_citation() -> None:
    index = TranscriptPageIndex(
        by_file_page={41: _label(41, "RT 45")},
        by_transcript_number={},
        by_citation_key={},
    )

    updated = append_page_citation_to_selected_text(
        "The child was detained. (RT 45.)",
        "The child was detained. (RT 45.)",
        41,
        index,
    )

    assert updated == "The child was detained. (RT 45.)"


@pytest.mark.skipif(shutil.which("rg") is None, reason="ripgrep is not installed")
def test_ripgrep_candidate_filter_matches_phrase_across_blank_line(tmp_path) -> None:
    page_path = tmp_path / "0055.txt"
    page_path.write_text(
        "MR. BLOCH: And for trial, Your Honor, my issue still\n\n"
        "is placement, probably a two-hour estimate for me.\n",
        encoding="utf-8",
    )
    regex = re.compile(
        build_pattern(preprocess_phrase("issue still is placement"), MAX_BREAKS),
        re.IGNORECASE | re.DOTALL,
    )
    app = SimpleNamespace(text_dir=tmp_path)

    matches = Focus._find_grep_candidate_pages(
        app,
        regex.pattern,
        [55],
        {55: page_path},
        threading.Event(),
    )

    assert matches == [55]
