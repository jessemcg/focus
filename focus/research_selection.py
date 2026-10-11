"""Explicit Focus research choices, outside the case bundle and independent of RP."""
from __future__ import annotations

import hashlib
import os
from dataclasses import asdict, dataclass
from pathlib import Path

from .practice_profiles import profile_store
from .profile_contract import ProfileRef, _json, _object, _require, read_file_at
from .profile_store import _atomic_json, _check_directory, _private_directory, _private_file


@dataclass(frozen=True)
class ResearchSelection:
    # A stored null is an explicit legacy choice; no file means no confirmation.
    profile_ref: ProfileRef | None


def _path(root: Path, store) -> Path:
    key = hashlib.sha256(os.fsencode(root.resolve(strict=False))).hexdigest()
    return store.config_root / "research-cases" / (key + ".json")


def read_selection(root: Path, *, store=None) -> ResearchSelection | None:
    store = store or profile_store()
    _require(store.application == "focus", "wrong_application", "research_selection")
    path = _path(root, store)
    if not path.parent.exists():
        _require(not path.parent.is_symlink(), "unsafe_store_directory", "research_selection")
        return None
    _check_directory(path.parent, private=True)
    if not path.exists():
        _require(not path.is_symlink(), "store_permissions", "research_selection")
        return None
    _private_file(path)
    fd = os.open(path.parent, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    try:
        value = _json(read_file_at(fd, path.name), "research_selection")
    finally:
        os.close(fd)
    _object(value, {"schema_version", "profile_ref"}, "research_selection")
    _require(type(value["schema_version"]) is int and value["schema_version"] == 1,
             "unsupported_version", "research_selection")
    ref = ProfileRef.from_dict(value["profile_ref"]) if value["profile_ref"] is not None else None
    _require(ref is None or ref.application == "focus", "wrong_application", "research_selection")
    return ResearchSelection(ref)


def apply_selection(root: Path, ref: ProfileRef | None, *, expected_previous: ResearchSelection | None,
                    store=None) -> ResearchSelection:
    """Only an explicit user action calls this; opening or querying a case never does."""
    store = store or profile_store()
    _require(store.application == "focus", "wrong_application", "research_selection")
    with store._locked():
        if ref is not None:
            store.load_profile_snapshot(ref)
            _require(ref.application == "focus", "wrong_application", "research_selection")
        _require(read_selection(root, store=store) == expected_previous,
                 "stale_research_selection", "research_selection")
        path = _path(root, store)
        _private_directory(path.parent)
        _atomic_json(path, {"schema_version": 1, "profile_ref": asdict(ref) if ref else None})
    return ResearchSelection(ref)


def requires_confirmation(root: Path, *, store=None) -> bool:
    """First Q&A use always requires a choice, including explicit legacy mode.

    Existing bundles remain unassigned on opening. Neither their preparation
    metadata nor an app default can silently authorize research instructions.
    """
    return read_selection(root, store=store) is None


def resolve_selection(root: Path, *, store=None):
    store = store or profile_store()
    selection = read_selection(root, store=store)
    if selection is None or selection.profile_ref is None:
        return None
    return store.load_profile_snapshot(selection.profile_ref)
