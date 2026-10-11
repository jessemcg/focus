"""Explicit private copy of the app's legacy prose, never user runtime config."""
from __future__ import annotations

from pathlib import Path

from .practice_profiles import bundled_profile_directory, validate_profile_directory
from .profile_contract import ProfileError, read_file_at
from .profile_workflows import ProfileEditor

REVIEW_NOTICE = (
    "Private legacy-guidance copy, not a migration. The original resources, settings and cases remain untouched. "
    "Legacy prose is preserved literally beneath the current application-owned contract; review historical "
    "workflow/output instructions in Preview. This copy includes only the canonical answer skill and SYSTEM "
    "prose, not tools, extensions or runtime/credential settings. Review the prose for secrets and private matter "
    "details before sharing. Save/Accept does not select a case or change the default."
)


def legacy_customization_editor(*, resources_root: Path | None = None) -> ProfileEditor:
    """Called only by an explicit copy action; cancellation leaves no files."""
    import os
    base = validate_profile_directory(bundled_profile_directory("california_dependency")).draft
    if base is None:
        raise ProfileError("invalid_bundled_profile", "legacy_copy")
    editor = ProfileEditor.create(base, "Private legacy customization")
    editor.manifest["description"] = "Private copy for explicit review; not selected automatically."
    root = resources_root or Path(__file__).resolve().parent / "agent_resources"
    fd = os.open(root, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    try:
        for resource, relative in (("research", "skills/focus-answer-record-questions/SKILL.md"),
                                   ("answer_guidance", "SYSTEM.md")):
            editor.resources[resource] = read_file_at(fd, relative, limit=256 * 1024).decode("utf-8")
    finally:
        os.close(fd)
    return editor
