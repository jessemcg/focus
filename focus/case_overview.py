"""Read-only access to RecordPrep's optional case overview."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


_OVERVIEW_STATUS = "nonauthoritative-orientation"
_FRONT_MATTER_FIELDS = (
    "artifact: recordprep-case-overview",
    "schema_version: 1",
    f"status: {_OVERVIEW_STATUS}",
)


def case_overview_path(root: Path) -> Path | None:
    candidates: list[Path] = []
    try:
        manifest = json.loads((root / "manifest.json").read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError):
        manifest = {}
    if isinstance(manifest, dict):
        files = manifest.get("files")
        configured = files.get("case_overview") if isinstance(files, dict) else None
        if isinstance(configured, str) and configured.strip():
            candidates.append(root / configured)
    candidates.append(root / "artifacts" / "case_overview.md")

    resolved_root = root.resolve(strict=False)
    for candidate in candidates:
        try:
            resolved = candidate.resolve(strict=False)
            resolved.relative_to(resolved_root)
            if resolved.is_file():
                return resolved
        except (OSError, RuntimeError, ValueError):
            continue
    return None


def overview_payload(root: Path) -> dict[str, Any]:
    """Return the helper's overview contract, with source Markdown intact."""
    result: dict[str, Any] = {
        "available": False,
        "status": "unavailable",
        "schema_version": None,
        "content": "",
    }
    path = case_overview_path(root)
    if path is None:
        return result
    result["status"] = "invalid"
    try:
        text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeError):
        return result
    required = (*_FRONT_MATTER_FIELDS, "# Case Overview", "> Orientation aid only.")
    if any(fragment not in text for fragment in required):
        return result
    return {
        "available": True,
        "status": _OVERVIEW_STATUS,
        "schema_version": 1,
        "content": text,
    }


def overview_display_markdown(text: str) -> str:
    """Strip only a recognized, delimited leading metadata block for display."""
    lines = text.splitlines(keepends=True)
    if not lines or lines[0].strip() != "---":
        return text
    fields: set[str] = set()
    for index, line in enumerate(lines[1:], 1):
        field = line.strip()
        if field == "---":
            if fields.issuperset(_FRONT_MATTER_FIELDS):
                return "".join(lines[index + 1:]).lstrip("\n\r")
            break
        if field:
            key, separator, _value = field.partition(":")
            # Do not mistake a later thematic break for the end of metadata.
            if not separator or not key.replace("_", "").replace("-", "").isalnum():
                break
            fields.add(field)
    return text
