import re
import threading

import focus.app as focus_app
from focus.app import Focus
from focus.core import (
    MAX_BREAKS,
    TranscriptPageIndex,
    TranscriptPageLabel,
    _render_markdown_text,
    append_page_citation_to_selected_text,
    build_grep_match_order,
    build_pattern,
    format_current_page_citation_for_clipboard,
    format_page_citation_range_for_clipboard,
    format_grep_status_text,
    next_grep_match_index,
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

    assert format_grep_status_text(match_order, 2) == "3 / 3"


def test_grep_status_text_clamps_out_of_range_positions() -> None:
    match_order = [(41, 0), (55, 0), (60, 0)]

    assert format_grep_status_text(match_order, -1) == "1 / 3"
    assert format_grep_status_text(match_order, 99) == "3 / 3"


def test_grep_status_text_is_empty_without_hits() -> None:
    assert format_grep_status_text([], 0) == ""


def test_next_grep_match_index_keeps_bounded_navigation_at_edges() -> None:
    assert next_grep_match_index(0, 3, -1, wrap=False) is None
    assert next_grep_match_index(2, 3, 1, wrap=False) is None


def test_next_grep_match_index_wraps_shortcut_navigation_at_edges() -> None:
    assert next_grep_match_index(0, 3, -1, wrap=True) == 2
    assert next_grep_match_index(2, 3, 1, wrap=True) == 0


def test_next_grep_match_index_moves_inside_result_range() -> None:
    assert next_grep_match_index(1, 3, -1, wrap=False) == 0
    assert next_grep_match_index(1, 3, 1, wrap=True) == 2


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


def test_page_citation_range_formats_single_page() -> None:
    result = format_page_citation_range_for_clipboard(
        _label(41, "RT 45"),
        _label(41, "RT 45"),
    )

    assert result.valid is True
    assert result.citation == "(RT 45.)"


def test_page_citation_range_formats_same_series_range() -> None:
    result = format_page_citation_range_for_clipboard(
        _label(12, "RT 12"),
        _label(15, "RT 15"),
    )

    assert result.valid is True
    assert result.citation == "(RT 12\u201315.)"


def test_page_citation_range_formats_ct_volume_range() -> None:
    result = format_page_citation_range_for_clipboard(
        _label(100, "1CT 100"),
        _label(104, "1CT 104"),
    )

    assert result.valid is True
    assert result.citation == "(1CT 100\u2013104.)"


def test_page_citation_range_rejects_mixed_series() -> None:
    result = format_page_citation_range_for_clipboard(
        _label(100, "1CT 100"),
        _label(104, "2CT 104"),
    )

    assert result.valid is False
    assert result.citation == ""
    assert result.message == "Citation range must stay in one series."


def test_page_citation_range_rejects_reversed_pages() -> None:
    result = format_page_citation_range_for_clipboard(
        _label(15, "RT 15"),
        _label(12, "RT 12"),
    )

    assert result.valid is False
    assert result.citation == ""
    assert result.message == "Citation range end must be after the start."


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


def test_python_worker_matches_smart_apostrophe_with_straight_query(
    tmp_path,
    monkeypatch,
) -> None:
    page_path = tmp_path / "0055.txt"
    source = (
        "Mother Courtney allowed father to come back into the family’s life "
        "and to help raise children Carter and Nova."
    )
    page_path.write_text(source, encoding="utf-8")
    phrase = (
        "mother Courtney allowed father to come back into the family's life "
        "and to help raise children Carter and Nova"
    )
    regex = re.compile(
        build_pattern(preprocess_phrase(phrase), MAX_BREAKS),
        re.IGNORECASE | re.DOTALL,
    )
    completed: dict[str, object] = {}

    def capture_result(_callback, generation, hits, matching_pages):
        completed.update(
            generation=generation,
            hits=hits,
            matching_pages=matching_pages,
        )
        return 1

    monkeypatch.setattr(focus_app.GLib, "idle_add", capture_result)

    class Harness:
        _read_text_file = Focus._read_text_file
        _map_normalized_span_to_original = Focus._map_normalized_span_to_original
        _grep_search_worker = Focus._grep_search_worker

        def _on_grep_search_finished(self, *_args):
            return False

    Harness()._grep_search_worker(
        regex,
        7,
        threading.Event(),
        [55],
        {55: page_path},
    )

    assert completed["generation"] == 7
    assert completed["matching_pages"] == [55]
    start, end = completed["hits"][55][0]
    assert source[start:end] == source.removesuffix(".")
