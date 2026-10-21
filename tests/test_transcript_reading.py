"""Synthetic presentation invariants; never read a real case/configuration."""
import re
import threading

import pytest

from transcript_reading_fixtures import (
    FOOTER, MISSING_FIRST_LINES, PHYSICAL_LINES, detached_page, flattened_page, short_flattened_page,
)

from focus.transcript_reading import (
    MAX_PAGE_BYTES, analyze_layout, original_presentation, render_readable,
    search_layout, search_projection,
)


SAMPLES = [
    "THE COURT: I DO NOT AGREE. THE ORDER\nWILL REMAIN IN EFFECT.\nMS. SAMPLE: YES, YOUR HONOR.",
    " 1 | Q. DID YOU SEE\n 2 | THE CHILD?\n 3 | A. I DID NOT.\n 4 | NO ONE DID.",
    "│ THE COURT: THIS IS\n10 │ NOT AN ORDER.\n11 │ IT IS A QUESTION.\n12 │ PLEASE ANSWER.",
    "Q. DID YOU SEE\n\nTHE CHILD?\n\nA. I DID NOT.\n\nNO ONE DID.",
    "Mixed-case prose stays\njust as it was.\n\nA meaningful paragraph follows.",
    "CROSS EXAMINATION\nBY MR. SAMPLE:\nQ. DID IT HAPPEN?\nA. NO.\n(THE WITNESS\nWAS EXCUSED.)",
    "SUPERIOR COURT\nCASE NO. JV-140\nAPPEARANCES: COUNSEL\nTHE COURT: CALL THE MATTER.",
    "THE COURT: **NOT MARKDOWN**. [NO](link). # HEADING. `LITERAL`.",
    "THE COURT: 12 CHILDREN, 28 DAYS, $2,500.25, SECTION 300.2.\nEXHIBIT 12 IS NOT ADMITTED.",
    "THE COURT: THIS IS A WORD-\nENDING HYPHEN, NOT AN OCR CORRECTION.",
    "THE COURT: MR. A. B. SAMPLE SAW THE F.B.I. AT 10:30 A.M.\nI DID NOT. DNA AND ICWA APPLY. JV-140 IS AN IDENTIFIER.",
    "THE COURT: İSTANBUL IS NOT A PERSON. WE SAW İSTANBUL.",
    short_flattened_page(),
    "THE COURT: There are 21 items and 24 photos. MS. SAMPLE: Correct. THE COURT: They remain.",
    "THE COURT: MR. A. B. SAMPLE WAS PRESENT. Q. WAS IT READ? A. YES.",
]


@pytest.mark.parametrize("source", SAMPLES)
def test_retained_characters_have_only_permitted_changes(source):
    result = render_readable(source)
    assert result.diagnostic == "readable"
    assert len(result.text) == len(result.mapping.starts) == len(result.mapping.ends)
    assert list(result.mapping.starts) == sorted(result.mapping.starts)
    assert list(result.mapping.ends) == sorted(result.mapping.ends)
    retained = set()
    for display, (start, end) in enumerate(zip(result.mapping.starts, result.mapping.ends)):
        char = result.text[display]
        if char.isspace():
            continue
        assert end == start + 1
        assert char == source[start]
        retained.add(start)
    for index, char in enumerate(source):
        if not char.isspace() and index not in retained:
            assert any(a <= index < b for a, b in result.removed)
    # Source/display conversion is stable even across removed furniture and
    # inserted paragraph whitespace, not a constant-length delta.
    for start, end in zip(result.mapping.starts, result.mapping.ends):
        left, right = result.mapping.display_span(start, end)
        if right > left:
            a, b = result.mapping.source_span(left, right)
            assert a <= start <= end <= b


def test_dialogue_parenthetical_and_hyphen():
    result = render_readable(SAMPLES[5]).text
    assert "\n\nQ. DID IT HAPPEN?\n\nA. NO." in result
    assert "(THE WITNESS WAS EXCUSED.)" in result
    assert "WORD-ENDING" in render_readable(SAMPLES[9]).text


def test_mixed_case_and_double_spacing():
    assert render_readable(SAMPLES[4]).text == (
        "Mixed-case prose stays just as it was.\n\nA meaningful paragraph follows.")
    assert render_readable(SAMPLES[3]).text == "Q. DID YOU SEE THE CHILD?\n\nA. I DID NOT. NO ONE DID."


@pytest.mark.parametrize("source", [
    "12 children\n28 days\n300.2 is a section\n$2,500.25",
    "1. First item\n2. Second item\n3. Third item\n4. Fourth item",
    "1  First item\n2  Second item\n4  Fourth item\n9  Ninth item",
    "10 | Single ambiguous line\nOrdinary speech -- not furniture",
])
def test_ambiguous_numbers_are_not_removed(source):
    assert not analyze_layout(source).removed
    assert search_projection(source)[0] == source


@pytest.mark.parametrize("separator", ["|", "│", "┃", "║"])
def test_confirmed_gutter_projection_and_range(separator):
    source = f" 9 {separator} DID YOU\n10 {separator} SEE THE\n11 {separator} CHILD?\n12 {separator} I DID NOT."
    text, mapping = search_projection(source, mapped=True)
    assert text == "DID YOU\nSEE THE\nCHILD?\nI DID NOT."
    a, b = mapping.source_span(0, text.index("?"))
    assert source[a:b].startswith("DID YOU")
    assert "11" in source[a:b]
    readable = render_readable(source)
    a, b = readable.mapping.display_span(a, b)
    assert readable.text[a:b] == "DID YOU SEE THE CHILD"


def test_missing_early_number_and_rule_only_line():
    source = " | SOME SPEECH\n10 | THAT CONTINUES\n11 | ON THIS PAGE.\n12 | NO MORE.\n────────────"
    projection, _ = search_projection(source)
    assert "|" not in projection
    assert "─" not in projection
    assert "SOME SPEECH" in projection


def test_capitalization_identifiers_and_punctuation_are_verbatim():
    text = render_readable(SAMPLES[10]).text
    assert "MR. A. B. SAMPLE SAW THE F.B.I. AT 10:30 A.M." in text
    assert "I DID NOT. DNA AND ICWA APPLY. JV-140 IS AN IDENTIFIER." in text
    assert "$2,500.25" in render_readable(SAMPLES[8]).text
    assert "SECTION 300.2." in render_readable(SAMPLES[8]).text


def test_unicode_characters_are_not_recased_or_expanded():
    source = "THE COURT: WE SAW İSTANBUL, ﬁ, ẞ AND Σ."
    result = render_readable(source)
    assert result.text == source
    a = source.index("İ")
    left, right = result.mapping.display_span(a, a + 1)
    assert result.text[left:right] == "İ"
    assert right == left + 1
    assert result.mapping.source_span(left, right) == (a, a + 1)


def test_structured_and_oversized_fallback():
    source = "NAME | DATE | AMOUNT\nTOTAL | TODAY | $20"
    assert render_readable(source).text == source
    assert render_readable(source).diagnostic == "original:structured"
    source = "X" * (MAX_PAGE_BYTES + 1)
    result = render_readable(source)
    assert result.text == source
    assert result.diagnostic == "original:oversized"
    assert not result.mapping.starts
    assert search_projection(source) == (source, None)
    assert original_presentation("a\nB").text == "a\nB"


def test_viewer_worker_hits_cross_gutters_and_keep_source_order(tmp_path, monkeypatch):
    import focus.app as module
    from focus.core import build_pattern, preprocess_phrase, MAX_BREAKS
    source = "1 | Q. DID YOU\n2 | SEE IT?\n3 | A. I DID NOT.\n4 | Q. DID YOU\n5 | SEE IT?"
    path = tmp_path / "0001.txt"
    path.write_text(source)
    completed = []
    monkeypatch.setattr(module.GLib, "idle_add", lambda *args: completed.append(args))

    class Harness:
        _read_text_file = module.Focus._read_text_file
        _map_normalized_span_to_original = module.Focus._map_normalized_span_to_original
        _grep_search_worker = module.Focus._grep_search_worker
        _on_grep_search_finished = lambda *args: None

    regex = re.compile(build_pattern(preprocess_phrase("did you see it"), MAX_BREAKS), re.I | re.S)
    Harness()._grep_search_worker(regex, 10, threading.Event(), [1], {1: path}, frozenset({1}))
    hits = completed[-1][2][1]
    assert len(hits) == 2 and hits[0][0] < hits[1][0]
    result = render_readable(source)
    assert [result.text[s:e].lower() for s, e in (result.mapping.display_span(*h) for h in hits)] == ["did you see it"] * 2
    completed.clear()
    cancel = threading.Event()
    cancel.set()
    Harness()._grep_search_worker(regex, 11, cancel, [1], {1: path}, frozenset({1}))
    assert not completed


def test_research_never_imports_presentation():
    from pathlib import Path
    root = Path(__file__).resolve().parents[1] / "focus"
    for name in ("agent_helper.py", "research_runtime.py", "core.py"):
        assert "transcript_reading" not in (root / name).read_text()


def test_strict_body_eligibility_does_not_change_sidebar(tmp_path):
    import json
    from focus.core import _resolve_record_layout
    from focus.record_categories import Category, load_category_index
    (tmp_path / "text_pages").mkdir()
    (tmp_path / "artifacts").mkdir()
    layout = _resolve_record_layout(tmp_path)
    layout.transcript_page_numbers_path.write_text(json.dumps({"entries": [
        {"file_page": 1, "page_type": "RT_body_first_page"},
        {"file_page": 2, "page_type": "RT_body"},
        {"file_page": 3, "page_type": "RT_index"},
        {"file_page": 4, "page_type": "RT_cover"},
    ]}))
    layout.source_map_path.write_text(json.dumps({"pages": [
        {"file_page": 2, "page_type": "RT_certificate"},
    ]}))
    layout.hearing_boundaries_path.write_text(json.dumps([
        {"start_page": 1, "end_page": 5}
    ]))
    strict = load_category_index(layout, range(1, 7), require_nonconflicting_body=True)
    eligible = {page for page, item in strict.items()
                if item.category == Category.HEARING and item.status == "classified"}
    assert eligible == {1, 5}
    assert load_category_index(layout, [2])[2].category == Category.HEARING


def test_presentation_does_not_leak_between_pages_modes_or_fallbacks():
    from focus.app import Focus

    class Harness:
        _reading_pages = frozenset({1, 2})
        _reading_mode = True
        _reading_controls = None
        _reading_status = None
        _render_page_display = Focus._render_page_display

    app = Harness()
    source = "THE COURT: NO."
    assert app._render_page_display(1, source, [(11, 13)])[0] == source
    assert app._reading_presentation.styles == ((0, 10),)
    assert app._reading_page == 1
    app._reading_mode = False
    assert app._render_page_display(1, source, None)[0] == source
    assert app._reading_presentation is None
    app._reading_mode = True
    app._render_page_display(1, source, None)
    app._render_page_display(99, "# Unrelated content", None)
    assert app._reading_presentation is None and app._reading_page is None
    source = "X" * (MAX_PAGE_BYTES + 1)
    assert app._render_page_display(2, source, [(1, 3)]) == (source, [(1, 3)])
    assert app._reading_presentation.diagnostic == "original:oversized"


def test_spelled_letters_numbered_lists_and_speech_dashes():
    source = "THE COURT: SPELL IT A B C, OR A-B-C.\n-- THIS IS SPEECH --"
    result = render_readable(source)
    assert "A B C" in result.text and "A-B-C" in result.text
    assert "--" in result.text
    source = "\n".join(f"{i}  Substantive item with a long description that must not disappear."
                       for i in range(1, 20))
    assert not analyze_layout(source).removed


def test_right_aligned_number_column_and_case_edge_cases():
    source = "\n".join(f"{i:2}  THIS PHYSICAL LINE CONTAINS SUBSTANTIVE TESTIMONY FOR THE RECORD."
                       for i in range(1, 29))
    result = render_readable(source)
    assert len(result.removed) == 28
    assert search_projection(source)[0].startswith("THIS PHYSICAL LINE")
    source = "THE COURT: IT WAS 2.5. THEN I SAID I'M NOT SURE. HE SAID, ‘NO.’ YES."
    assert render_readable(source).text == source
    source = "PETITIONER: SAMPLE\nRESPONDENT: OTHER\nTHE COURT: NO."
    assert "PETITIONER: SAMPLE\n\nRESPONDENT: OTHER\n\nTHE COURT: NO." == render_readable(source).text


def test_bare_answer_requires_established_qa_not_an_article():
    source = "THE COURT: IT WAS\nA CHILD IN THE ROOM."
    assert render_readable(source).text == "THE COURT: IT WAS A CHILD IN THE ROOM."
    source = "Q DID YOU SEE IT?\nA I DID NOT."
    assert render_readable(source).text == "Q DID YOU SEE IT?\n\nA I DID NOT."


def test_numbered_exhibit_table_is_not_a_pleading_gutter():
    source = "1 | EXHIBIT 10: PHOTO\n2 | EXHIBIT 11: MAP\n3 | EXHIBIT 12: REPORT"
    assert render_readable(source).text == source
    assert render_readable(source).diagnostic == "original:structured"
    assert search_projection(source) == (source, None)


def test_projection_composes_with_unicode_normalizer():
    from focus.core import normalize_text_for_search_with_map
    source = "1 | Q. WAS THE ﬁrst\n2 | DOCUMENT THE CHILD’S?\n3 | A. NO."
    projected, mapping = search_projection(source, mapped=True)
    normalized, offsets = normalize_text_for_search_with_map(projected)
    start = normalized.index("first")
    end = normalized.index("?")
    a, b = mapping.source_span(offsets[start], offsets[end - 1] + 1)
    assert source[a:b] == "ﬁrst\n2 | DOCUMENT THE CHILD’S"
    result = render_readable(source)
    left, right = result.mapping.display_span(a, b)
    assert result.text[left:right] == "ﬁrst DOCUMENT THE CHILD’S"


@pytest.mark.parametrize("source", [detached_page(), detached_page(double_spaced=True), flattened_page()])
def test_detached_and_flattened_gutters_preserve_content_and_maps(source):
    test_retained_characters_have_only_permitted_changes(source)
    result = render_readable(source)
    assert not re.search(r"(?m)^\s*\d{1,2}\s*$", result.text)
    assert "12 CHILDREN, 28 DAYS, OR $2,500.25" in result.text
    assert "SECTION 300.2" in result.text
    assert "IN JULY OF 2024" in result.text
    assert "A PERIOD OF 12 MONTHS" in result.text
    assert "IS NO REASON" in result.text
    assert "SAYS NO NEW MATERIAL" in result.text
    assert result.text.endswith("\n\n" + FOOTER)
    assert "SOURCE AND NO BASIS" in result.text
    projection, mapping = search_projection(source, mapped=True)
    assert mapping is not None
    a = projection.index("SOURCE")
    b = projection.index("REMOVING", a)
    start, end = mapping.source_span(a, b)
    left, right = result.mapping.display_span(start, end)
    assert result.text[left:right].strip() == "SOURCE AND NO BASIS FOR"
    assert mapping.source_span(projection.index("12 MONTHS"), projection.index("12 MONTHS") + 2) == (
        source.index("12 MONTHS"), source.index("12 MONTHS") + 2)


def test_flattened_paragraphs_are_not_double_spaced_physical_lines():
    source = flattened_page()
    layout = analyze_layout(source)
    assert len(layout.removed) == 28 - len(MISSING_FIRST_LINES)
    assert not layout.double_spaced
    result = render_readable(source)
    assert len(result.text.split("\n\n")) == 7  # header, five source paragraphs, footer
    assert "\n\nNO WORDS ARE CHANGED" in result.text
    assert "\n\nTHE REVIEW CONTINUES" in result.text
    assert "\n\nTHE COURT: THE RECORD" in result.text
    assert "\n\nMS. SAMPLE: NO. THE REQUEST" in result.text


@pytest.mark.parametrize("separator", ["\n", "\n\n"])
def test_detached_ordinary_numbered_lists_are_not_removed(separator):
    source = "Numbered substantive findings\n\n" + separator.join(
        part for i in range(1, 29)
        for part in (str(i), "THIS SEPARATE FINDING HAS A COMPLETE SUBSTANTIVE SENTENCE."))
    assert not analyze_layout(source).removed
    assert search_projection(source) == (source, None)
    short = "1\n12 children\n2\n28 days\n3\nSection 300.2"
    assert not analyze_layout(short).removed


def test_sparse_or_irregular_inline_numbers_are_not_a_gutter():
    source = "THE RECORD HAS 2 DOCUMENTS, 4 REPORTS, 5 PHOTOS AND 6 LETTERS."
    assert not analyze_layout(source).removed
    # Ascending values alone are insufficient, even over a full 1–28 range.
    source = " ".join(f"VALUE {n} IS SIGNIFICANT." for n in range(1, 29))
    assert not analyze_layout(source).removed
    assert search_projection(source) == (source, None)


@pytest.mark.parametrize("source", [
    "THE COURT: THERE IS NO URGENCY AND NO DOUBT. NO. THE CASE NO. 12 WAS READ IN JULY OF 2024. I MAY MARCH IN STEP.",
    "The court: There is NO urgency. No. 12 was read in jULy. Leave this capitalization alone.",
    "the court: lower-case testimony stays lower-case.",
])
def test_source_capitalization_is_never_translated(source):
    assert render_readable(source).text == source


@pytest.mark.parametrize("source", [detached_page(), flattened_page()])
def test_viewer_worker_searches_both_number_layouts_without_losing_real_quantities(source, tmp_path, monkeypatch):
    import focus.app as module
    from focus.core import MAX_BREAKS, build_pattern, preprocess_phrase
    page = tmp_path / "0001.txt"
    page.write_text(source)
    completed = []
    monkeypatch.setattr(module.GLib, "idle_add", lambda *args: completed.append(args))

    class Harness:
        _read_text_file = module.Focus._read_text_file
        _map_normalized_span_to_original = module.Focus._map_normalized_span_to_original
        _on_grep_search_finished = lambda *args: None

    for query in ("source and no basis", "a period of 12 months"):
        regex = re.compile(build_pattern(preprocess_phrase(query), MAX_BREAKS), re.I | re.S)
        module.Focus._grep_search_worker(Harness(), regex, 2, threading.Event(), [1], {1: page}, frozenset({1}))
        assert completed[-1][3] == [1]
        hit = completed[-1][2][1][0]
        result = render_readable(source)
        start, end = result.mapping.display_span(*hit)
        assert result.text[start:end].lower() == query


@pytest.mark.parametrize("source", SAMPLES + [detached_page(), flattened_page(), flattened_page().replace(" ", "\u00a0")])
def test_search_and_reader_share_gutter_and_structure_decisions(source):
    reading = analyze_layout(source)
    searching = search_layout(source)
    expected = () if reading.structured else reading.removed
    assert (searching.removed if searching else ()) == expected


def test_bare_column_with_an_empty_physical_line_keeps_search_parity():
    source = "\n".join(f"{n:2}  " + ("" if n == 3 else "THIS PHYSICAL LINE HAS SUBSTANTIVE TESTIMONY FOR THE RECORD.")
                       for n in range(1, 11))
    assert len(analyze_layout(source).removed) == 10
    assert search_layout(source).removed == analyze_layout(source).removed


def test_flattened_exhibit_lists_are_original_not_an_inferred_gutter():
    source = "\n\n".join(f"EXHIBIT {n} {text}" for n, text in enumerate(PHYSICAL_LINES, 1))
    assert render_readable(source).text == source
    assert render_readable(source).diagnostic == "original:structured"
    assert search_projection(source) == (source, None)


def test_sparse_confirmed_column_needs_only_two_twenty_values():
    markers = set(range(4, 19)) | {21, 24}
    source = "Page 88\n\n" + " ".join(
        (f"{n} " if n in markers else "") + line
        for n, line in enumerate(PHYSICAL_LINES, 1))
    layout = analyze_layout(source)
    assert len(layout.removed) == len(markers)
    assert search_layout(source).removed == layout.removed
    test_retained_characters_have_only_permitted_changes(source)


def test_widely_padded_number_only_rows_are_not_a_bare_text_column():
    source = "\n".join(f"{n:45}" for n in range(1, 11))
    assert not analyze_layout(source).removed
    assert search_projection(source) == (source, None)


@pytest.mark.parametrize("layout_name", ["flattened", "prefixed", "physical"])
def test_short_and_blank_rows_restore_only_structural_blocks(layout_name):
    source = short_flattened_page(layout_name)
    result = render_readable(source)
    layout = analyze_layout(source)
    assert len(layout.wraps) == (27 if layout_name == "flattened" else 0)
    searching = search_layout(source)
    assert (searching.wraps if searching else ()) == layout.wraps
    assert len(result.text.split("\n\n")) == 7  # header, five structural blocks, footer
    assert "IN THE ORIGINAL FORM. ANY QUESTIONS?" in result.text
    assert "\n\nMS. SAMPLE: YES, THE PAGE IMAGE.\n\nTHE COURT:" in result.text
    assert "\n\n(A BRIEF PAUSE OCCURRED WITHOUT FURTHER TESTIMONY.)\n\nTHE COURT:" in result.text
    assert "SECTION 742 REMAINS IN THE RECORD." in result.text
    assert "THE CURRENT STATE OF THE SOURCE IS VERIFIED." in result.text
    assert [result.text[a:b] for a, b in result.styles] == ["THE COURT:", "MS. SAMPLE:", "THE COURT:", "THE COURT:"]
    test_retained_characters_have_only_permitted_changes(source)


def test_uncertain_numbers_do_not_disable_speaker_formatting():
    source = "THE COURT: There are 21 items and 24 photos. MS. SAMPLE: Correct. THE COURT: They remain."
    result = render_readable(source)
    assert not result.removed
    assert result.text == source.replace(" MS. SAMPLE:", "\n\nMS. SAMPLE:").replace(" THE COURT:", "\n\nTHE COURT:")
    assert [result.text[a:b] for a, b in result.styles] == ["THE COURT:", "MS. SAMPLE:", "THE COURT:"]


def test_repeated_quantity_disqualifies_short_column_relaxation_not_dialogue():
    source = short_flattened_page().replace("REVIEW OF THIS", "REVIEW OF 12 ITEMS")
    result = render_readable(source)
    assert not result.removed
    assert "12 ITEMS" in result.text
    assert "\n\nMS. SAMPLE:" in result.text
    assert "\n\nTHE COURT:" in result.text
    test_retained_characters_have_only_permitted_changes(source)


def test_addressed_counsel_and_quoted_labels_are_not_new_turns():
    source = 'THE COURT: The words "HE SAID. MS. SAMPLE: NO." are quoted. Ms. Sample, please reply. MS. SAMPLE: YES.'
    result = render_readable(source)
    assert [result.text[a:b] for a, b in result.styles] == ["THE COURT:", "MS. SAMPLE:"]
    assert '"HE SAID. MS. SAMPLE: NO."' in result.text
    assert "Ms. Sample, please reply.\n\nMS. SAMPLE: YES." in result.text


def test_inline_qa_and_initials_are_distinguished_without_changing_case():
    source = "THE COURT: MR. A. B. SAMPLE WAS PRESENT. Q. WAS IT READ? A. YES."
    result = render_readable(source)
    assert result.text == "THE COURT: MR. A. B. SAMPLE WAS PRESENT.\n\nQ. WAS IT READ?\n\nA. YES."
    assert [result.text[a:b] for a, b in result.styles] == ["THE COURT:", "Q.", "A."]


@pytest.mark.parametrize("name", ["MS. O’Neil-Sample:", "Mr. Émile van Dijk:", "DR.SAMPLE:"])
def test_explicit_name_labels_are_verbatim_and_styled(name):
    source = f"THE COURT: Please reply. {name} I agree."
    result = render_readable(source)
    assert result.text == source.replace(f" {name}", f"\n\n{name}")
    assert [result.text[a:b] for a, b in result.styles] == ["THE COURT:", name]
