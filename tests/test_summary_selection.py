import json
from pathlib import Path

from focus.app import Focus
from focus.core import (
    HEARING_SUMMARY_CANDIDATES,
    HEARING_SUMMARY_MANIFEST_KEYS,
)


class SummaryFinder:
    _find_summary_in_dir = Focus._find_summary_in_dir
    _find_summary_in_manifest = Focus._find_summary_in_manifest

    def __init__(self, input_dir: Path) -> None:
        self.input_dir = input_dir
        self.toasts: list[str] = []

    def _ai_transient_toast(self, message: str) -> None:
        self.toasts.append(message)


def _find_hearing_summary(input_dir: Path) -> Path | None:
    finder = SummaryFinder(input_dir)
    return Focus._find_summary_in_dir(
        finder,
        "Hearing",
        HEARING_SUMMARY_CANDIDATES,
        ("hearing",),
        show_toast=False,
    )


def test_summary_dir_prefers_case_specific_organized_file(tmp_path) -> None:
    summaries_dir = tmp_path / "summaries"
    summaries_dir.mkdir()
    organized = summaries_dir / "hearings_sum_In_re_Michelle_W_organized.txt"
    organized.write_text("organized", encoding="utf-8")
    (summaries_dir / "hearing_sum.txt").write_text("ordinary", encoding="utf-8")
    (summaries_dir / "summarized_hearings_consolidated.txt").write_text(
        "consolidated",
        encoding="utf-8",
    )

    assert _find_hearing_summary(tmp_path) == organized


def test_summary_dir_prefers_ordinary_file_before_consolidated(tmp_path) -> None:
    summaries_dir = tmp_path / "summaries"
    summaries_dir.mkdir()
    ordinary = summaries_dir / "hearing_sum.txt"
    ordinary.write_text("ordinary", encoding="utf-8")
    (summaries_dir / "summarized_hearings_consolidated.txt").write_text(
        "consolidated",
        encoding="utf-8",
    )

    assert _find_hearing_summary(tmp_path) == ordinary


def test_summary_dir_keeps_consolidated_as_last_fallback(tmp_path) -> None:
    summaries_dir = tmp_path / "summaries"
    summaries_dir.mkdir()
    consolidated = summaries_dir / "summarized_hearings_consolidated.txt"
    consolidated.write_text("consolidated", encoding="utf-8")

    assert _find_hearing_summary(tmp_path) == consolidated


def test_preferred_summary_uses_organized_directory_file_before_old_manifest(
    tmp_path,
) -> None:
    summaries_dir = tmp_path / "summaries"
    summaries_dir.mkdir()
    organized = summaries_dir / "hearings_sum_In_re_Michelle_W_organized.txt"
    organized.write_text("organized", encoding="utf-8")
    consolidated = summaries_dir / "summarized_hearings_consolidated.txt"
    consolidated.write_text("consolidated", encoding="utf-8")
    manifest_path = tmp_path / "manifest.json"
    consolidated_relpath = "summaries/summarized_hearings_consolidated.txt"
    manifest_path.write_text(
        json.dumps(
            {
                "files": {
                    "consolidated_hearings": consolidated_relpath,
                }
            }
        ),
        encoding="utf-8",
    )
    finder = SummaryFinder(tmp_path)

    selected = Focus._find_preferred_summary_path(
        finder,
        "Hearing",
        manifest_path,
        HEARING_SUMMARY_MANIFEST_KEYS,
        HEARING_SUMMARY_CANDIDATES,
        ("hearing",),
        show_toast=False,
    )

    assert selected == organized
