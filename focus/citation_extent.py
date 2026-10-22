"""Read-only validation for inclusive, physically ordered transcript ranges."""
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
    if (start.file_page not in available or not start.citation_prefix
            or not start.citation_label or not start.series_id or not start.record_type
            or index.by_file_page.get(start.file_page) != start):
        raise ValueError("The starting page has no current transcript citation.")
    end = start
    for offset in range(1, additional_pages + 1):
        page = start.file_page + offset
        if page not in available:
            raise ValueError(f"Page {page} is unavailable; the range cannot skip it.")
        end = index.by_file_page.get(page)
        if end is None or end.file_page != page or not end.citation_label:
            raise ValueError(f"Page {page} has no transcript citation.")
        if (end.citation_prefix, end.series_id, end.record_type) != (
            start.citation_prefix, start.series_id, start.record_type
        ):
            raise ValueError("The citation range must stay in one transcript series.")
        if end.transcript_page_number != start.transcript_page_number + offset:
            raise ValueError("The citation range cannot cross a numbering gap or restart.")
    return end


def resolve_citation_range(
    anchor: TranscriptPageLabel,
    endpoint: TranscriptPageLabel,
    available_pages: Collection[int],
    index: TranscriptPageIndex,
) -> tuple[TranscriptPageLabel, TranscriptPageLabel]:
    """Validate both live identities and every page, allowing either direction.

    Physical order is authoritative: printed page numbers may restart in another
    volume. Never normalize direct formatter inputs; only this validated path
    orders endpoints before calling the canonical formatter.
    """
    available = set(available_pages)
    for label in (anchor, endpoint):
        if (label.file_page not in available or not label.citation_prefix
                or not label.citation_label or not label.series_id or not label.record_type
                or index.by_file_page.get(label.file_page) != label):
            raise ValueError("A citation endpoint is missing or no longer matches the current record.")
    lower, upper = sorted((anchor, endpoint), key=lambda label: label.file_page)
    end = resolve_citation_extent(lower, upper.file_page - lower.file_page, available, index)
    return lower, end
