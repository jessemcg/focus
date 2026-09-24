"""Content-driven rendering: mapping and theme changes must not rebuild text."""

from __future__ import annotations

from types import SimpleNamespace

from focus.app import Focus
from focus.core import AI_VIEW_AGENT_QA, AiOutputView


class FakeTag:
    def __init__(self) -> None:
        self.props: dict[str, object] = {}

    def set_property(self, name: str, value: object) -> None:
        self.props[name] = value


class MapHarness:
    _on_ai_output_view_mapped = Focus._on_ai_output_view_mapped
    _on_summary_view_mapped = Focus._on_summary_view_mapped

    def __init__(self) -> None:
        state = AiOutputView(raw="Rendered answer")
        self._ai_outputs = {AI_VIEW_AGENT_QA: state}
        self._summary_loaded_path = None
        self.rebuilds = 0

    def _restore_agent_answer_position_if_current(self) -> None:
        return

    def _restore_summary_position(self, _path: object) -> None:
        return

    def _apply_ai_output_links(self, _text: str, _state: object) -> None:
        self.rebuilds += 1

    def _apply_summary_links(self, _text: str) -> None:
        self.rebuilds += 1


class RecolorHarness:
    _refresh_ai_quote_colors = Focus._refresh_ai_quote_colors
    _recolor_link_tags = staticmethod(Focus._recolor_link_tags)

    def __init__(self) -> None:
        self._summary_view = SimpleNamespace()
        self._summary_buffer = SimpleNamespace()
        self._summary_link_tags: list[FakeTag] = []
        self._summary_link_tag_lookup: dict[FakeTag, tuple[str, str]] = {}
        self._ai_outputs: dict[str, AiOutputView] = {}
        self.emphasis_updates = 0
        self.legacy_rebuilds = 0

    def _resolve_ai_quote_color(self, _view: object):  # type: ignore[no-untyped-def]
        return SimpleNamespace(red=0.2, green=0.3, blue=0.4, alpha=1.0)

    def _ensure_summary_emphasis_tag(self, _buffer: object) -> None:
        self.emphasis_updates += 1

    def _apply_summary_links(self, _text: str) -> None:
        self.legacy_rebuilds += 1


def test_mapping_agent_output_does_not_rebuild_content() -> None:
    harness = MapHarness()
    harness._on_ai_output_view_mapped(None, AI_VIEW_AGENT_QA)
    assert harness.rebuilds == 0


def test_mapping_summary_does_not_rebuild_content() -> None:
    harness = MapHarness()
    harness._on_summary_view_mapped(None)
    assert harness.rebuilds == 0


def test_theme_recolor_updates_tags_in_place() -> None:
    harness = RecolorHarness()
    phrase_tag = FakeTag()
    page_tag = FakeTag()
    harness._summary_link_tags = [phrase_tag, page_tag]
    harness._summary_link_tag_lookup = {phrase_tag: ("phrase", "q"), page_tag: ("page", "0004")}

    harness._refresh_ai_quote_colors()

    assert harness.legacy_rebuilds == 0
    assert harness.emphasis_updates == 1
    assert phrase_tag.props["foreground-rgba"].red == 0.2
    # Page links stay brighter than phrase links.
    assert page_tag.props["foreground-rgba"].red > 0.2


def test_theme_recolor_skips_when_no_link_tags() -> None:
    harness = RecolorHarness()
    harness._refresh_ai_quote_colors()
    assert harness.legacy_rebuilds == 0
