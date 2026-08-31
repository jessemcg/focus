from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock

import pytest
from unittest.mock import patch

import focus.app as focus_app_module
from focus.app import Focus
from focus.agent_trace import TraceSnapshotError


class DummyWidget:
    def __init__(self) -> None:
        self.visible = True
        self.sensitive = False

    def set_visible(self, visible: bool) -> None:
        self.visible = visible

    def set_sensitive(self, sensitive: bool) -> None:
        self.sensitive = sensitive


class TraceHarness:
    """Bind Focus agent-trace methods onto a lightweight attribute namespace."""

    _agent_trace_source = Focus._agent_trace_source
    _on_agent_copy_trace_clicked = Focus._on_agent_copy_trace_clicked
    _sync_agent_output_header_state = Focus._sync_agent_output_header_state

    def __init__(self) -> None:
        self._agent_workspace_path: Path | None = None
        self._agent_session_log_path: Path | None = None
        self._agent_session_preserve_path: Path | None = None
        self._agent_output_header = DummyWidget()
        self._agent_answer_button = DummyWidget()
        self._agent_session_button = DummyWidget()
        self._agent_copy_trace_button = DummyWidget()
        self.toasts: list[str] = []

    # --- Focus collaborators the bound methods rely on ---

    def _agent_answer_has_content(self) -> bool:
        return False

    def _agent_session_has_content(self) -> bool:
        return False

    def _ai_transient_toast(self, text: str) -> None:
        self.toasts.append(text)


def _write_live_session(workspace: Path, records: list[dict]) -> Path:
    log = workspace / "pi-sessions" / "session.jsonl"
    log.parent.mkdir(parents=True, exist_ok=True)
    log.write_text(
        "".join(json.dumps(record) + "\n" for record in records), encoding="utf-8"
    )
    return log


def test_trace_source_prefers_live_workspace_log(tmp_path: Path) -> None:
    harness = TraceHarness()
    workspace = tmp_path / "workspace"
    live = _write_live_session(
        workspace, [{"type": "session", "cwd": str(workspace)}]
    )
    preserved = tmp_path / "preserved" / "run.jsonl"
    preserved.parent.mkdir(parents=True)
    preserved.write_text("stale", encoding="utf-8")

    harness._agent_workspace_path = workspace
    harness._agent_session_preserve_path = preserved
    assert harness._agent_trace_source() == live

    # Once the wrapper removed the workspace, the preserved copy takes over.
    harness._agent_workspace_path = None
    assert harness._agent_trace_source() == preserved

    harness._agent_session_preserve_path = None
    assert harness._agent_trace_source() is None


def test_trace_source_ignores_session_log_from_other_cwd(tmp_path: Path) -> None:
    harness = TraceHarness()
    workspace = tmp_path / "workspace"
    _write_live_session(workspace, [{"type": "session", "cwd": "/somewhere-else"}])

    harness._agent_workspace_path = workspace
    assert harness._agent_trace_source() is None


def test_header_state_exposes_copy_trace_without_answer_or_session(
    tmp_path: Path,
) -> None:
    harness = TraceHarness()
    preserved = tmp_path / "preserved" / "run.jsonl"
    preserved.parent.mkdir(parents=True)
    preserved.write_text("trace", encoding="utf-8")

    harness._sync_agent_output_header_state()
    assert not harness._agent_output_header.visible
    assert not harness._agent_copy_trace_button.sensitive

    harness._agent_session_preserve_path = preserved
    harness._sync_agent_output_header_state()
    assert harness._agent_output_header.visible
    assert harness._agent_copy_trace_button.sensitive
    assert not harness._agent_answer_button.sensitive
    assert not harness._agent_session_button.sensitive


def test_copy_trace_click_snapshots_then_copies_prompt(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    harness = TraceHarness()
    workspace = tmp_path / "workspace"
    _write_live_session(
        workspace,
        [
            {"type": "session", "cwd": str(workspace)},
            {"type": "message", "done": True},
        ],
    )
    destination = tmp_path / "exported" / "latest_trace.jsonl"
    monkeypatch.setenv("FOCUS_TRACE_PATH", str(destination))
    harness._agent_workspace_path = workspace

    clipboard = MagicMock()
    display = MagicMock()
    display.get_clipboard.return_value = clipboard
    with patch.object(focus_app_module, "Gdk") as gdk_mock:
        gdk_mock.Display.get_default.return_value = display
        harness._on_agent_copy_trace_clicked(object())

    assert destination.is_file()
    lines = destination.read_text(encoding="utf-8").splitlines()
    assert json.loads(lines[0])["type"] == "session"
    assert len(lines) == 2
    assert clipboard.set.call_count == 1
    prompt = clipboard.set.call_args.args[0]
    assert str(destination) in prompt
    assert "diagnostic evidence" in prompt
    assert any(str(destination) in toast for toast in harness.toasts)


def test_copy_trace_click_without_trace_reports_and_resyncs(tmp_path: Path) -> None:
    harness = TraceHarness()

    harness._on_agent_copy_trace_clicked(object())

    assert harness.toasts == [
        "Copy Trace: no session trace available for the current Agent run."
    ]


def test_copy_trace_click_snapshot_failure_preserves_clipboard(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    harness = TraceHarness()
    workspace = tmp_path / "workspace"
    # Header matches the workspace, but the second complete record is malformed.
    log = workspace / "pi-sessions" / "session.jsonl"
    log.parent.mkdir(parents=True, exist_ok=True)
    log.write_text(
        json.dumps({"type": "session", "cwd": str(workspace)}) + "\nnot json\n",
        encoding="utf-8",
    )
    destination = tmp_path / "exported" / "latest_trace.jsonl"
    destination.parent.mkdir(parents=True)
    destination.write_text("previous trace\n", encoding="utf-8")
    monkeypatch.setenv("FOCUS_TRACE_PATH", str(destination))
    harness._agent_workspace_path = workspace

    clipboard = MagicMock()
    display = MagicMock()
    display.get_clipboard.return_value = clipboard
    with patch.object(focus_app_module, "Gdk") as gdk_mock:
        gdk_mock.Display.get_default.return_value = display
        harness._on_agent_copy_trace_clicked(object())

    assert destination.read_text(encoding="utf-8") == "previous trace\n"
    assert clipboard.set.call_count == 0
    assert any("Copy Trace failed" in toast for toast in harness.toasts)


def test_copy_trace_click_invalid_override_is_rejected(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    harness = TraceHarness()
    workspace = tmp_path / "workspace"
    _write_live_session(workspace, [{"type": "session", "cwd": str(workspace)}])
    monkeypatch.setenv("FOCUS_TRACE_PATH", "relative/path.jsonl")
    harness._agent_workspace_path = workspace

    harness._on_agent_copy_trace_clicked(object())

    assert any("FOCUS_TRACE_PATH" in toast for toast in harness.toasts)


def test_copy_trace_click_clipboard_failure_keeps_saved_trace(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    harness = TraceHarness()
    workspace = tmp_path / "workspace"
    _write_live_session(workspace, [{"type": "session", "cwd": str(workspace)}])
    destination = tmp_path / "exported" / "latest_trace.jsonl"
    monkeypatch.setenv("FOCUS_TRACE_PATH", str(destination))
    harness._agent_workspace_path = workspace

    with patch.object(focus_app_module, "Gdk") as gdk_mock:
        gdk_mock.Display.get_default.return_value = None
        harness._on_agent_copy_trace_clicked(object())

    assert destination.is_file()
    assert any(
        "clipboard was unavailable" in toast and str(destination) in toast
        for toast in harness.toasts
    )


def test_snapshot_error_is_exported_for_callers() -> None:
    # The app module re-exports TraceSnapshotError for its failure handling.
    assert focus_app_module.TraceSnapshotError is TraceSnapshotError
