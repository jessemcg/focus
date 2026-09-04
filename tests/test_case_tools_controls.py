from pathlib import Path
from types import SimpleNamespace

from focus.app import Focus
from focus.core import (
    AGENT_SUBVIEW_ANSWER,
    AGENT_SUBVIEW_SESSION,
    AI_OUTPUT_MIN_HEIGHT,
    AI_VIEW_AGENT_QA,
    AI_VIEW_EXTRACT,
    AI_VIEW_FILE,
    AI_VIEW_SUMMARIZE,
    SUMMARY_SOURCE_HEARING,
    SUMMARY_SOURCE_MINUTES,
    SUMMARY_SOURCE_REPORTS,
)


class FakeButton:
    def __init__(self) -> None:
        self.active = False
        self.sensitive = False
        self.css_classes: set[str] = set()

    def set_active(self, active: bool) -> None:
        self.active = active

    def set_sensitive(self, sensitive: bool) -> None:
        self.sensitive = sensitive

    def add_css_class(self, css_class: str) -> None:
        self.css_classes.add(css_class)

    def remove_css_class(self, css_class: str) -> None:
        self.css_classes.discard(css_class)


class FakeVisibility:
    def __init__(self, visible: bool = False) -> None:
        self.visible = visible

    def get_visible(self) -> bool:
        return self.visible

    def set_visible(self, visible: bool) -> None:
        self.visible = visible


class FakeEntry:
    def __init__(self, text: str = "") -> None:
        self.text = text

    def get_text(self) -> str:
        return self.text


class FakeViewStack:
    def __init__(self, visible_child_name: str) -> None:
        self.visible_child_name = visible_child_name

    def get_visible_child_name(self) -> str:
        return self.visible_child_name


class FakeScrollerBounds:
    def __init__(self) -> None:
        self.calls: list[tuple[str, int]] = []

    def set_min_content_height(self, height: int) -> None:
        self.calls.append(("min", height))

    def set_max_content_height(self, height: int) -> None:
        self.calls.append(("max", height))


class FakeAdjustment:
    def __init__(
        self,
        *,
        lower: float = 0.0,
        upper: float = 1000.0,
        page_size: float = 100.0,
        value: float = 0.0,
    ) -> None:
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
    def __init__(self, adjustment: FakeAdjustment) -> None:
        self.adjustment = adjustment

    def get_vadjustment(self) -> FakeAdjustment:
        return self.adjustment


class FakeSummaryState:
    def __init__(self, fraction: float | None = None) -> None:
        self.summary_scroll_fraction = fraction


class SummaryScrollHarness:
    _summary_scroll_fraction = Focus._summary_scroll_fraction
    _on_summary_scroll = Focus._on_summary_scroll
    _capture_summary_scroll_position = Focus._capture_summary_scroll_position
    _apply_pending_summary_scroll_restore = Focus._apply_pending_summary_scroll_restore

    def __init__(self, adjustment: FakeAdjustment, fraction: float | None) -> None:
        self.state = FakeSummaryState(fraction)
        self._summary_scroller = FakeScroller(adjustment)
        self._summary_loaded_path = object()
        self._ai_active_view = AI_VIEW_FILE
        self._summary_scroll_restore_guard = False
        self._summary_pending_restore_fraction = fraction
        self._summary_scroll_restore_source_id = 1
        self._summary_scroll_restore_geometry = None
        self._summary_scroll_restore_stable_passes = 0
        self._summary_scroll_restore_attempts = 0
        self.progress_updates = 0

    def _summary_is_paged(self) -> bool:
        return False

    def _current_view_state(self) -> FakeSummaryState:
        return self.state

    def _update_summary_progress_label(self, _adjustment: FakeAdjustment) -> None:
        self.progress_updates += 1

    def _cancel_pending_summary_scroll_restore(self) -> None:
        self._summary_scroll_restore_source_id = None
        self._summary_pending_restore_fraction = None
        self._summary_scroll_restore_geometry = None
        self._summary_scroll_restore_stable_passes = 0
        self._summary_scroll_restore_attempts = 0


class CaseToolHarness:
    _open_case_tool_view = Focus._open_case_tool_view
    _open_case_tool_summary = Focus._open_case_tool_summary

    def __init__(self) -> None:
        self.calls: list[tuple[str, str | None]] = []

    def _ensure_ai_panel_visible(self) -> None:
        self.calls.append(("visible", None))

    def _set_ai_view(self, view_name: str) -> None:
        self.calls.append(("view", view_name))

    def _on_minutes_summary_clicked(self, _button: object) -> None:
        self.calls.append(("summary", SUMMARY_SOURCE_MINUTES))

    def _on_hearing_summary_clicked(self, _button: object) -> None:
        self.calls.append(("summary", SUMMARY_SOURCE_HEARING))

    def _on_reports_summary_clicked(self, _button: object) -> None:
        self.calls.append(("summary", SUMMARY_SOURCE_REPORTS))


class ToggleHarness:
    _sync_ai_view_toggles = Focus._sync_ai_view_toggles

    def __init__(self) -> None:
        self._ai_view_buttons = {
            AI_VIEW_AGENT_QA: FakeButton(),
        }
        self._summary_source_buttons = {
            SUMMARY_SOURCE_HEARING: FakeButton(),
            SUMMARY_SOURCE_REPORTS: FakeButton(),
        }
        self._summary_active_source: str | None = None
        self._more_case_tools_button = FakeButton()
        self._ai_view_toggle_guard = False


class AgentControlsHarness:
    _agent_answer_has_content = Focus._agent_answer_has_content
    _sync_agent_output_header_state = Focus._sync_agent_output_header_state
    _refresh_agent_submit_state = Focus._refresh_agent_submit_state

    def __init__(self) -> None:
        self._agent_last_answer_text = ""
        self._ai_outputs = {AI_VIEW_AGENT_QA: SimpleNamespace(raw="")}
        self._agent_output_header = FakeVisibility()
        self._agent_answer_button = FakeButton()
        self._agent_session_button = FakeButton()
        self._agent_copy_trace_button = FakeButton()
        self._agent_submit_button = FakeButton()
        self._agent_question_entry = FakeEntry()
        self.has_session = False
        self.trace_source: Path | None = None

    def _agent_session_has_content(self) -> bool:
        return self.has_session

    def _agent_trace_source(self) -> Path | None:
        return self.trace_source


class FakeTickWindow:
    def __init__(self) -> None:
        self.callbacks: list[object] = []
        self.removed: list[int] = []

    def add_tick_callback(self, callback: object) -> int:
        self.callbacks.append(callback)
        return 71

    def remove_tick_callback(self, callback_id: int) -> None:
        self.removed.append(callback_id)


class FakeResizeWidget:
    def __init__(self) -> None:
        self.resize_count = 0

    def queue_resize(self) -> None:
        self.resize_count += 1


class FakeResizeScroller(FakeResizeWidget):
    def __init__(self) -> None:
        super().__init__()
        self.child = FakeResizeWidget()

    def get_child(self) -> FakeResizeWidget:
        return self.child


class PostRenderResizeHarness:
    _ensure_ai_panel_post_render_resize = Focus._ensure_ai_panel_post_render_resize
    _on_ai_panel_post_render_tick = Focus._on_ai_panel_post_render_tick

    def __init__(self) -> None:
        self.win = FakeTickWindow()
        self.scroller = FakeResizeScroller()
        self._ai_panel_post_render_tick_id: int | None = None
        self._ai_panel_post_render_frames = 0
        self.height_updates = 0

    def _active_ai_output_scroller(self) -> tuple[FakeResizeScroller, bool]:
        return self.scroller, True

    def _update_embedded_ai_panel_height(self, *, force: bool = False) -> None:
        assert force
        self.height_updates += 1


class PresentationHarness:
    _case_tool_description = Focus._case_tool_description

    def __init__(self) -> None:
        self._ai_active_view = AI_VIEW_AGENT_QA
        self._summary_active_source: str | None = None


class SummaryActionHarness:
    _refresh_summary_actions_state = Focus._refresh_summary_actions_state

    def __init__(self) -> None:
        self._summary_loaded_path: object | None = None
        self._summary_raw = ""
        self._has_bookmark = False
        self._summary_bookmark_action_button = FakeButton()
        self._summary_return_bookmark_action_button = FakeButton()
        self.page_control_updates = 0

    def _summary_has_saved_bookmark(self) -> bool:
        return self._has_bookmark

    def _summary_is_paged(self) -> bool:
        return False

    def _update_summary_page_controls(self) -> None:
        self.page_control_updates += 1


class BodyVisibilityHarness:
    _active_ai_body_has_content = Focus._active_ai_body_has_content

    def __init__(self, view_name: str) -> None:
        self._ai_view_stack = FakeViewStack(view_name)
        self._ai_active_view = view_name
        self._agent_subview_name = AGENT_SUBVIEW_ANSWER
        self.has_output = False
        self.has_agent_session = False

    def _active_ai_output_scroller(self) -> tuple[None, bool]:
        return None, self.has_output

    def _agent_session_has_content(self) -> bool:
        return self.has_agent_session


def test_case_tool_view_action_opens_panel_before_switching_view() -> None:
    harness = CaseToolHarness()

    harness._open_case_tool_view(AI_VIEW_EXTRACT)

    assert harness.calls == [("visible", None), ("view", AI_VIEW_EXTRACT)]


def test_case_tool_summary_actions_open_panel_and_route_sources() -> None:
    for source in (
        SUMMARY_SOURCE_MINUTES,
        SUMMARY_SOURCE_HEARING,
        SUMMARY_SOURCE_REPORTS,
    ):
        harness = CaseToolHarness()

        harness._open_case_tool_summary(source)

        assert harness.calls == [("visible", None), ("summary", source)]


def test_case_tool_buttons_track_active_views_and_summary_sources() -> None:
    harness = ToggleHarness()

    harness._sync_ai_view_toggles(AI_VIEW_SUMMARIZE)
    assert "focus-ai-view-active" in harness._more_case_tools_button.css_classes
    assert not harness._ai_view_buttons[AI_VIEW_AGENT_QA].active

    harness._sync_ai_view_toggles(AI_VIEW_EXTRACT)
    assert "focus-ai-view-active" in harness._more_case_tools_button.css_classes
    assert not harness._ai_view_buttons[AI_VIEW_AGENT_QA].active

    harness._sync_ai_view_toggles(AI_VIEW_FILE)
    assert "focus-ai-view-active" in harness._more_case_tools_button.css_classes

    harness._summary_active_source = SUMMARY_SOURCE_HEARING
    harness._sync_ai_view_toggles(AI_VIEW_FILE)
    assert harness._summary_source_buttons[SUMMARY_SOURCE_HEARING].active
    assert not harness._summary_source_buttons[SUMMARY_SOURCE_REPORTS].active
    assert (
        "focus-ai-view-active"
        in harness._summary_source_buttons[SUMMARY_SOURCE_HEARING].css_classes
    )
    assert (
        "focus-ai-view-active"
        not in harness._summary_source_buttons[SUMMARY_SOURCE_REPORTS].css_classes
    )
    assert "focus-ai-view-active" not in harness._more_case_tools_button.css_classes

    harness._summary_active_source = SUMMARY_SOURCE_REPORTS
    harness._sync_ai_view_toggles(AI_VIEW_FILE)
    assert not harness._summary_source_buttons[SUMMARY_SOURCE_HEARING].active
    assert harness._summary_source_buttons[SUMMARY_SOURCE_REPORTS].active
    assert (
        "focus-ai-view-active"
        not in harness._summary_source_buttons[SUMMARY_SOURCE_HEARING].css_classes
    )
    assert (
        "focus-ai-view-active"
        in harness._summary_source_buttons[SUMMARY_SOURCE_REPORTS].css_classes
    )
    assert "focus-ai-view-active" not in harness._more_case_tools_button.css_classes

    harness._sync_ai_view_toggles(AI_VIEW_AGENT_QA)
    assert harness._ai_view_buttons[AI_VIEW_AGENT_QA].active
    assert not harness._summary_source_buttons[SUMMARY_SOURCE_HEARING].active
    assert not harness._summary_source_buttons[SUMMARY_SOURCE_REPORTS].active
    assert "focus-ai-view-active" not in harness._more_case_tools_button.css_classes


def test_agent_output_controls_appear_only_for_available_output() -> None:
    harness = AgentControlsHarness()

    harness._sync_agent_output_header_state()
    assert not harness._agent_output_header.visible
    assert not harness._agent_answer_button.sensitive
    assert not harness._agent_session_button.sensitive

    harness.has_session = True
    harness._sync_agent_output_header_state()
    assert harness._agent_output_header.visible
    assert not harness._agent_answer_button.sensitive
    assert harness._agent_session_button.sensitive

    harness.has_session = False
    harness._ai_outputs[AI_VIEW_AGENT_QA].raw = "Linked final answer"
    harness._sync_agent_output_header_state()
    assert harness._agent_output_header.visible
    assert harness._agent_answer_button.sensitive
    assert not harness._agent_session_button.sensitive


def test_agent_ask_button_tracks_question_text() -> None:
    harness = AgentControlsHarness()

    harness._refresh_agent_submit_state()
    assert not harness._agent_submit_button.sensitive

    harness._agent_question_entry.text = "  What did the court order?  "
    harness._refresh_agent_submit_state()
    assert harness._agent_submit_button.sensitive


def test_case_tool_descriptions_follow_the_active_source() -> None:
    harness = PresentationHarness()

    assert "original record" in harness._case_tool_description()

    harness._ai_active_view = AI_VIEW_FILE
    harness._summary_active_source = SUMMARY_SOURCE_HEARING
    assert "hearing summaries" in harness._case_tool_description()

    harness._summary_active_source = SUMMARY_SOURCE_REPORTS
    assert "report summaries" in harness._case_tool_description()

    harness._summary_active_source = SUMMARY_SOURCE_MINUTES
    assert "minute-order summaries" in harness._case_tool_description()


def test_summary_actions_track_printable_summary_state() -> None:
    harness = SummaryActionHarness()

    harness._refresh_summary_actions_state()
    assert not harness._summary_bookmark_action_button.sensitive
    assert not harness._summary_return_bookmark_action_button.sensitive

    harness._summary_loaded_path = object()
    harness._summary_raw = "Summary text"
    harness._has_bookmark = True
    harness._refresh_summary_actions_state()

    assert harness._summary_bookmark_action_button.sensitive
    assert harness._summary_return_bookmark_action_button.sensitive


def test_empty_header_only_views_do_not_reserve_body_space() -> None:
    for view_name in (
        AI_VIEW_AGENT_QA,
        AI_VIEW_SUMMARIZE,
        AI_VIEW_EXTRACT,
        AI_VIEW_FILE,
    ):
        harness = BodyVisibilityHarness(view_name)

        assert not harness._active_ai_body_has_content()


def test_dynamic_case_tool_content_expands_the_body() -> None:
    output_harness = BodyVisibilityHarness(AI_VIEW_SUMMARIZE)
    output_harness.has_output = True
    assert output_harness._active_ai_body_has_content()

    agent_harness = BodyVisibilityHarness(AI_VIEW_AGENT_QA)
    agent_harness._agent_subview_name = AGENT_SUBVIEW_SESSION
    agent_harness.has_agent_session = True
    assert agent_harness._active_ai_body_has_content()


def test_summary_emphasis_color_keeps_contrast_in_both_themes() -> None:
    bright = SimpleNamespace(red=0.8, green=0.95, blue=0.7)
    Focus._adjust_summary_emphasis_for_theme(bright, dark=False)
    assert Focus._rgba_luminance(bright) <= 0.580001

    dim = SimpleNamespace(red=0.1, green=0.2, blue=0.1)
    Focus._adjust_summary_emphasis_for_theme(dim, dark=True)
    assert Focus._rgba_luminance(dim) >= 0.519999


def test_embedded_output_minimum_is_readable_and_uses_available_height() -> None:
    harness = object()

    assert Focus._embedded_ai_output_min_height(harness, 100) == 100
    assert Focus._embedded_ai_output_min_height(harness, 400) == 140
    assert AI_OUTPUT_MIN_HEIGHT == 140


def test_embedded_panel_targets_one_third_with_a_short_window_floor() -> None:
    assert Focus._embedded_ai_panel_max_height(0) == 0
    assert Focus._embedded_ai_panel_max_height(200) == 200
    assert Focus._embedded_ai_panel_max_height(720) == 260
    assert Focus._embedded_ai_panel_max_height(1080) == 360
    assert Focus._embedded_ai_panel_max_height(2188) == 729


def test_scroller_bounds_clear_the_minimum_before_changing_the_maximum() -> None:
    scroller = FakeScrollerBounds()

    Focus._set_scroller_content_height_bounds(scroller, 36, 207)

    assert scroller.calls == [("min", -1), ("max", 207), ("min", 36)]


def test_post_render_resize_queues_layout_then_measures_once() -> None:
    harness = PostRenderResizeHarness()

    harness._ensure_ai_panel_post_render_resize()
    harness._ensure_ai_panel_post_render_resize()

    assert harness._ai_panel_post_render_tick_id == 71
    assert harness._ai_panel_post_render_frames == 2
    assert len(harness.win.callbacks) == 1
    assert harness._on_ai_panel_post_render_tick(harness.win, None)
    assert not harness._on_ai_panel_post_render_tick(harness.win, None)
    assert harness._ai_panel_post_render_tick_id is None
    assert harness._ai_panel_post_render_frames == 0
    assert harness.height_updates == 1
    assert harness.scroller.resize_count == 1
    assert harness.scroller.child.resize_count == 1


def test_pending_summary_restore_ignores_transient_scroll_fraction() -> None:
    adjustment = FakeAdjustment(upper=400.0, page_size=100.0, value=99.0)
    harness = SummaryScrollHarness(adjustment, 0.09)

    harness._on_summary_scroll(adjustment)
    harness._capture_summary_scroll_position()

    assert harness.state.summary_scroll_fraction == 0.09
    assert harness.progress_updates == 1


def test_pending_summary_restore_reapplies_fraction_until_geometry_is_stable() -> None:
    adjustment = FakeAdjustment(upper=1000.0, page_size=100.0, value=300.0)
    harness = SummaryScrollHarness(adjustment, 0.09)

    assert harness._apply_pending_summary_scroll_restore()
    assert adjustment.value == 81.0

    adjustment.upper = 400.0
    adjustment.value = 99.0
    harness._on_summary_scroll(adjustment)
    assert harness.state.summary_scroll_fraction == 0.09

    assert harness._apply_pending_summary_scroll_restore()
    assert adjustment.value == 27.0
    assert not harness._apply_pending_summary_scroll_restore()

    assert adjustment.value == 27.0
    assert harness.state.summary_scroll_fraction == 0.09
    assert harness._summary_pending_restore_fraction is None
