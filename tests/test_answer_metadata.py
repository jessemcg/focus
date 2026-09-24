from __future__ import annotations

from focus.answer_metadata import (
    DEFAULT_SUBTITLE,
    DEFAULT_TITLE,
    PARTIAL_SUBTITLE,
    parse_answer_metadata,
)


def test_parses_title_subtitle_and_prefix_end() -> None:
    markdown = (
        "# Supervised Visits Continued\n"
        "*Weekly visits remained supervised*\n"
        "\n"
        "The record describes \u201cweekly supervised visits\u201d...\n"
    )
    metadata = parse_answer_metadata(markdown)
    assert metadata.title == "Supervised Visits Continued"
    assert metadata.subtitle == "Weekly visits remained supervised"
    assert metadata.title_from_answer
    assert metadata.subtitle_from_answer
    expected = len("# Supervised Visits Continued\n*Weekly visits remained supervised*\n")
    assert metadata.prefix_end == expected
    # The original Markdown is never rewritten.
    assert markdown.startswith("# Supervised Visits Continued")


def test_tolerates_crlf_leading_whitespace_and_underscore_emphasis() -> None:
    markdown = "\r\n  #  Visitation Order  \r\n   _Visits stayed weekly_  \r\n\r\nBody text.\r\n"
    metadata = parse_answer_metadata(markdown)
    assert metadata.title == "Visitation Order"
    assert metadata.subtitle == "Visits stayed weekly"
    assert metadata.prefix_end > 0


def test_missing_title_uses_question_then_default() -> None:
    metadata = parse_answer_metadata("Body only.", question="Why were visits stopped?")
    assert metadata.title == "Why were visits stopped?"
    assert metadata.subtitle == DEFAULT_SUBTITLE
    assert not metadata.title_from_answer
    assert metadata.prefix_end == 0

    fallback = parse_answer_metadata("Body only.")
    assert fallback.title == DEFAULT_TITLE


def test_missing_subtitle_uses_partial_or_neutral_fallback() -> None:
    partial = parse_answer_metadata("# Title Only\n\nBody.", partial=True)
    assert partial.title == "Title Only"
    assert partial.subtitle == PARTIAL_SUBTITLE
    assert partial.prefix_end == len("# Title Only\n")

    neutral = parse_answer_metadata("# Title Only\n\nBody.")
    assert neutral.subtitle == DEFAULT_SUBTITLE


def test_blank_lines_between_heading_and_subtitle_are_allowed_but_bounded() -> None:
    with_gap = parse_answer_metadata("# Title\n\n*Subtitle*\n\nBody.")
    assert with_gap.title == "Title"
    assert with_gap.subtitle == "Subtitle"
    plain = parse_answer_metadata("# Title\n\nBody only.")
    assert plain.title == "Title"
    assert plain.subtitle == DEFAULT_SUBTITLE


def test_bold_only_line_is_not_a_subtitle() -> None:
    metadata = parse_answer_metadata("# Title\n**Bold body lead**\n")
    assert metadata.subtitle == DEFAULT_SUBTITLE
    assert metadata.prefix_end == len("# Title\n")


def test_metadata_quotes_are_not_transcript_link_targets() -> None:
    from focus.app import Focus

    instance = Focus.__new__(Focus)
    text = (
        '# The "best interest" finding\n'
        "*Standard applied*\n"
        "\n"
        'Body says "direct quote" here.\n'
    )
    metadata = parse_answer_metadata(text)
    rendered, spans = instance._extract_ai_link_spans(text, metadata.prefix_end)
    assert [phrase for _start, _end, phrase in spans] == ["direct quote"]
    # The heading quote is preserved verbatim, not stripped as a link phrase.
    assert '"best interest"' in rendered

    _unprotected, all_spans = instance._extract_ai_link_spans(text)
    assert "best interest" in [phrase for _start, _end, phrase in all_spans]
