from __future__ import annotations

from dataclasses import replace

from focus.app import Focus
from focus.saved_answers import AgentAnswerSnapshot, SavedAnswerListing, new_answer_id
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
    _leave_saved_answer_view = Focus._leave_saved_answer_view

    def __init__(self, run_id: str, artifact_path) -> None:
        super().__init__(run_id, artifact_path)
        self._save_answer_button = _FakeButton()
        self._latest_answer_button = _FakeButton()
        self._saved_answers_popover = None
        self._saved_answers_listing = SavedAnswerListing()
        self.revealed = 0

    def _reveal_agent_answer_view(self) -> None:
        self.revealed += 1


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
    assert harness._current_view_state().ai_output_raw["agent-qa"] == saved.markdown
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
