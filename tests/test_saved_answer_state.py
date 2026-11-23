from __future__ import annotations

from dataclasses import replace
from pathlib import Path
import stat
from types import SimpleNamespace
from urllib.parse import unquote, urlparse

import pytest

from focus import app as app_module
from focus.app import Focus
from focus.core import AGENT_SUBVIEW_ANSWER, AGENT_SUBVIEW_SESSION, AI_VIEW_AGENT_QA, AI_VIEW_FILE
from focus.saved_answers import (
    AgentAnswerSnapshot,
    SavedAnswerListing,
    SavedAnswerResult,
    new_answer_id,
    save_saved_answer,
)
from test_agent_answer_polling import (
    AgentAnswerPollHarness,
    _artifact_payload,
    _write,
)
from focus.agent_answer import create_focus_run_id, focus_answer_artifact_path


class _FakeButton:
    def __init__(self) -> None:
        self.label = ""
        self.sensitive = None
        self.visible = None
        self.tooltip = ""

    def set_label(self, value: str) -> None:
        self.label = value

    def set_sensitive(self, value: bool) -> None:
        self.sensitive = value

    def set_visible(self, value: bool) -> None:
        self.visible = value

    def set_tooltip_text(self, value: str) -> None:
        self.tooltip = value


class StateHarness(AgentAnswerPollHarness):
    _on_latest_answer_clicked = Focus._on_latest_answer_clicked
    _on_saved_answer_selected = Focus._on_saved_answer_selected
    _on_saved_answer_primary = Focus._on_saved_answer_primary
    _on_saved_answer_delete_requested = Focus._on_saved_answer_delete_requested
    _on_save_answer_clicked = Focus._on_save_answer_clicked
    _leave_saved_answer_view = Focus._leave_saved_answer_view
    _printable_answer_snapshot = Focus._printable_answer_snapshot
    _refresh_answer_pdf_button = Focus._refresh_answer_pdf_button
    _cancel_answer_pdf_request = Focus._cancel_answer_pdf_request
    _on_print_answer_clicked = Focus._on_print_answer_clicked
    _finish_answer_pdf_request = Focus._finish_answer_pdf_request
    _reset_saved_answers_state = Focus._reset_saved_answers_state

    def __init__(self, run_id: str, artifact_path) -> None:
        super().__init__(run_id, artifact_path)
        self._save_answer_button = _FakeButton()
        self._print_answer_button = _FakeButton()
        self._answer_pdf_request = None
        self._answer_pdf_deletions: set[str] = set()
        self._saved_answers_generation = 0
        self._ai_active_view = AI_VIEW_AGENT_QA
        self._latest_answer_button = _FakeButton()
        self._saved_answers_popover = None
        self._saved_answers_listing = SavedAnswerListing()
        self._last_saved_answer_id = ""
        self._record_layout = SimpleNamespace(root=Path("/tmp/focus-synthetic"))
        self.revealed = 0
        self.submitted: list[tuple[str, object]] = []
        self.toasts: list[str] = []
        self.failed_viewer_paths: list[Path] = []
        self.reloads = 0

    def _reveal_agent_answer_view(self) -> None:
        self.revealed += 1

    def _submit_saved_answers_task(self, kind, operation, callback) -> None:  # type: ignore[no-untyped-def]
        self.submitted.append((kind, callback))

    def _ai_transient_toast(self, message: str) -> None:
        self.toasts.append(message)

    def _show_answer_pdf_viewer_error(self, path: Path) -> None:
        self.failed_viewer_paths.append(path)

    def _reload_saved_answers(self) -> None:
        self.reloads += 1


def _saved_snapshot(markdown: str = "Saved answer text.\n") -> AgentAnswerSnapshot:
    return AgentAnswerSnapshot(
        answer_id=new_answer_id(),
        markdown=markdown,
        title="Saved Title",
        subtitle="Saved subtitle",
        status="complete",
        capture="submit_tool",
        answer_kind="answered",
        stop_reason="toolUse",
        question="Original question",
        saved_at="2026-09-23T12:00:00+00:00",
        origin="saved",
    )


def test_new_live_revision_does_not_replace_displayed_saved_answer(tmp_path) -> None:
    run_id = create_focus_run_id()
    path = focus_answer_artifact_path(run_id, tmp_path)
    harness = StateHarness(run_id, path)

    saved = _saved_snapshot()
    harness._display_agent_snapshot(saved, is_saved=True)
    assert harness._output_state.raw == saved.markdown
    assert harness._agent_displayed_is_saved

    live_markdown = 'New live answer with "a quote".\n'
    _write(path, _artifact_payload(run_id, 1, live_markdown))
    assert harness._poll_agent_answer() is True

    # The saved answer stays displayed and the live revision is retained.
    assert harness._output_state.raw == saved.markdown
    assert harness._agent_live_snapshot is not None
    assert harness._agent_live_snapshot.markdown == live_markdown
    assert harness._latest_answer_pending
    assert harness._latest_answer_button.visible is True
    assert harness._latest_answer_button.label == "Latest Answer •"
    assert harness.link_calls[-1] == saved.markdown

    # Latest Answer returns to the live workflow.
    harness._on_latest_answer_clicked(harness._latest_answer_button)
    assert harness._output_state.raw == live_markdown
    assert not harness._agent_displayed_is_saved
    assert harness._latest_answer_pending is False
    assert harness._latest_answer_button.visible is False


def test_save_button_tracks_displayed_snapshot(tmp_path) -> None:
    run_id = create_focus_run_id()
    path = focus_answer_artifact_path(run_id, tmp_path)
    harness = StateHarness(run_id, path)

    # No answer: saving is disabled.
    harness._display_agent_snapshot(_saved_snapshot(""), is_saved=True)
    harness._agent_displayed_snapshot = None
    harness._refresh_answer_action_state()
    assert harness._save_answer_button.sensitive is False

    live = replace(_saved_snapshot("Live text.\n"), origin="live")
    harness._display_agent_snapshot(live, is_saved=False)
    assert harness._save_answer_button.label == "Save Answer"
    assert harness._save_answer_button.sensitive is True

    # A saved snapshot shows Saved and cannot be re-saved.
    harness._display_agent_snapshot(_saved_snapshot(), is_saved=True)
    assert harness._save_answer_button.label == "Saved"
    assert harness._save_answer_button.sensitive is False


def test_session_selection_synchronizes_to_live_without_mislabeling(tmp_path) -> None:
    run_id = create_focus_run_id()
    path = focus_answer_artifact_path(run_id, tmp_path)
    harness = StateHarness(run_id, path)

    saved = _saved_snapshot()
    harness._display_agent_snapshot(saved, is_saved=True)
    live = replace(
        saved,
        answer_id=new_answer_id(),
        markdown="Live revision.\n",
        origin="live",
        saved_at=None,
    )
    harness._agent_live_snapshot = live

    harness._leave_saved_answer_view()

    assert harness._agent_displayed_snapshot is live
    assert harness._agent_displayed_is_saved is False
    # The buffer is synchronized lazily; it must not keep the saved text.
    harness._sync_agent_answer_buffer()
    assert harness._output_state.raw == live.markdown


def test_session_selection_without_live_keeps_saved_identity(tmp_path) -> None:
    run_id = create_focus_run_id()
    path = focus_answer_artifact_path(run_id, tmp_path)
    harness = StateHarness(run_id, path)

    saved = _saved_snapshot()
    harness._display_agent_snapshot(saved, is_saved=True)
    harness._agent_live_snapshot = None

    harness._leave_saved_answer_view()

    assert harness._agent_displayed_snapshot is saved
    assert harness._agent_displayed_is_saved is True


def test_primary_saved_answer_action_resumes_last_viewed(tmp_path) -> None:
    run_id = create_focus_run_id()
    path = focus_answer_artifact_path(run_id, tmp_path)
    harness = StateHarness(run_id, path)

    first = _saved_snapshot("First saved.\n").to_saved()
    second = _saved_snapshot("Second saved.\n").to_saved()
    harness._saved_answers_listing = SavedAnswerListing((first, second))
    harness._last_saved_answer_id = second.answer_id

    harness._on_saved_answer_primary()

    assert harness._output_state.raw == second.markdown
    assert harness._last_saved_answer_id == second.answer_id


def test_primary_saved_answer_action_falls_back_to_newest(tmp_path) -> None:
    run_id = create_focus_run_id()
    path = focus_answer_artifact_path(run_id, tmp_path)
    harness = StateHarness(run_id, path)

    newest = _saved_snapshot("Newest saved.\n").to_saved()
    older = _saved_snapshot("Older saved.\n").to_saved()
    harness._saved_answers_listing = SavedAnswerListing((newest, older))
    harness._last_saved_answer_id = "f" * 32

    harness._on_saved_answer_primary()

    assert harness._output_state.raw == newest.markdown
    assert harness._last_saved_answer_id == newest.answer_id


def test_primary_saved_answer_action_with_empty_library_toasts(tmp_path) -> None:
    run_id = create_focus_run_id()
    path = focus_answer_artifact_path(run_id, tmp_path)
    harness = StateHarness(run_id, path)

    harness._on_saved_answer_primary()

    assert harness.toasts == ["No saved answers for this case yet."]
    assert harness.reloads == 1


def test_selecting_saved_answer_records_last_viewed(tmp_path) -> None:
    run_id = create_focus_run_id()
    path = focus_answer_artifact_path(run_id, tmp_path)
    harness = StateHarness(run_id, path)

    saved = _saved_snapshot().to_saved()
    harness._saved_answers_listing = SavedAnswerListing((saved,))
    harness._on_saved_answer_selected(saved.answer_id)

    assert harness._last_saved_answer_id == saved.answer_id


def test_late_saved_answer_load_is_rejected(tmp_path) -> None:
    run_id = create_focus_run_id()
    path = focus_answer_artifact_path(run_id, tmp_path)
    harness = StateHarness(run_id, path)

    harness._on_saved_answer_selected("f" * 32)
    assert harness.submitted
    _kind, callback = harness.submitted[0]

    # A later user choice supersedes the queued load.
    harness._answer_navigation_generation += 1
    callback(SavedAnswerResult(answer=_saved_snapshot().to_saved()), None)

    assert harness.revealed == 0
    assert harness._output_state.raw == ""


def test_applied_saved_answer_load_still_displays(tmp_path) -> None:
    run_id = create_focus_run_id()
    path = focus_answer_artifact_path(run_id, tmp_path)
    harness = StateHarness(run_id, path)

    harness._on_saved_answer_selected("f" * 32)
    _kind, callback = harness.submitted[0]
    saved = _saved_snapshot().to_saved()
    callback(SavedAnswerResult(answer=saved), None)

    assert harness.revealed == 1
    assert harness._output_state.raw == saved.markdown


def test_selecting_saved_answer_reveals_agent_view(tmp_path) -> None:
    run_id = create_focus_run_id()
    path = focus_answer_artifact_path(run_id, tmp_path)
    harness = StateHarness(run_id, path)

    saved = _saved_snapshot().to_saved()
    harness._saved_answers_listing = SavedAnswerListing((saved,))
    harness._on_saved_answer_selected(saved.answer_id)

    # Even if a Hearings/Reports summary was the visible view, selection
    # switches back to Agent Q&A and shows the saved answer.
    assert harness.revealed == 1
    assert harness._output_state.raw == saved.markdown
    assert harness._agent_displayed_is_saved
    assert harness.subview_calls[-1] == "answer"


@pytest.fixture
def preview(tmp_path, monkeypatch):
    """Drive real staging while controlling both thread and GTK idle delivery."""
    runtime = tmp_path / "runtime"
    runtime.mkdir(mode=0o700)
    monkeypatch.setenv("XDG_RUNTIME_DIR", str(runtime))
    run_id = create_focus_run_id()
    app = StateHarness(run_id, focus_answer_artifact_path(run_id, tmp_path))
    bundle = tmp_path / "synthetic-bundle"
    bundle.mkdir()
    app._record_layout = SimpleNamespace(root=bundle)
    workers, idles, launched, holds = [], [], [], []
    app.hold = lambda: holds.append(True)
    app.release = holds.pop
    app.get_active_window = lambda: object()
    monkeypatch.setattr(app_module.threading, "Thread", lambda *, target, **_: SimpleNamespace(
        start=lambda: workers.append(target),
    ))
    monkeypatch.setattr(app_module.GLib, "idle_add", lambda call, *args: idles.append((call, args)))
    monkeypatch.setattr(app_module.Gio.AppInfo, "launch_default_for_uri",
                        lambda uri, _: launched.append(uri) is None)
    return SimpleNamespace(app=app, runtime=runtime, directory=runtime / "focus-answer-pdfs",
                           workers=workers, idles=idles, launched=launched, holds=holds)


def _finish_preview(preview) -> None:
    call, args = preview.idles.pop(0)
    assert call(*args) is False
    assert not preview.holds


def _run_preview(preview) -> None:
    preview.workers.pop(0)()
    _finish_preview(preview)


def test_print_contingent_on_successful_save_and_answer_view(preview) -> None:
    app = preview.app
    snapshot = replace(_saved_snapshot("Live text."), origin="live", saved_at=None)
    app._display_agent_snapshot(snapshot, is_saved=False)
    assert not app._print_answer_button.visible
    app._on_print_answer_clicked(None)
    assert not preview.workers
    app._on_save_answer_clicked(None)
    assert not app._print_answer_button.visible
    _, failure = app.submitted.pop()
    failure(None, OSError())
    assert not app._print_answer_button.visible
    app._on_save_answer_clicked(None)
    _, success = app.submitted.pop()
    success(SavedAnswerResult(answer=snapshot.to_saved()), None)
    assert app._print_answer_button.visible and app._print_answer_button.sensitive
    for view, subview in ((AI_VIEW_AGENT_QA, AGENT_SUBVIEW_SESSION), (AI_VIEW_FILE, AGENT_SUBVIEW_ANSWER)):
        app._ai_active_view, app._agent_subview_name = view, subview
        app._refresh_answer_pdf_button()
        assert not app._print_answer_button.visible
        app._on_print_answer_clicked(None)
        assert not preview.workers
    app._ai_active_view = AI_VIEW_AGENT_QA
    app._display_agent_snapshot(_saved_snapshot("  \n"), is_saved=True)
    assert not app._print_answer_button.visible


def test_preview_uses_displayed_snapshot_and_preserves_saved_answer(preview, monkeypatch) -> None:
    from focus import answer_pdf

    app = preview.app
    snapshot = replace(_saved_snapshot(), status="partial", stop_reason="length")
    result = save_saved_answer(app._record_layout.root, snapshot.to_saved())
    assert result.answer is not None
    app._display_agent_snapshot(AgentAnswerSnapshot.from_saved(result.answer), is_saved=True)
    app._answer_positions.capture(snapshot.answer_id, anchor_offset=19, scroll_fraction=0.4)
    position = app._answer_positions.get(snapshot.answer_id)
    case_files = {p: p.read_bytes() for p in app._record_layout.root.rglob("*") if p.is_file()}
    # Simulate arrival of a newer live answer while the real print is pending.
    app._on_print_answer_clicked(None)
    _write(app._agent_answer_artifact_path, _artifact_payload(app._agent_run_id, 1, "New live prose."))
    assert app._poll_agent_answer() is True
    app._on_print_answer_clicked(None)
    assert len(preview.workers) == 1 and not app._print_answer_button.sensitive

    rendered = []
    original = answer_pdf.render_answer_pdf

    def record(markdown, output):
        rendered.append(markdown)
        original(markdown, output)

    monkeypatch.setattr(answer_pdf, "render_answer_pdf", record)
    preview.workers.pop()()
    staged, = preview.directory.iterdir()
    assert staged.name.startswith(".stage-")
    assert stat.S_IMODE(staged.stat().st_mode) == 0o600
    assert not preview.launched
    _finish_preview(preview)
    assert rendered == [snapshot.markdown]
    assert app._agent_live_snapshot.markdown == "New live prose."
    assert app._output_state.raw == snapshot.markdown
    assert app._answer_positions.get(snapshot.answer_id) == position
    assert {p: p.read_bytes() for p in app._record_layout.root.rglob("*") if p.is_file()} == case_files
    pdf, = preview.directory.iterdir()
    assert preview.launched == [pdf.as_uri()]
    assert len(pdf.stem) == 64 and snapshot.answer_id not in pdf.name
    assert stat.S_IMODE(preview.directory.stat().st_mode) == 0o700
    assert stat.S_IMODE(pdf.stat().st_mode) == 0o600
    assert pdf.read_bytes().startswith(b"%PDF-")
    assert app._print_answer_button.sensitive

    app._on_print_answer_clicked(None)
    _run_preview(preview)
    assert list(preview.directory.iterdir()) == [pdf]
    assert preview.launched == [pdf.as_uri()] * 2


@pytest.mark.parametrize("change", ["switch", "case", "session-return", "summary-return", "delete", "close"])
def test_superseded_print_never_publishes(preview, monkeypatch, change) -> None:
    app = preview.app
    saved = _saved_snapshot()
    app._display_agent_snapshot(saved, is_saved=True)
    app._on_print_answer_clicked(None)
    preview.workers.pop()()
    assert len(list(preview.directory.iterdir())) == 1
    if change == "switch":
        app._display_agent_snapshot(_saved_snapshot("Another answer."), is_saved=True)
        app._display_agent_snapshot(saved, is_saved=True)
    elif change == "case":
        app._reset_saved_answers_state()
        app._case_generation += 1
    elif change == "session-return":
        app._agent_session_button = app._agent_answer_scroller = app._ai_panel_revealer = None
        app._sync_agent_session_widget_visibility = lambda: None
        app._refresh_search_highlighted_button = lambda: None
        Focus._set_agent_subview(app, AGENT_SUBVIEW_SESSION)
        assert not app._print_answer_button.visible
        Focus._set_agent_subview(app, AGENT_SUBVIEW_ANSWER)
    elif change == "summary-return":
        for name in ("_ai_view_stack", "_ai_controls_stack", "_ai_panel_revealer", "_summary_loaded_path"):
            setattr(app, name, None)
        app._auto_loading_summary = True
        for name in ("_sync_ai_view_toggles", "_refresh_case_tools_status", "_restore_summary_scroll_position",
                     "_update_summary_progress_label", "_capture_summary_scroll_position",
                     "_cancel_pending_summary_scroll_restore", "_sync_sidebar_active_page",
                     "_refresh_search_highlighted_button"):
            setattr(app, name, lambda *args: None)
        Focus._set_ai_view(app, AI_VIEW_FILE)
        assert not app._print_answer_button.visible
        Focus._set_ai_view(app, AI_VIEW_AGENT_QA)
    elif change == "delete":
        app._on_saved_answer_delete_requested(saved.answer_id)
        assert not app._print_answer_button.sensitive
    else:
        monkeypatch.setattr(app_module, "close_settings_before_parent", lambda _: False)
        app._image_print_window = app._transcript_breakdown_window = None
        for name in ("_clear_citation_extent", "_stop_grep_search_if_running", "_stop_agent_terminal",
                     "_stop_agent_answer_polling", "_cleanup_agent_answer_artifact",
                     "_stop_ai_panel_resize_tracking", "_cancel_pending_summary_scroll_restore"):
            setattr(app, name, lambda: None)
        assert Focus._on_main_window_close_request(app, None) is False
        app.get_active_window = lambda: None
    _finish_preview(preview)
    assert list(preview.directory.iterdir()) == []
    assert not preview.launched and not app.toasts


@pytest.mark.parametrize("fault", ["missing", "mode", "symlink", "no-write", "render"])
def test_preview_storage_or_render_failure_allows_retry(preview, monkeypatch, fault) -> None:
    from focus import answer_pdf, answer_pdf_preview

    def fail(*args, **kwargs):
        raise PermissionError("synthetic failure")

    app = preview.app
    app._display_agent_snapshot(_saved_snapshot(), is_saved=True)
    with monkeypatch.context() as patch:
        if fault == "missing":
            patch.delenv("XDG_RUNTIME_DIR")
        elif fault == "mode":
            preview.directory.mkdir(mode=0o755)
        elif fault == "symlink":
            preview.directory.symlink_to(app._record_layout.root, target_is_directory=True)
        elif fault == "no-write":
            patch.setattr(answer_pdf_preview.os, "mkdir", fail)
        else:
            patch.setattr(answer_pdf, "render_answer_pdf", fail)
        app._on_print_answer_clicked(None)
        _run_preview(preview)
    assert not preview.launched
    assert app.toasts == ["Could not create the printable PDF. Try again."]
    assert app._print_answer_button.sensitive
    assert not list(app._record_layout.root.iterdir())
    if fault == "symlink":
        preview.directory.unlink()
    elif preview.directory.exists():
        assert not list(preview.directory.iterdir())
        preview.directory.chmod(0o700)
    app._on_print_answer_clicked(None)
    _run_preview(preview)
    assert len(preview.launched) == 1


@pytest.mark.parametrize("raises", [True, False])
def test_viewer_failure_reports_completed_preview_path(preview, monkeypatch, raises) -> None:
    app = preview.app
    app._display_agent_snapshot(_saved_snapshot(), is_saved=True)

    def unavailable(uri, _):
        preview.launched.append(uri)
        if raises:
            raise app_module.GLib.Error("synthetic viewer failure")
        return False

    monkeypatch.setattr(app_module.Gio.AppInfo, "launch_default_for_uri", unavailable)
    app._on_print_answer_clicked(None)
    _run_preview(preview)
    uri, = preview.launched
    pdf = Path(unquote(urlparse(uri).path))
    assert pdf.exists()
    assert app.failed_viewer_paths == [pdf]
    assert app._print_answer_button.sensitive


def test_replaced_preview_directory_is_not_used(preview) -> None:
    app = preview.app
    app._display_agent_snapshot(_saved_snapshot(), is_saved=True)
    app._on_print_answer_clicked(None)
    preview.workers.pop()()
    moved = preview.directory.with_name("moved")
    preview.directory.rename(moved)
    preview.directory.mkdir(mode=0o700)
    _finish_preview(preview)
    assert not preview.launched
    assert not list(moved.iterdir()) and not list(preview.directory.iterdir())
    assert app.toasts == ["Could not create the printable PDF. Try again."]
