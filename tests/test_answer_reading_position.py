from __future__ import annotations

from focus.app import Focus
from focus.core import AGENT_SUBVIEW_ANSWER, AGENT_SUBVIEW_SESSION, AI_VIEW_AGENT_QA
from focus.reading_position import AnswerPositionCache
from focus.saved_answers import AgentAnswerSnapshot, new_answer_id


class FakeIter:
    def __init__(self, offset: int) -> None:
        self._offset = offset

    def get_offset(self) -> int:
        return self._offset


class FakeBuffer:
    def __init__(self, char_count: int = 5000) -> None:
        self._char_count = char_count

    def get_char_count(self) -> int:
        return self._char_count

    def get_iter_at_offset(self, offset: int) -> FakeIter:
        return FakeIter(offset)


class FakeView:
    def __init__(self, anchor: int = 0, *, mapped: bool = True) -> None:
        self._anchor = anchor
        self._mapped = mapped
        self._buffer = FakeBuffer()
        self.scroll_targets: list[int] = []

    def get_buffer(self) -> FakeBuffer:
        return self._buffer

    def get_iter_at_location(self, _x: int, _y: int) -> FakeIter:
        return FakeIter(self._anchor)

    def get_mapped(self) -> bool:
        return self._mapped

    def scroll_to_iter(self, iter_, *_args: object) -> bool:
        self.scroll_targets.append(iter_.get_offset())
        return True


class FakeAdjustment:
    def __init__(self, *, lower: float = 0.0, upper: float = 1000.0, page_size: float = 100.0, value: float = 0.0) -> None:
        self.lower = lower
        self.upper = upper
        self.page_size = page_size
        self.value = value

    def get_lower(self) -> float:
        return self.lower

    def get_upper(self) -> float:
        return self.upper

    def get_page_size(self) -> float:
        return self.page_size

    def get_value(self) -> float:
        return self.value

    def set_value(self, value: float) -> None:
        self.value = value


class FakeScroller:
    def __init__(self, adjustment: FakeAdjustment, *, visible: bool = True) -> None:
        self._adjustment = adjustment
        self._visible = visible

    def get_vadjustment(self) -> FakeAdjustment:
        return self._adjustment

    def get_visible(self) -> bool:
        return self._visible


class FakeContextLabel:
    def __init__(self) -> None:
        self.text = ""
        self.visible = False
        self.tooltip: str | None = None
        self.accessible: list[str] = []

    def set_text(self, text: str) -> None:
        self.text = text

    def set_visible(self, visible: bool) -> None:
        self.visible = visible

    def set_tooltip_text(self, tooltip: str | None) -> None:
        self.tooltip = tooltip

    def update_property(self, _props: object, values: object) -> None:
        self.accessible.extend(values)  # type: ignore[arg-type]


class ReadingHarness:
    _capture_text_position = Focus._capture_text_position
    _agent_answer_position_value = Focus._agent_answer_position_value
    _capture_agent_answer_position = Focus._capture_agent_answer_position
    _sync_agent_answer_buffer = Focus._sync_agent_answer_buffer
    _restore_agent_answer_position = Focus._restore_agent_answer_position
    _restore_agent_answer_position_if_current = Focus._restore_agent_answer_position_if_current
    _apply_pending_agent_answer_position_restore = (
        Focus._apply_pending_agent_answer_position_restore
    )
    _cancel_agent_answer_position_restore = Focus._cancel_agent_answer_position_restore
    _clear_answer_reading_positions = Focus._clear_answer_reading_positions
    _update_agent_context_line = Focus._update_agent_context_line
    _set_accessible_label = staticmethod(Focus._set_accessible_label)

    def __init__(self) -> None:
        self._agent_subview_name = AGENT_SUBVIEW_ANSWER
        self._agent_context_label = FakeContextLabel()
        self._ai_outputs: dict[str, object] = {}
        self._case_generation = 0
        self._answer_position_generation = 0
        self._answer_position_pending = None
        self._answer_position_restore_source_id = None
        self._answer_position_restore_attempts = 0
        self._answer_position_restore_geometry = None
        self._answer_position_restore_stable_passes = 0
        self._answer_positions = AnswerPositionCache()
        self._agent_displayed_snapshot: AgentAnswerSnapshot | None = None
        self._agent_displayed_is_saved = False


def _snapshot(markdown: str = "Answer body.\n") -> AgentAnswerSnapshot:
    return AgentAnswerSnapshot(
        answer_id=new_answer_id(),
        markdown=markdown,
        title="Title",
        subtitle="Subtitle",
        status="complete",
        capture="submit_tool",
        answer_kind="answered",
        stop_reason="toolUse",
        question="Was it?",
    )


def _state(harness: ReadingHarness, *, anchor: int, value: float, raw: str) -> object:
    from focus.core import AiOutputView

    view = FakeView(anchor)
    adjustment = FakeAdjustment(value=value)
    scroller = FakeScroller(adjustment)
    state = AiOutputView(raw=raw, view=view, scroller=scroller)
    harness._ai_outputs[AI_VIEW_AGENT_QA] = state
    return state


def test_first_open_starts_at_top_with_no_cached_position() -> None:
    harness = ReadingHarness()
    snapshot = _snapshot()
    _state(harness, anchor=0, value=0.0, raw=snapshot.markdown)
    harness._agent_displayed_snapshot = snapshot

    assert harness._answer_positions.get(snapshot.answer_id) is None
    assert harness._restore_agent_answer_position_if_current() is None


def test_capture_records_anchor_and_fraction_for_displayed_answer() -> None:
    harness = ReadingHarness()
    snapshot = _snapshot()
    _state(harness, anchor=812, value=180.0, raw=snapshot.markdown)
    harness._agent_displayed_snapshot = snapshot

    harness._capture_agent_answer_position()

    position = harness._answer_positions.get(snapshot.answer_id)
    assert position is not None
    assert position.anchor_offset == 812
    assert position.scroll_fraction == 0.2


def test_capture_skipped_when_buffer_shows_a_different_snapshot() -> None:
    harness = ReadingHarness()
    snapshot = _snapshot()
    _state(harness, anchor=812, value=180.0, raw="some other answer")
    harness._agent_displayed_snapshot = snapshot

    harness._capture_agent_answer_position()

    assert harness._answer_positions.get(snapshot.answer_id) is None


def test_revisit_schedules_and_applies_anchor_restore() -> None:
    harness = ReadingHarness()
    snapshot = _snapshot()
    state = _state(harness, anchor=0, value=0.0, raw=snapshot.markdown)
    harness._agent_displayed_snapshot = snapshot
    harness._answer_positions.capture(snapshot.answer_id, anchor_offset=900, scroll_fraction=0.4)

    harness._restore_agent_answer_position_if_current()
    pending = harness._answer_position_pending
    assert pending is not None
    assert pending[1] == snapshot.answer_id

    assert harness._apply_pending_agent_answer_position_restore()
    # Second pass confirms stable geometry and completes.
    assert not harness._apply_pending_agent_answer_position_restore()
    assert state.view.scroll_targets
    assert set(state.view.scroll_targets) == {900}
    assert harness._answer_position_pending is None


def test_stale_restore_is_rejected_when_navigation_changes() -> None:
    harness = ReadingHarness()
    snapshot = _snapshot()
    _state(harness, anchor=0, value=0.0, raw=snapshot.markdown)
    harness._agent_displayed_snapshot = snapshot
    harness._answer_positions.capture(snapshot.answer_id, anchor_offset=900, scroll_fraction=0.4)
    harness._restore_agent_answer_position_if_current()

    # A new user choice supersedes the pending restore.
    harness._agent_displayed_snapshot = _snapshot("Different.\n")
    harness._answer_position_generation += 1

    assert not harness._apply_pending_agent_answer_position_restore()
    assert harness._answer_position_pending is None


def test_case_change_clears_positions_and_cancels_pending() -> None:
    harness = ReadingHarness()
    snapshot = _snapshot()
    _state(harness, anchor=0, value=0.0, raw=snapshot.markdown)
    harness._agent_displayed_snapshot = snapshot
    harness._answer_positions.capture(snapshot.answer_id, anchor_offset=900, scroll_fraction=0.4)
    harness._restore_agent_answer_position_if_current()

    harness._clear_answer_reading_positions()

    assert harness._answer_position_pending is None
    assert len(harness._answer_positions) == 0
    assert harness._case_generation == 1


def test_sync_answer_buffer_only_renders_on_content_change() -> None:
    harness = ReadingHarness()
    applied: list[str] = []
    snapshot = _snapshot("Body A.\n")
    state = _state(harness, anchor=0, value=0.0, raw="Body A.\n")
    harness._agent_displayed_snapshot = snapshot
    harness._apply_ai_output_links = lambda text, _state: applied.append(text)  # type: ignore[method-assign]

    harness._sync_agent_answer_buffer()
    assert applied == []

    harness._agent_displayed_snapshot = _snapshot("Body B.\n")
    harness._sync_agent_answer_buffer()
    assert applied == ["Body B.\n"]
    assert state.raw == "Body B.\n"


def test_context_line_hidden_outside_answer_and_reports_identity() -> None:
    harness = ReadingHarness()
    saved = AgentAnswerSnapshot(
        answer_id=new_answer_id(),
        markdown="Saved.\n",
        title="T",
        subtitle="S",
        status="partial",
        capture="submit_tool",
        answer_kind="answered",
        stop_reason="length",
        question="Original question?",
        saved_at="2026-09-24T16:05:00+00:00",
        origin="saved",
    )
    harness._agent_displayed_snapshot = saved
    harness._agent_displayed_is_saved = True

    harness._update_agent_context_line()
    assert harness._agent_context_label.visible is True
    assert harness._agent_context_label.text.startswith("Saved answer · ")
    assert harness._agent_context_label.text.endswith("Partial")
    assert harness._agent_context_label.tooltip == "Original question?"

    harness._agent_subview_name = AGENT_SUBVIEW_SESSION
    harness._update_agent_context_line()
    assert harness._agent_context_label.visible is False


def test_live_context_line_identifies_latest_answer() -> None:
    harness = ReadingHarness()
    harness._agent_displayed_snapshot = _snapshot()
    harness._agent_displayed_is_saved = False

    harness._update_agent_context_line()

    assert harness._agent_context_label.text == "Latest answer"
    assert harness._agent_context_label.visible is True
