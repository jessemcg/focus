#!/usr/bin/env python3
"""Read-only record helper for Focus embedded Codex Agent sessions."""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import sqlite3
import sys
import tempfile
from pathlib import Path
from typing import Any


DEFAULT_RAG_CHUNK_COUNT = 8
RAG_PROVIDER_VOYAGE = "voyage"
RAG_PROVIDER_ISAACUS = "isaacus"
LEXICAL_STOPWORDS = {
    "about",
    "after",
    "also",
    "and",
    "are",
    "because",
    "before",
    "did",
    "does",
    "for",
    "from",
    "had",
    "has",
    "have",
    "how",
    "into",
    "that",
    "the",
    "their",
    "there",
    "this",
    "was",
    "were",
    "what",
    "when",
    "where",
    "which",
    "who",
    "why",
    "with",
}


def _read_json(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def _emit_json(payload: Any) -> None:
    print(json.dumps(payload, ensure_ascii=False, indent=2))


def _case_path(root: Path, relative: str | None, fallback: str) -> Path:
    if relative:
        candidate = Path(relative).expanduser()
        if not candidate.is_absolute():
            candidate = root / candidate
        return candidate.resolve(strict=False)
    return (root / fallback).resolve(strict=False)


def _load_source_map(root: Path) -> dict[str, Any]:
    path = root / "artifacts" / "source_map.json"
    data = _read_json(path)
    if not isinstance(data, dict):
        raise ValueError(f"Source map must be an object: {path}")
    return data


def _source_map_paths(root: Path, source_map: dict[str, Any]) -> dict[str, Path]:
    paths = source_map.get("paths") if isinstance(source_map.get("paths"), dict) else {}
    return {
        "source_map": _case_path(root, str(paths.get("source_map") or ""), "artifacts/source_map.json"),
        "text_pages": _case_path(root, str(paths.get("text_pages") or ""), "text_pages"),
        "image_pages": _case_path(root, str(paths.get("image_pages") or ""), "image_pages"),
        "case_overview": _case_path(root, str(paths.get("case_overview") or ""), "rag/case_overview.txt"),
        "vector_database": _case_path(root, str(paths.get("vector_database") or ""), "rag/vector_database"),
        "report_boundaries": _case_path(
            root,
            str(paths.get("report_boundaries") or ""),
            "artifacts/report_boundaries.json",
        ),
    }


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
        if file_name:
            lookup[file_name] = page
        file_page = page.get("file_page")
        if isinstance(file_page, int):
            lookup[f"{file_page:04d}.txt"] = page
    return lookup


def _coerce_page_number(value: Any) -> int | None:
    if isinstance(value, int):
        return value
    text = str(value or "").strip()
    if not text:
        return None
    match = re.search(r"(\d+)", text)
    if not match:
        return None
    return int(match.group(1))


def _page_by_number(source_map: dict[str, Any]) -> dict[int, dict[str, Any]]:
    pages = source_map.get("pages") if isinstance(source_map.get("pages"), list) else []
    lookup: dict[int, dict[str, Any]] = {}
    for page in pages:
        if not isinstance(page, dict):
            continue
        file_page = _coerce_page_number(page.get("file_page"))
        if file_page is not None:
            lookup[file_page] = page
    return lookup


def _lookup_pages_for_citation(source_map: dict[str, Any], citation: str) -> list[dict[str, Any]]:
    citation_key = _normalize_citation_key(citation)
    lookup = source_map.get("lookup") if isinstance(source_map.get("lookup"), dict) else {}
    by_citation = lookup.get("by_citation_key") if isinstance(lookup.get("by_citation_key"), dict) else {}
    raw = by_citation.get(citation_key)
    pages = source_map.get("pages") if isinstance(source_map.get("pages"), list) else []
    by_file = _page_by_file(source_map)
    if raw is None:
        return [
            page
            for page in pages
            if isinstance(page, dict)
            and _normalize_citation_key(str(page.get("citation_key") or "")) == citation_key
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
                page = by_file.get(item)
                if page:
                    matches.append(page)
        return matches
    if isinstance(raw, str):
        page = by_file.get(raw)
        return [page] if page else []
    return []


def _document_by_id(source_map: dict[str, Any], document_id: str) -> dict[str, Any] | None:
    documents = source_map.get("documents") if isinstance(source_map.get("documents"), list) else []
    for document in documents:
        if isinstance(document, dict) and str(document.get("id") or "") == document_id:
            return document
    lookup = source_map.get("lookup") if isinstance(source_map.get("lookup"), dict) else {}
    by_report = lookup.get("by_report_id") if isinstance(lookup.get("by_report_id"), dict) else {}
    raw = by_report.get(document_id)
    if isinstance(raw, dict):
        return raw
    return None


def _document_citation(document: dict[str, Any] | None) -> dict[str, Any]:
    if not document:
        return {}
    citation_range = str(document.get("citation_range") or "").strip()
    citation_label = str(document.get("citation_label") or document.get("citation") or "").strip()
    payload: dict[str, Any] = {
        "document_id": document.get("id", ""),
        "document_label": document.get("label") or document.get("title") or document.get("name") or "",
    }
    if citation_range:
        payload["citation_range"] = citation_range
    if citation_label:
        payload["citation_label"] = citation_label
    return payload


def _page_range_citation(source_map: dict[str, Any], start_page: Any, end_page: Any) -> dict[str, Any]:
    start_number = _coerce_page_number(start_page)
    end_number = _coerce_page_number(end_page if end_page not in (None, "") else start_page)
    if start_number is None:
        return {}
    if end_number is None:
        end_number = start_number
    by_number = _page_by_number(source_map)
    start = by_number.get(start_number)
    end = by_number.get(end_number)
    if not start:
        return {}
    start_label = str(start.get("citation_label") or "").strip()
    end_label = str((end or start).get("citation_label") or "").strip()
    if not start_label:
        return {}
    payload: dict[str, Any] = {
        "start_page": f"{start_number:04d}",
        "end_page": f"{end_number:04d}",
        "start_citation_label": start_label,
        "end_citation_label": end_label or start_label,
    }
    if end_number == start_number or not end_label or end_label == start_label:
        payload["citation_label"] = start_label
    else:
        payload["citation_range"] = f"{start_label}-{end_label}"
    return payload


def _resolve_chunk_citation(source_map: dict[str, Any], metadata: dict[str, Any]) -> dict[str, Any]:
    document_id = str(
        metadata.get("report_id")
        or metadata.get("document_id")
        or metadata.get("source_document_id")
        or ""
    ).strip()
    document_payload = _document_citation(_document_by_id(source_map, document_id)) if document_id else {}
    page_payload = _page_range_citation(
        source_map,
        metadata.get("start_page") or metadata.get("page") or metadata.get("file_page"),
        metadata.get("end_page") or metadata.get("page") or metadata.get("file_page"),
    )

    resolved: dict[str, Any] = {}
    if document_payload:
        resolved.update(document_payload)
    if page_payload:
        resolved.update({key: value for key, value in page_payload.items() if value})
    if resolved.get("citation_label") or resolved.get("citation_range"):
        resolved["citation_status"] = "resolved"
        resolved["citation_source"] = "source_map"
        return resolved
    return {"citation_status": "unresolved"}


def _copy_vector_database(vector_dir: Path) -> tempfile.TemporaryDirectory[str]:
    temp_dir = tempfile.TemporaryDirectory(prefix="focus-rag-vector-")
    target = Path(temp_dir.name) / "vector_database"
    shutil.copytree(vector_dir, target)
    return temp_dir


def _metadata_value(row: sqlite3.Row) -> Any:
    for key in ("string_value", "int_value", "float_value", "bool_value"):
        value = row[key]
        if value is not None:
            return bool(value) if key == "bool_value" else value
    return ""


def _question_terms(question: str) -> list[str]:
    seen: set[str] = set()
    terms: list[str] = []
    for term in re.findall(r"[A-Za-z0-9']{3,}", question.casefold()):
        if term in LEXICAL_STOPWORDS or term in seen:
            continue
        seen.add(term)
        terms.append(term)
    return terms


def _lexical_score(content: str, metadata: dict[str, Any], terms: list[str]) -> int:
    haystack = " ".join(
        [
            content,
            " ".join(str(value) for value in metadata.values() if value not in (None, "")),
        ]
    ).casefold()
    score = 0
    for term in terms:
        occurrences = haystack.count(term)
        if occurrences:
            score += 2 + min(occurrences, 8)
    return score


def _chroma_lexical_search(
    vector_dir: Path,
    source_map: dict[str, Any],
    question: str,
    k: int,
) -> list[dict[str, Any]]:
    db_path = vector_dir / "chroma.sqlite3"
    if not db_path.is_file():
        return []
    terms = _question_terms(question)
    if not terms:
        return []
    chunks_by_id: dict[int, dict[str, Any]] = {}
    uri = f"file:{db_path.as_posix()}?mode=ro"
    with sqlite3.connect(uri, uri=True) as connection:
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA query_only=ON")
        rows = connection.execute(
            """
            SELECT e.id, e.embedding_id, m.key, m.string_value, m.int_value, m.float_value, m.bool_value
            FROM embeddings e
            JOIN embedding_metadata m ON m.id = e.id
            ORDER BY e.id
            """
        )
        for row in rows:
            chunk = chunks_by_id.setdefault(
                int(row["id"]),
                {"embedding_id": row["embedding_id"], "metadata": {}, "content": ""},
            )
            key = str(row["key"] or "")
            value = _metadata_value(row)
            if key == "chroma:document":
                chunk["content"] = str(value or "")
            elif key:
                chunk["metadata"][key] = value

    ranked: list[tuple[int, dict[str, Any]]] = []
    for chunk in chunks_by_id.values():
        score = _lexical_score(str(chunk.get("content") or ""), chunk["metadata"], terms)
        if score > 0:
            ranked.append((score, chunk))
    ranked.sort(
        key=lambda item: (
            -item[0],
            str(item[1]["metadata"].get("source") or ""),
            int(_coerce_page_number(item[1]["metadata"].get("start_page")) or 0),
        )
    )

    results: list[dict[str, Any]] = []
    for rank, (score, chunk) in enumerate(ranked[:k], start=1):
        metadata = chunk["metadata"]
        citation = _resolve_chunk_citation(source_map, metadata)
        results.append(
            {
                "rank": rank,
                "metadata": metadata,
                "source": metadata.get("source") or metadata.get("page") or "",
                "lexical_score": score,
                **citation,
                "content": chunk.get("content") or "",
            }
        )
    return results


def _read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="ignore")


def _grep_text_pages(root: Path, source_map: dict[str, Any], phrase: str, limit: int) -> list[dict[str, Any]]:
    paths = _source_map_paths(root, source_map)
    text_dir = paths["text_pages"]
    by_file = _page_by_file(source_map)
    lowered = phrase.casefold()
    matches: list[dict[str, Any]] = []
    for path in sorted(text_dir.glob("*.txt")):
        text = _read_text(path)
        if lowered not in text.casefold():
            continue
        page = by_file.get(path.name, {})
        lines = text.splitlines()
        for line_no, line in enumerate(lines, start=1):
            if lowered not in line.casefold():
                continue
            matches.append(
                {
                    "source": str(path.relative_to(root)) if path.is_relative_to(root) else str(path),
                    "line": line_no,
                    "citation_label": page.get("citation_label", ""),
                    "citation_key": page.get("citation_key", ""),
                    "file_page": page.get("file_page"),
                    "text": line.strip(),
                }
            )
            if len(matches) >= limit:
                return matches
    return matches


def _load_config(config_path: Path | None) -> dict[str, Any]:
    if config_path is None:
        env_path = os.environ.get("FOCUS_CONFIG_FILE", "")
        config_path = Path(env_path).expanduser() if env_path else Path(__file__).resolve().parents[1] / "config.json"
    if not config_path.exists():
        return {}
    data = _read_json(config_path)
    return data if isinstance(data, dict) else {}


def _normalize_rag_provider(value: Any) -> str:
    provider = str(value or "").strip().casefold()
    return provider if provider in {RAG_PROVIDER_VOYAGE, RAG_PROVIDER_ISAACUS} else RAG_PROVIDER_VOYAGE


def _extract_embedding_vectors(response: Any) -> list[list[float]]:
    embeddings = getattr(response, "embeddings", None)
    if embeddings is None and isinstance(response, dict):
        embeddings = response.get("embeddings")
    if not isinstance(embeddings, list):
        raise ValueError("Invalid embeddings response format.")
    vectors: list[list[float]] = []
    for item in embeddings:
        vector = getattr(item, "embedding", None)
        if vector is None and isinstance(item, dict):
            vector = item.get("embedding")
        if not isinstance(vector, list):
            raise ValueError("Missing embedding vector in response.")
        vectors.append(vector)
    return vectors


def _build_embeddings(config: dict[str, Any]) -> Any:
    provider = _normalize_rag_provider(config.get("rag_provider"))
    if provider == RAG_PROVIDER_ISAACUS:
        api_key = str(config.get("rag_isaacus_api_key") or "").strip()
        model = str(config.get("rag_isaacus_model") or "kanon-2-embedder").strip()
        if not api_key:
            raise RuntimeError("Isaacus API key is missing in Focus config.")
        isaacus_module = __import__("isaacus")
        client = getattr(isaacus_module, "Isaacus")(api_key=api_key)

        class IsaacusEmbeddings:
            def embed_documents(self, texts: list[str]) -> list[list[float]]:
                if not texts:
                    return []
                response = client.embeddings.create(
                    model=model,
                    texts=texts,
                    task="retrieval/document",
                )
                return _extract_embedding_vectors(response)

            def embed_query(self, text: str) -> list[float]:
                response = client.embeddings.create(
                    model=model,
                    texts=[text],
                    task="retrieval/query",
                )
                vectors = _extract_embedding_vectors(response)
                if not vectors:
                    raise ValueError("Isaacus returned no embedding vectors.")
                return vectors[0]

        return IsaacusEmbeddings()

    api_key = str(
        config.get("rag_voyage_api_key")
        or config.get("voyage_api_key")
        or ""
    ).strip()
    model = str(
        config.get("rag_voyage_model")
        or config.get("voyage_model")
        or "voyage-law-2"
    ).strip()
    if not api_key:
        raise RuntimeError("Voyage API key is missing in Focus config.")
    from langchain_voyageai import VoyageAIEmbeddings  # type: ignore

    return VoyageAIEmbeddings(voyage_api_key=api_key, model=model)


def _rag_query(root: Path, source_map: dict[str, Any], question: str, k: int, config_path: Path | None) -> dict[str, Any]:
    from langchain_chroma import Chroma  # type: ignore

    paths = _source_map_paths(root, source_map)
    vector_dir = paths["vector_database"]
    if not vector_dir.is_dir():
        raise RuntimeError(f"Vector database not found: {vector_dir}")
    config = _load_config(config_path)
    try:
        embeddings = _build_embeddings(config)
        with _copy_vector_database(vector_dir) as temp_vector_root:
            temp_vector_dir = Path(temp_vector_root) / "vector_database"
            store = Chroma(persist_directory=str(temp_vector_dir), embedding_function=embeddings)
            docs = store.similarity_search(question, k=k)
        chunks: list[dict[str, Any]] = []
        for rank, doc in enumerate(docs, start=1):
            metadata = getattr(doc, "metadata", {}) or {}
            citation = _resolve_chunk_citation(source_map, metadata)
            chunks.append(
                {
                    "rank": rank,
                    "metadata": metadata,
                    "source": metadata.get("source") or metadata.get("page") or "",
                    **citation,
                    "content": getattr(doc, "page_content", "") or "",
                }
            )
        return {"question": question, "k": k, "retrieval_mode": "vector", "chunks": chunks}
    except Exception as exc:  # noqa: BLE001
        chunks = _chroma_lexical_search(vector_dir, source_map, question, k)
        return {
            "question": question,
            "k": k,
            "retrieval_mode": "lexical_fallback",
            "vector_error": f"{exc.__class__.__name__}: {exc}",
            "chunks": chunks,
        }


def command_map(args: argparse.Namespace) -> None:
    root = args.case_root.resolve(strict=False)
    source_map = _load_source_map(root)
    payload = {
        "case_name": source_map.get("case_name", ""),
        "root_dir": source_map.get("root_dir", ""),
        "counts": source_map.get("counts", {}),
        "paths": source_map.get("paths", {}),
        "citation_series": source_map.get("citation_series", []),
        "documents": source_map.get("documents", []),
        "warnings": source_map.get("warnings", []),
    }
    _emit_json(payload)


def command_lookup(args: argparse.Namespace) -> None:
    root = args.case_root.resolve(strict=False)
    source_map = _load_source_map(root)
    _emit_json({"citation": args.citation, "matches": _lookup_pages_for_citation(source_map, args.citation)})


def command_document(args: argparse.Namespace) -> None:
    root = args.case_root.resolve(strict=False)
    source_map = _load_source_map(root)
    document = _document_by_id(source_map, args.id)
    if document is None:
        raise RuntimeError(f"Document not found: {args.id}")
    _emit_json(document)


def command_grep(args: argparse.Namespace) -> None:
    root = args.case_root.resolve(strict=False)
    source_map = _load_source_map(root)
    _emit_json(
        {
            "query": args.phrase,
            "matches": _grep_text_pages(root, source_map, args.phrase, args.limit),
        }
    )


def command_rag(args: argparse.Namespace) -> None:
    root = args.case_root.resolve(strict=False)
    source_map = _load_source_map(root)
    _emit_json(_rag_query(root, source_map, args.question, args.k, args.config))


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--case-root",
        type=Path,
        default=Path(os.environ.get("FOCUS_AGENT_CASE_ROOT", ".")).expanduser(),
    )
    parser.add_argument("--config", type=Path, default=None)
    subparsers = parser.add_subparsers(dest="command", required=True)

    map_parser = subparsers.add_parser("map", help="Print source-map summary.")
    map_parser.add_argument("--json", action="store_true", help="Accepted for readability; output is always JSON.")
    map_parser.set_defaults(func=command_map)

    lookup_parser = subparsers.add_parser("lookup", help="Lookup pages by citation.")
    lookup_parser.add_argument("--citation", required=True)
    lookup_parser.add_argument("--json", action="store_true", help="Accepted for readability; output is always JSON.")
    lookup_parser.set_defaults(func=command_lookup)

    doc_parser = subparsers.add_parser("document", help="Lookup a source-map document by id.")
    doc_parser.add_argument("--id", required=True)
    doc_parser.add_argument("--json", action="store_true", help="Accepted for readability; output is always JSON.")
    doc_parser.set_defaults(func=command_document)

    grep_parser = subparsers.add_parser("grep", help="Search text pages.")
    grep_parser.add_argument("phrase")
    grep_parser.add_argument("--limit", type=int, default=20)
    grep_parser.add_argument("--json", action="store_true", help="Accepted for readability; output is always JSON.")
    grep_parser.set_defaults(func=command_grep)

    rag_parser = subparsers.add_parser("rag", help="Query the Focus vector database.")
    rag_parser.add_argument("question")
    rag_parser.add_argument("--k", type=int, default=DEFAULT_RAG_CHUNK_COUNT)
    rag_parser.add_argument("--json", action="store_true", help="Accepted for readability; output is always JSON.")
    rag_parser.set_defaults(func=command_rag)
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
