"""Read preparation selection/publication as metadata, never profile instructions."""
from __future__ import annotations

import os
from dataclasses import asdict
from pathlib import Path

from .profile_artifacts import preparation_provenance, preparation_selection
from .profile_contract import ProfileError, _json, read_file_at


def _read(root: Path, relative: str):
    """Only callers' fixed sidecar names; descriptor-relative, bounded, no links."""
    path = root / relative
    if not path.exists() and not path.is_symlink():
        return None, "missing"
    try:
        fd = os.open(root, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
        try:
            value = _json(read_file_at(fd, relative), "preparation")
        finally:
            os.close(fd)
        return value, "read"
    except (OSError, ProfileError):
        return None, "invalid"


def preparation_context(root: Path, map_provenance: dict | None) -> dict:
    """Keep selected preparation and actually published preparation separate.

    Reading/opening a case never creates its binding, accepts a profile, resolves
    a profile folder, or changes defaults. A missing RecordPrep instruction store
    has no effect on browsing. Focus research always uses its fixed neutral method.
    """
    selection, selection_status = _read(root, ".recordprep/practice-profile.json")
    publication, publication_status = _read(root, "artifacts/practice_profile_provenance.json")
    selected = None
    published = None
    notices = []
    if selection_status == "read":
        try:
            selected = asdict(preparation_selection(selection))
        except ProfileError:
            selection_status = "invalid"
    if publication_status == "read":
        try:
            published = preparation_provenance(publication)
        except ProfileError:
            publication_status = "invalid"
    if selection_status == "invalid":
        notices.append("invalid_preparation_selection")
    if publication_status == "invalid":
        notices.append("invalid_preparation_publication")
    # Only validated map metadata describes the map actually consumed by Q&A.
    if selected is not None and (map_provenance is None or selected != map_provenance["profile_ref"]):
        notices.append("selected_preparation_differs_from_map")
    if published is not None and published != map_provenance:
        notices.append("published_preparation_differs_from_map")
    return {"selected_profile_ref": selected, "published_provenance": published,
            "map_provenance": map_provenance, "selection_status": selection_status,
            "publication_status": publication_status, "notices": notices}
