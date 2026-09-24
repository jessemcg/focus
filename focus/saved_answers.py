"""Durable per-case Focus saved-answer library.

Saved answers live beside the active record bundle so they follow the case
through Dropbox::

    <record-layout-root>/.focus/saved-answers/<answer-uuid>.json

One self-contained JSON file per answer keeps the library rebuildable from
files alone (no shared index that can diverge during synchronization).  The
module is GTK-independent; every operation returns explicit typed results and
never raises for ordinary I/O or validation failures.  Listing is read-only and
creates no directories.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import json
import os
import re
import stat
import tempfile
import uuid
from pathlib import Path
from typing import Any

from .agent_answer import (
    ANSWER_ARTIFACT_STATUSES,
    ANSWER_CAPTURE_MODES,
    ANSWER_KINDS,
    ANSWER_STOP_REASONS,
)

SAVED_ANSWERS_SCHEMA_VERSION = 1
SAVED_ANSWERS_DIR_NAME = ".focus"
SAVED_ANSWERS_SUBDIR = "saved-answers"
ANSWER_ID_RE = re.compile(r"^[0-9a-f]{32}$")
_TEMP_PREFIX = ".tmp-"


@dataclass(frozen=True, slots=True)
class SavedAnswer:
    schema_version: int
    answer_id: str
    saved_at: str
    title: str
    subtitle: str
    markdown: str
    status: str
    capture: str
    answer_kind: str
    stop_reason: str
    question: str | None

    def to_payload(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "answer_id": self.answer_id,
            "saved_at": self.saved_at,
            "title": self.title,
            "subtitle": self.subtitle,
            "markdown": self.markdown,
            "status": self.status,
            "capture": self.capture,
            "answer_kind": self.answer_kind,
            "stop_reason": self.stop_reason,
            "question": self.question,
        }


@dataclass(frozen=True, slots=True)
class AgentAnswerSnapshot:
    """One immutable Agent answer, live or previously saved."""

    answer_id: str
    markdown: str
    title: str
    subtitle: str
    status: str
    capture: str
    answer_kind: str
    stop_reason: str
    question: str | None
    saved_at: str | None = None
    origin: str = "live"

    @property
    def partial(self) -> bool:
        return self.status == "partial" or self.stop_reason in {"length", "error", "aborted"}

    @classmethod
    def from_saved(cls, saved: SavedAnswer) -> "AgentAnswerSnapshot":
        return cls(
            answer_id=saved.answer_id,
            markdown=saved.markdown,
            title=saved.title,
            subtitle=saved.subtitle,
            status=saved.status,
            capture=saved.capture,
            answer_kind=saved.answer_kind,
            stop_reason=saved.stop_reason,
            question=saved.question,
            saved_at=saved.saved_at,
            origin="saved",
        )

    def to_saved(self, *, saved_at: str | None = None) -> SavedAnswer:
        return SavedAnswer(
            schema_version=SAVED_ANSWERS_SCHEMA_VERSION,
            answer_id=self.answer_id,
            saved_at=saved_at or self.saved_at or utc_now(),
            title=self.title,
            subtitle=self.subtitle,
            markdown=self.markdown,
            status=self.status,
            capture=self.capture,
            answer_kind=self.answer_kind,
            stop_reason=self.stop_reason,
            question=self.question,
        )


@dataclass(frozen=True, slots=True)
class SavedAnswerIssue:
    filename: str
    code: str
    message: str


@dataclass(frozen=True, slots=True)
class SavedAnswerListing:
    answers: tuple[SavedAnswer, ...] = ()
    issues: tuple[SavedAnswerIssue, ...] = ()


@dataclass(frozen=True, slots=True)
class SavedAnswerResult:
    answer: SavedAnswer | None
    error: str = ""


class _AnswerFileError(Exception):
    def __init__(self, code: str, message: str = "") -> None:
        super().__init__(message or code)
        self.code = code
        self.message = message or code


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def new_answer_id() -> str:
    return uuid.uuid4().hex


def saved_answers_dir(root: Path) -> Path:
    return Path(root) / SAVED_ANSWERS_DIR_NAME / SAVED_ANSWERS_SUBDIR


def _ensure_store_dir(root: Path) -> Path:
    base = Path(root) / SAVED_ANSWERS_DIR_NAME
    store = base / SAVED_ANSWERS_SUBDIR
    store.mkdir(mode=0o700, parents=True, exist_ok=True)
    for path in (base, store):
        path_stat = os.lstat(path)
        if stat.S_ISLNK(path_stat.st_mode) or not stat.S_ISDIR(path_stat.st_mode):
            raise OSError("saved-answer store is not a real directory")
        if path_stat.st_mode & 0o077:
            path.chmod(0o700)
    return store


def _validate_answer(answer: SavedAnswer) -> None:
    if answer.schema_version != SAVED_ANSWERS_SCHEMA_VERSION:
        raise _AnswerFileError("unsupported_schema")
    if not ANSWER_ID_RE.fullmatch(answer.answer_id):
        raise _AnswerFileError("invalid_answer_id")
    if not isinstance(answer.saved_at, str) or not answer.saved_at.strip():
        raise _AnswerFileError("invalid_saved_at")
    for value in (answer.title, answer.subtitle, answer.markdown, answer.capture,
                  answer.answer_kind, answer.stop_reason):
        if not isinstance(value, str):
            raise _AnswerFileError("invalid_field")
    if not answer.markdown.strip():
        raise _AnswerFileError("empty_markdown")
    if answer.status not in ANSWER_ARTIFACT_STATUSES:
        raise _AnswerFileError("invalid_status")
    if answer.capture not in ANSWER_CAPTURE_MODES:
        raise _AnswerFileError("invalid_capture")
    if answer.answer_kind not in ANSWER_KINDS:
        raise _AnswerFileError("invalid_answer_kind")
    if answer.stop_reason not in ANSWER_STOP_REASONS:
        raise _AnswerFileError("invalid_stop_reason")
    if answer.question is not None and not isinstance(answer.question, str):
        raise _AnswerFileError("invalid_question")


def _answer_from_payload(payload: Any) -> SavedAnswer:
    if not isinstance(payload, dict):
        raise _AnswerFileError("malformed")
    schema_version = payload.get("schema_version")
    if schema_version != SAVED_ANSWERS_SCHEMA_VERSION:
        raise _AnswerFileError("unsupported_schema")
    answer_id = payload.get("answer_id")
    markdown = payload.get("markdown")
    if not isinstance(answer_id, str) or not isinstance(markdown, str):
        raise _AnswerFileError("malformed")
    answer = SavedAnswer(
        schema_version=SAVED_ANSWERS_SCHEMA_VERSION,
        answer_id=answer_id,
        saved_at=payload.get("saved_at") if isinstance(payload.get("saved_at"), str) else "",
        title=payload.get("title") if isinstance(payload.get("title"), str) else "",
        subtitle=payload.get("subtitle") if isinstance(payload.get("subtitle"), str) else "",
        markdown=markdown,
        status=payload.get("status") if isinstance(payload.get("status"), str) else "",
        capture=payload.get("capture") if isinstance(payload.get("capture"), str) else "",
        answer_kind=payload.get("answer_kind") if isinstance(payload.get("answer_kind"), str) else "",
        stop_reason=payload.get("stop_reason") if isinstance(payload.get("stop_reason"), str) else "",
        question=payload.get("question") if isinstance(payload.get("question"), str) else None,
    )
    _validate_answer(answer)
    return answer


def _read_owned_regular(fd: int) -> str:
    chunks: list[bytes] = []
    while True:
        chunk = os.read(fd, 65536)
        if not chunk:
            break
        chunks.append(chunk)
    try:
        return b"".join(chunks).decode("utf-8")
    except UnicodeDecodeError:
        raise _AnswerFileError("malformed") from None


def _open_entry(store_fd: int, name: str) -> tuple[int, os.stat_result]:
    try:
        entry_stat = os.stat(name, dir_fd=store_fd, follow_symlinks=False)
    except FileNotFoundError:
        raise _AnswerFileError("missing") from None
    if stat.S_ISLNK(entry_stat.st_mode):
        raise _AnswerFileError("symlink")
    if not stat.S_ISREG(entry_stat.st_mode):
        raise _AnswerFileError("unsafe_entry")
    if entry_stat.st_nlink != 1:
        raise _AnswerFileError("hardlink")
    if entry_stat.st_uid != os.getuid():
        raise _AnswerFileError("foreign_owner")
    try:
        fd = os.open(name, os.O_RDONLY | os.O_NOFOLLOW, dir_fd=store_fd)
    except FileNotFoundError:
        raise _AnswerFileError("missing") from None
    except OSError as exc:
        raise _AnswerFileError("unreadable", str(exc)) from None
    opened = os.fstat(fd)
    if not stat.S_ISREG(opened.st_mode) or opened.st_nlink != 1 or opened.st_uid != os.getuid():
        os.close(fd)
        raise _AnswerFileError("unsafe_entry")
    return fd, opened


def _load_from_store(store: Path, name: str) -> tuple[SavedAnswer, os.stat_result]:
    store_fd = os.open(store, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    try:
        return _load_with_fd(store_fd, name)
    finally:
        os.close(store_fd)


def _load_with_fd(store_fd: int, name: str) -> tuple[SavedAnswer, os.stat_result]:
    fd, file_stat = _open_entry(store_fd, name)
    try:
        raw = _read_owned_regular(fd)
    finally:
        os.close(fd)
    try:
        payload = json.loads(raw)
    except (json.JSONDecodeError, ValueError):
        raise _AnswerFileError("malformed") from None
    answer = _answer_from_payload(payload)
    if f"{answer.answer_id}.json" != name:
        raise _AnswerFileError("id_filename_mismatch")
    return answer, file_stat


def _list_store(root: Path) -> tuple[int | None, SavedAnswerIssue | None]:
    store = saved_answers_dir(root)
    try:
        store_stat = os.lstat(store)
    except FileNotFoundError:
        return None, None
    except OSError as exc:
        return None, SavedAnswerIssue(str(store), "unreadable_store", str(exc))
    if stat.S_ISLNK(store_stat.st_mode) or not stat.S_ISDIR(store_stat.st_mode):
        return None, SavedAnswerIssue(str(store), "unsafe_store", "Store is not a real directory.")
    try:
        fd = os.open(store, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    except OSError as exc:
        return None, SavedAnswerIssue(str(store), "unreadable_store", str(exc))
    return fd, None


def list_saved_answers(root: Path) -> SavedAnswerListing:
    """Rebuild the library from files, newest first; never creates anything."""
    store_fd, store_issue = _list_store(root)
    if store_fd is None:
        return SavedAnswerListing((), (store_issue,) if store_issue else ())
    answers: list[SavedAnswer] = []
    issues: list[SavedAnswerIssue] = []
    try:
        with os.scandir(store_fd) as entries:
            for entry in entries:
                name = entry.name
                if name.startswith(_TEMP_PREFIX) or name.startswith("._"):
                    issues.append(
                        SavedAnswerIssue(name, "unexpected_entry", "Leftover or metadata file.")
                    )
                    continue
                if not name.endswith(".json"):
                    issues.append(
                        SavedAnswerIssue(name, "unexpected_entry", "Not a saved-answer file.")
                    )
                    continue
                stem = name[: -len(".json")]
                if not ANSWER_ID_RE.fullmatch(stem):
                    issues.append(
                        SavedAnswerIssue(name, "invalid_name", "Filename is not an answer id.")
                    )
                    continue
                try:
                    answer, file_stat = _load_with_fd(store_fd, name)
                except _AnswerFileError as exc:
                    issues.append(SavedAnswerIssue(name, exc.code, exc.message))
                    continue
                answers.append(answer)
                if file_stat.st_mode & 0o077:
                    issues.append(
                        SavedAnswerIssue(
                            name,
                            "broad_permissions",
                            "Saved answer is readable beyond the owner; it loaded untouched.",
                        )
                    )
    finally:
        os.close(store_fd)
    answers.sort(key=lambda item: (item.saved_at, item.answer_id), reverse=True)
    return SavedAnswerListing(tuple(answers), tuple(issues))


def load_saved_answer(root: Path, answer_id: str) -> SavedAnswerResult:
    if not ANSWER_ID_RE.fullmatch(answer_id):
        return SavedAnswerResult(None, "invalid_answer_id")
    store_fd, store_issue = _list_store(root)
    if store_fd is None:
        return SavedAnswerResult(None, store_issue.code if store_issue else "missing")
    try:
        answer, _stat = _load_with_fd(store_fd, f"{answer_id}.json")
    except _AnswerFileError as exc:
        return SavedAnswerResult(None, exc.code)
    finally:
        os.close(store_fd)
    return SavedAnswerResult(answer)


def _same_answer(left: SavedAnswer, right: SavedAnswer) -> bool:
    return left.to_payload() == right.to_payload()


def save_saved_answer(root: Path, answer: SavedAnswer) -> SavedAnswerResult:
    """Publish one immutable answer file; existing identical saves are idempotent."""
    try:
        _validate_answer(answer)
    except _AnswerFileError as exc:
        return SavedAnswerResult(None, exc.code)
    try:
        store = _ensure_store_dir(root)
    except OSError:
        return SavedAnswerResult(None, "store_unavailable")
    final_name = f"{answer.answer_id}.json"
    try:
        existing, _stat = _load_from_store(store, final_name)
    except _AnswerFileError as exc:
        existing = None
        if exc.code != "missing":
            return SavedAnswerResult(None, "conflict")
    if existing is not None:
        if _same_answer(existing, answer):
            return SavedAnswerResult(existing)
        return SavedAnswerResult(None, "conflict")

    data = (
        json.dumps(answer.to_payload(), ensure_ascii=False, sort_keys=True, indent=2) + "\n"
    ).encode("utf-8")
    temp_path: str | None = None
    try:
        handle = tempfile.NamedTemporaryFile(
            mode="wb",
            prefix=_TEMP_PREFIX,
            dir=str(store),
            delete=False,
        )
        temp_path = handle.name
        try:
            os.fchmod(handle.fileno(), 0o600)
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
        finally:
            handle.close()
        try:
            os.link(temp_path, store / final_name)
        except FileExistsError:
            return SavedAnswerResult(None, "conflict")
    except OSError:
        return SavedAnswerResult(None, "write_failed")
    finally:
        if temp_path is not None:
            try:
                os.unlink(temp_path)
            except OSError:
                pass
    return SavedAnswerResult(answer)


def delete_saved_answer(root: Path, answer_id: str) -> SavedAnswerResult:
    if not ANSWER_ID_RE.fullmatch(answer_id):
        return SavedAnswerResult(None, "invalid_answer_id")
    store_fd, store_issue = _list_store(root)
    if store_fd is None:
        return SavedAnswerResult(None, store_issue.code if store_issue else "missing")
    name = f"{answer_id}.json"
    try:
        fd, _stat = _open_entry(store_fd, name)
        os.close(fd)
        os.unlink(name, dir_fd=store_fd)
    except _AnswerFileError as exc:
        return SavedAnswerResult(None, exc.code)
    except OSError:
        return SavedAnswerResult(None, "delete_failed")
    finally:
        os.close(store_fd)
    return SavedAnswerResult(None)
