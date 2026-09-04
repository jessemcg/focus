"""Strict loader for RecordPrep page-matched summary editions.

Focus is the consumer: it never repaginates or parses the PDF layout. It
validates the page-map sidecar as a unit against the canonical summary text
and the generated PDF (by hash only), then displays one selectable page of
sidecar text at a time. Any failure degrades safely to the legacy continuous
summary behavior.
"""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Any

PAGE_MAP_ARTIFACT = "recordprep-summary-pages"
PAGE_MAP_SCHEMA_VERSION = 1
# Focus consumes editions produced by any supported RecordPrep layout. v2 is
# the denser current Letter layout; v1 sidecars remain readable so bundles
# keep working until RecordPrep rebuilds them.
SUPPORTED_LAYOUT_IDS: tuple[str, ...] = (
    "recordprep-summary-letter-v1",
    "recordprep-summary-letter-v2",
)

# Focus summary sources mapped to RecordPrep page-map categories.
FOCUS_SOURCE_TO_EDITION_KIND = {
    "hearing": "hearings",
    "reports": "reports",
    "minutes": "minutes",
}


class SummaryEditionError(ValueError):
    """Raised when a page-map sidecar is missing, malformed, or stale."""


@dataclass(frozen=True)
class SummaryEditionLink:
    label: str
    target_page: int
    start: int
    end: int


@dataclass(frozen=True)
class SummaryEditionPage:
    page: int
    text: str
    source_first_line: int
    source_last_line: int
    links: tuple[SummaryEditionLink, ...] = ()


@dataclass(frozen=True)
class SummaryEdition:
    kind: str
    root_dir: Path
    source_path: Path
    source_sha256: str
    pdf_path: Path
    pdf_sha256: str
    pages: tuple[SummaryEditionPage, ...]
    layout_id: str = ""

    @property
    def page_count(self) -> int:
        return len(self.pages)


def _sha256_file(path: Path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def _normalize_text(value: str) -> str:
    return " ".join(value.split())


def _resolve_inside_root(value: Any, root_dir: Path) -> Path:
    if not isinstance(value, str) or not value.strip():
        raise SummaryEditionError("Edition path is missing.")
    pure = PurePosixPath(value)
    if pure.is_absolute() or ".." in pure.parts:
        raise SummaryEditionError("Edition path escapes the case bundle.")
    resolved = (root_dir / pure).resolve()
    root = root_dir.resolve()
    try:
        resolved.relative_to(root)
    except ValueError as exc:
        raise SummaryEditionError("Edition path escapes the case bundle.") from exc
    return resolved


def edition_manifest_paths(
    manifest_files: dict[str, Any] | None,
    manifest_dir: Path,
    edition_kind: str,
) -> tuple[Path, Path] | None:
    """Resolve companion paths from manifest keys, when present."""
    if not isinstance(manifest_files, dict):
        return None
    pdf_value = manifest_files.get(f"summarized_{edition_kind}_pdf")
    pages_value = manifest_files.get(f"summarized_{edition_kind}_pages")
    if not isinstance(pdf_value, str) or not isinstance(pages_value, str):
        return None
    return (manifest_dir / pdf_value, manifest_dir / pages_value)


def edition_same_stem_paths(summary_path: Path) -> tuple[Path, Path]:
    """Same-stem convention for manifest-less bundles."""
    editions_dir = summary_path.parent / "editions"
    stem = summary_path.stem
    return (
        editions_dir / f"{stem}.pdf",
        editions_dir / f"{stem}.pages.json",
    )


def load_summary_edition(
    *,
    focus_source: str,
    summary_path: Path,
    bundle_root: Path,
    manifest_files: dict[str, Any] | None = None,
    manifest_dir: Path | None = None,
) -> SummaryEdition:
    """Load and fully validate one edition; raise SummaryEditionError otherwise."""
    edition_kind = FOCUS_SOURCE_TO_EDITION_KIND.get(focus_source)
    if edition_kind is None:
        raise SummaryEditionError(f"Unknown summary source: {focus_source}")

    summary_path = Path(summary_path)
    bundle_root = Path(bundle_root)
    companions = edition_manifest_paths(manifest_files, manifest_dir or bundle_root, edition_kind)
    if companions is None:
        companions = edition_same_stem_paths(summary_path)
    pdf_path, pages_path = companions

    if not pages_path.exists() or not pdf_path.exists():
        raise SummaryEditionError("Summary edition files are missing.")
    try:
        page_map = json.loads(pages_path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise SummaryEditionError("Page map sidecar is not valid JSON.") from exc
    if not isinstance(page_map, dict):
        raise SummaryEditionError("Page map sidecar is not an object.")

    problems: list[str] = []
    if page_map.get("artifact") != PAGE_MAP_ARTIFACT:
        problems.append("artifact identifier mismatch")
    if page_map.get("schema_version") != PAGE_MAP_SCHEMA_VERSION:
        problems.append("unsupported schema version")
    if page_map.get("kind") != edition_kind:
        problems.append("category mismatch")
    layout = page_map.get("layout")
    if not isinstance(layout, dict) or layout.get("id") not in SUPPORTED_LAYOUT_IDS:
        problems.append("layout mismatch")
    if problems:
        raise SummaryEditionError(
            "Page map sidecar rejected: " + ", ".join(problems) + "."
        )
    layout_id = str(layout["id"])

    source_info = page_map.get("source")
    pdf_info = page_map.get("pdf")
    pages = page_map.get("pages")
    if not isinstance(source_info, dict) or not isinstance(pdf_info, dict):
        raise SummaryEditionError("Page map sidecar is missing source/pdf sections.")
    if not isinstance(pages, list) or not pages:
        raise SummaryEditionError("Page map sidecar has no pages.")

    try:
        resolved_source = _resolve_inside_root(source_info.get("path"), bundle_root)
        resolved_pdf = _resolve_inside_root(pdf_info.get("path"), bundle_root)
    except SummaryEditionError:
        raise
    if resolved_source != summary_path.resolve():
        raise SummaryEditionError("Page map does not describe the selected summary file.")
    if resolved_pdf != pdf_path.resolve():
        raise SummaryEditionError("Page map PDF path does not match its sidecar location.")

    source_sha = source_info.get("sha256")
    if not isinstance(source_sha, str) or source_sha.lower() != _sha256_file(summary_path):
        raise SummaryEditionError("Summary text changed since this edition was built.")
    pdf_sha = pdf_info.get("sha256")
    if not isinstance(pdf_sha, str) or pdf_sha.lower() != _sha256_file(pdf_path):
        raise SummaryEditionError("Summary PDF changed since this page map was built.")
    declared_count = pdf_info.get("page_count")
    if not isinstance(declared_count, int) or declared_count != len(pages):
        raise SummaryEditionError("Page map page count does not match its PDF.")

    validated: list[SummaryEditionPage] = []
    previous_last_line = 0
    for index, entry in enumerate(pages):
        if not isinstance(entry, dict):
            raise SummaryEditionError("Page map page entry is malformed.")
        if entry.get("page") != index + 1:
            raise SummaryEditionError("Page map page numbers are not consecutive starting at 1.")
        text = entry.get("text")
        first_line = entry.get("source_first_line")
        last_line = entry.get("source_last_line")
        if not isinstance(text, str):
            raise SummaryEditionError("Page map page text is missing.")
        if not isinstance(first_line, int) or not isinstance(last_line, int):
            raise SummaryEditionError("Page map source line range is missing.")
        if first_line < 0 or last_line < first_line:
            raise SummaryEditionError("Page map source line range is invalid.")
        if first_line < previous_last_line and not (first_line == 0 and last_line == 0):
            raise SummaryEditionError("Page map source line ranges are not monotonic.")
        previous_last_line = last_line

        links: list[SummaryEditionLink] = []
        spans: list[tuple[int, int]] = []
        raw_links = entry.get("links", [])
        if not isinstance(raw_links, list):
            raise SummaryEditionError("Page map links are malformed.")
        for link in raw_links:
            if not isinstance(link, dict):
                raise SummaryEditionError("Page map link entry is malformed.")
            start, end = link.get("start"), link.get("end")
            label, target = link.get("label"), link.get("target_page")
            if (
                not isinstance(start, int)
                or not isinstance(end, int)
                or start < 0
                or end > len(text)
                or start >= end
            ):
                raise SummaryEditionError("Page map link span is out of bounds.")
            if not isinstance(label, str) or text[start:end] != label:
                raise SummaryEditionError("Page map link span does not match its label.")
            if not isinstance(target, int) or target <= 0:
                raise SummaryEditionError("Page map link target is invalid.")
            spans.append((start, end))
            links.append(
                SummaryEditionLink(label=label, target_page=target, start=start, end=end)
            )
        ordered = sorted(spans)
        for (_ps, pe), (ns, _ne) in zip(ordered, ordered[1:]):
            if ns < pe:
                raise SummaryEditionError("Page map link spans overlap.")

        validated.append(
            SummaryEditionPage(
                page=index + 1,
                text=text,
                source_first_line=first_line,
                source_last_line=last_line,
                links=tuple(links),
            )
        )

    return SummaryEdition(
        kind=edition_kind,
        root_dir=bundle_root,
        source_path=summary_path,
        source_sha256=source_sha.lower(),
        pdf_path=pdf_path,
        pdf_sha256=pdf_sha.lower(),
        pages=tuple(validated),
        layout_id=layout_id,
    )


def render_page_text(edition: SummaryEdition, page_number: int) -> str:
    """Render one page's selectable text with trusted record-page links.

    Link spans are synthesized back into the established
    ``[label](page:NNNN)`` representation purely in memory so Focus's link
    renderer, themes, and selection behavior apply unchanged.
    """
    page = edition.pages[page_number - 1]
    pieces: list[str] = []
    cursor = 0
    for link in sorted(page.links, key=lambda item: (item.start, item.end)):
        if link.start < cursor:
            continue
        pieces.append(page.text[cursor : link.start])
        pieces.append(f"[{link.label}](page:{link.target_page})")
        cursor = link.end
    pieces.append(page.text[cursor:])
    return "".join(pieces)


_NEWLINE_RUN_RE = re.compile(r"\n+")


def with_paragraph_spacing(text: str) -> str:
    """Display form of paginated page text: one empty line per paragraph.

    RecordPrep's sidecar page text uses newlines only at extracted
    paragraph/block boundaries (visual line wrapping is already spaces), so
    every newline run — after ``render_page_text`` has reconstructed the
    trusted link syntax — normalizes to exactly ``\\n\\n``. Leading and
    trailing newlines are dropped so spacing is never added at page edges,
    and each page is transformed independently, so paragraphs are never
    joined or spaced across paper-page boundaries. The sidecar text, link
    offsets, and source-line mapping remain unchanged; apply this only to
    paginated display and search text, never to legacy continuous summaries.
    """
    if not text:
        return text
    return _NEWLINE_RUN_RE.sub("\n\n", text).strip("\n")


def find_page_for_source_line(edition: SummaryEdition, line_number: int) -> int:
    """First sidecar page whose source-line range contains ``line_number``."""
    for page in edition.pages:
        if page.source_first_line <= line_number <= page.source_last_line:
            return page.page
        if page.source_first_line > line_number and page.source_first_line > 0:
            return page.page
    return edition.page_count if edition.page_count else 1


_TRUSTED_LINK_DISPLAY_RE = re.compile(r"\[([^\]\[]+)\]\(page:\d+\)")


def _render_stripped(edition: SummaryEdition, page_number: int) -> str:
    """Displayed-text form: link syntax collapses to its label."""
    return _TRUSTED_LINK_DISPLAY_RE.sub(
        lambda match: match.group(1), render_page_text(edition, page_number)
    )


def search_pages(
    edition: SummaryEdition,
    query: str,
    *,
    render=None,
    casefold: bool = True,
) -> list[tuple[int, int, int]]:
    """Search every page in document order; returns ``(page, start, end)``.

    ``render`` maps a page's sidecar text to exactly the text Focus displays,
    so returned offsets are buffer offsets for the displayed page. The default
    strips record-page link syntax to its label.
    """
    if not query:
        return []
    if render is None:
        render = _render_stripped
    matches: list[tuple[int, int, int]] = []
    for page in edition.pages:
        text = render(edition, page.page)
        haystack = text.casefold() if casefold else text
        needle = query.casefold() if casefold else query
        start = 0
        while True:
            found = haystack.find(needle, start)
            if found < 0:
                break
            matches.append((page.page, found, found + len(needle)))
            start = found + len(needle)
    return matches
