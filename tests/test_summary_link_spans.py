"""Quote-link span extraction: style-matched pairing and clean rendering."""

from focus.app import Focus


class LinkSpanHarness:
    _extract_ai_link_spans = Focus._extract_ai_link_spans

    def __init__(self) -> None:
        self._summary_active_source = None
        self._summary_loaded_path = None
        self._summary_buffer = None


def _extract(text: str) -> tuple[str, list[tuple[int, int, str]]]:
    return LinkSpanHarness()._extract_ai_link_spans(text)


def test_doubled_model_quotes_never_bridge_paragraphs() -> None:
    """Regression: `"“phrase”"` previously paired across quote styles, so one
    span swallowed the text up to the next quote character — rendering whole
    paragraphs as clickable links with quote marks and boundary spaces eaten."""
    text = (
        "According to the report, the mother bit Adrienne and then "
        '“tried to stab her with a screwdriver”; the grandfather '
        'witnessed the stabbing. She was “technically homeless”, and the '
        'mother “is not mentally there”.'
    )
    rendered, spans = _extract(text)

    phrases = [phrase for _start, _end, phrase in spans]
    assert phrases == [
        "tried to stab her with a screwdriver",
        "technically homeless",
        "is not mentally there",
    ]
    assert max(len(phrase) for phrase in phrases) <= len(
        "tried to stab her with a screwdriver"
    )
    # Quote marks are dropped from display, all other characters (including
    # the boundary spaces) are preserved.
    assert '" peaks' not in rendered
    assert "\u201c" not in rendered and "\u201d" not in rendered and '"' not in rendered
    assert "and then tried to stab" in rendered
    assert "witnessed the stabbing. She was technically homeless , and" in rendered.replace(
        "homeless ,", "homeless,"
    ) or "She was technically homeless, and" in rendered


def test_straight_and_curly_quotes_do_not_cross_pair() -> None:
    text = 'She said "good cause" and \u201cbest interest\u201d together.'
    rendered, spans = _extract(text)
    assert [phrase for _s, _e, phrase in spans] == ["good cause", "best interest"]
    assert "She said good cause and best interest together." == rendered


def test_bold_spans_still_link() -> None:
    rendered, spans = _extract("Keep the **material outcome** visible.")
    assert [phrase for _s, _e, phrase in spans] == ["material outcome"]
    assert rendered == "Keep the material outcome visible."


def test_unclosed_quote_never_links() -> None:
    rendered, spans = _extract('He began "to explain the ruling but never closed it.')
    assert spans == []
    assert rendered == 'He began "to explain the ruling but never closed it.'
