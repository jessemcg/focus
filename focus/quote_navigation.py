"""Read-only metadata-7 quotation navigation, independent of GTK and research.

No guessed destination or record-wide phrase search exists in this module.
New-contract failures explicitly disable trusted navigation; they cannot become
legacy phrase links. The caller supplies the physical source-page inventory.
"""
from __future__ import annotations

import hashlib
import json
import os
import stat
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Iterable

from .profile_artifacts import (validate_quotation_destination,
                                validate_summary_navigation_metadata)

_MAX_ARTIFACT_BYTES = 32 * 1024 * 1024
_MAX_SOURCE_BYTES = 16 * 1024 * 1024
_NEW_FIELDS = {"navigation_contract", "editorial_contract", "quote_occurrences", "navigation_sha256"}


@dataclass(frozen=True)
class QuoteDestination:
    file_page: int
    path: str
    source_start: int
    source_end: int
    display_start: int
    display_end: int
    source_sha256: str


@dataclass(frozen=True)
class QuoteOccurrence:
    occurrence_id: str
    quote_id: str
    item_id: str
    start: int
    end: int
    display_text: str
    status: str
    destination: QuoteDestination | None
    warning: str = ""


@dataclass(frozen=True)
class SummaryNavigation:
    mode: str  # legacy / anchored / disabled; anchored may contain warnings.
    occurrences: tuple[QuoteOccurrence, ...] = ()
    warnings: tuple[str, ...] = ()
    navigation_sha256: str = ""
    final_text_sha256: str = ""

    @property
    def legacy_phrase_links(self) -> bool:
        return self.mode == "legacy"

    @property
    def unresolved_count(self) -> int:
        return sum(q.destination is None for q in self.occurrences)

    def occurrence(self, identity: str) -> QuoteOccurrence | None:
        return next((q for q in self.occurrences if q.occurrence_id == identity), None)


def normalize_source_display(raw: str) -> tuple[str, tuple[int, ...]]:
    """Focus newline normalization and raw-codepoint boundary -> GTK map.

    GTK offsets count Unicode characters, NOT UTF-8 bytes, JavaScript UTF-16
    code units or normalized-search positions. Reading-mode transformations
    must apply their existing display-span mapping *after* this map.
    """
    chars, mapping = [], [0]
    previous_cr = False
    for char in raw:
        if char == "\n" and previous_cr:
            previous_cr = False
        elif char == "\r":
            chars.append("\n")
            previous_cr = True
        else:
            chars.append(char)
            previous_cr = False
        mapping.append(len(chars))
    return "".join(chars), tuple(mapping)


def _read_inside(root: Path, relative: str, maximum: int) -> bytes:
    pure = PurePosixPath(relative)
    if pure.is_absolute() or not pure.parts or any(p in {".", ".."} for p in pure.parts) or "\\" in relative:
        raise ValueError("Unsafe quotation artifact path.")
    fd = os.open(root, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    try:
        for component in pure.parts[:-1]:
            next_fd = os.open(component, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=fd)
            os.close(fd)
            fd = next_fd
        file_fd = os.open(pure.parts[-1], os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=fd)
        try:
            before = os.fstat(file_fd)
            if not stat.S_ISREG(before.st_mode) or before.st_nlink != 1 or before.st_size > maximum:
                raise ValueError("Unsafe quotation artifact.")
            with os.fdopen(file_fd, "rb", closefd=False) as stream:
                data = stream.read(maximum + 1)
            after = os.fstat(file_fd)
            if (len(data) > maximum or (before.st_ino, before.st_size, before.st_mtime_ns, before.st_ctime_ns) !=
                    (after.st_ino, after.st_size, after.st_mtime_ns, after.st_ctime_ns)):
                raise ValueError("Quotation artifact changed while reading.")
            return data
        finally:
            os.close(file_fd)
    finally:
        os.close(fd)


def _relative(path: Path, root: Path) -> str:
    # Do not resolve the candidate first: that would hide a symlink component.
    try:
        return path.absolute().relative_to(root.absolute()).as_posix()
    except ValueError as exc:
        raise ValueError("Summary is outside the selected bundle.") from exc


def load_summary_navigation(*, summary_path: Path, bundle_root: Path,
                            permitted_pages: Iterable[int], new_contract_expected: bool = False) -> SummaryNavigation:
    """Load committed TXT/metadata pairs. No reads or closes cause writes.

    Legacy schemas 1–6 without new-contract markers retain old behavior.
    An absent sidecar is legacy. An unreadable/malformed/unknown sidecar is
    conservative: readable text remains the caller's responsibility but no
    guessed phrase link is authorized. Source failures disable each affected
    occurrence while preserving unaffected validated destinations.
    """
    permitted = set(permitted_pages)
    if any(type(n) is not int or n < 1 for n in permitted):
        return SummaryNavigation("disabled", warnings=("invalid_source_inventory",))
    try:
        relative = _relative(summary_path, bundle_root)
        meta_relative = str(PurePosixPath(relative).with_suffix(".meta.json"))
    except ValueError:
        return SummaryNavigation("disabled", warnings=("summary_outside_bundle",))
    try:
        raw = _read_inside(bundle_root, meta_relative, _MAX_ARTIFACT_BYTES)
    except FileNotFoundError:
        return (SummaryNavigation("disabled", warnings=("navigation_metadata_missing",))
                if new_contract_expected else SummaryNavigation("legacy"))
    except (OSError, ValueError):
        return SummaryNavigation("disabled", warnings=("navigation_metadata_unreadable",))
    try:
        metadata = json.loads(raw.decode("utf-8"))
        if not isinstance(metadata, dict):
            raise ValueError("Invalid metadata.")
        version = metadata.get("schema_version")
        if not _NEW_FIELDS.intersection(metadata) and type(version) is int and version in range(1, 7):
            # A prior historical sidecar paired with newly replaced TXT must
            # not authorize guesses during interrupted publication.
            if new_contract_expected:
                raise ValueError("Expected current navigation contract.")
            expected = metadata.get("final_text_sha256")
            if expected is not None and expected != hashlib.sha256(_read_inside(bundle_root, relative, _MAX_ARTIFACT_BYTES)).hexdigest():
                raise ValueError("Historical summary text/metadata mismatch.")
            return SummaryNavigation("legacy")
        final_data = _read_inside(bundle_root, relative, _MAX_ARTIFACT_BYTES)
        text = final_data.decode("utf-8")
        validate_summary_navigation_metadata(metadata, text)
    except (OSError, ValueError, TypeError, UnicodeError):
        return SummaryNavigation("disabled", warnings=("navigation_metadata_stale_or_invalid",))
    cache, occurrences, warnings = {}, [], []
    for record in metadata["quote_occurrences"]:
        destination, warning = None, ""
        if record["status"] != "anchored":
            warning = "quotation_unverified"
        else:
            try:
                anchor = record["anchor"]
                number = anchor["file_page"]
                if number not in permitted:
                    raise ValueError("Destination outside physical inventory.")
                if number not in cache:
                    cache[number] = _read_inside(bundle_root, anchor["path"], _MAX_SOURCE_BYTES)
                data = cache[number]
                validate_quotation_destination(record, data)
                _, mapping = normalize_source_display(data.decode("utf-8"))
                destination = QuoteDestination(number, anchor["path"], anchor["source_start"], anchor["source_end"],
                    mapping[anchor["source_start"]], mapping[anchor["source_end"]], anchor["sha256"])
            except (OSError, ValueError, KeyError, TypeError, UnicodeError):
                warning = "quotation_source_stale_or_invalid"
        if warning:
            warnings.append(warning)
        occurrences.append(QuoteOccurrence(record["occurrence_id"], record["quote_id"], record["item_id"],
            record["start"], record["end"], record["display_text"], record["status"], destination, warning))
    # Re-read committed pair after the source reads. Never trust a mixture of
    # editions if publication overlaps loading. Source bytes are also checked
    # again on activation by revalidate_destination().
    try:
        if (_read_inside(bundle_root, meta_relative, _MAX_ARTIFACT_BYTES) != raw or
                _read_inside(bundle_root, relative, _MAX_ARTIFACT_BYTES) != final_data):
            raise ValueError("Summary changed during navigation load.")
    except (OSError, ValueError):
        return SummaryNavigation("disabled", warnings=("summary_changed_during_navigation_load",))
    return SummaryNavigation("anchored", tuple(occurrences), tuple(dict.fromkeys(warnings)), metadata["navigation_sha256"], metadata['final_text_sha256'])


def navigation_display(text: str, navigation: SummaryNavigation):
    """Ledger-only continuous display; never parse quote text for destinations."""
    if navigation.mode != 'anchored':
        return normalize_source_display(text)[0], ()
    if hashlib.sha256(text.encode('utf-8')).hexdigest() != navigation.final_text_sha256:
        raise ValueError('Summary changed after navigation load.')
    removed = set()
    for q in navigation.occurrences:
        if q.start < 1 or q.end >= len(text) or text[q.start-1] != '“' or text[q.end] != '”':
            raise ValueError('Recorded quotation delimiters disagree.')
        removed.update((q.start-1,q.end))
    parts, mapping = [], [0]
    for i,char in enumerate(text):
        if i not in removed:
            parts.append(char)
        mapping.append(len(parts))
    display, newlines = normalize_source_display(''.join(parts))
    spans = tuple((newlines[mapping[q.start]],newlines[mapping[q.end]],q.occurrence_id) for q in navigation.occurrences)
    return display, spans


def revalidate_destination(*, summary_path: Path, bundle_root: Path, permitted_pages: Iterable[int],
                           navigation_sha256: str, occurrence_id: str) -> QuoteDestination | None:
    """Click-time revalidation; no cached destination or phrase-search fallback."""
    current = load_summary_navigation(summary_path=summary_path, bundle_root=bundle_root,
                                      permitted_pages=permitted_pages, new_contract_expected=True)
    if current.mode != "anchored" or current.navigation_sha256 != navigation_sha256:
        return None
    occurrence = current.occurrence(occurrence_id)
    return occurrence.destination if occurrence is not None else None
