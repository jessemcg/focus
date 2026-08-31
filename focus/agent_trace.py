"""Focus Agent session-trace discovery and snapshotting.

The embedded Agent runs PI inside a private disposable workspace. While the
run is active, PI persists its session JSONL under the workspace's
``pi-sessions`` directory; when the wrapper exits it preserves that file under
Focus's private runtime directory so failed and completed runs remain
diagnosable. This module owns the discovery contract for both locations, the
validated atomic snapshot workflow, and the clipboard trace path.
"""

from __future__ import annotations

import json
import os
import tempfile
from collections.abc import Mapping
from pathlib import Path

from .agent_answer import RUN_ID_RE

PI_SESSION_LOG_GLOB = "**/*.jsonl"
TRACE_STATE_DIR_PARTS = ("focus", "traces")
TRACE_FILENAME = "latest_trace.jsonl"


class TraceSnapshotError(Exception):
    """A PI session trace could not be validated or published as a snapshot."""


def pi_session_log_matches_cwd(path: Path, cwd: Path) -> bool:
    """Return True when the session JSONL header records the given cwd."""
    wanted = str(cwd)
    try:
        with path.open("r", encoding="utf-8", errors="replace") as handle:
            for line in handle:
                if not line.strip():
                    continue
                try:
                    payload = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if not isinstance(payload, dict) or payload.get("type") != "session":
                    continue
                return payload.get("cwd") == wanted
    except OSError:
        return False
    return False


def find_latest_pi_session_log_for_cwd(sessions_root: Path, cwd: Path) -> Path | None:
    """Return the newest session JSONL under sessions_root whose header matches cwd."""
    if not sessions_root.is_dir():
        return None
    try:
        candidates = sorted(
            sessions_root.glob(PI_SESSION_LOG_GLOB),
            key=lambda item: item.stat().st_mtime,
            reverse=True,
        )
    except OSError:
        return None
    for candidate in candidates:
        if candidate.is_file() and pi_session_log_matches_cwd(candidate, cwd):
            return candidate
    return None


def focus_session_preserve_dir() -> Path:
    """Return Focus's private runtime directory for preserved session traces."""
    configured = str(os.environ.get("XDG_RUNTIME_DIR", "") or "").strip()
    if configured:
        root = Path(configured).expanduser()
    else:
        root = Path(tempfile.gettempdir()) / f"focus-{os.getuid()}"
    path = root / "focus" / "agent-sessions"
    path.mkdir(mode=0o700, parents=True, exist_ok=True)
    try:
        path.chmod(0o700)
    except OSError:
        pass
    return path.resolve(strict=False)


def focus_preserved_session_path(
    run_id: str,
    preserve_dir: Path | None = None,
) -> Path:
    """Return the deterministic preserved-session path for one Agent run."""
    if not RUN_ID_RE.fullmatch(run_id):
        raise ValueError("Invalid Focus Agent run identifier.")
    root = (preserve_dir or focus_session_preserve_dir()).expanduser().resolve(strict=False)
    return root / f"{run_id}.jsonl"


def reasoning_trace_path(environ: Mapping[str, str] | None = None) -> Path:
    """Resolve the destination for the latest Agent trace snapshot.

    The default is private per-user XDG state. An absolute
    ``FOCUS_TRACE_PATH`` file path overrides it, and a relative
    override or relative ``XDG_STATE_HOME`` is rejected.
    """
    env = os.environ if environ is None else environ
    override = str(env.get("FOCUS_TRACE_PATH", "")).strip()
    if override:
        candidate = Path(os.path.expanduser(override))
        if not candidate.is_absolute():
            raise ValueError(
                "FOCUS_TRACE_PATH must expand to an absolute file path"
            )
        return candidate
    state_home = str(env.get("XDG_STATE_HOME", "")).strip()
    if state_home:
        base = Path(state_home)
        if not base.is_absolute():
            raise ValueError("XDG_STATE_HOME must be an absolute directory path")
    else:
        base = Path.home() / ".local" / "state"
    return base.joinpath(*TRACE_STATE_DIR_PARTS) / TRACE_FILENAME


def _trace_private_directory(directory: Path) -> None:
    """Create missing state directories with private 0700 permissions."""
    missing: list[Path] = []
    current = directory
    while not current.exists():
        missing.append(current)
        parent = current.parent
        if parent == current:
            break
        current = parent
    for created in reversed(missing):
        created.mkdir()
        os.chmod(created, 0o700)


def snapshot_pi_session_jsonl(source: Path, destination: Path) -> Path:
    """Publish a validated snapshot of a PI session JSONL file.

    Every complete newline-terminated record must be valid JSON and the first
    copied record must be a PI ``session`` header. A trailing partial record
    left by an active writer is omitted; a trailing record that is already
    complete JSON is kept. The snapshot is written through a private temporary
    file and atomically replaces ``destination``, so the previous trace
    survives any validation or write failure.
    """
    try:
        data = source.read_bytes()
    except FileNotFoundError as exc:
        raise TraceSnapshotError(f"Session log not found: {source}") from exc
    except OSError as exc:
        raise TraceSnapshotError(f"Could not read session log {source}: {exc}") from exc

    lines = data.split(b"\n")
    trailing = b""
    if not data:
        lines = []
    elif data.endswith(b"\n"):
        lines = lines[:-1]
    else:
        trailing = lines.pop()

    records: list[bytes] = []
    line_number = 0
    for line in lines:
        line_number += 1
        if not line.strip():
            continue
        try:
            json.loads(line.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise TraceSnapshotError(
                f"Malformed session record at line {line_number} in {source}: {exc}"
            ) from exc
        records.append(line)

    if trailing.strip():
        try:
            json.loads(trailing.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            trailing = b""
        else:
            records.append(trailing)

    if not records:
        raise TraceSnapshotError(f"Session log is empty: {source}")
    try:
        header = json.loads(records[0].decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise TraceSnapshotError(
            f"Session log has a malformed header record in {source}: {exc}"
        ) from exc
    if not isinstance(header, dict) or header.get("type") != "session":
        raise TraceSnapshotError(
            f"Session log does not begin with a PI session header: {source}"
        )

    payload = b"".join(record + b"\n" for record in records)
    try:
        if destination.exists() and destination.is_dir():
            raise TraceSnapshotError(
                f"Trace destination is a directory, not a file: {destination}"
            )
        _trace_private_directory(destination.parent)
        handle_fd, temp_name = tempfile.mkstemp(
            dir=str(destination.parent),
            prefix=".latest_trace.",
            suffix=".tmp",
        )
        temp_path = Path(temp_name)
        try:
            with os.fdopen(handle_fd, "wb") as handle:
                handle.write(payload)
                handle.flush()
                os.fsync(handle.fileno())
            os.chmod(temp_path, 0o600)
            os.replace(temp_path, destination)
        except BaseException:
            try:
                temp_path.unlink()
            except OSError:
                pass
            raise
    except TraceSnapshotError:
        raise
    except OSError as exc:
        raise TraceSnapshotError(
            f"Could not write trace snapshot to {destination}: {exc}"
        ) from exc
    return destination


def trace_clipboard_text(path: Path) -> str:
    """Return the absolute trace path placed on the clipboard for Copy Trace."""
    return str(Path(os.path.abspath(os.path.expanduser(str(path)))))
