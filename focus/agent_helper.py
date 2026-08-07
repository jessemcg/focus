#!/usr/bin/env python3
"""Read-only record metadata helper for embedded PI Agent sessions."""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import unicodedata
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


def _case_overview_path(root: Path) -> Path | None:
    candidates: list[Path] = []
    manifest_path = root / "manifest.json"
    try:
        manifest = _read_json(manifest_path)
    except (OSError, UnicodeError, json.JSONDecodeError):
        manifest = {}
    if isinstance(manifest, dict):
        files = manifest.get("files") if isinstance(manifest.get("files"), dict) else {}
        configured = files.get("case_overview")
        if isinstance(configured, str) and configured.strip():
            candidates.append(root / configured)
    candidates.append(root / "artifacts" / "case_overview.md")

    resolved_root = root.resolve(strict=False)
    for candidate in candidates:
        try:
            resolved = candidate.resolve(strict=False)
            resolved.relative_to(resolved_root)
        except (OSError, RuntimeError, ValueError):
            continue
        if resolved.is_file():
            return resolved
    return None


def _overview_payload(root: Path) -> dict[str, Any]:
    path = _case_overview_path(root)
    if path is None:
        return {
            "available": False,
            "status": "unavailable",
            "schema_version": None,
            "content": "",
        }
    try:
        text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeError):
        return {
            "available": False,
            "status": "invalid",
            "schema_version": None,
            "content": "",
        }
    required = (
        "artifact: recordprep-case-overview",
        "schema_version: 1",
        "status: nonauthoritative-orientation",
        "# Case Overview",
        "> Orientation aid only.",
    )
    if any(fragment not in text for fragment in required):
        return {
            "available": False,
            "status": "invalid",
            "schema_version": None,
            "content": "",
        }
    return {
        "available": True,
        "status": "nonauthoritative-orientation",
        "schema_version": 1,
        "content": text,
    }


def command_overview(args: argparse.Namespace) -> None:
    root = args.case_root.resolve(strict=False)
    _emit_json(_overview_payload(root))


def _empty_source_map_context(status: str) -> dict[str, Any]:
    return {
        "available": False,
        "status": status,
        "schema_version": None,
        "participant_index_schema_version": None,
        "case_name": "",
        "counts": {},
        "citation_series": [],
        "warnings": [],
        "capabilities": {},
    }


def _source_map_context_payload(root: Path) -> dict[str, Any]:
    path = root / "artifacts" / "source_map.json"
    try:
        source_map = _read_json(path)
    except FileNotFoundError:
        return _empty_source_map_context("unavailable")
    except (OSError, UnicodeError, json.JSONDecodeError):
        return _empty_source_map_context("invalid")
    if not isinstance(source_map, dict):
        return _empty_source_map_context("invalid")

    raw_pages = source_map.get("pages")
    raw_documents = source_map.get("documents", [])
    raw_participant_index = source_map.get("participant_index")
    if raw_participant_index is None:
        raw_participant_index = {}
    raw_counts = source_map.get("counts", {})
    raw_citation_series = source_map.get("citation_series", [])
    raw_warnings = source_map.get("warnings", [])
    if (
        not isinstance(raw_pages, list)
        or not isinstance(raw_documents, list)
        or not isinstance(raw_participant_index, dict)
        or not isinstance(raw_counts, dict)
        or not isinstance(raw_citation_series, list)
        or not isinstance(raw_warnings, list)
    ):
        return _empty_source_map_context("invalid")
    raw_hearings = raw_participant_index.get("hearings", [])
    if not isinstance(raw_hearings, list):
        return _empty_source_map_context("invalid")

    documents = [item for item in raw_documents if isinstance(item, dict)]
    participant_index = raw_participant_index
    hearings = [item for item in raw_hearings if isinstance(item, dict)]
    capabilities = {
        "document_scope": bool(documents),
        "hearing_date_scope": any(
            document.get("type") == "hearing" and document.get("date")
            for document in documents
        ),
        "participant_context": bool(hearings),
        "witness_scope": any(
            isinstance(hearing.get("witnesses", []), list)
            and any(
                isinstance(item, dict)
                for item in hearing.get("witnesses", [])
            )
            for hearing in hearings
        ),
        "counsel_role_scope": any(
            isinstance(hearing.get("counsel", []), list)
            and any(
                isinstance(item, dict)
                for item in hearing.get("counsel", [])
            )
            for hearing in hearings
        ),
    }
    return {
        "available": True,
        "status": "valid",
        "schema_version": source_map.get("schema_version", 1),
        "participant_index_schema_version": participant_index.get("schema_version"),
        "case_name": source_map.get("case_name", ""),
        "counts": raw_counts,
        "citation_series": raw_citation_series,
        "warnings": raw_warnings,
        "capabilities": capabilities,
    }


def command_context(args: argparse.Namespace) -> None:
    root = args.case_root.resolve(strict=False)
    _emit_json(
        {
            "overview": _overview_payload(root),
            "source_map": _source_map_context_payload(root),
        }
    )


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


def _resolve_case_file(root: Path, value: object) -> tuple[str, bool]:
    raw_path = str(value or "").strip()
    if not raw_path:
        return "", False
    candidate = Path(raw_path).expanduser()
    if not candidate.is_absolute():
        candidate = root / candidate
    try:
        resolved = candidate.resolve(strict=False)
        resolved.relative_to(root)
    except (OSError, RuntimeError, ValueError):
        return "", False
    return str(resolved), resolved.is_file()


def _page_match_payload(root: Path, page: dict[str, Any]) -> dict[str, Any]:
    payload = dict(page)
    resolved_text_path, text_exists = _resolve_case_file(
        root,
        page.get("text_path"),
    )
    resolved_image_path, image_exists = _resolve_case_file(
        root,
        page.get("image_path"),
    )
    payload["resolved_text_path"] = resolved_text_path
    payload["text_exists"] = text_exists
    payload["resolved_image_path"] = resolved_image_path
    payload["image_exists"] = image_exists
    return payload


def _page_match_payloads(
    root: Path,
    pages: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    return [_page_match_payload(root, page) for page in pages]


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
            "schema_version": source_map.get("schema_version", 1),
            "case_name": source_map.get("case_name", ""),
            "root_dir": source_map.get("root_dir", ""),
            "counts": source_map.get("counts", {}),
            "paths": source_map.get("paths", {}),
            "citation_series": source_map.get("citation_series", []),
            "documents": source_map.get("documents", []),
            "participant_index": source_map.get("participant_index", {}),
            "warnings": source_map.get("warnings", []),
        }
    )


def command_lookup(args: argparse.Namespace) -> None:
    root = args.case_root.resolve(strict=False)
    source_map = _load_source_map(root)
    if args.citation:
        matches = _lookup_pages_for_citation(source_map, args.citation)
        _emit_json(
            {
                "citation": args.citation,
                "matches": _page_match_payloads(root, matches),
            }
        )
        return
    matches = _lookup_pages_for_file(source_map, args.file)
    _emit_json(
        {
            "file": args.file,
            "matches": _page_match_payloads(root, matches),
        }
    )


def _normalize_search_text(value: str) -> str:
    value = unicodedata.normalize("NFKC", value).casefold()
    value = re.sub(r"-\s*\n\s*", "", value)
    value = re.sub(r"[^\w]+", " ", value, flags=re.UNICODE)
    return " ".join(value.split())


def _document_page_numbers(document: dict[str, Any]) -> set[int]:
    try:
        start = int(document.get("start_page") or 0)
        end = int(document.get("end_page") or 0)
    except (TypeError, ValueError):
        return set()
    return set(range(start, end + 1)) if start and end >= start else set()


def _candidate_pages(source_map: dict[str, Any], args: argparse.Namespace) -> list[dict[str, Any]]:
    pages = [item for item in source_map.get("pages", []) if isinstance(item, dict)]
    allowed: set[int] | None = None
    documents = [item for item in source_map.get("documents", []) if isinstance(item, dict)]
    for document_id in args.document or []:
        document = _document_by_id(source_map, document_id)
        scope = _document_page_numbers(document) if document else set()
        allowed = scope if allowed is None else allowed & scope
    if args.hearing_date:
        wanted = _normalize_search_text(args.hearing_date)
        scope: set[int] = set()
        for document in documents:
            if document.get("type") == "hearing" and _normalize_search_text(str(document.get("date") or "")) == wanted:
                scope.update(_document_page_numbers(document))
        allowed = scope if allowed is None else allowed & scope
    participant = source_map.get("participant_index") if isinstance(source_map.get("participant_index"), dict) else {}
    hearings = [item for item in participant.get("hearings", []) if isinstance(item, dict)]
    if args.witness:
        wanted = _normalize_search_text(args.witness)
        scope: set[int] = set()
        for hearing in hearings:
            for witness in hearing.get("witnesses", []):
                if not isinstance(witness, dict):
                    continue
                names = [str(witness.get("name") or ""), *[str(item) for item in witness.get("aliases", [])]]
                if any(wanted in _normalize_search_text(name) or _normalize_search_text(name) in wanted for name in names if name):
                    for exam in witness.get("examinations", []):
                        if not isinstance(exam, dict):
                            continue
                        try:
                            start = int(exam.get("start_file_page") or 0)
                            end = int(exam.get("end_file_page") or start)
                        except (TypeError, ValueError):
                            continue
                        scope.update(range(start, end + 1))
        allowed = scope if allowed is None else allowed & scope
    if args.counsel_role:
        wanted = _normalize_search_text(args.counsel_role).replace(" ", "_")
        scope: set[int] = set()
        for hearing in hearings:
            if any(
                _normalize_search_text(str(item.get("role_id") or "")).replace(" ", "_") == wanted
                or _normalize_search_text(str(item.get("role_label") or "")).replace(" ", "_") == wanted
                for item in hearing.get("counsel", []) if isinstance(item, dict)
            ):
                try:
                    scope.update(range(int(hearing.get("start_page") or 0), int(hearing.get("end_page") or -1) + 1))
                except (TypeError, ValueError):
                    pass
        allowed = scope if allowed is None else allowed & scope
    if allowed is None:
        return pages
    return [page for page in pages if isinstance(page.get("file_page"), int) and page["file_page"] in allowed]


def _participant_aliases_for_page(source_map: dict[str, Any], page_number: int) -> list[str]:
    participant = source_map.get("participant_index") if isinstance(source_map.get("participant_index"), dict) else {}
    aliases: list[str] = []
    for hearing in participant.get("hearings", []):
        if not isinstance(hearing, dict):
            continue
        try:
            if not int(hearing.get("start_page") or 0) <= page_number <= int(hearing.get("end_page") or 0):
                continue
        except (TypeError, ValueError):
            continue
        for person in [
            *hearing.get("counsel", []),
            *hearing.get("participants", []),
            *hearing.get("witnesses", []),
        ]:
            if not isinstance(person, dict):
                continue
            aliases.extend(
                str(value) for value in (
                    person.get("name"), person.get("role_id"), person.get("role_label"),
                    *person.get("aliases", []),
                ) if value
            )
    return aliases


def _search_score(normalized_text: str, normalized_query: str, metadata: str) -> tuple[float, str]:
    if not normalized_query:
        return 0.0, ""
    if normalized_query in normalized_text:
        return 100.0 + min(20.0, len(normalized_query) / 10), "exact-phrase"
    terms = [term for term in normalized_query.split() if len(term) > 1]
    if not terms:
        return 0.0, ""
    positions = [normalized_text.find(term) for term in terms]
    present = [position for position in positions if position >= 0]
    metadata_hits = sum(term in metadata for term in terms)
    if len(present) == len(terms):
        span = max(present) - min(present) if len(present) > 1 else 0
        return 65.0 + 20.0 / (1.0 + span / 100.0) + metadata_hits * 2, "all-terms"
    if present:
        return 15.0 * len(present) / len(terms) + metadata_hits * 3, "partial-terms"
    if metadata_hits:
        return 10.0 + metadata_hits * 3, "participant-metadata"
    return 0.0, ""


def command_search(args: argparse.Namespace) -> None:
    root = args.case_root.resolve(strict=False)
    source_map = _load_source_map(root)
    queries = [value for value in args.query if _normalize_search_text(value)]
    candidates = _candidate_pages(source_map, args)
    near_pages = _lookup_pages_for_citation(source_map, args.current_citation) if args.current_citation else []
    near_number = int(near_pages[0].get("file_page") or 0) if near_pages else 0
    results: list[dict[str, Any]] = []
    for page in candidates:
        text_path = str(page.get("text_path") or "").strip()
        resolved_text_path, text_exists = _resolve_case_file(root, text_path)
        if not text_exists:
            continue
        try:
            raw_text = Path(resolved_text_path).read_text(
                encoding="utf-8",
                errors="ignore",
            )
        except OSError:
            continue
        normalized_text = _normalize_search_text(raw_text)
        page_number = int(page.get("file_page") or 0)
        aliases = _participant_aliases_for_page(source_map, page_number)
        metadata = _normalize_search_text(" ".join([
            str(page.get("citation_label") or ""), str(page.get("page_type") or ""),
            *[str(value) for value in page.get("document_ids", [])], *aliases,
        ]))
        best_score = 0.0
        best_reason = ""
        matched: list[str] = []
        for query in queries:
            score, reason = _search_score(normalized_text, _normalize_search_text(query), metadata)
            if score > 0:
                matched.append(query)
            if score > best_score:
                best_score, best_reason = score, reason
        if not best_score:
            continue
        if near_number:
            best_score += max(0.0, 12.0 - abs(page_number - near_number) * 0.5)
        first_terms = [_normalize_search_text(value).split()[0] for value in matched if _normalize_search_text(value).split()]
        compact = " ".join(raw_text.split())
        position = -1
        for term in first_terms:
            position = compact.casefold().find(term.casefold())
            if position >= 0:
                break
        if position < 0:
            position = 0
        snippet = compact[max(0, position - 220): position + 500]
        if position > 220:
            snippet = "…" + snippet
        if position + 500 < len(compact):
            snippet += "…"
        results.append({
            "score": round(best_score, 3), "reason": best_reason,
            "matched_queries": matched, "citation_label": page.get("citation_label", ""),
            "citation_key": page.get("citation_key", ""), "file_page": page_number,
            "text_path": text_path, "resolved_text_path": resolved_text_path,
            "text_exists": True, "document_ids": page.get("document_ids", []),
            "hearing_id": page.get("hearing_id", ""),
            "participants": page.get("participants", []),
            "witnesses": page.get("witnesses", []),
            "examinations": page.get("examinations", []), "snippet": snippet,
        })
    results.sort(key=lambda item: (-float(item["score"]), int(item["file_page"])))
    total = len(results)
    limited = results[: args.max_results]
    _emit_json({
        "queries": queries, "scopes": {
            "document": args.document or [], "hearing_date": args.hearing_date or "",
            "witness": args.witness or "", "counsel_role": args.counsel_role or "",
            "current_citation": args.current_citation or "",
        },
        "ranking_hints": {"current_citation": args.current_citation or ""},
        "candidate_pages": len(candidates), "total_matches": total,
        "truncated": total > len(limited), "matches": limited,
    })


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

    overview_parser = subparsers.add_parser(
        "overview",
        help="Read the optional nonauthoritative case-orientation overview.",
    )
    overview_parser.add_argument(
        "--json",
        action="store_true",
        help="Accepted for readability; output is always JSON.",
    )
    overview_parser.set_defaults(func=command_overview)

    context_parser = subparsers.add_parser(
        "context",
        help="Read compact overview and source-map research context.",
    )
    context_parser.add_argument(
        "--json",
        action="store_true",
        help="Accepted for readability; output is always JSON.",
    )
    context_parser.set_defaults(func=command_context)

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

    search_parser = subparsers.add_parser(
        "search",
        help="Search source pages on demand without an index or database.",
    )
    search_parser.add_argument("--query", action="append", required=True)
    search_parser.add_argument("--document", action="append")
    search_parser.add_argument("--hearing-date")
    search_parser.add_argument("--witness")
    search_parser.add_argument("--counsel-role")
    search_parser.add_argument("--current-citation")
    search_parser.add_argument("--max-results", type=int, default=20, choices=range(1, 101))
    search_parser.add_argument("--json", action="store_true")
    search_parser.set_defaults(func=command_search)

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
