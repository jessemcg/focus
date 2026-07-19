#!/usr/bin/env python3
"""Read-only record metadata helper for embedded PI Agent sessions."""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from pathlib import Path
from typing import Any


def _read_json(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def _emit_json(payload: Any) -> None:
    print(json.dumps(payload, ensure_ascii=False, indent=2))


def _load_source_map(root: Path) -> dict[str, Any]:
    path = root / "artifacts" / "source_map.json"
    data = _read_json(path)
    if not isinstance(data, dict):
        raise ValueError(f"Source map must be an object: {path}")
    return data


def _normalize_citation_key(value: str) -> str:
    cleaned = re.sub(r"\s+", " ", value.strip().upper())
    match = re.fullmatch(r"([A-Z]+)\s*[: ]\s*(\d+)", cleaned)
    if match:
        return f"{match.group(1)}:{int(match.group(2))}"
    return cleaned.replace(" ", ":")


def _page_by_file(source_map: dict[str, Any]) -> dict[str, dict[str, Any]]:
    pages = source_map.get("pages") if isinstance(source_map.get("pages"), list) else []
    lookup: dict[str, dict[str, Any]] = {}
    for page in pages:
        if not isinstance(page, dict):
            continue
        file_name = str(page.get("file_name") or "").strip()
        text_path = str(page.get("text_path") or "").strip()
        if file_name:
            lookup[file_name] = page
        if text_path:
            lookup[text_path.replace("\\", "/")] = page
        file_page = page.get("file_page")
        if isinstance(file_page, int):
            lookup[f"{file_page:04d}.txt"] = page
    return lookup


def _lookup_pages_for_citation(
    source_map: dict[str, Any],
    citation: str,
) -> list[dict[str, Any]]:
    citation_key = _normalize_citation_key(citation)
    lookup = source_map.get("lookup") if isinstance(source_map.get("lookup"), dict) else {}
    by_citation = (
        lookup.get("by_citation_key")
        if isinstance(lookup.get("by_citation_key"), dict)
        else {}
    )
    raw = by_citation.get(citation_key)
    pages = source_map.get("pages") if isinstance(source_map.get("pages"), list) else []
    by_file = _page_by_file(source_map)
    if raw is None:
        return [
            page
            for page in pages
            if isinstance(page, dict)
            and _normalize_citation_key(str(page.get("citation_key") or ""))
            == citation_key
        ]
    if isinstance(raw, dict):
        return [raw]
    if isinstance(raw, list):
        matches: list[dict[str, Any]] = []
        for item in raw:
            if isinstance(item, dict):
                matches.append(item)
            elif isinstance(item, int):
                page = by_file.get(f"{item:04d}.txt")
                if page:
                    matches.append(page)
            elif isinstance(item, str):
                page = by_file.get(item.replace("\\", "/")) or by_file.get(
                    Path(item).name
                )
                if page:
                    matches.append(page)
        return matches
    if isinstance(raw, str):
        page = by_file.get(raw.replace("\\", "/")) or by_file.get(Path(raw).name)
        return [page] if page else []
    return []


def _lookup_pages_for_file(
    source_map: dict[str, Any],
    file_reference: str,
) -> list[dict[str, Any]]:
    normalized = file_reference.strip().replace("\\", "/")
    if not normalized:
        return []
    file_name = Path(normalized).name
    pages = source_map.get("pages") if isinstance(source_map.get("pages"), list) else []
    matches: list[dict[str, Any]] = []
    for page in pages:
        if not isinstance(page, dict):
            continue
        page_file = str(page.get("file_name") or "").strip().replace("\\", "/")
        text_path = str(page.get("text_path") or "").strip().replace("\\", "/")
        if (
            normalized == page_file
            or normalized == text_path
            or file_name == page_file
            or (text_path and normalized.endswith(f"/{text_path}"))
        ):
            matches.append(page)
    return matches


def _document_by_id(
    source_map: dict[str, Any],
    document_id: str,
) -> dict[str, Any] | None:
    documents = (
        source_map.get("documents")
        if isinstance(source_map.get("documents"), list)
        else []
    )
    for document in documents:
        if isinstance(document, dict) and str(document.get("id") or "") == document_id:
            return document
    lookup = source_map.get("lookup") if isinstance(source_map.get("lookup"), dict) else {}
    by_report = (
        lookup.get("by_report_id")
        if isinstance(lookup.get("by_report_id"), dict)
        else {}
    )
    raw = by_report.get(document_id)
    return raw if isinstance(raw, dict) else None


def command_map(args: argparse.Namespace) -> None:
    root = args.case_root.resolve(strict=False)
    source_map = _load_source_map(root)
    _emit_json(
        {
            "case_name": source_map.get("case_name", ""),
            "root_dir": source_map.get("root_dir", ""),
            "counts": source_map.get("counts", {}),
            "paths": source_map.get("paths", {}),
            "citation_series": source_map.get("citation_series", []),
            "documents": source_map.get("documents", []),
            "warnings": source_map.get("warnings", []),
        }
    )


def command_lookup(args: argparse.Namespace) -> None:
    root = args.case_root.resolve(strict=False)
    source_map = _load_source_map(root)
    if args.citation:
        _emit_json(
            {
                "citation": args.citation,
                "matches": _lookup_pages_for_citation(source_map, args.citation),
            }
        )
        return
    _emit_json(
        {
            "file": args.file,
            "matches": _lookup_pages_for_file(source_map, args.file),
        }
    )


def command_document(args: argparse.Namespace) -> None:
    root = args.case_root.resolve(strict=False)
    source_map = _load_source_map(root)
    document = _document_by_id(source_map, args.id)
    if document is None:
        raise RuntimeError(f"Document not found: {args.id}")
    _emit_json(document)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--case-root",
        type=Path,
        default=Path(os.environ.get("FOCUS_AGENT_CASE_ROOT", ".")).expanduser(),
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    map_parser = subparsers.add_parser("map", help="Print source-map summary.")
    map_parser.add_argument(
        "--json",
        action="store_true",
        help="Accepted for readability; output is always JSON.",
    )
    map_parser.set_defaults(func=command_map)

    lookup_parser = subparsers.add_parser(
        "lookup",
        help="Lookup source-map pages by record citation or text-page file.",
    )
    lookup_group = lookup_parser.add_mutually_exclusive_group(required=True)
    lookup_group.add_argument("--citation")
    lookup_group.add_argument("--file")
    lookup_parser.add_argument(
        "--json",
        action="store_true",
        help="Accepted for readability; output is always JSON.",
    )
    lookup_parser.set_defaults(func=command_lookup)

    doc_parser = subparsers.add_parser(
        "document",
        help="Lookup a source-map document by id.",
    )
    doc_parser.add_argument("--id", required=True)
    doc_parser.add_argument(
        "--json",
        action="store_true",
        help="Accepted for readability; output is always JSON.",
    )
    doc_parser.set_defaults(func=command_document)
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        args.func(args)
    except Exception as exc:  # noqa: BLE001
        _emit_json({"error": str(exc), "type": exc.__class__.__name__})
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
