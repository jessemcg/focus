from __future__ import annotations

from datetime import datetime

from focus.answer_presentation import (
    answer_quality_label,
    format_saved_at,
)


def test_format_saved_at_uses_local_time_and_human_readable_shape() -> None:
    # A UTC instant formatted in local time keeps a readable, month-name date.
    text = format_saved_at("2026-09-24T16:05:00+00:00")
    assert "2026" in text
    assert "Sep" in text
    assert ":" in text
    # The local-time conversion matches the standard library's conversion.
    expected = datetime.fromisoformat("2026-09-24T16:05:00+00:00").astimezone()
    assert str(expected.day) in text
    assert expected.strftime("%b") in text


def test_format_saved_at_degrades_safely() -> None:
    assert format_saved_at("") == ""
    assert format_saved_at(None) == ""
    assert format_saved_at("not a date") == "not a date"


def test_answer_quality_label_matches_partial_and_best_effort() -> None:
    assert answer_quality_label(status="complete", stop_reason="toolUse", capture="submit_tool") == ""
    assert answer_quality_label(status="partial", stop_reason="toolUse", capture="submit_tool") == "Partial"
    assert answer_quality_label(status="complete", stop_reason="length", capture="submit_tool") == "Partial"
    assert answer_quality_label(status="complete", stop_reason="aborted", capture="submit_tool") == "Partial"
    assert (
        answer_quality_label(status="complete", stop_reason="toolUse", capture="assistant_fallback")
        == "Best-effort"
    )
