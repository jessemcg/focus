import re
import shutil
import threading
from types import SimpleNamespace

import pytest

from focus import (
    Focus,
    MAX_BREAKS,
    _render_markdown_text,
    build_pattern,
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
