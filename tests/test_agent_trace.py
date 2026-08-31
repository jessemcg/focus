from __future__ import annotations

import json
import os
from pathlib import Path

import pytest
from unittest.mock import patch

from focus.agent_trace import (
    TraceSnapshotError,
    find_latest_pi_session_log_for_cwd,
    focus_preserved_session_path,
    pi_session_log_matches_cwd,
    reasoning_trace_path,
    snapshot_pi_session_jsonl,
    trace_clipboard_text,
)


def _write_session(
    workspace: Path,
    records: list[dict],
    partial: bytes = b"",
) -> Path:
    log = workspace / "pi-sessions" / "session.jsonl"
    log.parent.mkdir(parents=True, exist_ok=True)
    payload = b"".join(
        (json.dumps(record) + "\n").encode("utf-8") for record in records
    )
    log.write_bytes(payload + partial)
    return log


def test_reasoning_trace_path_uses_xdg_state_home() -> None:
    assert reasoning_trace_path({"XDG_STATE_HOME": "/xdg-state"}) == Path(
        "/xdg-state/focus/traces/latest_trace.jsonl"
    )


def test_reasoning_trace_path_falls_back_to_local_state() -> None:
    assert reasoning_trace_path({}) == (
        Path.home() / ".local/state/focus/traces/latest_trace.jsonl"
    )


def test_reasoning_trace_path_override_expands_home_and_requires_absolute(
    tmp_path: Path,
) -> None:
    with patch.dict(
        os.environ,
        {"HOME": str(tmp_path), "FOCUS_TRACE_PATH": "~/traces/x.jsonl"},
    ):
        assert reasoning_trace_path() == tmp_path / "traces/x.jsonl"

    with pytest.raises(ValueError):
        reasoning_trace_path({"FOCUS_TRACE_PATH": "traces/x.jsonl"})
    with pytest.raises(ValueError):
        reasoning_trace_path({"XDG_STATE_HOME": "relative/state"})


def test_focus_preserved_session_path_is_run_scoped(tmp_path: Path) -> None:
    run_id = "abcdefghijklmnopqrstuvwx"
    assert focus_preserved_session_path(run_id, tmp_path) == (
        tmp_path / f"{run_id}.jsonl"
    )
    with pytest.raises(ValueError):
        focus_preserved_session_path("short", tmp_path)


def test_find_latest_pi_session_log_for_cwd_matches_header(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    matching = _write_session(workspace, [{"type": "session", "cwd": str(workspace)}])

    other = tmp_path / "other-workspace"
    _write_session(other, [{"type": "session", "cwd": "/somewhere-else"}])

    assert find_latest_pi_session_log_for_cwd(
        workspace / "pi-sessions", workspace
    ) == matching
    assert pi_session_log_matches_cwd(matching, workspace)
    assert not pi_session_log_matches_cwd(matching, other)
    assert find_latest_pi_session_log_for_cwd(tmp_path / "missing", workspace) is None


def test_snapshot_copies_complete_records_byte_for_byte(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    source = _write_session(
        workspace,
        [
            {"type": "session", "cwd": str(workspace)},
            {"type": "message", "message": {"role": "assistant"}},
            {"type": "error", "detail": "boom"},
        ],
    )
    payload = source.read_bytes()
    destination = tmp_path / "state/focus/traces/latest_trace.jsonl"

    assert snapshot_pi_session_jsonl(source, destination) == destination
    assert destination.read_bytes() == payload
    first = json.loads(destination.read_text(encoding="utf-8").splitlines()[0])
    assert first["type"] == "session"


def test_snapshot_omits_incomplete_trailing_record(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    source = _write_session(
        workspace,
        [
            {"type": "session", "cwd": str(workspace)},
            {"type": "message", "done": True},
        ],
        partial=b'{"type":"message","partial":',
    )
    destination = tmp_path / "traces/latest_trace.jsonl"

    snapshot_pi_session_jsonl(source, destination)

    lines = destination.read_text(encoding="utf-8").splitlines()
    assert len(lines) == 2
    assert json.loads(lines[1]) == {"type": "message", "done": True}


def test_snapshot_keeps_complete_trailing_record_without_newline(
    tmp_path: Path,
) -> None:
    workspace = tmp_path / "workspace"
    source = _write_session(
        workspace,
        [
            {"type": "session", "cwd": str(workspace)},
            {"type": "message", "done": True},
        ],
        partial=b'{"type":"message","complete":true}',
    )
    destination = tmp_path / "traces/latest_trace.jsonl"

    snapshot_pi_session_jsonl(source, destination)

    lines = destination.read_text(encoding="utf-8").splitlines()
    assert len(lines) == 3
    assert json.loads(lines[2]) == {"type": "message", "complete": True}


def test_snapshot_rejects_invalid_sources(tmp_path: Path) -> None:
    destination = tmp_path / "traces/latest_trace.jsonl"

    malformed = tmp_path / "malformed.jsonl"
    malformed.write_text(
        json.dumps({"type": "session", "cwd": "/workspace"}) + "\nnot json at all\n",
        encoding="utf-8",
    )
    with pytest.raises(TraceSnapshotError):
        snapshot_pi_session_jsonl(malformed, destination)

    no_header = tmp_path / "no_header.jsonl"
    no_header.write_text(
        json.dumps({"type": "message", "message": {}}) + "\n",
        encoding="utf-8",
    )
    with pytest.raises(TraceSnapshotError):
        snapshot_pi_session_jsonl(no_header, destination)

    empty = tmp_path / "empty.jsonl"
    empty.write_bytes(b"")
    with pytest.raises(TraceSnapshotError):
        snapshot_pi_session_jsonl(empty, destination)

    with pytest.raises(TraceSnapshotError):
        snapshot_pi_session_jsonl(tmp_path / "missing.jsonl", destination)

    assert not destination.exists()


def test_snapshot_preserves_previous_destination_on_failure(tmp_path: Path) -> None:
    destination = tmp_path / "traces/latest_trace.jsonl"
    destination.parent.mkdir(parents=True)
    previous = b'{"type":"session","cwd":"/old"}\n'
    destination.write_bytes(previous)
    source = tmp_path / "malformed.jsonl"
    source.write_text(
        json.dumps({"type": "session", "cwd": "/workspace"}) + "\nnot json\n",
        encoding="utf-8",
    )

    with pytest.raises(TraceSnapshotError):
        snapshot_pi_session_jsonl(source, destination)

    assert destination.read_bytes() == previous
    assert [entry.name for entry in destination.parent.iterdir()] == [
        "latest_trace.jsonl"
    ]


def test_snapshot_replaces_atomically_with_private_permissions(
    tmp_path: Path,
) -> None:
    workspace = tmp_path / "workspace"
    source = _write_session(workspace, [{"type": "session", "cwd": "/one"}])
    destination = tmp_path / "state/focus/traces/latest_trace.jsonl"

    snapshot_pi_session_jsonl(source, destination)
    assert oct(destination.stat().st_mode & 0o777) == "0o600"
    traces_dir = destination.parent
    assert oct(traces_dir.stat().st_mode & 0o777) == "0o700"
    assert oct(traces_dir.parent.stat().st_mode & 0o777) == "0o700"

    _write_session(workspace, [{"type": "session", "cwd": "/two"}])
    inode_before = destination.stat().st_ino
    snapshot_pi_session_jsonl(source, destination)

    assert destination.read_bytes() == (
        json.dumps({"type": "session", "cwd": "/two"}) + "\n"
    ).encode("utf-8")
    assert destination.stat().st_ino != inode_before
    assert sorted(entry.name for entry in traces_dir.iterdir()) == [
        "latest_trace.jsonl"
    ]


def test_trace_clipboard_text_is_path_only(tmp_path: Path) -> None:
    path = tmp_path / "traces/latest_trace.jsonl"
    text = trace_clipboard_text(path)

    assert text == str(path)
    assert "\n" not in text
    assert "review" not in text.casefold()
    assert "diagnostic" not in text.casefold()
