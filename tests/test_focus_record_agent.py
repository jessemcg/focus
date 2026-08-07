from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys


HELPER = Path(__file__).resolve().parents[1] / "focus" / "agent_helper.py"


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


def _set_page_image_path(root: Path, file_name: str, image_path: str) -> None:
    source_map_path = root / "artifacts" / "source_map.json"
    source_map = json.loads(source_map_path.read_text(encoding="utf-8"))
    page = next(
        item for item in source_map["pages"] if item["file_name"] == file_name
    )
    page["image_path"] = image_path
    source_map_path.write_text(json.dumps(source_map), encoding="utf-8")


def test_map_outputs_case_summary(tmp_path) -> None:
    root = _write_case_bundle(tmp_path)

    payload = _run_helper(root, "map", "--json")

    assert payload["case_name"] == "Test Case"
    assert payload["counts"]["pages"] == 2
    assert payload["citation_series"][0]["citation_prefix"] == "CT"


def test_lookup_resolves_citation_label(tmp_path) -> None:
    root = _write_case_bundle(tmp_path)

    payload = _run_helper(root, "lookup", "--citation", "CT 1", "--json")

    assert payload["matches"][0]["file_name"] == "0001.txt"
    assert payload["matches"][0]["citation_label"] == "CT 1"
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
        "--current-citation",
        "CT 1",
        "--json",
    )

    assert payload["candidate_pages"] == 1
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
