import json

from focus import (
    TranscriptPageIndex,
    format_toc_page_subtitle,
    load_transcript_page_index,
    parse_transcript_page_jump_query,
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


def test_parse_transcript_page_jump_query() -> None:
    assert parse_transcript_page_jump_query("606").kind == "bare"
    assert parse_transcript_page_jump_query("p0876").kind == "file"
    assert parse_transcript_page_jump_query("file 876").page_number == 876

    query = parse_transcript_page_jump_query("1 RT 20")

    assert query.kind == "citation"
    assert query.citation_prefix == "1RT"
    assert query.page_number == 20
