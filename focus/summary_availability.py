"""Read-only final-summary content checks; no GTK, profiles or model freshness.

Discovery precedence belongs to the caller. A missing/corrupt sidecar does not
make readable legacy prose unavailable; diagnostics distinguish that from empty.
"""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
from pathlib import Path
import re

TITLES = {
    "hearing": "Hearings Summary", "reports": "Reports Summary",
    "motions": "Motions Summary", "minutes": "Minutes Summary",
}


@dataclass(frozen=True)
class SummaryAvailability:
    path: Path | None
    status: str  # available, empty, missing, unreadable, intermediate
    diagnostics: tuple[str, ...] = ()

    @property
    def available(self) -> bool:
        return self.status == "available"


def file_signature(path: Path) -> tuple:
    try:
        info = path.stat()
        return (str(path), info.st_dev, info.st_ino, info.st_size,
                info.st_mtime_ns, info.st_ctime_ns)
    except OSError as exc:
        return (str(path), type(exc).__name__)


def filename_source(path: Path) -> str | None:
    """Known family prefixes precede arbitrary words in the case-name suffix."""
    family = re.match(r'^(?:summarized_|summary_)?(hearings?|reports?|motions?|minutes?)(?:_|\.|$)',
                      path.name.casefold())
    return ({'hearing': 'hearing', 'report': 'reports', 'motion': 'motions', 'minute': 'minutes'}
            [family[1].rstrip('s')] if family else None)


def discover_summary(root: Path, source: str, manifest_path: Path | None,
                     keys: tuple[str, ...], candidates: tuple[str, ...],
                     keywords: tuple[str, ...], *, cache: dict | None = None) -> SummaryAvailability:
    """Resolve the preferred final first, then assess its contents, never skip
    a current empty final in favor of a stale legacy summary. Cache only by
    case identity and file signatures; no asynchronous wrong-case callbacks.
    """
    paths = []
    diagnostics = []
    manifest = {}
    if manifest_path is not None:
        try:
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            if not isinstance(manifest, dict):
                raise ValueError("invalid manifest")
        except (OSError, UnicodeError, ValueError):
            diagnostics.append("manifest_unreadable_or_corrupt")
    files = manifest.get("files") if isinstance(manifest.get("files"), dict) else {}
    for key in keys:
        raw = files.get(key)
        if isinstance(raw, str) and raw.strip():
            path = Path(raw).expanduser()
            if not path.is_absolute():
                path = (manifest_path.parent if manifest_path else root) / path
            tier = 0 if key.startswith("summarized_") else 1 if "organized" in key else 3 if "consolidated" in key else 2
            paths.append((tier, path))
    directory = root / "summaries"
    try:
        entries = list(directory.iterdir())
        for path in entries:
            inferred = filename_source(path)
            if inferred and inferred != source:
                continue
            if path.name in candidates or any(word in path.name.casefold() for word in keywords):
                paths.append((1 if "organized" in path.name.casefold() else
                              3 if "consolidated" in path.name.casefold() else 2, path))
    except FileNotFoundError:
        entries = []
    except OSError:
        entries = []
        diagnostics.append("summary_directory_unreadable")
    signature = (str(root.resolve()), source,
                 file_signature(manifest_path) if manifest_path else None,
                 file_signature(root / "case_name.txt"),
                 tuple((tier, file_signature(path), file_signature(path.with_suffix(".meta.json")))
                       for tier, path in paths))
    if cache is not None and signature in cache:
        return cache[signature]
    try:
        case_name = (root / "case_name.txt").read_text(encoding="utf-8").replace("_", " ").strip()
    except (OSError, UnicodeError):
        case_name = ""
    result = SummaryAvailability(None, "missing", tuple(diagnostics))
    failed = None
    for _, path in sorted(paths, key=lambda item: (item[0], item[1].name.casefold())):
        if path.suffix.lower() not in (".txt", ".md"):
            continue
        if {"digests", "facts"} & set(re.split(r"[^a-z0-9]+", path.name.casefold())):
            continue
        current = inspect_summary(path, source, case_name=case_name)
        if current.status in ("missing", "intermediate"):
            continue
        if current.status == "unreadable":
            failed = current
            continue
        result = SummaryAvailability(current.path, current.status,
                                     tuple(diagnostics) + current.diagnostics)
        break
    else:
        if failed is not None:
            result = failed
        elif diagnostics:
            result = SummaryAvailability(None, "unreadable", tuple(diagnostics))
    if cache is not None:
        # Bounded to the current result for each kind, not a history of cases.
        for old in list(cache):
            if old[1] == source:
                del cache[old]
        cache[signature] = result
    return result


def inspect_summary(path: Path | None, source: str, *, case_name: str = "") -> SummaryAvailability:
    if path is None:
        return SummaryAvailability(None, "missing")
    try:
        data = path.read_bytes()
        text = data.decode("utf-8")
    except FileNotFoundError:
        return SummaryAvailability(path, "missing")
    except (OSError, UnicodeError):
        return SummaryAvailability(path, "unreadable", ("summary_unreadable",))
    if "recordprep:digest-" in text:
        return SummaryAvailability(path, "intermediate", ("digest_not_final",))
    diagnostics = []
    meta_path = path.with_suffix(".meta.json")
    if meta_path.exists():
        try:
            meta = json.loads(meta_path.read_text(encoding="utf-8"))
            expected_kind = "hearings" if source == "hearing" else source
            if isinstance(meta, dict) and meta.get("schema_version") == 6:
                from .profile_artifacts import motion_application_metadata
                if expected_kind != "motions":
                    raise ValueError("Schema 6 is motion-only.")
                motion_application_metadata(meta.get("application_metadata"))
            if (isinstance(meta, dict)
                    and meta.get("artifact") == "recordprep-summary-final-meta"
                    and type(meta.get("schema_version")) is int
                    and meta["schema_version"] in (3, 4, 5, 6)
                    and meta.get("kind") == expected_kind
                    and meta.get("final_text_sha256") == hashlib.sha256(data).hexdigest()
                    and isinstance(meta.get("item_ids"), list)
                    and all(isinstance(item, str) and item for item in meta["item_ids"])):
                if not meta["item_ids"]:
                    return SummaryAvailability(path, "empty")
            elif (source == 'minutes' and isinstance(meta, dict)
                  and meta.get('artifact') == 'recordprep-minute-summary'
                  and type(meta.get('schema_version')) is int and meta['schema_version'] in (1, 2, 3, 4, 5)
                  and meta.get('final_sha256') == hashlib.sha256(data).hexdigest()
                  and isinstance(meta.get('inputs'), dict)
                  and all(isinstance(key, str) and key and isinstance(value, str)
                          for key, value in meta['inputs'].items())):
                if not meta['inputs']:
                    return SummaryAvailability(path, 'empty')
            else:
                diagnostics.append("metadata_unusable_or_stale")
        except (OSError, UnicodeError, ValueError):
            diagnostics.append("metadata_unreadable_or_corrupt")
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    if not lines:
        return SummaryAvailability(path, "empty", tuple(diagnostics))
    title = TITLES.get(source, "")
    # Only the exact application title, optionally followed by this case's
    # exact name, is a historical zero-document output. A document heading
    # with null categories remains a real document, not a zero-item output.
    first = lines[0].removeprefix("# ")
    title_matches = first == title or (source == 'minutes' and first == 'Minute Orders Summary')
    if title_matches and (len(lines) == 1 or
                           (len(lines) == 2 and case_name and lines[1] == case_name)):
        return SummaryAvailability(path, "empty", tuple(diagnostics))
    return SummaryAvailability(path, "available", tuple(diagnostics))
