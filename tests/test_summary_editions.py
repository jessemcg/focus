"""Tests for page-matched summary editions (Focus consumer side).

Synthetic only: no real case material. The loader validates sidecars by hash
and structure without parsing the PDF, so tests author small sidecars against
a static minimal PDF fixture.
"""

import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import pytest

from focus.app import Focus
from focus.summary_editions import (
    FOCUS_SOURCE_TO_EDITION_KIND,
    SummaryEditionError,
    edition_manifest_paths,
    edition_same_stem_paths,
    find_page_for_source_line,
    load_summary_edition,
    render_page_text,
    search_pages,
    with_paragraph_spacing,
)

# Minimal deliberately-authored one-page PDF fixture (static bytes; the
# loader verifies integrity by SHA-256 only and never parses the PDF).
MINIMAL_PDF = b"""%PDF-1.4
1 0 obj<</Type/Catalog/Pages 2 0 R>>endobj
2 0 obj<</Type/Pages/Kids[3 0 R]/Count 1>>endobj
3 0 obj<</Type/Page/Parent 2 0 R/MediaBox[0 0 612 792]>>endobj
trailer<</Root 1 0 R>>
%%EOF
"""


def _sha256_bytes(data: bytes) -> str:
    import hashlib

    return hashlib.sha256(data).hexdigest()


def _sidecar_pages(spec: list[dict]) -> list[dict]:
    return [
        {
            "page": index + 1,
            "text": entry["text"],
            "source_first_line": entry["first"],
            "source_last_line": entry["last"],
            "links": [
                {
                    "start": link["start"],
                    "end": link["end"],
                    "label": link["label"],
                    "target_page": link["target"],
                }
                for link in entry.get("links", [])
            ],
        }
        for index, entry in enumerate(spec)
    ]


def _build_edition(
    tmp_path: Path,
    *,
    focus_source: str = "hearing",
    kind: str | None = None,
    source_text: str = "First paragraph.\n\nSecond paragraph.\n",
    pages_spec: list[dict] | None = None,
    summary_name: str = "hearings_sum_IsoCase.txt",
    use_manifest: bool = True,
    mutate_sidecar=None,
    source_sha: str | None = None,
    pdf_sha: str | None = None,
) -> tuple[Path, Path, Path]:
    kind = kind or FOCUS_SOURCE_TO_EDITION_KIND[focus_source]
    pages_spec = pages_spec or [
        {"text": "First paragraph.", "first": 1, "last": 1},
        {"text": "Second paragraph.", "first": 3, "last": 3},
    ]
    root = tmp_path
    summaries = root / "summaries"
    summaries.mkdir(parents=True, exist_ok=True)
    summary_path = summaries / summary_name
    summary_path.write_text(source_text, encoding="utf-8")

    editions = summaries / "editions"
    editions.mkdir(exist_ok=True)
    stem = summary_path.stem
    pdf_path = editions / f"{stem}.pdf"
    pdf_path.write_bytes(MINIMAL_PDF)
    pages_path = editions / f"{stem}.pages.json"

    page_map = {
        "artifact": "recordprep-summary-pages",
        "schema_version": 1,
        "kind": kind,
        "layout": {"id": "recordprep-summary-letter-v1"},
        "source": {
            "path": f"summaries/{summary_name}",
            "sha256": source_sha or _sha256_bytes(source_text.encode("utf-8")),
        },
        "pdf": {
            "path": f"summaries/editions/{stem}.pdf",
            "sha256": pdf_sha or _sha256_bytes(MINIMAL_PDF),
            "page_count": len(pages_spec),
        },
        "pages": _sidecar_pages(pages_spec),
    }
    if mutate_sidecar is not None:
        mutate_sidecar(page_map)
    pages_path.write_text(json.dumps(page_map, indent=2), encoding="utf-8")

    if use_manifest:
        manifest = {
            "schema_version": 2,
            "files": {
                f"summarized_{kind}_pdf": f"summaries/editions/{stem}.pdf",
                f"summarized_{kind}_pages": f"summaries/editions/{stem}.pages.json",
            },
        }
        (root / "manifest.json").write_text(
            json.dumps(manifest, indent=2), encoding="utf-8"
        )
    return root, summary_path, pages_path


def _load(root: Path, summary_path: Path, focus_source: str = "hearing"):
    manifest_files = {
        "summarized_hearings_pdf": None,
    }
    manifest_path = root / "manifest.json"
    manifest_files = None
    if manifest_path.exists():
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        manifest_files = manifest.get("files")
    return load_summary_edition(
        focus_source=focus_source,
        summary_path=summary_path,
        bundle_root=root,
        manifest_files=manifest_files,
        manifest_dir=root,
    )


class EditionDiscoveryTests(unittest.TestCase):
    def test_manifest_companion_discovery(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root, summary_path, _pages = _build_edition(Path(temporary))
            edition = _load(root, summary_path)
            self.assertEqual(edition.kind, "hearings")
            self.assertEqual(edition.page_count, 2)
            self.assertEqual(edition.pages[0].text, "First paragraph.")

    def test_same_stem_discovery_without_manifest(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root, summary_path, _pages = _build_edition(
                Path(temporary), use_manifest=False
            )
            edition = _load(root, summary_path)
            self.assertEqual(edition.page_count, 2)

    def test_missing_companions_raise(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root, summary_path, pages_path = _build_edition(Path(temporary))
            pages_path.unlink()
            with pytest.raises(SummaryEditionError):
                _load(root, summary_path)

    def test_stale_source_hash_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root, summary_path, _pages = _build_edition(Path(temporary))
            summary_path.write_text("Changed summary text.\n", encoding="utf-8")
            with pytest.raises(SummaryEditionError, match="Summary text changed"):
                _load(root, summary_path)

    def test_stale_pdf_hash_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root, summary_path, pages_path = _build_edition(Path(temporary))
            (root / "summaries/editions/hearings_sum_IsoCase.pdf").write_bytes(
                b"different pdf"
            )
            with pytest.raises(SummaryEditionError, match="PDF changed"):
                _load(root, summary_path)

    def test_malformed_sidecar_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root, summary_path, pages_path = _build_edition(Path(temporary))
            pages_path.write_text("{not json", encoding="utf-8")
            with pytest.raises(SummaryEditionError):
                _load(root, summary_path)

    def test_wrong_schema_and_kind_are_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root, summary_path, _pages = _build_edition(
                Path(temporary),
                mutate_sidecar=lambda pm: pm.update({"schema_version": 99}),
            )
            with pytest.raises(SummaryEditionError, match="schema"):
                _load(root, summary_path)
        with tempfile.TemporaryDirectory() as temporary:
            root, summary_path, _pages = _build_edition(
                Path(temporary), kind="reports"
            )
            with pytest.raises(SummaryEditionError, match="category"):
                _load(root, summary_path)

    def test_page_gap_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root, summary_path, _pages = _build_edition(
                Path(temporary),
                pages_spec=[
                    {"text": "One.", "first": 1, "last": 1},
                    {"text": "Two.", "first": 3, "last": 3},
                    {"text": "Three.", "first": 5, "last": 5},
                ],
                mutate_sidecar=lambda pm: pm["pages"][2].update({"page": 4}),
            )
            with pytest.raises(SummaryEditionError, match="consecutive"):
                _load(root, summary_path)

    def test_path_escaping_sidecar_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root, summary_path, _pages = _build_edition(
                Path(temporary),
                mutate_sidecar=lambda pm: pm["pdf"].update(
                    {"path": "../../outside.pdf"}
                ),
            )
            with pytest.raises(SummaryEditionError, match="escapes"):
                _load(root, summary_path)

    def test_link_span_mismatch_is_rejected(self) -> None:
        def corrupt(page_map: dict) -> None:
            page_map["pages"][0]["links"] = [
                {"start": 0, "end": 5, "label": "Wrong", "target_page": 12}
            ]

        with tempfile.TemporaryDirectory() as temporary:
            root, summary_path, _pages = _build_edition(
                Path(temporary),
                pages_spec=[
                    {
                        "text": "First paragraph.",
                        "first": 1,
                        "last": 1,
                        "links": [
                            {"start": 6, "end": 16, "label": "paragraph.", "target": 12}
                        ],
                    },
                    {"text": "Second paragraph.", "first": 3, "last": 3},
                ],
                mutate_sidecar=corrupt,
            )
            with pytest.raises(SummaryEditionError, match="label"):
                _load(root, summary_path)


class EditionRenderAndSearchTests(unittest.TestCase):
    def _edition_with_links(self, tmp_path: Path):
        pages_spec = [
            {
                "text": "March 3, 2025 Hearing Minute Order end.",
                "first": 1,
                "last": 1,
                "links": [
                    {"start": 14, "end": 21, "label": "Hearing", "target": 1234},
                    {"start": 22, "end": 34, "label": "Minute Order", "target": 567},
                ],
            },
            {"text": "Second page body.", "first": 3, "last": 3},
        ]
        root, summary_path, _pages = _build_edition(
            tmp_path, pages_spec=pages_spec
        )
        return _load(root, summary_path)

    def test_render_page_text_synthesizes_record_page_links(self) -> None:
        import tempfile

        with tempfile.TemporaryDirectory() as temporary:
            edition = self._edition_with_links(Path(temporary))
            self.assertEqual(
                render_page_text(edition, 1),
                "March 3, 2025 [Hearing](page:1234) [Minute Order](page:567) end.",
            )
            self.assertEqual(render_page_text(edition, 2), "Second page body.")

    def test_search_pages_spans_all_pages_in_document_order(self) -> None:
        import tempfile

        with tempfile.TemporaryDirectory() as temporary:
            edition = self._edition_with_links(Path(temporary))
            matches = search_pages(edition, "PAGE")
            self.assertEqual(
                matches,
                [(2, 7, 11)],
            )
            # Link syntax is stripped from displayed text: page:1234 never matches.
            self.assertEqual(search_pages(edition, "page:1234"), [])
            body_matches = search_pages(edition, "e")
            self.assertTrue(all(m[0] in (1, 2) for m in body_matches))
            pages = [m[0] for m in body_matches]
            self.assertEqual(pages, sorted(pages))

    def test_find_page_for_source_line_maps_legacy_line_bookmarks(self) -> None:
        import tempfile

        with tempfile.TemporaryDirectory() as temporary:
            pages_spec = [
                {"text": "One.", "first": 1, "last": 5},
                {"text": "Two.", "first": 6, "last": 10},
                {"text": "Three.", "first": 11, "last": 15},
            ]
            root, summary_path, _pages = _build_edition(
                Path(temporary), pages_spec=pages_spec
            )
            edition = _load(root, summary_path)
            self.assertEqual(find_page_for_source_line(edition, 1), 1)
            self.assertEqual(find_page_for_source_line(edition, 5), 1)
            self.assertEqual(find_page_for_source_line(edition, 6), 2)
            self.assertEqual(find_page_for_source_line(edition, 15), 3)
            self.assertEqual(find_page_for_source_line(edition, 999), 3)



class ParagraphSpacingTests(unittest.TestCase):
    """Paginated display spacing: one empty line between paragraphs."""

    def test_two_paragraphs_render_with_exactly_one_empty_line(self) -> None:
        self.assertEqual(
            with_paragraph_spacing("First paragraph.\nSecond paragraph."),
            "First paragraph.\n\nSecond paragraph.",
        )

    def test_existing_newline_runs_normalize_without_accumulating(self) -> None:
        self.assertEqual(
            with_paragraph_spacing("First.\n\n\nSecond.\n\n\n\n\nThird."),
            "First.\n\nSecond.\n\nThird.",
        )

    def test_no_spacing_added_at_page_edges(self) -> None:
        self.assertEqual(
            with_paragraph_spacing("\n\nFirst.\nSecond.\n\n\n"),
            "First.\n\nSecond.",
        )
        self.assertEqual(
            with_paragraph_spacing("Only paragraph."), "Only paragraph."
        )
        self.assertEqual(with_paragraph_spacing(""), "")

    def test_render_page_text_itself_stays_unspaced(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            pages_spec = [
                {
                    "text": "First paragraph.\nSecond paragraph.",
                    "first": 1,
                    "last": 2,
                },
                {"text": "Third paragraph.", "first": 3, "last": 3},
            ]
            root, summary_path, _pages = _build_edition(
                Path(temporary), pages_spec=pages_spec
            )
            edition = _load(root, summary_path)
            # The loader and renderer keep sidecar text and link offsets
            # untouched; spacing is a separate display-only transformation.
            self.assertEqual(
                render_page_text(edition, 1),
                "First paragraph.\nSecond paragraph.",
            )

    def test_links_reconstruct_correctly_across_paragraph_boundary(self) -> None:
        text = "First paragraph body.\nSecond paragraph continues here."
        pages_spec = [
            {
                "text": text,
                "first": 1,
                "last": 2,
                "links": [
                    {
                        "start": text.index("First"),
                        "end": text.index("First") + len("First"),
                        "label": "First",
                        "target": 12,
                    },
                    {
                        "start": text.index("Second"),
                        "end": text.index("Second") + len("Second"),
                        "label": "Second",
                        "target": 345,
                    },
                ],
            },
        ]
        with tempfile.TemporaryDirectory() as temporary:
            root, summary_path, _pages = _build_edition(
                Path(temporary), pages_spec=pages_spec
            )
            edition = _load(root, summary_path)
            self.assertEqual(
                with_paragraph_spacing(render_page_text(edition, 1)),
                "[First](page:12) paragraph body.\n\n"
                "[Second](page:345) paragraph continues here.",
            )

    def test_paginated_search_offsets_match_spaced_display(self) -> None:
        pages_spec = [
            {
                "text": "First paragraph body.\nSecond paragraph body here.",
                "first": 1,
                "last": 2,
            },
            {"text": "Third paragraph body.", "first": 3, "last": 3},
        ]
        with tempfile.TemporaryDirectory() as temporary:
            root, summary_path, _pages = _build_edition(
                Path(temporary), pages_spec=pages_spec
            )
            edition = _load(root, summary_path)
            displayed = with_paragraph_spacing(render_page_text(edition, 1))
            needle = "Second"
            # The legacy default render stays aligned to unspaced sidecar text.
            legacy = search_pages(edition, needle)
            assert legacy == [
                (
                    1,
                    edition.pages[0].text.index(needle),
                    edition.pages[0].text.index(needle) + len(needle),
                )
            ]
            # App-style paginated search matches the spaced display offsets.
            spaced = search_pages(
                edition,
                needle,
                render=lambda _edition, page_number: with_paragraph_spacing(
                    render_page_text(edition, page_number)
                ),
            )
            assert spaced == [
                (1, displayed.index(needle), displayed.index(needle) + len(needle))
            ]


class FakePageWidget:

    def __init__(self) -> None:
        self.visible = False
        self.text = ""
        self.sensitive = True

    def set_visible(self, value: bool) -> None:
        self.visible = value

    def set_text(self, value: str) -> None:
        self.text = value

    def get_text(self) -> str:
        return self.text

    def set_sensitive(self, value: bool) -> None:
        self.sensitive = value

    def set_enabled(self, value: bool) -> None:
        self.set_sensitive(value)


class FakeViewState:
    def __init__(self) -> None:
        self.summary_current_page = None


class PagedHarness:
    """Binds real paged-summary Focus methods onto a minimal fake."""

    _summary_is_paged = Focus._summary_is_paged
    _display_summary_page = Focus._display_summary_page
    _update_summary_page_controls = Focus._update_summary_page_controls
    _on_summary_prev_page_clicked = Focus._on_summary_prev_page_clicked
    _on_summary_next_page_clicked = Focus._on_summary_next_page_clicked
    _on_summary_page_entry_activate = Focus._on_summary_page_entry_activate
    _refresh_summary_actions_state = Focus._refresh_summary_actions_state
    _summary_has_saved_bookmark = Focus._summary_has_saved_bookmark
    _summary_bookmark_page = Focus._summary_bookmark_page
    _extract_summary_bookmark_entry = Focus._extract_summary_bookmark_entry
    _summary_bookmarks_path_for = Focus._summary_bookmarks_path_for
    _read_summary_bookmarks = Focus._read_summary_bookmarks
    _extract_summary_bookmark_line = Focus._extract_summary_bookmark_line
    _on_summary_print_clicked = Focus._on_summary_print_clicked
    _open_page_matched_pdf = Focus._open_page_matched_pdf
    _load_summary_edition_for = Focus._load_summary_edition_for
    _summary_page_search_text = Focus._summary_page_search_text
    _extract_ai_link_spans = Focus._extract_ai_link_spans
    _extract_markdown_page_link_spans = Focus._extract_markdown_page_link_spans

    def __init__(self, edition) -> None:
        self._summary_edition = edition
        self._summary_edition_page = 1
        self._summary_loaded_path = edition.source_path if edition else None
        self._summary_active_source = "hearing"
        self._summary_raw = ""
        self._state = FakeViewState()
        self._summary_progress_label = FakePageWidget()
        self._summary_prev_page_button = FakePageWidget()
        self._summary_next_page_button = FakePageWidget()
        self._summary_page_entry = FakePageWidget()
        self._summary_page_total_label = FakePageWidget()
        self._summary_open_pdf_button = FakePageWidget()
        self._summary_bookmark_action_button = FakePageWidget()
        self._summary_return_bookmark_action_button = FakePageWidget()
        self._summary_print_action = FakePageWidget()
        self._summary_buffer = object()  # truthy sentinel; rendering is faked
        self._summary_view = None
        self.input_dir = Path(tempfile.mkdtemp())
        self.link_applied: list[str] = []
        self.highlight_calls = 0
        self.toasts: list[str] = []

    def _apply_summary_search_highlights(self) -> None:
        self.highlight_calls += 1

    def _on_summary_begin_print(self, *_args) -> None:
        pass

    def _on_summary_draw_page(self, *_args) -> None:
        pass

    def _get_ai_host_window(self):  # noqa: ANN201
        return None

    def _current_view_state(self) -> FakeViewState:
        return self._state

    def _apply_summary_links(self, text: str) -> None:
        self.link_applied.append(text)

    def _ai_transient_toast(self, message: str) -> None:
        self.toasts.append(message)



class PagedBehaviorTests:
    def _edition(self, tmp_path: Path):
        root, summary_path, _pages = _build_edition(tmp_path)
        return _load(root, summary_path)


class TestPageNavigation(PagedBehaviorTests):
    def test_bounds_and_direct_jumps(self, tmp_path) -> None:
        harness = PagedHarness(self._edition(tmp_path))

        harness._display_summary_page(1)
        assert harness._summary_edition_page == 1
        assert harness._state.summary_current_page == 1
        assert harness._summary_raw == "First paragraph."

        harness._on_summary_prev_page_clicked(None)
        assert harness._summary_edition_page == 1
        assert not harness._summary_prev_page_button.sensitive

        harness._on_summary_next_page_clicked(None)
        assert harness._summary_edition_page == 2
        assert harness._summary_raw == "Second paragraph."

        harness._on_summary_next_page_clicked(None)
        assert harness._summary_edition_page == 2
        assert not harness._summary_next_page_button.sensitive

        harness._summary_page_entry.set_text("1")
        harness._on_summary_page_entry_activate(harness._summary_page_entry)
        assert harness._summary_edition_page == 1

        harness._summary_page_entry.set_text("9")
        harness._on_summary_page_entry_activate(harness._summary_page_entry)
        assert harness._summary_edition_page == 1
        assert any("outside" in toast for toast in harness.toasts)

        harness._summary_page_entry.set_text("not-a-number")
        harness._on_summary_page_entry_activate(harness._summary_page_entry)
        assert harness._summary_edition_page == 1

    def test_page_controls_visibility_and_totals(self, tmp_path) -> None:
        harness = PagedHarness(self._edition(tmp_path))
        harness._display_summary_page(1)
        assert harness._summary_page_total_label.text == "of 2"
        assert harness._summary_page_entry.text == "1"
        assert harness._summary_open_pdf_button.visible
        assert not harness._summary_progress_label.visible

    def test_page_text_preserves_links_for_renderer(self, tmp_path) -> None:
        pages_spec = [
            {
                "text": "March 3, 2025 Hearing end.",
                "first": 1,
                "last": 1,
                "links": [{"start": 14, "end": 21, "label": "Hearing", "target": 1234}],
            },
            {"text": "Second page.", "first": 3, "last": 3},
        ]
        root, summary_path, _pages = _build_edition(
            tmp_path, pages_spec=pages_spec
        )
        harness = PagedHarness(_load(root, summary_path))
        harness._display_summary_page(1)
        assert harness.link_applied[-1] == "March 3, 2025 [Hearing](page:1234) end."
        harness._display_summary_page(2)
        assert harness.link_applied[-1] == "Second page."

    def test_display_receives_paragraph_spaced_text(self, tmp_path) -> None:
        pages_spec = [
            {
                "text": "First paragraph body.\nSecond paragraph body here.",
                "first": 1,
                "last": 2,
            },
            {"text": "Third paragraph body.", "first": 3, "last": 3},
        ]
        root, summary_path, _pages = _build_edition(tmp_path, pages_spec=pages_spec)
        harness = PagedHarness(_load(root, summary_path))
        harness._display_summary_page(1)
        expected = "First paragraph body.\n\nSecond paragraph body here."
        assert harness._summary_raw == expected
        assert harness.link_applied[-1] == expected
        harness._display_summary_page(2)
        assert harness.link_applied[-1] == "Third paragraph body."

    def test_paged_search_matches_spaced_buffer_offsets(self, tmp_path) -> None:
        pages_spec = [
            {
                "text": "First paragraph body.\nSecond paragraph body here.",
                "first": 1,
                "last": 2,
            },
            {"text": "Third paragraph body.", "first": 3, "last": 3},
        ]
        root, summary_path, _pages = _build_edition(tmp_path, pages_spec=pages_spec)
        edition = _load(root, summary_path)
        harness = PagedHarness(edition)
        harness._display_summary_page(1)
        buffer_text = harness._summary_page_search_text(harness._summary_raw)
        matches = search_pages(
            edition,
            "Second",
            render=lambda _edition, page_number: harness._summary_page_search_text(
                with_paragraph_spacing(render_page_text(edition, page_number))
            ),
        )
        assert matches == [
            (
                1,
                buffer_text.index("Second"),
                buffer_text.index("Second") + len("Second"),
            )
        ]


class TestBookmarks(PagedBehaviorTests):
    def _seed_bookmark(self, harness: PagedHarness, entry: dict) -> Path:
        bookmarks_path = harness._summary_bookmarks_path_for(
            harness._summary_loaded_path
        )
        bookmarks_path.parent.mkdir(parents=True, exist_ok=True)
        bookmarks_path.write_text(
            json.dumps({"version": 2, "bookmarks": {harness._summary_loaded_path.name: entry}}),
            encoding="utf-8",
        )
        return bookmarks_path

    def test_version2_page_bookmark_return(self, tmp_path) -> None:
        harness = PagedHarness(self._edition(tmp_path))
        self._seed_bookmark(
            harness,
            {
                "page": 2,
                "line": 3,
                "source_sha256": harness._summary_edition.source_sha256,
                "version": 2,
                "updated_at": "2026-09-03T00:00:00+00:00",
            },
        )
        assert harness._summary_bookmark_page(harness._summary_loaded_path) == 2

    def test_version2_hash_mismatch_starts_at_page_one(self, tmp_path) -> None:
        harness = PagedHarness(self._edition(tmp_path))
        self._seed_bookmark(
            harness,
            {
                "page": 2,
                "line": 3,
                "source_sha256": "0" * 64,
                "version": 2,
                "updated_at": "2026-09-03T00:00:00+00:00",
            },
        )
        assert harness._summary_bookmark_page(harness._summary_loaded_path) == 1
        assert any("changed" in toast for toast in harness.toasts)

    def test_version2_out_of_range_page_is_rejected(self, tmp_path) -> None:
        harness = PagedHarness(self._edition(tmp_path))
        self._seed_bookmark(
            harness,
            {
                "page": 9,
                "line": 3,
                "source_sha256": harness._summary_edition.source_sha256,
                "version": 2,
                "updated_at": "2026-09-03T00:00:00+00:00",
            },
        )
        assert harness._summary_bookmark_page(harness._summary_loaded_path) == 1

    def test_version1_line_bookmark_maps_to_page(self, tmp_path) -> None:
        harness = PagedHarness(self._edition(tmp_path))
        self._seed_bookmark(
            harness,
            {"line": 3, "updated_at": "2026-09-03T00:00:00+00:00"},
        )
        assert harness._summary_bookmark_page(harness._summary_loaded_path) == 2
        assert not any("changed" in toast for toast in harness.toasts)

    def test_version2_entry_keeps_line_for_older_clients(self, tmp_path) -> None:
        harness = PagedHarness(self._edition(tmp_path))
        self._seed_bookmark(
            harness,
            {
                "page": 2,
                "line": 3,
                "source_sha256": harness._summary_edition.source_sha256,
                "version": 2,
                "updated_at": "2026-09-03T00:00:00+00:00",
            },
        )
        assert harness._extract_summary_bookmark_line(harness._summary_loaded_path) == 3


class TestPrintRouting(PagedBehaviorTests):
    def test_paged_print_routes_to_page_matched_pdf(self, tmp_path) -> None:
        class OpenPdfSpyHarness(PagedHarness):
            opened_pdf = False

            def _open_page_matched_pdf(self) -> bool:
                self.opened_pdf = True
                return True

        harness = OpenPdfSpyHarness(self._edition(tmp_path))
        harness._summary_raw = "First paragraph."
        harness._on_summary_print_clicked(None)
        assert harness.opened_pdf

    def test_legacy_print_falls_back_to_print_operation(self, tmp_path) -> None:
        root, summary_path, _pages = _build_edition(tmp_path)
        edition = _load(root, summary_path)
        harness = PagedHarness(edition)
        harness._summary_raw = "Legacy text."
        harness._summary_is_paged = lambda: False
        with mock.patch.object(
            harness, "_open_page_matched_pdf", return_value=True
        ) as open_pdf, mock.patch("focus.app.Gtk.PrintOperation") as operation:
            harness._on_summary_print_clicked(None)
        open_pdf.assert_not_called()
        operation.assert_called_once()

    def test_open_pdf_reports_absolute_path_without_viewer(self, tmp_path) -> None:
        import focus.app as app

        root, summary_path, _pages = _build_edition(tmp_path)
        harness = PagedHarness(_load(root, summary_path))
        harness.input_dir = root
        with mock.patch.object(
            app.Gio.AppInfo,
            "launch_default_for_uri",
            side_effect=RuntimeError("no viewer"),
        ):
            opened = harness._open_page_matched_pdf()
        assert not opened
        assert any(
            str(harness._summary_edition.pdf_path.resolve()) in toast
            for toast in harness.toasts
        )
