from __future__ import annotations

import json
import os
import stat
from pathlib import Path

from focus.saved_answers import (
    SAVED_ANSWERS_SCHEMA_VERSION,
    AgentAnswerSnapshot,
    SavedAnswer,
    delete_saved_answer,
    list_saved_answers,
    load_saved_answer,
    new_answer_id,
    save_saved_answer,
    saved_answers_dir,
)


def _answer(
    answer_id: str | None = None,
    *,
    markdown: str = 'The record says "short quote" and [see page](page: 2).\n',
    title: str = "A Title",
    subtitle: str = "A subtitle",
    status: str = "complete",
    stop_reason: str = "toolUse",
    capture: str = "submit_tool",
    answer_kind: str = "answered",
    question: str | None = "Why?",
    saved_at: str = "2026-09-23T12:00:00+00:00",
) -> SavedAnswer:
    return SavedAnswer(
        schema_version=SAVED_ANSWERS_SCHEMA_VERSION,
        answer_id=answer_id or new_answer_id(),
        saved_at=saved_at,
        title=title,
        subtitle=subtitle,
        markdown=markdown,
        status=status,
        capture=capture,
        answer_kind=answer_kind,
        stop_reason=stop_reason,
        question=question,
    )


def test_roundtrip_unicode_and_link_syntax(tmp_path: Path) -> None:
    markdown = "Curly “quotes”, em—dash, ellipsis…, and [page](page: 12).\n"
    answer = _answer(markdown=markdown)
    result = save_saved_answer(tmp_path, answer)
    assert result.error == ""
    assert result.answer is not None

    loaded = load_saved_answer(tmp_path, answer.answer_id)
    assert loaded.error == ""
    assert loaded.answer is not None
    assert loaded.answer.markdown == markdown
    assert loaded.answer.to_payload() == answer.to_payload()

    store = saved_answers_dir(tmp_path)
    file_stat = (store / f"{answer.answer_id}.json").stat()
    assert stat.S_IMODE(file_stat.st_mode) == 0o600
    assert stat.S_IMODE(store.stat().st_mode) == 0o700

    deletion = delete_saved_answer(tmp_path, answer.answer_id)
    assert deletion.error == ""
    assert not (store / f"{answer.answer_id}.json").exists()
    assert list_saved_answers(tmp_path).answers == ()


def test_repeat_save_is_idempotent_and_conflict_is_refused(tmp_path: Path) -> None:
    answer = _answer(markdown="First snapshot.\n")
    assert save_saved_answer(tmp_path, answer).error == ""
    mtime_before = (saved_answers_dir(tmp_path) / f"{answer.answer_id}.json").stat().st_mtime_ns

    again = save_saved_answer(tmp_path, answer)
    assert again.error == ""
    assert again.answer is not None
    mtime_after = (saved_answers_dir(tmp_path) / f"{answer.answer_id}.json").stat().st_mtime_ns
    assert mtime_before == mtime_after  # no rewrite

    conflicting = _answer(answer.answer_id, markdown="Different content.\n")
    conflict = save_saved_answer(tmp_path, conflicting)
    assert conflict.error == "conflict"
    assert load_saved_answer(tmp_path, answer.answer_id).answer.markdown == "First snapshot.\n"


def test_newer_revisions_remain_separate(tmp_path: Path) -> None:
    first = _answer(markdown="Revision one.\n", saved_at="2026-09-23T12:00:00+00:00")
    second = _answer(markdown="Revision two.\n", saved_at="2026-09-23T12:05:00+00:00")
    save_saved_answer(tmp_path, first)
    save_saved_answer(tmp_path, second)
    listing = list_saved_answers(tmp_path)
    assert [item.markdown for item in listing.answers] == [
        "Revision two.\n",
        "Revision one.\n",
    ]


def test_browsing_absent_library_creates_nothing(tmp_path: Path) -> None:
    listing = list_saved_answers(tmp_path)
    assert listing.answers == ()
    assert not (tmp_path / ".focus").exists()
    assert load_saved_answer(tmp_path, new_answer_id()).error == "missing"
    assert delete_saved_answer(tmp_path, new_answer_id()).error == "missing"


def test_malformed_and_unsupported_files_reported_but_healthy_loads(tmp_path: Path) -> None:
    store = saved_answers_dir(tmp_path)
    store.mkdir(parents=True, mode=0o700)

    good = _answer(markdown="Healthy answer.\n")
    save_saved_answer(tmp_path, good)

    bad_id = new_answer_id()
    (store / f"{bad_id}.json").write_text("{not json", encoding="utf-8")
    unsupported_id = new_answer_id()
    (store / f"{unsupported_id}.json").write_text(
        json.dumps({"schema_version": 99, "answer_id": unsupported_id}), encoding="utf-8"
    )
    mismatch_id = new_answer_id()
    payload = _answer().to_payload()
    payload["answer_id"] = new_answer_id()
    (store / f"{mismatch_id}.json").write_text(json.dumps(payload), encoding="utf-8")
    (store / "notes.txt").write_text("not an answer", encoding="utf-8")

    listing = list_saved_answers(tmp_path)
    assert [item.answer_id for item in listing.answers] == [good.answer_id]
    codes = {issue.code for issue in listing.issues}
    assert {"malformed", "unsupported_schema", "id_filename_mismatch", "unexpected_entry"} <= codes
    # Unfamiliar files are left untouched.
    assert (store / f"{bad_id}.json").read_text(encoding="utf-8") == "{not json"
    assert (store / "notes.txt").exists()


def test_symlink_hardlink_directory_and_fifo_entries_are_rejected(tmp_path: Path) -> None:
    store = saved_answers_dir(tmp_path)
    store.mkdir(parents=True, mode=0o700)

    target = tmp_path / "outside.json"
    target.write_text(json.dumps(_answer().to_payload()), encoding="utf-8")
    link_id = new_answer_id()
    os.symlink(target, store / f"{link_id}.json")

    hard_id = new_answer_id()
    os.link(target, store / f"{hard_id}.json")

    dir_id = new_answer_id()
    (store / f"{dir_id}.json").mkdir()

    fifo_id = new_answer_id()
    os.mkfifo(store / f"{fifo_id}.json")

    listing = list_saved_answers(tmp_path)
    assert listing.answers == ()
    codes = sorted({issue.code for issue in listing.issues})
    assert {"symlink", "hardlink", "unsafe_entry"} <= set(codes)
    assert target.exists()


def test_broad_permissions_are_warned_but_loaded_without_chmod(tmp_path: Path) -> None:
    answer = _answer(markdown="Synced privately.\n")
    save_saved_answer(tmp_path, answer)
    path = saved_answers_dir(tmp_path) / f"{answer.answer_id}.json"
    path.chmod(0o644)

    listing = list_saved_answers(tmp_path)
    assert [item.answer_id for item in listing.answers] == [answer.answer_id]
    assert any(issue.code == "broad_permissions" for issue in listing.issues)
    # Browsing must never rewrite or chmod synchronized files.
    assert stat.S_IMODE(path.stat().st_mode) == 0o644


def test_invalid_answer_ids_rejected(tmp_path: Path) -> None:
    for bad in ("../escape", "not-a-uuid", "", "a" * 31):
        assert load_saved_answer(tmp_path, bad).error == "invalid_answer_id"
        assert delete_saved_answer(tmp_path, bad).error == "invalid_answer_id"
    for bad in ("../escape", "not-a-uuid", "a" * 31):
        result = save_saved_answer(tmp_path, _answer(bad))
        assert result.error == "invalid_answer_id"


def test_two_cases_do_not_share_entries_and_move_preserves_library(tmp_path: Path) -> None:
    case_a = tmp_path / "A"
    case_b = tmp_path / "B"
    case_a.mkdir()
    case_b.mkdir()
    save_saved_answer(case_a, _answer(markdown="Only A.\n"))
    assert list_saved_answers(case_b).answers == ()

    moved = tmp_path / "A-moved"
    case_a.rename(moved)
    listing = list_saved_answers(moved)
    assert [item.markdown for item in listing.answers] == ["Only A.\n"]


def test_snapshot_roundtrip_preserves_partial_status() -> None:
    snapshot = AgentAnswerSnapshot(
        answer_id=new_answer_id(),
        markdown="Partial text.\n",
        title="Title",
        subtitle="Partial answer",
        status="partial",
        capture="assistant_fallback",
        answer_kind="insufficient_text",
        stop_reason="length",
        question=None,
    )
    assert snapshot.partial
    saved = snapshot.to_saved()
    restored = AgentAnswerSnapshot.from_saved(saved)
    assert restored.origin == "saved"
    assert restored.status == "partial"
    assert restored.stop_reason == "length"
    assert restored.markdown == snapshot.markdown
