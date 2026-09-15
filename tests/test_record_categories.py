import json
from dataclasses import FrozenInstanceError

import pytest

from focus.core import TocBookmark, TocCategory, _resolve_record_layout, load_record_boundaries
from focus.record_categories import (
    Category as C, Classification, PALETTE, load_category_index, parse_ranges,
    positive_page, with_toc_fallback,
)


@pytest.fixture
def bundle(tmp_path):
    (tmp_path / "text_pages").mkdir()
    (tmp_path / "artifacts").mkdir()
    (tmp_path / "manifest.json").write_text('{"schema_version": 2}')
    return _resolve_record_layout(tmp_path)


def put(path, value):
    path.write_text(json.dumps(value))


@pytest.mark.parametrize("token,category", [
    ("RT_body", C.HEARING), ("RT_body_first_page", C.HEARING),
    ("CT_report", C.REPORT), ("CT_minute_order", C.MINUTE_ORDER),
    ("CT_minute_order_first_page", C.MINUTE_ORDER),
    ("CT_form", C.FORM), ("CT_form_first_page", C.FORM),
])
def test_explicit_unnumbered_file_page(bundle, token, category):
    put(bundle.transcript_page_numbers_path, {"entries": [
        {"file_page": "0041", "page_type": f" {token.swapcase()} ",
         "transcript_page_number": 999, "status": "unnumbered"}]})
    result = load_category_index(bundle, [41, 999])
    assert result[41].category == category
    assert result[41].provenance == "transcript"
    assert result[999] == Classification()
    with pytest.raises(FrozenInstanceError):
        result[41].status = "x"


def test_precedence_explicit_neutral_and_no_form_extension(bundle):
    put(bundle.transcript_page_numbers_path, {"entries": [
        {"file_page": 1, "page_type": "CT_form"},
        {"file_page": 2, "page_type": "CT_index"},
        {"file_page": 3, "page_type": "unknown"},
        {"file_page": 4, "page_type": " "}]})
    put(bundle.source_map_path, {"pages": [
        {"file_page": n, "page_type": "CT_report", "text_path": "/do/not/read"}
        for n in range(1, 5)]})
    put(bundle.report_boundaries_path, [{"start_page": 1, "end_page": 5, "report_date": "2026-01-01"}])
    toc = [TocCategory("Forms", None, [TocBookmark("A form", 6)])]
    index = load_category_index(bundle, range(1, 9), toc)
    assert [index[n].category for n in range(1, 9)] == [
        C.FORM, C.UNKNOWN, C.UNKNOWN, C.REPORT, C.REPORT, C.FORM, C.UNKNOWN, C.UNKNOWN]
    assert index[4].provenance == "source_map"
    assert index[5].provenance == "boundary"
    assert index[6].provenance == "toc"
    assert index[2].caption == "Other · CT"


def test_date_independent_reversed_ranges_gaps_overlap(bundle):
    put(bundle.report_boundaries_path, [{"start_page": "0005", "end_page": 2, "report_date": "today"}])
    put(bundle.hearing_boundaries_path, [{"start_page": 5, "end_page": 7}])
    put(bundle.minutes_boundaries_path, [{"start_page": 7, "end_page": 7}])
    index = load_category_index(bundle, range(1, 10))
    assert index[1].category == C.UNKNOWN
    assert all(index[n].category == C.REPORT for n in (2, 3, 4))
    assert index[5].status == index[7].status == "conflict"
    assert index[6].category == C.HEARING
    assert index[8].category == C.UNKNOWN
    assert index[6].caption == "Hearing"  # ranges do not invent RT identity
    assert load_record_boundaries(bundle.report_boundaries_path) == ()


def test_duplicates_identity_and_selected_tier_conflicts(bundle):
    put(bundle.transcript_page_numbers_path, {"entries": [
        {"file_page": 1, "page_type": "CT_form"}, {"file_page": 1, "page_type": "CT_report"},
        {"file_page": 2, "page_type": "RT_body", "record_type": "CT"},
        {"file_page": 3, "page_type": "CT_form"}, {"file_page": 3, "page_type": "CT_form_first_page"},
        {"file_page": 4, "record_type": "RT"},
        {"file_page": 5, "record_type": "RT"}, {"file_page": 5, "record_type": "CT"},
        {"file_page": 6, "page_type": "CT_form"}]})
    put(bundle.source_map_path, {"pages": [
        {"file_page": 6, "page_type": "CT_report"},
        {"file_page": 6, "page_type": "CT_minute_order"},
        {"file_page": 7, "page_type": "CT_report"},
        {"file_page": 7, "page_type": "CT_form"}]})
    toc = [TocCategory("Forms", None, [TocBookmark("form", 4), TocBookmark("form", 5)])]
    index = load_category_index(bundle, range(1, 8), toc)
    assert all(index[n].status == "conflict" for n in (1, 2, 4, 5, 7))
    assert index[3].category == index[6].category == C.FORM
    assert index[5].record_type == ""


@pytest.mark.parametrize("bad", [True, False, 0, -1, 1.2, "1.0", "-2", "", None, [], {}, "²"])
def test_invalid_identifiers(bad):
    assert positive_page(bad) is None
    assert parse_ranges([{"start_page": bad, "end_page": 9}]) == ()


def test_bad_rows_and_external_file_paths_do_not_join(bundle):
    put(bundle.source_map_path, {"pages": [None, [],
        {"file_page": True, "page_type": "CT_form"},
        {"file_page": 44, "file_name": "0001.txt", "page_type": "CT_form"},
        {"file_page": 1.0, "page_type": "CT_form"}]})
    assert load_category_index(bundle, [1]) == {1: Classification()}


@pytest.mark.parametrize("raw", ["{", "null", "[]", '{"entries": 1}', '\ufffd'])
def test_missing_malformed_and_unreadable_metadata(bundle, raw):
    assert load_category_index(bundle, [1]) == {1: Classification()}
    bundle.transcript_page_numbers_path.write_text(raw)
    bundle.source_map_path.mkdir()  # unreadable as a file
    assert load_category_index(bundle, [1]) == {1: Classification()}
    bundle.transcript_page_numbers_path.write_bytes(b"\xff")
    assert load_category_index(bundle, [1]) == {1: Classification()}


def test_toc_exact_conflict_and_replacement(bundle):
    base = load_category_index(bundle, [1, 2, 3, 4])
    toc = [TocCategory(" hEaRiNgS ", 4, [TocBookmark("one", 1)]),
           TocCategory("Reports", None, [TocBookmark("two", 2)]),
           TocCategory("Forms", None, [TocBookmark("two also", 2)])]
    result = with_toc_fallback(base, toc)
    assert result[1].category == C.HEARING
    assert result[2].status == "conflict"
    assert result[3] == result[4] == Classification()
    assert with_toc_fallback(base, []) == base


def test_legacy_and_verified_identity_without_category(tmp_path):
    (tmp_path / "text_record").mkdir()
    layout = _resolve_record_layout(tmp_path)
    assert load_category_index(layout, [1]) == {1: Classification()}
    layout.transcript_page_numbers_path.parent.mkdir()
    put(layout.transcript_page_numbers_path, {"citation_series": [
        {"series_id": "a", "record_type": "RT"}], "entries": [
        {"file_page": 1, "citation_series_id": "a"}]})
    assert load_category_index(layout, [1])[1].caption == "Other · RT"


def test_default_reader_contrast():
    def luminance(channels):
        linear = [v / 12.92 if v <= .04045 else ((v + .055) / 1.055) ** 2.4 for v in channels]
        return sum(a * b for a, b in zip(linear, (.2126, .7152, .0722)))
    for accent, _ in PALETTE.values():
        rgb = [int(accent[i:i+2], 16) / 255 for i in (1, 3, 5)]
        assert (luminance([.9 + .1 * c for c in rgb]) + .05) / .05 >= 18.3
