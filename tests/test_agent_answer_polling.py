from __future__ import annotations

import json
from pathlib import Path

from focus.agent_answer import create_focus_run_id, focus_answer_artifact_path
from focus.app import Focus
from focus.core import (
    AGENT_SUBVIEW_ANSWER,
    AI_VIEW_AGENT_QA,
    AiOutputView,
    FocusViewState,
)


def _artifact_payload(
    run_id: str,
    revision: int,
    markdown: str,
    *,
    capture: str = "submit_tool",
    status: str = "complete",
    answer_kind: str = "answered",
) -> dict:
    return {
        "schema_version": 1,
        "run_id": run_id,
        "revision": revision,
        "status": status,
        "capture": capture,
        "answer_kind": answer_kind,
        "markdown": markdown,
        "warnings": [],
        "diagnostics": {
            "provider": "fireworks",
            "model": "accounts/fireworks/models/deepseek-v4-pro-0813",
            "thinking": "low",
            "stop_reason": "toolUse" if capture == "submit_tool" else "stop",
            "assistant_turns": 4,
            "tool_calls": 5,
            "searches": 2,
            "pages_read": 3,
            "grep_calls": 0,
            "map_inspections": 0,
            "usage": {
                "input": 10,
                "output": 20,
                "cache_read": 30,
                "reported_cost": 0.04,
            },
            "elapsed_ms": 100,
        },
    }


def _write(path: Path, payload: dict, mode: int = 0o600) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")
    path.chmod(mode)


class AgentAnswerPollHarness:
    _poll_agent_answer = Focus._poll_agent_answer

    def __init__(self, run_id: str, artifact_path: Path) -> None:
        self._agent_run_id = run_id
        self._agent_answer_artifact_path = artifact_path
        self._agent_answer_revision = 0
        self._agent_answer_diagnostics: dict = {}
        self._agent_last_answer_text = ""
        self._agent_answer_status = ""
        self._agent_terminal_active = True
        self._agent_answer_poll_id = 123
        self._agent_workspace_path: Path | None = None
        self._agent_session_log_path: Path | None = None
        self._agent_session_preserve_path: Path | None = None
        self.header_syncs = 0
        self._output_state = AiOutputView()
        self._ai_outputs = {AI_VIEW_AGENT_QA: self._output_state}
        self._view_state = FocusViewState()
        self.link_calls: list[str] = []
        self.subview_calls: list[str] = []
        self.status_calls: list[tuple[str, bool]] = []
        self.height_updates = 0

    def _get_ai_output_state(self, view_name: str) -> AiOutputView:
        return self._ai_outputs[view_name]

    def _current_view_state(self) -> FocusViewState:
        return self._view_state

    def _apply_ai_output_links(self, text: str, state: AiOutputView) -> None:
        self.link_calls.append(text)

    def _set_agent_subview(self, subview_name: str) -> None:
        self.subview_calls.append(subview_name)

    def _update_ai_status(self, text: str, spinning: bool) -> None:
        self.status_calls.append((text, spinning))

    def _queue_embedded_ai_panel_height_update(self, *, after_render: bool = False) -> None:
        self.height_updates += 1

    def _sync_agent_output_header_state(self) -> None:
        self.header_syncs += 1


def test_poll_accepts_two_revisions_and_renders_latest_through_links(tmp_path) -> None:
    run_id = create_focus_run_id()
    path = focus_answer_artifact_path(run_id, tmp_path)
    harness = AgentAnswerPollHarness(run_id, path)

    first_markdown = 'First answer with "a short quote".'
    second_markdown = "Second answer replaces the first unchanged."

    _write(path, _artifact_payload(run_id, 1, first_markdown))
    assert harness._poll_agent_answer() is True

    _write(path, _artifact_payload(run_id, 2, second_markdown))
    assert harness._poll_agent_answer() is True

    # The second revision replaced the raw output and latest-answer text.
    assert harness._output_state.raw == second_markdown
    assert harness._current_view_state().ai_output_raw[AI_VIEW_AGENT_QA] == second_markdown
    assert harness._agent_last_answer_text == second_markdown

    # Only the final answer is passed through the shared rendering path.
    assert harness.link_calls == [first_markdown, second_markdown]

    # Each accepted answer switches Focus to the Answer subview.
    assert harness.subview_calls == [AGENT_SUBVIEW_ANSWER, AGENT_SUBVIEW_ANSWER]

    # Status is updated (non-spinning) and panel height recalculated.
    assert harness.status_calls and all(not spinning for _, spinning in harness.status_calls)
    assert harness._agent_answer_status == "Final answer ready."
    assert harness.height_updates == 2

    # Polling stays active while the terminal is still alive.
    assert harness._agent_answer_poll_id == 123


def test_poll_keeps_polling_until_terminal_exits(tmp_path) -> None:
    run_id = create_focus_run_id()
    path = focus_answer_artifact_path(run_id, tmp_path)
    harness = AgentAnswerPollHarness(run_id, path)
    _write(path, _artifact_payload(run_id, 1, "Only answer."))

    assert harness._poll_agent_answer() is True

    harness._agent_terminal_active = False
    assert harness._poll_agent_answer() is False
    assert harness._agent_answer_poll_id is None


def test_poll_does_not_replace_answer_on_stale_revision(tmp_path) -> None:
    run_id = create_focus_run_id()
    path = focus_answer_artifact_path(run_id, tmp_path)
    harness = AgentAnswerPollHarness(run_id, path)
    first_markdown = "Accepted answer."

    _write(path, _artifact_payload(run_id, 1, first_markdown))
    assert harness._poll_agent_answer() is True

    # Rewriting the same revision must not overwrite the displayed answer.
    _write(path, _artifact_payload(run_id, 1, "Stale duplicate."))
    assert harness._poll_agent_answer() is True

    assert harness._agent_last_answer_text == first_markdown
    assert harness._output_state.raw == first_markdown
    assert harness.link_calls == [first_markdown]


def test_poll_discovers_live_session_log_once(tmp_path) -> None:
    run_id = create_focus_run_id()
    path = focus_answer_artifact_path(run_id, tmp_path)
    harness = AgentAnswerPollHarness(run_id, path)
    _write(path, _artifact_payload(run_id, 1, "Answer text."))

    workspace = tmp_path / "workspace"
    session_log = workspace / "pi-sessions" / "session.jsonl"
    session_log.parent.mkdir(parents=True)
    session_log.write_text(
        json.dumps({"type": "session", "cwd": str(workspace)}) + "\n",
        encoding="utf-8",
    )
    harness._agent_workspace_path = workspace

    assert harness._poll_agent_answer() is True
    assert harness._agent_session_log_path == session_log
    # Discovery resynchronizes the output header exactly once.
    assert harness.header_syncs == 1

    # A later poll keeps the already-discovered log and does not re-sync.
    assert harness._poll_agent_answer() is True
    assert harness._agent_session_log_path == session_log
    assert harness.header_syncs == 1


def test_poll_without_workspace_skips_session_discovery(tmp_path) -> None:
    run_id = create_focus_run_id()
    path = focus_answer_artifact_path(run_id, tmp_path)
    harness = AgentAnswerPollHarness(run_id, path)
    _write(path, _artifact_payload(run_id, 1, "Answer text."))

    assert harness._poll_agent_answer() is True
    assert harness._agent_session_log_path is None
    assert harness.header_syncs == 0
