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
        "Mother attended therapy.\nChild was safe.\n",
        encoding="utf-8",
    )
    (text_dir / "0002.txt").write_text(
        "The report discusses medication compliance.\n",
        encoding="utf-8",
    )
    (image_dir / "0001.png").write_bytes(b"fake png payload")
    source_map = {
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
            },
            {
                "file_name": "0002.txt",
                "file_page": 2,
                "text_path": "text_pages/0002.txt",
                "citation_label": "CT 2",
                "citation_key": "CT:2",
            },
        ],
        "documents": [
            {
                "id": "report:0002",
                "type": "report",
                "label": "Test Report",
                "citation_range": "CT 2-CT 2",
                "start_page": "0002",
                "end_page": "0002",
            }
        ],
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


def test_lookup_unknown_file_returns_no_matches(tmp_path) -> None:
    root = _write_case_bundle(tmp_path)

    payload = _run_helper(root, "lookup", "--file", "text_pages/9999.txt", "--json")

    assert payload["matches"] == []


def test_document_resolves_document_id(tmp_path) -> None:
    root = _write_case_bundle(tmp_path)

    payload = _run_helper(root, "document", "--id", "report:0002", "--json")

    assert payload["label"] == "Test Report"
    assert payload["citation_range"] == "CT 2-CT 2"


def test_removed_agent_search_and_rag_commands_are_unavailable(tmp_path) -> None:
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
