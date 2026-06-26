import json

from focus.core import (
    RecordBoundary,
    TranscriptPageLabel,
    TranscriptPageIndex,
    find_minute_order_boundary_for_transcript_page,
    format_page_nav_labels,
    format_toc_page_subtitle,
    format_transcript_page_choice_label,
    load_record_boundaries,
    load_transcript_page_index,
    parse_transcript_page_jump_query,
    record_boundary_date_for_page,
    should_show_minute_order_return,
)


def test_load_transcript_page_index_uses_citation_series(tmp_path) -> None:
    path = tmp_path / "transcript_page_numbers.json"
    path.write_text(
        json.dumps(
            {
                "citation_series": [
                    {
                        "series_id": "ct-1",
                        "record_type": "CT",
                        "citation_prefix": "1CT",
                        "prefix_reason": "Overlaps with CT series 2.",
                    },
                    {
                        "series_id": "ct-2",
                        "record_type": "CT",
                        "citation_prefix": "2CT",
                        "definition_draft": "Second clerk's transcript series.",
                    },
                ],
                "entries": [
                    {
                        "file_page": "0001",
                        "transcript_page_number": 1,
                        "citation_series_id": "ct-1",
                        "citation_prefix": "1CT",
                        "citation_label": "1CT 1",
                        "status": "selected",
                    },
                    {
                        "file_page": "0401",
                        "transcript_page_number": 1,
                        "citation_series_id": "ct-2",
                        "status": "selected",
                    },
                    {
                        "file_page": "0500",
                        "transcript_page_number": 10,
                        "citation_series_id": "ct-2",
                        "status": "ambiguous",
                    },
                ],
            }
        ),
        encoding="utf-8",
    )

    index = load_transcript_page_index(path)

    assert index.by_file_page[1].citation_label == "1CT 1"
    assert index.by_file_page[401].citation_label == "2CT 1"
    assert index.by_file_page[401].series_description == "Second clerk's transcript series."
    assert [label.file_page for label in index.by_transcript_number[1]] == [1, 401]
    assert index.by_citation_key["1CT:1"][0].file_page == 1
    assert index.by_citation_key["2CT:1"][0].file_page == 401
    assert 500 not in index.by_file_page


def test_load_transcript_page_index_falls_back_to_record_type_prefix(tmp_path) -> None:
    path = tmp_path / "transcript_page_numbers.json"
    path.write_text(
        json.dumps(
            {
                "entries": [
                    {
                        "file_page": 876,
                        "record_type": "CT",
                        "transcript_page_number": "606",
                        "status": "selected",
                    }
                ]
            }
        ),
        encoding="utf-8",
    )

    label = load_transcript_page_index(path).by_file_page[876]

    assert label.citation_prefix == "CT"
    assert label.citation_label == "CT 606"
    assert label.citation_key == "CT:606"


def test_format_toc_page_subtitle_uses_transcript_citation_label(tmp_path) -> None:
    path = tmp_path / "transcript_page_numbers.json"
    path.write_text(
        json.dumps(
            {
                "entries": [
                    {
                        "file_page": 95,
                        "record_type": "CT",
                        "transcript_page_number": 25,
                        "citation_prefix": "1CT",
                        "citation_label": "1CT 25",
                        "status": "selected",
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    index = load_transcript_page_index(path)

    assert format_toc_page_subtitle(95, index) == "1CT 25"


def test_format_toc_page_subtitle_falls_back_to_text_filename() -> None:
    index = TranscriptPageIndex({}, {}, {})

    assert format_toc_page_subtitle(95, index) == "0095.txt"


def test_format_toc_page_subtitle_falls_back_for_missing_index_page(tmp_path) -> None:
    path = tmp_path / "transcript_page_numbers.json"
    path.write_text(
        json.dumps(
            {
                "entries": [
                    {
                        "file_page": 10,
                        "record_type": "RT",
                        "transcript_page_number": 10,
                        "citation_label": "RT 10",
                        "status": "selected",
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    index = load_transcript_page_index(path)

    assert format_toc_page_subtitle(95, index) == "0095.txt"


def test_format_page_nav_labels_uses_citation_and_page_progress(tmp_path) -> None:
    path = tmp_path / "transcript_page_numbers.json"
    path.write_text(
        json.dumps(
            {
                "entries": [
                    {
                        "file_page": 1201,
                        "record_type": "CT",
                        "transcript_page_number": 690,
                        "citation_label": "CT 690",
                        "status": "selected",
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    index = load_transcript_page_index(path)

    assert format_page_nav_labels(1201, 1530, index) == (
        "CT 690",
        "1201/1530",
    )


def test_format_page_nav_labels_falls_back_to_file_page_progress() -> None:
    index = TranscriptPageIndex({}, {}, {})

    assert format_page_nav_labels(1201, 1530, index) == ("1201", "/1530")


def test_format_page_nav_labels_handles_empty_pages() -> None:
    index = TranscriptPageIndex({}, {}, {})

    assert format_page_nav_labels(None, 0, index) == ("", "--/--")


def test_format_transcript_page_choice_label_removes_slash_filename() -> None:
    label = TranscriptPageLabel(
        file_page=1201,
        transcript_page_number=690,
        citation_prefix="CT",
        citation_label="CT 690",
        citation_key="CT:690",
        record_type="CT",
        series_id="",
        series_description="",
        status="selected",
    )

    assert format_transcript_page_choice_label(label) == "CT 690  text 1201"


def test_parse_transcript_page_jump_query() -> None:
    assert parse_transcript_page_jump_query("606").kind == "bare"
    assert parse_transcript_page_jump_query("p0876").kind == "file"
    assert parse_transcript_page_jump_query("file 876").page_number == 876

    query = parse_transcript_page_jump_query("1 RT 20")

    assert query.kind == "citation"
    assert query.citation_prefix == "1RT"
    assert query.page_number == 20


def test_load_record_boundaries_parses_ranges(tmp_path) -> None:
    path = tmp_path / "minutes_boundaries.json"
    path.write_text(
        json.dumps(
            [
                {"date": "May 23, 2017", "start_page": "0665", "end_page": "0666"},
                {"date": "Bad", "start_page": "", "end_page": "1"},
                {"date": "April 10, 2018", "start_page": "0906", "end_page": "0904"},
            ]
        ),
        encoding="utf-8",
    )

    boundaries = load_record_boundaries(path)

    assert boundaries == (
        RecordBoundary("May 23, 2017", 665, 666),
        RecordBoundary("April 10, 2018", 904, 906),
    )


def test_load_record_boundaries_handles_missing_or_malformed_files(tmp_path) -> None:
    missing = tmp_path / "missing.json"
    malformed = tmp_path / "malformed.json"
    malformed.write_text("{", encoding="utf-8")

    assert load_record_boundaries(missing) == ()
    assert load_record_boundaries(malformed) == ()


def test_record_boundary_date_for_hearing_page() -> None:
    hearing_boundaries = (RecordBoundary("April 10, 2018", 22, 43),)
    minute_boundaries = (RecordBoundary("April 10, 2018", 904, 906),)

    assert (
        record_boundary_date_for_page(22, hearing_boundaries, minute_boundaries)
        == "April 10, 2018"
    )


def test_record_boundary_date_for_minute_order_page() -> None:
    hearing_boundaries = (RecordBoundary("April 10, 2018", 22, 43),)
    minute_boundaries = (RecordBoundary("April 10, 2018", 904, 906),)

    assert (
        record_boundary_date_for_page(905, hearing_boundaries, minute_boundaries)
        == "April 10, 2018"
    )


def test_record_boundary_date_prefers_minute_boundary_if_ranges_overlap() -> None:
    hearing_boundaries = (RecordBoundary("Hearing Date", 22, 43),)
    minute_boundaries = (RecordBoundary("Minute Date", 40, 42),)

    assert (
        record_boundary_date_for_page(41, hearing_boundaries, minute_boundaries)
        == "Minute Date"
    )


def test_record_boundary_date_is_empty_outside_boundaries() -> None:
    hearing_boundaries = (RecordBoundary("April 10, 2018", 22, 43),)
    minute_boundaries = (RecordBoundary("April 10, 2018", 904, 906),)

    assert record_boundary_date_for_page(100, hearing_boundaries, minute_boundaries) == ""
    assert record_boundary_date_for_page(None, hearing_boundaries, minute_boundaries) == ""


def test_find_minute_order_boundary_for_matched_rt_page(tmp_path) -> None:
    path = tmp_path / "transcript_page_numbers.json"
    path.write_text(
        json.dumps(
            {
                "entries": [
                    {
                        "file_page": 22,
                        "record_type": "RT",
                        "transcript_page_number": 22,
                        "citation_label": "1RT 22",
                        "status": "selected",
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    index = load_transcript_page_index(path)
    hearing_boundaries = (RecordBoundary("April 10, 2018", 22, 43),)
    minute_boundaries = (RecordBoundary("April 10, 2018", 904, 906),)

    target = find_minute_order_boundary_for_transcript_page(
        22,
        index,
        hearing_boundaries,
        minute_boundaries,
    )

    assert target == RecordBoundary("April 10, 2018", 904, 906)


def test_find_minute_order_boundary_ignores_unmatched_or_non_rt_pages(tmp_path) -> None:
    path = tmp_path / "transcript_page_numbers.json"
    path.write_text(
        json.dumps(
            {
                "entries": [
                    {
                        "file_page": 22,
                        "record_type": "RT",
                        "transcript_page_number": 22,
                        "citation_label": "1RT 22",
                        "status": "selected",
                    },
                    {
                        "file_page": 904,
                        "record_type": "CT",
                        "transcript_page_number": 393,
                        "citation_label": "CT 393",
                        "status": "selected",
                    },
                ]
            }
        ),
        encoding="utf-8",
    )
    index = load_transcript_page_index(path)
    hearing_boundaries = (RecordBoundary("April 10, 2018", 22, 43),)
    minute_boundaries = (RecordBoundary("Other Date", 904, 906),)

    assert (
        find_minute_order_boundary_for_transcript_page(
            22,
            index,
            hearing_boundaries,
            minute_boundaries,
        )
        is None
    )
    assert (
        find_minute_order_boundary_for_transcript_page(
            904,
            index,
            hearing_boundaries,
            minute_boundaries,
        )
        is None
    )


def test_minute_order_return_stays_active_across_boundary_pages() -> None:
    boundary = RecordBoundary("July 27, 2017", 689, 691)

    assert should_show_minute_order_return(689, 22, boundary) is True
    assert should_show_minute_order_return(690, 22, boundary) is True
    assert should_show_minute_order_return(691, 22, boundary) is True


def test_minute_order_return_stays_active_outside_boundary_until_used() -> None:
    boundary = RecordBoundary("July 27, 2017", 689, 691)

    assert should_show_minute_order_return(688, 22, boundary) is True
    assert should_show_minute_order_return(692, 22, boundary) is True


def test_minute_order_return_requires_pending_return_page() -> None:
    boundary = RecordBoundary("July 27, 2017", 689, 691)

    assert should_show_minute_order_return(690, None, boundary) is False
    assert should_show_minute_order_return(None, 22, boundary) is False
