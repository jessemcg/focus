"""Read-only overview discovery and Case Tools presentation using fiction only."""

import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from focus.case_overview import overview_display_markdown, overview_payload


FIXTURE = Path(__file__).parent / "fixtures" / "case_overview_v1.md"


def _bundle(root, *, overview=False):
    (root / "text_pages").mkdir(parents=True)
    for page in (1, 2):
        (root / "text_pages" / f"{page:04d}.txt").write_text(f"Synthetic record page {page}.\n")
    (root / "artifacts").mkdir()
    path = root / "artifacts" / "case_overview.md"
    if overview:
        path.write_bytes(FIXTURE.read_bytes())
    return path


def test_overview_lookup_prefers_manifest_and_falls_back_without_source_map(tmp_path):
    default = _bundle(tmp_path, overview=True)
    source = FIXTURE.read_text(encoding="utf-8")
    default_payload = {
        "available": True,
        "status": "nonauthoritative-orientation",
        "schema_version": 1,
        "content": source,
    }
    assert overview_payload(tmp_path) == default_payload

    selected = tmp_path / "custom.md"
    selected.write_text(source + "\nManifest-selected text.\n", encoding="utf-8")
    (tmp_path / "manifest.json").write_text(json.dumps({"files": {"case_overview": selected.name}}))
    assert overview_payload(tmp_path) == default_payload | {"content": selected.read_text()}
    selected.write_bytes(b"\xff")
    assert overview_payload(tmp_path)["status"] == "invalid"
    selected.unlink()
    assert overview_payload(tmp_path) == default_payload
    default.unlink()
    assert overview_payload(tmp_path) == {
        "available": False, "status": "unavailable", "schema_version": None, "content": "",
    }


@pytest.mark.parametrize("configured", ["../outside.md", "absolute", "linked.md"])
def test_overview_rejects_outside_paths(tmp_path, configured):
    case = tmp_path / "case"
    default = _bundle(case)
    outside = tmp_path / "outside.md"
    outside.write_bytes(FIXTURE.read_bytes())
    (case / "linked.md").symlink_to(outside)
    if configured == "absolute":
        configured = str(outside)
    (case / "manifest.json").write_text(json.dumps({"files": {"case_overview": configured}}))
    assert overview_payload(case)["status"] == "unavailable"
    default.symlink_to(outside)
    assert overview_payload(case)["status"] == "unavailable"


@pytest.mark.parametrize("unsupported", [b"\xff", b"# Case Overview\nNo metadata.\n", None])
def test_overview_rejects_invalid_content(tmp_path, unsupported):
    path = _bundle(tmp_path)
    if unsupported is None:
        unsupported = FIXTURE.read_bytes().replace(b"schema_version: 1", b"schema_version: 2")
    path.write_bytes(unsupported)
    assert overview_payload(tmp_path) == {
        "available": False, "status": "invalid", "schema_version": None, "content": "",
    }


def test_only_recognized_leading_metadata_is_stripped():
    source = FIXTURE.read_text(encoding="utf-8")
    body = overview_display_markdown(source)
    assert body == source.split("---\n", 2)[2].lstrip("\n")
    assert overview_display_markdown(body + "\n" + source) == body + "\n" + source
    unrelated = "---\nother: metadata\n---\n\n" + body
    assert overview_display_markdown(unrelated) == unrelated
    unclosed = source.replace("\n---\n", "\n", 1) + "\n---\n"
    assert overview_display_markdown(unclosed) == unclosed


def test_case_tools_overview_presentation_and_refresh(tmp_path, monkeypatch):
    from focus import app as module, core

    if not core.Gtk.init_check():
        pytest.skip("GTK display unavailable")
    monkeypatch.setattr(module, "APPLICATION_ID", "com.mcglaw.Focus.CaseOverviewTest")
    first, second = tmp_path / "first", tmp_path / "second"
    path = _bundle(first, overview=True)
    _bundle(second)
    summaries = first / "summaries"
    summaries.mkdir()
    summary_path = summaries / "reports_sum.txt"
    summary_path.write_text("Synthetic report summary: the inspection was postponed.\n")
    original = path.read_bytes()
    app = module.Focus(input_override=first)
    assert app.register(None)
    app.activate()
    try:
        overview_button = app._ai_view_buttons[core.AI_VIEW_CASE_OVERVIEW]
        agent_button = app._ai_view_buttons[core.AI_VIEW_AGENT_QA]
        wrapper = overview_button.get_parent()
        assert wrapper.get_prev_sibling().get_child() is agent_button
        assert wrapper.get_next_sibling().get_child() is app._summary_source_buttons[core.SUMMARY_SOURCE_HEARING]
        assert wrapper.get_parent().get_max_children_per_line() == 6
        assert overview_button.get_visible() and wrapper.get_visible()
        app._open_case_tool_summary(core.SUMMARY_SOURCE_REPORTS)
        summary = app._summary_loaded_path, app._summary_raw
        assert summary[0] == summary_path
        app.current_index = 1
        app._load_current()
        overview_button.set_active(True)
        assert app._ai_view_stack.get_visible_child_name() == core.AI_VIEW_CASE_OVERVIEW
        assert app._ai_controls_stack.get_visible_child().get_first_child() is None
        assert app._current_page_number() == 2

        view = app._overview_scroller.get_child()
        assert not view.get_editable() and view.get_wrap_mode() == core.Gtk.WrapMode.WORD_CHAR
        buffer = view.get_buffer()

        def contents():
            return buffer.get_text(*buffer.get_bounds(), False)

        def tags_at(fragment):
            offset = contents().index(fragment)
            return {tag.get_property("name") for tag in buffer.get_iter_at_offset(offset).get_tags()}

        expected = (
            "Case Overview", "Orientation aid only.", "Parties and Roles", "Procedural Posture",
            "Key Events", "Principal Issues", "Record Scope", "The fixture ends with this final orientation paragraph.",
        )
        assert [contents().index(text) for text in expected] == sorted(contents().index(text) for text in expected)
        assert contents().startswith("Case Overview\n")
        assert contents().rstrip().endswith(expected[-1])
        assert "- January 2, 2030" in contents()
        assert "md-h1" in tags_at("Case Overview")
        assert "md-blockquote" in tags_at("Orientation aid only.")
        assert "md-h2" in tags_at("Record Scope")
        assert tags_at("applicant") == {"md-bold"}
        assert tags_at("respondent") == {"md-italic"}
        assert path.read_bytes() == original

        changes = []
        buffer.connect("changed", lambda _buffer: changes.append(True))
        active = SimpleNamespace(is_active=lambda: True)
        app._on_window_active_changed(active, None)
        assert not changes
        path.write_bytes(original + b"\nRevised overview.\n")
        app._scan_pages()
        assert changes and "Revised overview." in contents()
        assert overview_button.get_active()
        assert (app._summary_loaded_path, app._summary_raw) == summary

        path.write_bytes(b"\xff")
        app._on_window_active_changed(active, None)
        assert app._ai_active_view == core.AI_VIEW_AGENT_QA and agent_button.get_active()
        assert not overview_button.get_visible() and not wrapper.get_visible() and contents() == ""
        path.write_bytes(original)
        app._on_window_active_changed(active, None)
        path.unlink()
        toasts = []
        monkeypatch.setattr(app, "_ai_transient_toast", toasts.append)
        overview_button.set_active(True)
        assert toasts == ["Case Overview unavailable."]
        assert not overview_button.get_active() and app._ai_active_view == core.AI_VIEW_AGENT_QA

        path.write_bytes(original)
        app._scan_pages()
        overview_button.set_active(True)
        app._apply_input_dir(second, persist=False)
        assert app._ai_view_stack.get_visible_child_name() == core.AI_VIEW_AGENT_QA
        assert not overview_button.get_visible() and not wrapper.get_visible() and contents() == ""
        assert path.read_bytes() == original
        assert not core.CONFIG_FILE.exists()
    finally:
        app._stop_ai_panel_resize_tracking()
        app.win.destroy()
        app.quit()
