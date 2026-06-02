import json

from focus import (
    load_record_range_choices,
    record_range_choice_for_page,
    validate_sum_page_fields,
)


def test_load_record_range_choices_from_manifest_boundaries(tmp_path) -> None:
    artifacts = tmp_path / "artifacts"
    artifacts.mkdir()
    (tmp_path / "manifest.json").write_text(
        json.dumps(
            {
                "files": {
                    "hearing_boundaries": "artifacts/hearings.json",
                    "report_boundaries": "artifacts/reports.json",
                    "minutes_boundaries": "artifacts/minutes.json",
                }
            }
        ),
        encoding="utf-8",
    )
    (artifacts / "hearings.json").write_text(
        json.dumps([{"date": "July 30, 2025", "start_page": "0003", "end_page": "0016"}]),
        encoding="utf-8",
    )
    (artifacts / "reports.json").write_text(
        json.dumps(
            [
                {
                    "report_label": "July 30, 2025 - Status Review Report",
                    "start_page": "0044",
                    "end_page": "0059",
                }
            ]
        ),
        encoding="utf-8",
    )
    (artifacts / "minutes.json").write_text(
        json.dumps([{"date": "August 1, 2025", "start_page": "0278", "end_page": "0278"}]),
        encoding="utf-8",
    )

    choices = load_record_range_choices(tmp_path)

    assert [(choice.label, choice.start_page, choice.end_page) for choice in choices] == [
        ("Hearing - July 30, 2025", 3, 16),
        ("Report - July 30, 2025 - Status Review Report", 44, 59),
        ("Minute Order - August 1, 2025", 278, 278),
    ]


def test_record_range_choice_for_page_prefers_smallest_containing_choice(tmp_path) -> None:
    artifacts = tmp_path / "artifacts"
    artifacts.mkdir()
    (artifacts / "hearing_boundaries.json").write_text(
        json.dumps(
            [
                {"date": "Full", "start_page": "0003", "end_page": "0016"},
                {"date": "Narrow", "start_page": "0005", "end_page": "0006"},
            ]
        ),
        encoding="utf-8",
    )

    choices = load_record_range_choices(tmp_path)

    assert record_range_choice_for_page(choices, 5).label == "Hearing - Narrow"
    assert record_range_choice_for_page(choices, 17) is None


def test_validate_sum_page_fields_accepts_available_targets_only() -> None:
    validation = validate_sum_page_fields("3", "6", [1, 3, 5, 7])

    assert validation.valid is True
    assert validation.start_page == 3
    assert validation.end_page == 6
    assert validation.targets == (3, 5)
    assert validation.message == "2 pages"


def test_validate_sum_page_fields_rejects_invalid_ranges() -> None:
    pages = [1, 2, 3]

    assert validate_sum_page_fields("", "3", pages).message == "Enter start and end pages."
    assert validate_sum_page_fields("a", "3", pages).message == "Use digits only."
    assert validate_sum_page_fields("3", "1", pages).message == "Start must be before end."
    assert validate_sum_page_fields("10", "12", pages).message == "No matching pages."
