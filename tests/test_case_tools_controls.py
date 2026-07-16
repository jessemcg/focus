from focus.app import Focus
from focus.core import (
    AGENT_SUBVIEW_ANSWER,
    AGENT_SUBVIEW_SESSION,
    AI_VIEW_AGENT_QA,
    AI_VIEW_EXTRACT,
    AI_VIEW_FILE,
    AI_VIEW_QA,
    AI_VIEW_RAG_AUDIT,
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


class FakeAction:
    def __init__(self) -> None:
        self.enabled = False

    def set_enabled(self, enabled: bool) -> None:
        self.enabled = enabled


class FakeVisibility:
    def __init__(self, visible: bool = False) -> None:
        self.visible = visible

    def get_visible(self) -> bool:
        return self.visible


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
            AI_VIEW_QA: FakeButton(),
            AI_VIEW_AGENT_QA: FakeButton(),
        }
        self._more_case_tools_button = FakeButton()
        self._ai_view_toggle_guard = False


class SummaryActionHarness:
    _refresh_summary_actions_state = Focus._refresh_summary_actions_state

    def __init__(self) -> None:
        self._summary_loaded_path: object | None = None
        self._summary_raw = ""
        self._has_bookmark = False
        self._summary_bookmark_action_button = FakeButton()
        self._summary_return_bookmark_action_button = FakeButton()
        self._summary_print_action = FakeAction()

    def _summary_has_saved_bookmark(self) -> bool:
        return self._has_bookmark


class BodyVisibilityHarness:
    _active_ai_body_has_content = Focus._active_ai_body_has_content

    def __init__(self, view_name: str) -> None:
        self._ai_view_stack = FakeViewStack(view_name)
        self._ai_active_view = view_name
        self._agent_subview_name = AGENT_SUBVIEW_ANSWER
        self._rag_filter_chip = FakeVisibility()
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


def test_more_button_is_active_only_for_summary_views() -> None:
    harness = ToggleHarness()

    harness._sync_ai_view_toggles(AI_VIEW_SUMMARIZE)
    assert "focus-ai-view-active" in harness._more_case_tools_button.css_classes
    assert not harness._ai_view_buttons[AI_VIEW_QA].active
    assert not harness._ai_view_buttons[AI_VIEW_AGENT_QA].active

    harness._sync_ai_view_toggles(AI_VIEW_FILE)
    assert "focus-ai-view-active" in harness._more_case_tools_button.css_classes

    harness._sync_ai_view_toggles(AI_VIEW_RAG_AUDIT)
    assert "focus-ai-view-active" not in harness._more_case_tools_button.css_classes

    harness._sync_ai_view_toggles(AI_VIEW_AGENT_QA)
    assert harness._ai_view_buttons[AI_VIEW_AGENT_QA].active
    assert "focus-ai-view-active" not in harness._more_case_tools_button.css_classes


def test_print_summary_action_tracks_printable_summary_state() -> None:
    harness = SummaryActionHarness()

    harness._refresh_summary_actions_state()
    assert not harness._summary_print_action.enabled

    harness._summary_loaded_path = object()
    harness._summary_raw = "Summary text"
    harness._has_bookmark = True
    harness._refresh_summary_actions_state()

    assert harness._summary_bookmark_action_button.sensitive
    assert harness._summary_return_bookmark_action_button.sensitive
    assert harness._summary_print_action.enabled


def test_empty_header_only_views_do_not_reserve_body_space() -> None:
    for view_name in (AI_VIEW_QA, AI_VIEW_AGENT_QA, AI_VIEW_SUMMARIZE, AI_VIEW_FILE):
        harness = BodyVisibilityHarness(view_name)

        assert not harness._active_ai_body_has_content()


def test_views_with_body_controls_remain_expanded() -> None:
    for view_name in (AI_VIEW_EXTRACT, AI_VIEW_RAG_AUDIT):
        harness = BodyVisibilityHarness(view_name)

        assert harness._active_ai_body_has_content()


def test_dynamic_case_tool_content_expands_the_body() -> None:
    output_harness = BodyVisibilityHarness(AI_VIEW_SUMMARIZE)
    output_harness.has_output = True
    assert output_harness._active_ai_body_has_content()

    filter_harness = BodyVisibilityHarness(AI_VIEW_QA)
    filter_harness._rag_filter_chip.visible = True
    assert filter_harness._active_ai_body_has_content()

    agent_harness = BodyVisibilityHarness(AI_VIEW_AGENT_QA)
    agent_harness._agent_subview_name = AGENT_SUBVIEW_SESSION
    agent_harness.has_agent_session = True
    assert agent_harness._active_ai_body_has_content()


def test_scroller_bounds_clear_the_minimum_before_changing_the_maximum() -> None:
    scroller = FakeScrollerBounds()

    Focus._set_scroller_content_height_bounds(scroller, 36, 207)

    assert scroller.calls == [("min", -1), ("max", 207), ("min", 36)]
