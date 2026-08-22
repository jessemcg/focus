from __future__ import annotations

import json
import os

from focus.agent_answer import (
    create_focus_run_id,
    focus_answer_artifact_path,
    focus_answer_status_message,
    lint_focus_answer,
    read_focus_answer_artifact,
    remove_focus_answer_artifact,
)


def _artifact(run_id: str, markdown: str = "Useful answer.", **changes: object) -> dict:
    payload = {
        "schema_version": 1,
        "run_id": run_id,
        "revision": 1,
        "status": "complete",
        "capture": "submit_tool",
        "answer_kind": "answered",
        "markdown": markdown,
        "warnings": [],
        "diagnostics": {
            "provider": "fireworks",
            "model": "accounts/fireworks/models/deepseek-v4-pro-0813",
            "thinking": "low",
            "stop_reason": "toolUse",
            "assistant_turns": 7,
            "tool_calls": 9,
            "searches": 2,
            "pages_read": 6,
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
    payload.update(changes)
    return payload


def _write_artifact(path, payload: object, mode: int = 0o600) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")
    path.chmod(mode)


def test_lint_diagnostics_never_mutate_formatting_imperfect_markdown() -> None:
    markdown = (
        "**Planning checklist:** preserve this best-effort answer.\n\n"
        "The case overview says \"this quotation contains far more than five words\". "
        "See CT 12."
    )

    warnings = lint_focus_answer(markdown)

    assert {"long_quote", "bold_markup", "record_metadata"} <= set(warnings)
    assert markdown == (
        "**Planning checklist:** preserve this best-effort answer.\n\n"
        "The case overview says \"this quotation contains far more than five words\". "
        "See CT 12."
    )


def test_valid_submit_artifact_is_accepted_unchanged_with_nonblocking_warning(tmp_path) -> None:
    run_id = create_focus_run_id()
    path = focus_answer_artifact_path(run_id, tmp_path)
    markdown = 'The answer rests on "a quotation longer than five total words".'
    _write_artifact(path, _artifact(run_id, markdown))

    result = read_focus_answer_artifact(path, run_id=run_id)

    assert result.error == ""
    assert result.artifact is not None
    assert result.artifact.markdown == markdown
    assert "long_quote" in result.artifact.warnings


def test_length_and_provider_interruption_artifacts_preserve_usable_text(tmp_path) -> None:
    for stop_reason in ("length", "error", "aborted"):
        run_id = create_focus_run_id()
        path = focus_answer_artifact_path(run_id, tmp_path)
        payload = _artifact(
            run_id,
            "Available partial answer.",
            status="partial",
            capture="assistant_fallback",
        )
        payload["diagnostics"]["stop_reason"] = stop_reason
        _write_artifact(path, payload)

        result = read_focus_answer_artifact(path, run_id=run_id)

        assert result.artifact is not None
        assert result.artifact.markdown == "Available partial answer."
        assert result.artifact.status == "partial"
        expected = (
            "Partial answer—output limit reached."
            if stop_reason == "length"
            else f"Partial answer—Agent {stop_reason}."
        )
        assert focus_answer_status_message(result.artifact) == expected


def test_plain_assistant_fallback_gets_subdued_best_effort_status(tmp_path) -> None:
    run_id = create_focus_run_id()
    path = focus_answer_artifact_path(run_id, tmp_path)
    payload = _artifact(run_id, "Plain final answer.", capture="assistant_fallback")
    payload["diagnostics"]["stop_reason"] = "stop"
    _write_artifact(path, payload)

    result = read_focus_answer_artifact(path, run_id=run_id)

    assert result.artifact is not None
    assert focus_answer_status_message(result.artifact) == "Best-effort answer ready."


def test_provider_error_without_text_has_clear_failure_status(tmp_path) -> None:
    run_id = create_focus_run_id()
    path = focus_answer_artifact_path(run_id, tmp_path)
    payload = _artifact(
        run_id,
        "",
        status="partial",
        capture="assistant_fallback",
        answer_kind="insufficient_text",
    )
    payload["diagnostics"]["stop_reason"] = "error"
    _write_artifact(path, payload)

    result = read_focus_answer_artifact(path, run_id=run_id)

    assert result.artifact is not None
    assert focus_answer_status_message(result.artifact) == (
        "Provider/session failure: no usable answer text."
    )


def test_tool_use_narration_cannot_be_an_assistant_fallback(tmp_path) -> None:
    run_id = create_focus_run_id()
    path = focus_answer_artifact_path(run_id, tmp_path)
    payload = _artifact(run_id, "Interim narration", capture="assistant_fallback")
    payload["diagnostics"]["stop_reason"] = "toolUse"
    _write_artifact(path, payload)

    result = read_focus_answer_artifact(path, run_id=run_id)

    assert result.artifact is None
    assert result.error == "invalid_capture_stop_reason"


def test_artifact_rejects_wrong_run_stale_revision_and_unsupported_modes(tmp_path) -> None:
    run_id = create_focus_run_id()
    path = focus_answer_artifact_path(run_id, tmp_path)
    _write_artifact(path, _artifact("z" * 24))
    assert read_focus_answer_artifact(path, run_id=run_id).error == "wrong_run_id"

    _write_artifact(path, _artifact(run_id))
    assert read_focus_answer_artifact(path, run_id=run_id, last_revision=1).error == "stale_revision"

    _write_artifact(path, _artifact(run_id, status="pending"))
    assert read_focus_answer_artifact(path, run_id=run_id).error == "invalid_status"

    _write_artifact(path, _artifact(run_id, capture="session_parser"))
    assert read_focus_answer_artifact(path, run_id=run_id).error == "invalid_capture"


def test_artifact_rejects_malformed_insecure_and_duplicate_revisions(tmp_path) -> None:
    run_id = create_focus_run_id()
    path = focus_answer_artifact_path(run_id, tmp_path)
    path.write_text("{not-json", encoding="utf-8")
    path.chmod(0o600)
    assert read_focus_answer_artifact(path, run_id=run_id).error == "malformed"

    _write_artifact(path, _artifact(run_id), mode=0o644)
    assert read_focus_answer_artifact(path, run_id=run_id).error == "insecure_artifact"

    _write_artifact(path, _artifact(run_id))
    first = read_focus_answer_artifact(path, run_id=run_id)
    assert first.artifact is not None
    duplicate = read_focus_answer_artifact(
        path,
        run_id=run_id,
        last_revision=first.artifact.revision,
    )
    assert duplicate.error == "stale_revision"


def test_artifact_cleanup_is_idempotent(tmp_path) -> None:
    run_id = create_focus_run_id()
    path = focus_answer_artifact_path(run_id, tmp_path)
    _write_artifact(path, _artifact(run_id))

    remove_focus_answer_artifact(path)
    remove_focus_answer_artifact(path)

    assert not path.exists()
