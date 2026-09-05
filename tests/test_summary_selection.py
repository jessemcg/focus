import json
from pathlib import Path

from focus.app import Focus
from focus.core import (
    HEARING_SUMMARY_CANDIDATES,
    HEARING_SUMMARY_MANIFEST_KEYS,
    REPORTS_SUMMARY_CANDIDATES,
    REPORTS_SUMMARY_MANIFEST_KEYS,
)

DIGEST_MARKDOWN = (
    "# RecordPrep hearings digests — Case_Name\n"
    "\n"
    "<!-- recordprep:digest-document "
    '{"artifact": "recordprep-summary-digest-markdown"} -->\n'
    "\n"
    "Generated, nonauthoritative RecordPrep artifact.\n"
)


class SummaryFinder:
    _find_summary_in_dir = Focus._find_summary_in_dir
    _find_summary_in_manifest = Focus._find_summary_in_manifest
    _find_preferred_summary_path = Focus._find_preferred_summary_path
    _cached_summary_is_ineligible = Focus._cached_summary_is_ineligible
    _discard_ineligible_cached_summary = Focus._discard_ineligible_cached_summary

    def __init__(self, input_dir: Path) -> None:
        self.input_dir = input_dir
        self.toasts: list[str] = []
        self._summary_loaded_path: Path | None = None
        self._summary_raw = ""
        self._summary_edition = None
        self.discarded = 0

    def _ai_transient_toast(self, message: str) -> None:
        self.toasts.append(message)

    def _current_view_state(self):
        return self

    def _set_summary_text(self, text: str, *, switch_view: bool = True) -> None:
        self._summary_raw = text


def _find_hearing_summary(input_dir: Path) -> Path | None:
    finder = SummaryFinder(input_dir)
    return Focus._find_summary_in_dir(
        finder,
        "Hearing",
        HEARING_SUMMARY_CANDIDATES,
        ("hearing",),
        show_toast=False,
    )


def _preferred_hearing_summary(input_dir: Path, *, keys=None) -> Path | None:
    finder = SummaryFinder(input_dir)
    return finder._find_preferred_summary_path(
        "Hearing",
        input_dir / "manifest.json" if (input_dir / "manifest.json").exists() else None,
        keys or HEARING_SUMMARY_MANIFEST_KEYS,
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


def test_summary_dir_rejects_digest_markdown_even_alphabetically_first(tmp_path) -> None:
    summaries_dir = tmp_path / "summaries"
    summaries_dir.mkdir()
    # Alphabetically "hearings_digests_..." precedes "hearings_sum_...".
    digest = summaries_dir / "hearings_digests_Case_Name.md"
    digest.write_text(DIGEST_MARKDOWN, encoding="utf-8")
    final = summaries_dir / "hearings_sum_Case_Name.txt"
    final.write_text("final narrative", encoding="utf-8")

    assert _find_hearing_summary(tmp_path) == final


def test_summary_dir_returns_none_for_digest_only_folder(tmp_path) -> None:
    summaries_dir = tmp_path / "summaries"
    summaries_dir.mkdir()
    (summaries_dir / "hearings_digests_Case_Name.md").write_text(
        DIGEST_MARKDOWN, encoding="utf-8"
    )
    (summaries_dir / "reports_digests_Case_Name.jsonl").write_text("{}", encoding="utf-8")

    assert _find_hearing_summary(tmp_path) is None


def test_summary_dir_rejects_legacy_facts_family(tmp_path) -> None:
    summaries_dir = tmp_path / "summaries"
    summaries_dir.mkdir()
    (summaries_dir / "hearings_facts_Case_Name.jsonl").write_text("[]", encoding="utf-8")

    assert _find_hearing_summary(tmp_path) is None


def test_summary_dir_allows_ordinary_summary_mentioning_digest(tmp_path) -> None:
    summaries_dir = tmp_path / "summaries"
    summaries_dir.mkdir()
    ordinary = summaries_dir / "hearing_sum.txt"
    ordinary.write_text(
        "The court reviewed the digest of the record and ruled.", encoding="utf-8"
    )

    assert _find_hearing_summary(tmp_path) == ordinary


def test_summary_dir_rejects_renamed_digest_with_reserved_marker(tmp_path) -> None:
    summaries_dir = tmp_path / "summaries"
    summaries_dir.mkdir()
    renamed = summaries_dir / "hearing_notes.md"
    renamed.write_text(DIGEST_MARKDOWN, encoding="utf-8")

    assert _find_hearing_summary(tmp_path) is None


def test_summary_dir_rejects_unreadable_candidate(tmp_path) -> None:
    summaries_dir = tmp_path / "summaries"
    summaries_dir.mkdir()
    # A directory named like a summary is neither readable nor a regular file.
    (summaries_dir / "hearing_sum.txt").mkdir()

    assert _find_hearing_summary(tmp_path) is None


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


def test_preferred_summary_current_manifest_final_beats_directory_digest(tmp_path) -> None:
    summaries_dir = tmp_path / "summaries"
    summaries_dir.mkdir()
    digest = summaries_dir / "hearings_digests_Case_Name.md"
    digest.write_text(DIGEST_MARKDOWN, encoding="utf-8")
    final_relpath = "summaries/hearings_sum_Case_Name.txt"
    final = summaries_dir / "hearings_sum_Case_Name.txt"
    final.write_text("final narrative", encoding="utf-8")
    manifest_path = tmp_path / "manifest.json"
    manifest_path.write_text(
        json.dumps({"files": {"summarized_hearings": final_relpath}}),
        encoding="utf-8",
    )

    selected = _preferred_hearing_summary(tmp_path)

    assert selected == final


def test_preferred_summary_ignores_manifest_reference_to_digest(tmp_path) -> None:
    summaries_dir = tmp_path / "summaries"
    summaries_dir.mkdir()
    digest_relpath = "summaries/hearings_digests_Case_Name.md"
    (summaries_dir / "hearings_digests_Case_Name.md").write_text(
        DIGEST_MARKDOWN, encoding="utf-8"
    )
    ordinary = summaries_dir / "hearing_sum.txt"
    ordinary.write_text("ordinary", encoding="utf-8")
    manifest_path = tmp_path / "manifest.json"
    manifest_path.write_text(
        json.dumps({"files": {"summarized_hearings": digest_relpath}}),
        encoding="utf-8",
    )

    selected = _preferred_hearing_summary(tmp_path)

    assert selected == ordinary


def test_preferred_summary_ignores_renamed_digest_manifest_reference(tmp_path) -> None:
    summaries_dir = tmp_path / "summaries"
    summaries_dir.mkdir()
    (summaries_dir / "notes.md").write_text(DIGEST_MARKDOWN, encoding="utf-8")
    manifest_path = tmp_path / "manifest.json"
    manifest_path.write_text(
        json.dumps({"files": {"summarized_hearings": "summaries/notes.md"}}),
        encoding="utf-8",
    )

    assert _preferred_hearing_summary(tmp_path) is None


def test_preferred_summary_digest_only_folder_returns_none(tmp_path) -> None:
    summaries_dir = tmp_path / "summaries"
    summaries_dir.mkdir()
    (summaries_dir / "hearings_digests_Case_Name.md").write_text(
        DIGEST_MARKDOWN, encoding="utf-8"
    )

    assert _preferred_hearing_summary(tmp_path) is None


def test_preferred_summary_preserves_reports_precedence(tmp_path) -> None:
    summaries_dir = tmp_path / "summaries"
    summaries_dir.mkdir()
    (summaries_dir / "reports_digests_Case_Name.md").write_text(
        DIGEST_MARKDOWN.replace("hearings digests", "reports digests"),
        encoding="utf-8",
    )
    final = summaries_dir / "reports_sum_Case_Name.txt"
    final.write_text("final report narrative", encoding="utf-8")

    finder = SummaryFinder(tmp_path)
    selected = finder._find_preferred_summary_path(
        "Reports",
        None,
        REPORTS_SUMMARY_MANIFEST_KEYS,
        REPORTS_SUMMARY_CANDIDATES,
        ("report", "reports"),
        show_toast=False,
    )

    assert selected == final


def test_cached_digest_text_is_discarded(tmp_path) -> None:
    digest_path = tmp_path / "hearings_digests_Case_Name.md"
    digest_path.write_text(DIGEST_MARKDOWN, encoding="utf-8")
    finder = SummaryFinder(tmp_path)
    finder._summary_loaded_path = digest_path
    finder._summary_raw = DIGEST_MARKDOWN

    assert finder._cached_summary_is_ineligible() is True
    assert finder._discard_ineligible_cached_summary() is True
    assert finder._summary_loaded_path is None
    assert finder._summary_raw == ""
    # A second discard is a no-op: the rejected path is not restored.
    assert finder._discard_ineligible_cached_summary() is False


def test_cached_final_summary_is_not_discarded(tmp_path) -> None:
    final_path = tmp_path / "hearings_sum_Case_Name.txt"
    final_path.write_text("final narrative", encoding="utf-8")
    finder = SummaryFinder(tmp_path)
    finder._summary_loaded_path = final_path
    finder._summary_raw = "final narrative"

    assert finder._cached_summary_is_ineligible() is False
    assert finder._discard_ineligible_cached_summary() is False
    assert finder._summary_loaded_path == final_path


def test_cached_text_with_digest_marker_is_discarded_even_without_path(tmp_path) -> None:
    finder = SummaryFinder(tmp_path)
    finder._summary_loaded_path = None
    finder._summary_raw = "already cached digest text\n" + DIGEST_MARKDOWN

    assert finder._cached_summary_is_ineligible() is True
    assert finder._discard_ineligible_cached_summary() is True
