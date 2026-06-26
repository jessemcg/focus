import json
import os

from focus.core import (
    codex_session_log_matches_cwd,
    extract_latest_codex_final_answer_from_jsonl,
    find_latest_codex_session_log_for_cwd,
)


def _write_jsonl(path, rows) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            if isinstance(row, str):
                handle.write(row + "\n")
            else:
                handle.write(json.dumps(row) + "\n")


def test_extract_latest_codex_final_answer_ignores_non_final_messages(tmp_path) -> None:
    log_path = tmp_path / "rollout.jsonl"
    _write_jsonl(
        log_path,
        [
            {
                "type": "response_item",
                "payload": {
                    "type": "message",
                    "role": "assistant",
                    "phase": "commentary",
                    "content": [{"type": "output_text", "text": "working"}],
                },
            },
            "{not valid json",
            {
                "type": "response_item",
                "payload": {
                    "type": "message",
                    "role": "assistant",
                    "phase": "final_answer",
                    "content": [{"type": "output_text", "text": "first answer"}],
                },
            },
            {
                "type": "response_item",
                "payload": {
                    "type": "message",
                    "role": "assistant",
                    "phase": "final_answer",
                    "content": [{"type": "output_text", "text": "latest answer"}],
                },
            },
        ],
    )

    assert extract_latest_codex_final_answer_from_jsonl(log_path) == "latest answer"


def test_extract_latest_codex_final_answer_uses_task_complete_message(tmp_path) -> None:
    log_path = tmp_path / "rollout.jsonl"
    _write_jsonl(
        log_path,
        [
            {
                "type": "response_item",
                "payload": {
                    "type": "message",
                    "role": "assistant",
                    "phase": None,
                    "content": [{"type": "output_text", "text": "I'll search first."}],
                },
            },
            {
                "type": "event_msg",
                "payload": {
                    "type": "task_complete",
                    "last_agent_message": "Mother moved to **Santa Maria, California**. (CT 250-252.)",
                },
            },
        ],
    )

    assert (
        extract_latest_codex_final_answer_from_jsonl(log_path)
        == "Mother moved to **Santa Maria, California**. (CT 250-252.)"
    )


def test_codex_session_log_matches_cwd_from_session_meta(tmp_path) -> None:
    workspace = tmp_path / "workspace"
    log_path = tmp_path / "rollout.jsonl"
    _write_jsonl(
        log_path,
        [
            "{partial",
            {
                "type": "session_meta",
                "payload": {"cwd": str(workspace)},
            },
        ],
    )

    assert codex_session_log_matches_cwd(log_path, workspace)
    assert not codex_session_log_matches_cwd(log_path, tmp_path / "other")


def test_find_latest_codex_session_log_for_cwd(tmp_path) -> None:
    sessions_root = tmp_path / "codex" / "sessions"
    workspace = tmp_path / "agent-workspace"
    old_log = sessions_root / "2026" / "06" / "25" / "rollout-old.jsonl"
    new_log = sessions_root / "2026" / "06" / "25" / "rollout-new.jsonl"
    other_log = sessions_root / "2026" / "06" / "25" / "rollout-other.jsonl"
    _write_jsonl(old_log, [{"type": "session_meta", "payload": {"cwd": str(workspace)}}])
    _write_jsonl(new_log, [{"type": "session_meta", "payload": {"cwd": str(workspace)}}])
    _write_jsonl(other_log, [{"type": "session_meta", "payload": {"cwd": str(tmp_path / "other")}}])
    os.utime(old_log, (1, 1))
    os.utime(new_log, (3, 3))
    os.utime(other_log, (2, 2))

    assert find_latest_codex_session_log_for_cwd(sessions_root, workspace) == new_log
