"""Presentation checks for the Saved Answers split button."""

from __future__ import annotations

from dataclasses import replace

import gi
import pytest

gi.require_version("Adw", "1")
gi.require_version("Gtk", "4.0")

from gi.repository import Adw, Gtk  # noqa: E402

# Importing focus.app first loads the remaining GI version requirements.
from focus.app import Focus  # noqa: E402,F401
from focus.ui.saved_answers import SavedAnswersPopover  # noqa: E402


def _build(on_primary=None) -> SavedAnswersPopover:
    return SavedAnswersPopover(
        on_select=lambda _answer_id: None,
        on_delete=lambda _answer_id: None,
        on_primary=on_primary,
    )


def test_saved_answers_is_a_labeled_split_button() -> None:
    popover = _build()

    assert isinstance(popover.button, Adw.SplitButton)
    assert popover.button.get_tooltip_text()
    assert popover.button.get_dropdown_tooltip()
    assert popover.button.get_popover() is popover.popover
    child = popover.button.get_child()
    assert isinstance(child, Adw.ButtonContent)
    assert child.get_label() == "Saved Answers"


def test_primary_area_invokes_the_primary_callback() -> None:
    calls: list[str] = []
    popover = _build(on_primary=lambda: calls.append("primary"))

    popover.button.emit("clicked")

    assert calls == ["primary"]


def test_arrow_opens_the_library_popover() -> None:
    popover = _build(on_primary=lambda: None)

    # The dropdown part is the internal MenuButton child of the split button.
    dropdown = popover.button.get_last_child()
    assert isinstance(dropdown, Gtk.MenuButton)
    assert dropdown.get_popover() is popover.popover
    assert dropdown.get_tooltip_text() == popover.button.get_dropdown_tooltip()


@pytest.mark.parametrize("version", [1, 2, 3])
def test_popover_rows_retain_captured_provenance_and_quality(tmp_path, version):
    from focus.research_context import research_context_bytes
    from focus.research_runtime import ResearchPin
    from test_research_runtime import case, historical_context
    from test_saved_answers import _answer

    context = None
    if version == 2:
        context = research_context_bytes(historical_context())
    elif version == 3:
        context = research_context_bytes(ResearchPin.capture(case(tmp_path / "case")).metadata())
    answer = replace(_answer(), schema_version=version, research_context=context,
                     status="partial", stop_reason="length")
    row = _build()._build_row(answer)
    expected = {1: "Historical research: unrecorded",
                2: "Historical research profile:",
                3: "Focus method: focus-record-qa · v1"}[version]
    assert expected in row.get_tooltip_text()
    assert "RecordPrep preparation:" in row.get_tooltip_text()
    assert "Partial" in row.get_subtitle()
    assert "Saved " in row.get_subtitle()
    assert row.answer_id == answer.answer_id
    assert answer.research_context == context
