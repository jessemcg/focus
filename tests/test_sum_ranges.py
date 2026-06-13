import json

from focus import (
    TranscriptPageIndex,
    load_transcript_page_index,
    validate_sum_page_fields,
)


def _write_transcript_index(tmp_path, entries) -> TranscriptPageIndex:
    path = tmp_path / "transcript_page_numbers.json"
    path.write_text(json.dumps({"entries": entries}), encoding="utf-8")
    return load_transcript_page_index(path)


def test_validate_sum_page_fields_resolves_unique_bare_transcript_pages(tmp_path) -> None:
    index = _write_transcript_index(
        tmp_path,
        [
            {
                "file_page": 3,
                "record_type": "RT",
                "transcript_page_number": 3,
                "citation_label": "RT 3",
                "status": "selected",
            },
            {
                "file_page": 4,
                "record_type": "RT",
                "transcript_page_number": 4,
                "citation_label": "RT 4",
                "status": "selected",
            },
        ],
    )

    validation = validate_sum_page_fields("3", "4", [1, 3, 4, 10], index)

    assert validation.valid is True
    assert validation.start_page == 3
    assert validation.end_page == 4
    assert validation.targets == (3, 4)
    assert validation.start_label == "RT 3"
    assert validation.end_label == "RT 4"


def test_validate_sum_page_fields_resolves_prefixed_duplicate_transcript_page(tmp_path) -> None:
    index = _write_transcript_index(
        tmp_path,
        [
            {
                "file_page": 1,
                "record_type": "CT",
                "transcript_page_number": 1,
                "citation_prefix": "1CT",
                "citation_label": "1CT 1",
                "status": "selected",
            },
            {
                "file_page": 401,
                "record_type": "CT",
                "transcript_page_number": 1,
                "citation_prefix": "2CT",
                "citation_label": "2CT 1",
                "status": "selected",
            },
        ],
    )

    validation = validate_sum_page_fields("2CT 1", "2CT 1", [1, 401], index)

    assert validation.valid is True
    assert validation.targets == (401,)
    assert validation.start_label == "2CT 1"
    assert validation.end_label == "2CT 1"


def test_validate_sum_page_fields_infers_end_prefix_from_start_prefix(tmp_path) -> None:
    index = _write_transcript_index(
        tmp_path,
        [
            {
                "file_page": 10,
                "record_type": "CT",
                "citation_prefix": "1CT",
                "transcript_page_number": 25,
                "citation_label": "1CT 25",
                "status": "selected",
            },
            {
                "file_page": 20,
                "record_type": "CT",
                "citation_prefix": "1CT",
                "transcript_page_number": 40,
                "citation_label": "1CT 40",
                "status": "selected",
            },
            {
                "file_page": 410,
                "record_type": "CT",
                "citation_prefix": "2CT",
                "transcript_page_number": 40,
                "citation_label": "2CT 40",
                "status": "selected",
            },
        ],
    )

    validation = validate_sum_page_fields("1CT 25", "40", [10, 20, 410], index)

    assert validation.valid is True
    assert validation.targets == (10, 20)
    assert validation.start_label == "1CT 25"
    assert validation.end_label == "1CT 40"


def test_validate_sum_page_fields_infers_start_prefix_from_end_prefix(tmp_path) -> None:
    index = _write_transcript_index(
        tmp_path,
        [
            {
                "file_page": 10,
                "record_type": "CT",
                "citation_prefix": "1CT",
                "transcript_page_number": 25,
                "citation_label": "1CT 25",
                "status": "selected",
            },
            {
                "file_page": 20,
                "record_type": "CT",
                "citation_prefix": "1CT",
                "transcript_page_number": 40,
                "citation_label": "1CT 40",
                "status": "selected",
            },
            {
                "file_page": 410,
                "record_type": "CT",
                "citation_prefix": "2CT",
                "transcript_page_number": 25,
                "citation_label": "2CT 25",
                "status": "selected",
            },
        ],
    )

    validation = validate_sum_page_fields("25", "1CT 40", [10, 20, 410], index)

    assert validation.valid is True
    assert validation.targets == (10, 20)
    assert validation.start_label == "1CT 25"
    assert validation.end_label == "1CT 40"


def test_validate_sum_page_fields_prompts_for_duplicate_bare_range_despite_current_page(tmp_path) -> None:
    index = _write_transcript_index(
        tmp_path,
        [
            {
                "file_page": 10,
                "record_type": "CT",
                "citation_prefix": "1CT",
                "transcript_page_number": 25,
                "citation_label": "1CT 25",
                "status": "selected",
            },
            {
                "file_page": 20,
                "record_type": "CT",
                "citation_prefix": "1CT",
                "transcript_page_number": 40,
                "citation_label": "1CT 40",
                "status": "selected",
            },
            {
                "file_page": 410,
                "record_type": "CT",
                "citation_prefix": "2CT",
                "transcript_page_number": 25,
                "citation_label": "2CT 25",
                "status": "selected",
            },
            {
                "file_page": 420,
                "record_type": "CT",
                "citation_prefix": "2CT",
                "transcript_page_number": 40,
                "citation_label": "2CT 40",
                "status": "selected",
            },
        ],
    )

    validation = validate_sum_page_fields("25", "40", [10, 20, 410, 420], index, current_page=410)

    assert validation.valid is False
    assert [choice.label for choice in validation.ambiguous_range_choices] == [
        "1CT 25-1CT 40",
        "2CT 25-2CT 40",
    ]


def test_validate_sum_page_fields_infers_only_matching_bare_series(tmp_path) -> None:
    index = _write_transcript_index(
        tmp_path,
        [
            {
                "file_page": 10,
                "record_type": "RT",
                "citation_prefix": "RT",
                "transcript_page_number": 3,
                "citation_label": "RT 3",
                "status": "selected",
            },
            {
                "file_page": 11,
                "record_type": "RT",
                "citation_prefix": "RT",
                "transcript_page_number": 4,
                "citation_label": "RT 4",
                "status": "selected",
            },
            {
                "file_page": 410,
                "record_type": "CT",
                "citation_prefix": "1CT",
                "transcript_page_number": 3,
                "citation_label": "1CT 3",
                "status": "selected",
            },
        ],
    )

    validation = validate_sum_page_fields("3", "4", [10, 11, 410], index)

    assert validation.valid is True
    assert validation.targets == (10, 11)
    assert validation.start_label == "RT 3"
    assert validation.end_label == "RT 4"


def test_validate_sum_page_fields_reports_ambiguous_bare_transcript_range(tmp_path) -> None:
    index = _write_transcript_index(
        tmp_path,
        [
            {
                "file_page": 1,
                "record_type": "CT",
                "transcript_page_number": 1,
                "citation_prefix": "1CT",
                "citation_label": "1CT 1",
                "status": "selected",
            },
            {
                "file_page": 2,
                "record_type": "CT",
                "transcript_page_number": 2,
                "citation_prefix": "1CT",
                "citation_label": "1CT 2",
                "status": "selected",
            },
            {
                "file_page": 401,
                "record_type": "CT",
                "transcript_page_number": 1,
                "citation_prefix": "2CT",
                "citation_label": "2CT 1",
                "status": "selected",
            },
            {
                "file_page": 402,
                "record_type": "CT",
                "transcript_page_number": 2,
                "citation_prefix": "2CT",
                "citation_label": "2CT 2",
                "status": "selected",
            },
        ],
    )

    validation = validate_sum_page_fields("1", "2", [1, 2, 401, 402], index)

    assert validation.valid is False
    assert [choice.label for choice in validation.ambiguous_range_choices] == [
        "1CT 1-1CT 2",
        "2CT 1-2CT 2",
    ]


def test_validate_sum_page_fields_does_not_fall_back_to_file_page_when_index_exists(tmp_path) -> None:
    index = _write_transcript_index(
        tmp_path,
        [
            {
                "file_page": 10,
                "record_type": "RT",
                "transcript_page_number": 1,
                "citation_label": "RT 1",
                "status": "selected",
            }
        ],
    )

    validation = validate_sum_page_fields("95", "95", [10, 95], index)

    assert validation.valid is False
    assert validation.message == "Transcript page 95 not available."


def test_validate_sum_page_fields_accepts_file_pages_without_transcript_index() -> None:
    validation = validate_sum_page_fields("3", "5", [1, 3, 5], TranscriptPageIndex({}, {}, {}))

    assert validation.valid is True
    assert validation.start_page == 3
    assert validation.end_page == 5
    assert validation.targets == (3, 5)
    assert validation.start_label == "0003.txt"
    assert validation.end_label == "0005.txt"


def test_validate_sum_page_fields_rejects_invalid_ranges(tmp_path) -> None:
    index = _write_transcript_index(
        tmp_path,
        [
            {
                "file_page": 3,
                "record_type": "RT",
                "transcript_page_number": 3,
                "citation_label": "RT 3",
                "status": "selected",
            },
            {
                "file_page": 4,
                "record_type": "RT",
                "transcript_page_number": 4,
                "citation_label": "RT 4",
                "status": "selected",
            },
        ],
    )

    assert validate_sum_page_fields("", "RT 4", [3, 4], index).message == "Enter start and end pages."
    assert (
        validate_sum_page_fields("file 3", "RT 4", [3, 4], index).message
        == "Use transcript citation pages, not .txt page numbers."
    )
    assert validate_sum_page_fields("RT 4", "RT 3", [3, 4], index).message == "Start must be before end."
