"""Read-only validation for the reader's anchored, forward citation extent."""
from collections.abc import Collection

from .core import TranscriptPageIndex, TranscriptPageLabel


def resolve_citation_extent(
    start: TranscriptPageLabel,
    additional_pages: int,
    available_pages: Collection[int],
    index: TranscriptPageIndex,
) -> TranscriptPageLabel:
    """Return the endpoint, rejecting missing pages and incompatible metadata.

    Check every intervening physical page, not just the two endpoints. A matching
    prefix alone cannot establish that separately numbered volumes form a range.
    Nothing here reads records, delivers citations, or changes application state.
    """
    if additional_pages < 0:
        raise ValueError("The range end must not precede its starting page.")
    if additional_pages >= len(available_pages):
        raise ValueError("No more pages are available for this citation range.")
    available = set(available_pages)
    if start.file_page not in available or not start.citation_prefix:
        raise ValueError("No transcript citation is available for the starting page.")
    end = start
    for offset in range(1, additional_pages + 1):
        page = start.file_page + offset
        if page not in available:
            raise ValueError(f"Page {page} is unavailable; the range cannot skip it.")
        end = index.by_file_page.get(page)
        if end is None:
            raise ValueError(f"Page {page} has no transcript citation.")
        if (end.citation_prefix, end.series_id, end.record_type) != (
            start.citation_prefix, start.series_id, start.record_type
        ):
            raise ValueError("The citation range must stay in one transcript series.")
        if end.transcript_page_number != start.transcript_page_number + offset:
            raise ValueError("The citation range cannot cross a numbering gap or restart.")
    return end
