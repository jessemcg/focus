from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys


HELPER = Path(__file__).resolve().parents[1] / "focus" / "agent_helper.py"


CASE_OVERVIEW = """---
artifact: recordprep-case-overview
schema_version: 1
status: nonauthoritative-orientation
---

# Case Overview

> Orientation aid only. Verify every factual claim against mapped source pages before relying on or citing it.

## Parties and Roles

The synthetic record concerns a child and the child’s parents.

## Procedural Posture

The available material includes a hearing and a report.

## Key Events

- January 2, 2025: The first included hearing occurred.

## Principal Issues

The apparent issue concerns placement.

## Record Scope

The fixture contains two mapped source pages.
"""


def _write_case_bundle(tmp_path: Path) -> Path:
    root = tmp_path / "case_bundle"
    text_dir = root / "text_pages"
    image_dir = root / "image_pages"
    artifacts = root / "artifacts"
    text_dir.mkdir(parents=True)
    image_dir.mkdir(parents=True)
    artifacts.mkdir(parents=True)
    (text_dir / "0001.txt").write_text(
        "Mother attended ther-\napy. The maternal grandmother placement was safe.\n",
        encoding="utf-8",
    )
    (text_dir / "0002.txt").write_text(
        "The report discusses medication compliance.\n",
        encoding="utf-8",
    )
    (image_dir / "0001.png").write_bytes(b"fake png payload")
    source_map = {
        "schema_version": 2,
        "case_name": "Test Case",
        "root_dir": str(root),
        "paths": {
            "source_map": "artifacts/source_map.json",
            "case_overview": "artifacts/case_overview.md",
            "text_pages": "text_pages",
            "report_boundaries": "artifacts/report_boundaries.json",
        },
        "counts": {"pages": 2, "documents": 1},
        "citation_series": [
            {"series_id": "ct_main", "citation_prefix": "CT", "record_type": "CT"}
        ],
        "pages": [
            {
                "file_name": "0001.txt",
                "file_page": 1,
                "text_path": "text_pages/0001.txt",
                "image_path": "image_pages/0001.png",
                "page_type": "CT_form",
                "record_type": "CT",
                "citation_label": "CT 1",
                "citation_key": "CT:1",
                "document_ids": ["hearing:0001"],
                "hearing_id": "hearing:0001",
                "participants": [{
                    "id": "participant:grandmother",
                    "role_id": "relative",
                    "role_label": "Maternal grandmother",
                    "name": "Mary Jones",
                    "attendance_status": "present",
                    "speaking_status": "spoke",
                    "sworn_status": "unsworn",
                }],
                "witnesses": [{"id": "witness:mother", "name": "Mother"}],
                "examinations": [{"type": "direct", "examiner_role_id": "mothers_counsel"}],
            },
            {
                "file_name": "0002.txt",
                "file_page": 2,
                "text_path": "text_pages/0002.txt",
                "citation_label": "CT 2",
                "citation_key": "CT:2",
                "document_ids": ["report:0002"],
            },
        ],
        "documents": [
            {
                "id": "hearing:0001",
                "type": "hearing",
                "label": "January 2, 2025",
                "date": "January 2, 2025",
                "start_page": 1,
                "end_page": 1,
            },
            {
                "id": "report:0002",
                "type": "report",
                "label": "Test Report",
                "citation_range": "CT 2-CT 2",
                "start_page": 2,
                "end_page": 2,
            }
        ],
        "participant_index": {
            "schema_version": 2,
            "hearings": [{
                "id": "hearing:0001",
                "date": "January 2, 2025",
                "start_page": 1,
                "end_page": 1,
                "counsel": [{
                    "role_id": "mothers_counsel",
                    "role_label": "Mother’s counsel",
                    "name": "Jane Smith",
                    "aliases": ["Ms. Smith"],
                    "organization": "JCA",
                    "appearance_status": "present",
                }],
                "participants": [{
                    "id": "participant:grandmother",
                    "role_id": "relative",
                    "role_label": "Maternal grandmother",
                    "name": "Mary Jones",
                    "aliases": ["maternal grandmother"],
                    "attendance_status": "present",
                    "speaking_status": "spoke",
                    "sworn_status": "unsworn",
                }],
                "witness_status": "verified",
                "witnesses": [{
                    "id": "witness:mother",
                    "name": "Mother",
                    "aliases": ["the mother"],
                    "examinations": [{"start_file_page": 1, "end_file_page": 1}],
                }],
            }],
        },
        "lookup": {
            "by_citation_key": {"CT:1": ["0001.txt"]},
            "by_report_id": {},
        },
        "warnings": [],
    }
    (artifacts / "case_overview.md").write_text(
        CASE_OVERVIEW,
        encoding="utf-8",
    )
    (artifacts / "source_map.json").write_text(
        json.dumps(source_map),
        encoding="utf-8",
    )
    (artifacts / "report_boundaries.json").write_text("[]", encoding="utf-8")
    return root


def _run_helper(root: Path, *args: str) -> dict:
    completed = subprocess.run(
        [sys.executable, str(HELPER), "--case-root", str(root), *args],
        check=True,
        text=True,
        capture_output=True,
    )
    return json.loads(completed.stdout)


def _set_page_path(
    root: Path,
    file_name: str,
    key: str,
    value: str,
) -> None:
    source_map_path = root / "artifacts" / "source_map.json"
    source_map = json.loads(source_map_path.read_text(encoding="utf-8"))
    page = next(
        item for item in source_map["pages"] if item["file_name"] == file_name
    )
    page[key] = value
    source_map_path.write_text(json.dumps(source_map), encoding="utf-8")


def _set_page_image_path(root: Path, file_name: str, image_path: str) -> None:
    _set_page_path(root, file_name, "image_path", image_path)


def _set_page_text_path(root: Path, file_name: str, text_path: str) -> None:
    _set_page_path(root, file_name, "text_path", text_path)


def test_overview_returns_nonauthoritative_orientation_before_map(tmp_path) -> None:
    root = _write_case_bundle(tmp_path)

    payload = _run_helper(root, "overview", "--json")

    assert payload["available"] is True
    assert payload["status"] == "nonauthoritative-orientation"
    assert payload["schema_version"] == 1
    assert "# Case Overview" in payload["content"]
    assert "Orientation aid only" in payload["content"]


def test_overview_is_optional_for_older_bundles(tmp_path) -> None:
    root = _write_case_bundle(tmp_path)
    (root / "artifacts/case_overview.md").unlink()

    payload = _run_helper(root, "overview", "--json")

    assert payload == {
        "available": False,
        "status": "unavailable",
        "schema_version": None,
        "content": "",
    }


def test_overview_rejects_unversioned_content(tmp_path) -> None:
    root = _write_case_bundle(tmp_path)
    (root / "artifacts/case_overview.md").write_text(
        "# Case Overview\n\nUnversioned text.",
        encoding="utf-8",
    )

    payload = _run_helper(root, "overview", "--json")

    assert payload == {
        "available": False,
        "status": "invalid",
        "schema_version": None,
        "content": "",
    }


def test_map_outputs_case_summary(tmp_path) -> None:
    root = _write_case_bundle(tmp_path)

    payload = _run_helper(root, "map", "--json")

    assert payload["case_name"] == "Test Case"
    assert payload["paths"]["case_overview"] == "artifacts/case_overview.md"
    assert payload["counts"]["pages"] == 2
    assert payload["citation_series"][0]["citation_prefix"] == "CT"


def test_context_combines_overview_with_compact_schema_v2_map_status(tmp_path) -> None:
    root = _write_case_bundle(tmp_path)

    payload = _run_helper(root, "context", "--json")

    assert payload["overview"]["available"] is True
    source_map = payload["source_map"]
    assert source_map["status"] == "valid"
    assert source_map["schema_version"] == 2
    assert source_map["participant_index_schema_version"] == 2
    assert source_map["counts"]["pages"] == 2
    assert source_map["capabilities"] == {
        "document_scope": True,
        "hearing_date_scope": True,
        "participant_context": True,
        "witness_scope": True,
        "counsel_role_scope": True,
    }
    assert "documents" not in source_map
    assert "participant_index" not in source_map


def test_context_reports_unavailable_and_invalid_overviews_independently(
    tmp_path,
) -> None:
    root = _write_case_bundle(tmp_path)
    overview_path = root / "artifacts/case_overview.md"
    overview_path.unlink()

    unavailable = _run_helper(root, "context", "--json")

    assert unavailable["overview"]["status"] == "unavailable"
    assert unavailable["source_map"]["status"] == "valid"

    overview_path.write_text(
        "# Case Overview\n\nUnversioned text.",
        encoding="utf-8",
    )
    invalid = _run_helper(root, "context", "--json")

    assert invalid["overview"]["status"] == "invalid"
    assert invalid["source_map"]["status"] == "valid"


def test_context_reports_missing_and_invalid_source_maps(tmp_path) -> None:
    root = _write_case_bundle(tmp_path)
    source_map_path = root / "artifacts/source_map.json"
    source_map_path.unlink()

    missing = _run_helper(root, "context", "--json")

    assert missing["source_map"]["status"] == "unavailable"
    assert missing["source_map"]["available"] is False

    source_map_path.write_text("{not valid json", encoding="utf-8")
    invalid_json = _run_helper(root, "context", "--json")

    assert invalid_json["source_map"]["status"] == "invalid"
    assert invalid_json["source_map"]["available"] is False

    source_map_path.write_text(json.dumps({"documents": {}}), encoding="utf-8")
    malformed = _run_helper(root, "context", "--json")

    assert malformed["source_map"]["status"] == "invalid"
    assert malformed["source_map"]["available"] is False


def test_context_reports_schema_v1_capabilities_and_warnings(tmp_path) -> None:
    root = _write_case_bundle(tmp_path)
    source_map_path = root / "artifacts/source_map.json"
    source_map = json.loads(source_map_path.read_text(encoding="utf-8"))
    source_map["schema_version"] = 1
    source_map.pop("participant_index")
    source_map["warnings"] = ["Participant context unavailable."]
    source_map_path.write_text(json.dumps(source_map), encoding="utf-8")

    payload = _run_helper(root, "context", "--json")["source_map"]

    assert payload["schema_version"] == 1
    assert payload["participant_index_schema_version"] is None
    assert payload["capabilities"]["document_scope"] is True
    assert payload["capabilities"]["participant_context"] is False
    assert payload["capabilities"]["witness_scope"] is False
    assert payload["warnings"] == ["Participant context unavailable."]


def test_lookup_resolves_citation_label(tmp_path) -> None:
    root = _write_case_bundle(tmp_path)

    payload = _run_helper(root, "lookup", "--citation", "CT 1", "--json")

    assert payload["matches"][0]["file_name"] == "0001.txt"
    assert payload["matches"][0]["citation_label"] == "CT 1"
    assert payload["matches"][0]["resolved_text_path"] == str(
        root / "text_pages" / "0001.txt"
    )
    assert payload["matches"][0]["text_exists"] is True
    assert payload["matches"][0]["image_path"] == "image_pages/0001.png"
    assert payload["matches"][0]["resolved_image_path"] == str(
        root / "image_pages" / "0001.png"
    )
    assert payload["matches"][0]["image_exists"] is True


def test_lookup_resolves_file_reference_forms(tmp_path) -> None:
    root = _write_case_bundle(tmp_path)
    references = (
        "0001.txt",
        "text_pages/0001.txt",
        str(root / "text_pages" / "0001.txt"),
    )

    for reference in references:
        payload = _run_helper(root, "lookup", "--file", reference, "--json")
        assert payload["matches"][0]["citation_label"] == "CT 1"
        assert payload["matches"][0]["citation_key"] == "CT:1"
        assert payload["matches"][0]["resolved_image_path"] == str(
            root / "image_pages" / "0001.png"
        )
        assert payload["matches"][0]["image_exists"] is True


def test_lookup_reports_page_without_image_mapping(tmp_path) -> None:
    root = _write_case_bundle(tmp_path)

    payload = _run_helper(root, "lookup", "--citation", "CT 2", "--json")

    assert payload["matches"][0]["resolved_image_path"] == ""
    assert payload["matches"][0]["image_exists"] is False


def test_lookup_reports_safe_missing_image(tmp_path) -> None:
    root = _write_case_bundle(tmp_path)
    _set_page_image_path(root, "0002.txt", "image_pages/0002.png")

    payload = _run_helper(root, "lookup", "--citation", "CT 2", "--json")

    assert payload["matches"][0]["resolved_image_path"] == str(
        root / "image_pages" / "0002.png"
    )
    assert payload["matches"][0]["image_exists"] is False


def test_lookup_accepts_absolute_image_inside_case_root(tmp_path) -> None:
    root = _write_case_bundle(tmp_path)
    image_path = root / "image_pages" / "0001.png"
    _set_page_image_path(root, "0001.txt", str(image_path))

    payload = _run_helper(root, "lookup", "--citation", "CT 1", "--json")

    assert payload["matches"][0]["image_path"] == str(image_path)
    assert payload["matches"][0]["resolved_image_path"] == str(image_path)
    assert payload["matches"][0]["image_exists"] is True


def test_lookup_rejects_image_outside_case_root(tmp_path) -> None:
    root = _write_case_bundle(tmp_path)
    outside_image = tmp_path / "outside.png"
    outside_image.write_bytes(b"fake png payload")
    _set_page_image_path(root, "0002.txt", "../outside.png")

    payload = _run_helper(root, "lookup", "--citation", "CT 2", "--json")

    assert payload["matches"][0]["resolved_image_path"] == ""
    assert payload["matches"][0]["image_exists"] is False


def test_lookup_unknown_file_returns_no_matches(tmp_path) -> None:
    root = _write_case_bundle(tmp_path)

    payload = _run_helper(root, "lookup", "--file", "text_pages/9999.txt", "--json")

    assert payload["matches"] == []


def test_lookup_reports_safe_missing_text_path(tmp_path) -> None:
    root = _write_case_bundle(tmp_path)
    _set_page_text_path(root, "0001.txt", "text_pages/missing.txt")

    payload = _run_helper(root, "lookup", "--citation", "CT 1", "--json")
    search = _run_helper(root, "search", "--query", "mother", "--json")

    assert payload["matches"][0]["resolved_text_path"] == str(
        root / "text_pages/missing.txt"
    )
    assert payload["matches"][0]["text_exists"] is False
    assert search["total_matches"] == 0


def test_lookup_accepts_absolute_text_path_inside_case_root(tmp_path) -> None:
    root = _write_case_bundle(tmp_path)
    text_path = root / "text_pages/0001.txt"
    _set_page_text_path(root, "0001.txt", str(text_path))

    payload = _run_helper(root, "lookup", "--citation", "CT 1", "--json")

    assert payload["matches"][0]["resolved_text_path"] == str(text_path)
    assert payload["matches"][0]["text_exists"] is True


def test_lookup_and_search_reject_text_path_outside_case_root(tmp_path) -> None:
    root = _write_case_bundle(tmp_path)
    outside_text = tmp_path / "outside.txt"
    outside_text.write_text("maternal grandmother placement", encoding="utf-8")
    _set_page_text_path(root, "0001.txt", "../outside.txt")

    lookup = _run_helper(root, "lookup", "--citation", "CT 1", "--json")
    search = _run_helper(
        root,
        "search",
        "--query",
        "maternal grandmother placement",
        "--json",
    )

    assert lookup["matches"][0]["resolved_text_path"] == ""
    assert lookup["matches"][0]["text_exists"] is False
    assert search["total_matches"] == 0

    _set_page_text_path(root, "0001.txt", str(outside_text))
    absolute_lookup = _run_helper(
        root,
        "lookup",
        "--citation",
        "CT 1",
        "--json",
    )
    absolute_search = _run_helper(
        root,
        "search",
        "--query",
        "maternal grandmother placement",
        "--json",
    )

    assert absolute_lookup["matches"][0]["resolved_text_path"] == ""
    assert absolute_lookup["matches"][0]["text_exists"] is False
    assert absolute_search["total_matches"] == 0


def test_document_resolves_document_id(tmp_path) -> None:
    root = _write_case_bundle(tmp_path)

    payload = _run_helper(root, "document", "--id", "report:0002", "--json")

    assert payload["label"] == "Test Report"
    assert payload["citation_range"] == "CT 2-CT 2"


def test_search_normalizes_ocr_hyphenation_and_returns_citation_context(tmp_path) -> None:
    root = _write_case_bundle(tmp_path)

    payload = _run_helper(
        root,
        "search",
        "--query",
        "mother attended therapy",
        "--query",
        "maternal grandmother placement",
        "--max-results",
        "5",
        "--json",
    )

    assert payload["candidate_pages"] == 2
    assert payload["total_matches"] == 1
    match = payload["matches"][0]
    assert match["citation_label"] == "CT 1"
    assert match["text_path"] == "text_pages/0001.txt"
    assert match["resolved_text_path"] == str(root / "text_pages/0001.txt")
    assert match["text_exists"] is True
    assert match["participants"][0]["name"] == "Mary Jones"
    assert match["witnesses"][0]["name"] == "Mother"
    assert match["reason"] == "exact-phrase"


def test_search_uses_non_counsel_participant_metadata(tmp_path) -> None:
    root = _write_case_bundle(tmp_path)

    payload = _run_helper(
        root,
        "search",
        "--query",
        "Mary Jones",
        "--json",
    )

    assert payload["total_matches"] == 1
    assert payload["matches"][0]["reason"] == "participant-metadata"
    assert payload["matches"][0]["participants"][0]["role_id"] == "relative"


def test_search_scopes_by_witness_counsel_and_hearing_date(tmp_path) -> None:
    root = _write_case_bundle(tmp_path)

    payload = _run_helper(
        root,
        "search",
        "--query",
        "placement safe",
        "--witness",
        "the mother",
        "--counsel-role",
        "mothers_counsel",
        "--hearing-date",
        "January 2, 2025",
        "--json",
    )

    assert payload["candidate_pages"] == 1
    assert "ranking_hints" not in payload
    assert payload["matches"][0]["hearing_id"] == "hearing:0001"
    assert payload["matches"][0]["score"] > 65


def test_search_is_read_only(tmp_path) -> None:
    root = _write_case_bundle(tmp_path)
    before = sorted((path.relative_to(root), path.stat().st_mtime_ns) for path in root.rglob("*") if path.is_file())

    _run_helper(root, "search", "--query", "medication compliance", "--json")

    after = sorted((path.relative_to(root), path.stat().st_mtime_ns) for path in root.rglob("*") if path.is_file())
    assert after == before


def test_removed_legacy_search_commands_are_unavailable(tmp_path) -> None:
    root = _write_case_bundle(tmp_path)

    for command in ("grep", "rag"):
        completed = subprocess.run(
            [
                sys.executable,
                str(HELPER),
                "--case-root",
                str(root),
                command,
                "question",
            ],
            check=False,
            text=True,
            capture_output=True,
        )
        assert completed.returncode == 2
        assert "invalid choice" in completed.stderr


def test_missing_source_map_returns_structured_error(tmp_path) -> None:
    root = tmp_path / "empty_case"
    root.mkdir()

    completed = subprocess.run(
        [sys.executable, str(HELPER), "--case-root", str(root), "map", "--json"],
        check=False,
        text=True,
        capture_output=True,
    )

    assert completed.returncode == 1
    payload = json.loads(completed.stdout)
    assert payload["type"] == "FileNotFoundError"
