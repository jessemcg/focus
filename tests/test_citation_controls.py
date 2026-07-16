from focus.app import Focus
from focus.core import TranscriptPageLabel


def _label(file_page: int, citation_label: str) -> TranscriptPageLabel:
    citation_prefix, page_number = citation_label.split()
    return TranscriptPageLabel(
        file_page=file_page,
        transcript_page_number=int(page_number),
        citation_prefix=citation_prefix,
        citation_label=citation_label,
        citation_key=citation_label.lower(),
        record_type="reporter_transcript",
        series_id=citation_prefix.lower(),
        series_description=citation_prefix,
        status="official",
    )


class CitationRangeHarness:
    _insert_page_citation_range_in_prose_or_clipboard = (
        Focus._insert_page_citation_range_in_prose_or_clipboard
    )

    def __init__(self, current_label: TranscriptPageLabel) -> None:
        self.current_label = current_label
        self._page_citation_range_start: TranscriptPageLabel | None = None
        self.synced_starts: list[TranscriptPageLabel | None] = []
        self.sent_citations: list[str] = []
        self.toasts: list[str] = []

    def _current_transcript_page_label(self) -> TranscriptPageLabel:
        return self.current_label

    def _sync_citation_buttons(self) -> None:
        self.synced_starts.append(self._page_citation_range_start)

    def _send_text_to_prose_record_citations_action(self, text: str) -> bool:
        self.sent_citations.append(text)
        return True

    def _copy_text_to_clipboard(self, _text: str) -> bool:
        raise AssertionError("clipboard fallback should not run when Prose accepts the citation")

    def _transient_toast(self, message: str) -> None:
        self.toasts.append(message)


class CitationClickHarness:
    _on_current_page_citation_clicked = Focus._on_current_page_citation_clicked
    _on_page_citation_range_clicked = Focus._on_page_citation_range_clicked

    def __init__(self) -> None:
        self.current_page_clicks = 0
        self.range_clicks = 0

    def _insert_current_page_citation_in_prose_or_clipboard(self) -> bool:
        self.current_page_clicks += 1
        return True

    def _insert_page_citation_range_in_prose_or_clipboard(self) -> bool:
        self.range_clicks += 1
        return True


def test_range_button_first_click_stores_start_without_inserting() -> None:
    start = _label(41, "RT 45")
    harness = CitationRangeHarness(start)

    result = harness._insert_page_citation_range_in_prose_or_clipboard()

    assert result is True
    assert harness._page_citation_range_start == start
    assert harness.synced_starts == [start]
    assert harness.sent_citations == []


def test_range_button_second_click_inserts_and_clears_range() -> None:
    start = _label(41, "RT 45")
    end = _label(44, "RT 48")
    harness = CitationRangeHarness(end)
    harness._page_citation_range_start = start

    result = harness._insert_page_citation_range_in_prose_or_clipboard()

    assert result is True
    assert harness.sent_citations == ["(RT 45\u201348.)"]
    assert harness._page_citation_range_start is None
    assert harness.synced_starts == [None]


def test_citation_buttons_route_to_independent_actions() -> None:
    harness = CitationClickHarness()

    harness._on_current_page_citation_clicked(None)
    harness._on_page_citation_range_clicked(None)

    assert harness.current_page_clicks == 1
    assert harness.range_clicks == 1
