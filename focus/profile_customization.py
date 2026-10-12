"""Read-only preservation of prior research prose beneath current safeguards."""
from __future__ import annotations

import hashlib
import os
from pathlib import Path

from .practice_profiles import bundled_profile_directory, validate_profile_directory
from .profile_contract import ProfileError, read_file_at
from .profile_workflows import ProfileEditor

REVIEW_NOTICE = "Includes your previous Dependency settings."
# Exact tracked shipped content, not a name-based guess at user ownership.
KNOWN_GUIDANCE = {
    "research": {"d0c5cae988a7744f3d04aac52acfc4e4b41146a3467152cbd9b2db90ff51b7c6"},
    "answer_guidance": {"bb0afad8e442dba21aaaa6b63c5301dfc520c1cc1d20ce03c06d4dab42ed4a52"},
}


def legacy_customization_editor(*, resources_root: Path | None = None, base=None) -> ProfileEditor:
    base = base or validate_profile_directory(bundled_profile_directory("california_dependency")).draft
    if base is None:
        raise ProfileError("invalid_bundled_profile", "initialization")
    editor = ProfileEditor(base)
    root = resources_root or Path(__file__).resolve().parent / "agent_resources"
    fd = os.open(root, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    try:
        for resource, relative in (("research", "skills/focus-answer-record-questions/SKILL.md"),
                                   ("answer_guidance", "SYSTEM.md")):
            data = read_file_at(fd, relative)
            if hashlib.sha256(data).hexdigest() not in KNOWN_GUIDANCE[resource]:
                text = data.decode("utf-8")
                if text.strip():
                    editor.resources[resource] += "\n\nPrevious personal guidance (subordinate):\n" + text
    finally:
        os.close(fd)
    return editor


def initial_candidate(base, *, resources_root=None):
    if base.ref.specialty_id != "california-juvenile-dependency":
        return None
    editor = legacy_customization_editor(base=base, resources_root=resources_root)
    snapshot = editor.snapshot()
    return (snapshot, REVIEW_NOTICE) if snapshot.ref != base.ref else None
