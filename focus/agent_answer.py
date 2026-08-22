"""Best-effort Focus Agent answer linting and artifact transport."""

from __future__ import annotations

from dataclasses import dataclass
import json
import os
import re
import secrets
import stat
import tempfile
from pathlib import Path
from typing import Any

ANSWER_ARTIFACT_SCHEMA_VERSION = 1
ANSWER_ARTIFACT_STATUSES = frozenset({"complete", "partial"})
ANSWER_CAPTURE_MODES = frozenset({"submit_tool", "assistant_fallback"})
ANSWER_KINDS = frozenset({"answered", "not_found", "insufficient_text"})
ANSWER_WARNING_CATEGORIES = frozenset(
    {
        "long_quote",
        "bold_markup",
        "record_metadata",
        "long_answer",
        "limited_quote_support",
    }
)
ANSWER_STOP_REASONS = frozenset({"stop", "length", "toolUse", "error", "aborted"})
RUN_ID_RE = re.compile(r"^[A-Za-z0-9_-]{20,128}$")
_QUOTE_RE = re.compile(r'["“]([^"”\n]+)["”]')
_RECORD_METADATA_RE = re.compile(
    r"(?:\b(?:CT|RT|CR|ER|AR)\s*[: ]\s*\d+\b|"
    r"\bcitation_(?:label|key|range)\b|"
    r"\b(?:case )?overview\b|"
    r"\btext_pages/|\b\d{4,}\.txt\b)",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class FocusAnswerArtifact:
    schema_version: int
    run_id: str
    revision: int
    status: str
    capture: str
    answer_kind: str
    markdown: str
    warnings: tuple[str, ...]
    diagnostics: dict[str, Any]


@dataclass(frozen=True)
class FocusAnswerArtifactRead:
    artifact: FocusAnswerArtifact | None
    error: str = ""


def create_focus_run_id() -> str:
    """Return an opaque identifier suitable for one answer transport."""
    return secrets.token_urlsafe(24)


def focus_answer_runtime_dir() -> Path:
    """Return Focus's private runtime directory for ephemeral answer artifacts."""
    configured = str(os.environ.get("XDG_RUNTIME_DIR", "") or "").strip()
    if configured:
        root = Path(configured).expanduser()
    else:
        root = Path(tempfile.gettempdir()) / f"focus-{os.getuid()}"
    path = root / "focus" / "agent-answers"
    path.mkdir(mode=0o700, parents=True, exist_ok=True)
    try:
        path.chmod(0o700)
    except OSError:
        pass
    return path.resolve(strict=False)


def focus_answer_artifact_path(run_id: str, runtime_dir: Path | None = None) -> Path:
    if not RUN_ID_RE.fullmatch(run_id):
        raise ValueError("Invalid Focus Agent run identifier.")
    root = (runtime_dir or focus_answer_runtime_dir()).expanduser().resolve(strict=False)
    return root / f"{run_id}.json"


def remove_focus_answer_artifact(path: Path | None) -> None:
    if path is None:
        return
    try:
        path.unlink(missing_ok=True)
    except OSError:
        pass


def lint_focus_answer(markdown: str) -> tuple[str, ...]:
    """Return category-only, non-blocking diagnostics without changing text."""
    warnings: set[str] = set()
    quotes = _QUOTE_RE.findall(markdown)
    if any(len(re.findall(r"\b[\w’'-]+\b", quote)) > 5 for quote in quotes):
        warnings.add("long_quote")
    if "**" in markdown or "__" in markdown:
        warnings.add("bold_markup")
    if _RECORD_METADATA_RE.search(markdown):
        warnings.add("record_metadata")
    if len(markdown) > 16_000 or len(markdown.split()) > 2_500:
        warnings.add("long_answer")

    substantive_blocks = []
    for block in re.split(r"\n\s*\n", markdown):
        cleaned = block.strip()
        if not cleaned or cleaned.startswith("#"):
            continue
        if re.search(
            r"\b(?:not found|could not (?:be )?located|insufficient text|"
            r"cannot be determined|available text)\b",
            cleaned,
            re.IGNORECASE,
        ):
            continue
        substantive_blocks.append(cleaned)
    if substantive_blocks and any(not _QUOTE_RE.search(block) for block in substantive_blocks):
        warnings.add("limited_quote_support")
    return tuple(sorted(warnings))


def _validated_diagnostics(value: Any) -> dict[str, Any] | None:
    if not isinstance(value, dict):
        return None
    diagnostics: dict[str, Any] = {}
    for key in ("provider", "model", "thinking", "stop_reason"):
        item = value.get(key, "")
        if not isinstance(item, str):
            return None
        diagnostics[key] = item
    if diagnostics["stop_reason"] not in ANSWER_STOP_REASONS:
        return None
    for key in (
        "assistant_turns",
        "tool_calls",
        "searches",
        "pages_read",
        "grep_calls",
        "map_inspections",
        "elapsed_ms",
    ):
        item = value.get(key, 0)
        if not isinstance(item, int) or isinstance(item, bool) or item < 0:
            return None
        diagnostics[key] = item
    usage = value.get("usage", {})
    if not isinstance(usage, dict):
        return None
    clean_usage: dict[str, int | float] = {}
    for key in ("input", "output", "cache_read"):
        item = usage.get(key, 0)
        if not isinstance(item, (int, float)) or isinstance(item, bool) or item < 0:
            return None
        clean_usage[key] = item
    cost = usage.get("reported_cost", 0)
    if not isinstance(cost, (int, float)) or isinstance(cost, bool) or cost < 0:
        return None
    clean_usage["reported_cost"] = cost
    diagnostics["usage"] = clean_usage
    return diagnostics


def focus_answer_status_message(artifact: FocusAnswerArtifact) -> str:
    """Return the subdued UI status for a transport-valid artifact."""
    if not artifact.markdown.strip():
        return "Provider/session failure: no usable answer text."
    stop_reason = str(artifact.diagnostics.get("stop_reason") or "")
    if stop_reason == "length":
        return "Partial answer—output limit reached."
    if stop_reason in {"error", "aborted"}:
        return f"Partial answer—Agent {stop_reason}."
    if artifact.capture == "assistant_fallback":
        return "Best-effort answer ready."
    return "Final answer ready."


def read_focus_answer_artifact(
    path: Path,
    *,
    run_id: str,
    last_revision: int = 0,
) -> FocusAnswerArtifactRead:
    """Read one artifact with transport-integrity checks; never judge answer quality."""
    if not RUN_ID_RE.fullmatch(run_id):
        return FocusAnswerArtifactRead(None, "invalid_run_id")
    try:
        file_stat = path.stat()
        if not stat.S_ISREG(file_stat.st_mode) or file_stat.st_mode & 0o077:
            return FocusAnswerArtifactRead(None, "insecure_artifact")
        payload = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return FocusAnswerArtifactRead(None, "missing")
    except PermissionError:
        return FocusAnswerArtifactRead(None, "unreadable")
    except (OSError, UnicodeError, json.JSONDecodeError):
        return FocusAnswerArtifactRead(None, "malformed")
    if not isinstance(payload, dict):
        return FocusAnswerArtifactRead(None, "malformed")
    if payload.get("schema_version") != ANSWER_ARTIFACT_SCHEMA_VERSION:
        return FocusAnswerArtifactRead(None, "unsupported_schema")
    if payload.get("run_id") != run_id:
        return FocusAnswerArtifactRead(None, "wrong_run_id")
    revision = payload.get("revision")
    if not isinstance(revision, int) or isinstance(revision, bool) or revision < 1:
        return FocusAnswerArtifactRead(None, "invalid_revision")
    if revision <= last_revision:
        return FocusAnswerArtifactRead(None, "stale_revision")
    status = payload.get("status")
    capture = payload.get("capture")
    answer_kind = payload.get("answer_kind")
    markdown = payload.get("markdown")
    warnings = payload.get("warnings")
    diagnostics = _validated_diagnostics(payload.get("diagnostics"))
    if status not in ANSWER_ARTIFACT_STATUSES:
        return FocusAnswerArtifactRead(None, "invalid_status")
    if capture not in ANSWER_CAPTURE_MODES:
        return FocusAnswerArtifactRead(None, "invalid_capture")
    stop_reason = diagnostics.get("stop_reason") if diagnostics is not None else None
    if (
        (capture == "submit_tool" and stop_reason != "toolUse")
        or (capture == "assistant_fallback" and stop_reason == "toolUse")
    ):
        return FocusAnswerArtifactRead(None, "invalid_capture_stop_reason")
    if answer_kind not in ANSWER_KINDS:
        return FocusAnswerArtifactRead(None, "invalid_answer_kind")
    if not isinstance(markdown, str):
        return FocusAnswerArtifactRead(None, "invalid_markdown")
    if (
        not isinstance(warnings, list)
        or any(item not in ANSWER_WARNING_CATEGORIES for item in warnings)
        or diagnostics is None
    ):
        return FocusAnswerArtifactRead(None, "invalid_diagnostics")
    merged_warnings = tuple(sorted(set(warnings) | set(lint_focus_answer(markdown))))
    return FocusAnswerArtifactRead(
        FocusAnswerArtifact(
            schema_version=ANSWER_ARTIFACT_SCHEMA_VERSION,
            run_id=run_id,
            revision=revision,
            status=status,
            capture=capture,
            answer_kind=answer_kind,
            markdown=markdown,
            warnings=merged_warnings,
            diagnostics=diagnostics,
        )
    )
