"""Local question templates and guarded Focus-owned preferences (no GTK or Pi discovery)."""
from __future__ import annotations

from contextlib import contextmanager
from dataclasses import dataclass
import hashlib
import os
from pathlib import Path
import stat
import unicodedata

from ._model_schema import LEVELS
from ._model_store import Failure, identity, parse, save_ordinary, snapshot
from .paths import config_dir

MAX_SKILL_BYTES = 64 * 1024
PREFS_NAME = "research-skills.json"


@dataclass(frozen=True, slots=True)
class SkillPreferences:
    folder: str = ""
    model_key: tuple[str, str] | None = None
    effort: str | None = None


def preferences_path() -> Path:
    return config_dir() / PREFS_NAME


def read_preferences(path: Path | None = None) -> tuple[SkillPreferences, str]:
    current = snapshot(path if path is not None else preferences_path())
    return _parse_preferences(parse(current["bytes"])), current["revision"]


def _parse_preferences(value: dict) -> SkillPreferences:
    folder = value.get("folder", "")
    if (set(value) - {"folder", "provider", "model", "effort"}
            or not isinstance(folder, str)
            or (folder and not _valid_folder(folder))):
        raise Failure("invalid research skills folder or settings")
    key = None
    if "provider" in value or "model" in value:
        ident = identity({"provider": value.get("provider"), "model": value.get("model")})
        key = ident["provider"], ident["model"]
    effort = value.get("effort")
    if (key is not None and not folder) or ("effort" in value and (key is None or effort not in LEVELS)):
        raise Failure("Skill reasoning requires a configured folder and an explicit skill model")
    return SkillPreferences(folder, key, effort)


def save_preferences(preferences: SkillPreferences, revision: str, path: Path | None = None) -> str:
    data = {}
    if preferences.folder:
        data["folder"] = preferences.folder
    if preferences.model_key is not None:
        data["provider"], data["model"] = preferences.model_key
    if preferences.effort is not None:
        data["effort"] = preferences.effort
    _parse_preferences(data)
    return save_ordinary(path if path is not None else preferences_path(), data, expected=revision)


@dataclass(frozen=True, slots=True)
class ResearchSkill:
    key: str  # Relative path, never the potentially duplicate display title.
    title: str
    fingerprint: tuple


@dataclass(frozen=True, slots=True)
class SkillListing:
    skills: tuple[ResearchSkill, ...] = ()
    notices: tuple[str, ...] = ()


class SkillChanged(ValueError):
    """The selected entry no longer corresponds to what the picker displayed."""


def _safe_text(value: str, *, multiline: bool = True) -> bool:
    return all(ch in "\n\t\r" and multiline or unicodedata.category(ch) not in {"Cc", "Cs"}
               for ch in value)


def _valid_folder(folder: str) -> bool:
    path = Path(folder)
    return path.is_absolute() and ".." not in path.parts and _safe_text(folder, multiline=False)


_DIR_FLAGS = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC


@contextmanager
def _directory(folder: str):
    path = Path(folder)
    if not _valid_folder(folder):
        raise ValueError("Choose an absolute local folder without redirected paths.")
    fd = os.open("/", _DIR_FLAGS)
    try:
        for part in path.parts[1:]:
            next_fd = os.open(part, _DIR_FLAGS, dir_fd=fd)
            os.close(fd)
            fd = next_fd
        yield fd
    finally:
        os.close(fd)


def _visible(name: str) -> bool:
    return bool(name and not name.startswith(".") and _safe_text(name, multiline=False))


def _envelope(raw: bytes) -> str:
    try:
        body = raw.decode("utf-8-sig")
    except UnicodeError as exc:
        raise ValueError("not valid UTF-8") from exc
    if not _safe_text(body):
        raise ValueError("contains non-text control characters")
    lines = body.splitlines(keepends=True)
    if lines and lines[0].rstrip() == "---":
        end = next((i for i, line in enumerate(lines[1:], 1) if line.rstrip() == "---"), None)
        if end is None:
            raise ValueError("missing closing frontmatter delimiter (---)")
        body = "".join(lines[end + 1:])
    if not body.strip():
        raise ValueError("no question text")
    return body


def _title(body: str, fallback: str) -> str:
    from markdown_it import MarkdownIt

    tokens = MarkdownIt("commonmark").parse(body)
    for index, token in enumerate(tokens):
        if token.type == "heading_open" and token.level == 0:
            children = tokens[index + 1].children or []
            title = " ".join("".join(
                child.content for child in children if child.type in {"text", "code_inline", "image"}
            ).split())
            if title:
                return title
    return fallback


def _fingerprint(info: os.stat_result) -> tuple[int, ...]:
    return info.st_dev, info.st_ino, info.st_size, info.st_mtime_ns, info.st_ctime_ns


def _read_entry(fd: int, name: str) -> tuple[str, tuple]:
    def check(info: os.stat_result) -> None:
        if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1:
            raise ValueError("not a regular, unlinked Markdown file (links are skipped)")
        if info.st_size > MAX_SKILL_BYTES:
            raise ValueError("larger than 64 KiB")

    check(os.stat(name, dir_fd=fd, follow_symlinks=False))
    file_fd = os.open(name, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK | os.O_CLOEXEC, dir_fd=fd)
    with os.fdopen(file_fd, "rb") as handle:
        before = os.fstat(file_fd)
        check(before)
        raw = handle.read(MAX_SKILL_BYTES + 1)
        if len(raw) > MAX_SKILL_BYTES:
            raise ValueError("larger than 64 KiB")
        after = os.fstat(file_fd)
        if (_fingerprint(before) != _fingerprint(after)
                or _fingerprint(after) != _fingerprint(os.stat(name, dir_fd=fd, follow_symlinks=False))):
            raise ValueError("file changed while being read")
    return _envelope(raw), (*_fingerprint(after), hashlib.sha256(raw).hexdigest())


def _reason(exc: Exception) -> str:
    if isinstance(exc, OSError):
        return exc.strerror or "could not safely read the entry"
    return str(exc)


def discover_skills(folder: str) -> SkillListing:
    """Scan only visible direct Markdown files and direct children containing SKILL.md."""
    skills: list[ResearchSkill] = []
    notices: list[str] = []

    def add(fd: int, name: str, key: str, fallback: str) -> None:
        try:
            body, fingerprint = _read_entry(fd, name)
            skills.append(ResearchSkill(key, _title(body, fallback), fingerprint))
        except (OSError, ValueError) as exc:
            notices.append(f"{key}: {_reason(exc)}")

    try:
        with _directory(folder) as fd:
            for name in sorted(os.listdir(fd), key=str.casefold):
                if name.startswith("."):
                    continue
                if not _visible(name):
                    notices.append(f"{name!r}: unsupported filename")
                    continue
                try:
                    info = os.stat(name, dir_fd=fd, follow_symlinks=False)
                    if stat.S_ISDIR(info.st_mode):
                        child = os.open(name, _DIR_FLAGS, dir_fd=fd)
                        try:
                            try:
                                os.stat("SKILL.md", dir_fd=child, follow_symlinks=False)
                            except FileNotFoundError:
                                continue
                            add(child, "SKILL.md", f"{name}/SKILL.md", name)
                        finally:
                            os.close(child)
                    elif name.endswith(".md"):
                        add(fd, name, name, Path(name).stem)
                    elif stat.S_ISLNK(info.st_mode):
                        notices.append(f"{name}: links are skipped")
                except OSError as exc:
                    notices.append(f"{name}: {_reason(exc)}")
    except (OSError, ValueError) as exc:
        notices.append(f"Cannot open the Research skills folder: {_reason(exc)}")
    skills.sort(key=lambda skill: (skill.title.casefold(), skill.key.casefold(), skill.key))
    return SkillListing(tuple(skills), tuple(notices))


def read_selected_skill(folder: str, selected: ResearchSkill) -> str:
    """Read the picked relative path again, refusing replacement even under the same title."""
    parts = selected.key.split("/")
    if not all(map(_visible, parts)) or not (
        (len(parts) == 1 and parts[0].endswith(".md")) or (len(parts) == 2 and parts[1] == "SKILL.md")
    ):
        raise SkillChanged("Invalid research skill selection.")
    try:
        with _directory(folder) as fd:
            if len(parts) == 1:
                body, fingerprint = _read_entry(fd, parts[0])
            else:
                child = os.open(parts[0], _DIR_FLAGS, dir_fd=fd)
                try:
                    body, fingerprint = _read_entry(child, parts[1])
                finally:
                    os.close(child)
        if fingerprint == selected.fingerprint:
            return body
    except (ValueError, OSError):
        pass
    raise SkillChanged("That research skill changed or disappeared. Choose it again from the refreshed list.")
