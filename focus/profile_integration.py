"""Focus GUI adapters for independently owned research profiles."""
from __future__ import annotations

import os
from pathlib import Path

from .profile_contract import ProfileError, _json, read_file_at
from .profile_artifacts import source_map_profile_metadata
from .preparation_context import preparation_context
from .research_selection import read_selection, apply_selection
from .research_profiles import compile_research
from .practice_profiles import profile_store


def reference_label(ref) -> str:
    if ref is None:
        return "Legacy / unassigned"
    if not isinstance(ref, dict):
        from dataclasses import asdict
        ref = asdict(ref)
    return f"{ref['specialty_id']} · {ref['version']} · {ref['content_sha256'][:8]}"


def context_description(root: Path | None) -> str:
    if root is None:
        return "No case open. Defaults and profile authoring are independent of case selections."
    research = None
    try:
        choice = read_selection(root)
        research = choice.profile_ref if choice is not None else None
        lines = ["Research choice: " + (reference_label(research) if choice is not None else "Not yet confirmed")]
        if research is not None:
            try:
                profile_store().load_profile_snapshot(research)
            except (ValueError, OSError):
                lines.append("Selected research instructions unavailable. Explicitly restore/register the matching revision or choose an alternative before new research; browsing remains available.")
    except (ValueError, OSError):
        lines = ["Research choice unavailable; choose an explicit available revision."]
    try:
        fd = os.open(root, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
        try:
            provenance = source_map_profile_metadata(_json(read_file_at(fd, "artifacts/source_map.json", limit=64 * 1024 * 1024), "source_map"))
        finally:
            os.close(fd)
        context = preparation_context(root, provenance)
        lines.extend([f"Preparation recorded by current map: {reference_label(provenance['profile_ref'] if provenance else None)}",
                      f"Selected preparation (not necessarily published): {reference_label(context['selected_profile_ref'])}"])
        if context["notices"]:
            lines.append("Preparation selection/publication differs or is invalid. Existing answers retain their recorded provenance.")
        if provenance is not None:
            identity = provenance["profile_ref"]["specialty_id"]
            if identity not in profile_store().read_registry()["heads"]:
                lines.append("No accepted local research counterpart. Explicitly choose an alternative or author a counterpart; case metadata never authorizes instructions.")
            if research is not None and research.specialty_id != identity:
                lines.append("Different research and preparation specialties; this is not itself structural incompatibility.")
    except (ValueError, OSError):
        lines.append("Preparation/map metadata unavailable. Browsing and saved answers remain available; no guidance was substituted.")
    return "\n".join(lines)


def preview(snapshot):
    compiled = compile_research(snapshot)
    package = Path(__file__).parent
    return {
        "Application-owned evidence, scope and answer contract": (package / "agent_resources/profile-answer-core.md").read_text(encoding="utf-8"),
        "Effective staged research skill (profile guidance explicitly subordinate)": compiled.skill,
        "Literal ranking preferences (never corpus filters)": "\n".join(f"{name}: {', '.join(terms) or '(none)'}" for name, terms in snapshot.resource("search").items()),
    }


def update_indicator(app) -> None:
    widget = getattr(app, "_practice_profile_button", None)
    if widget is None:
        return
    try:
        root = getattr(getattr(app, "_record_layout", None), "root", None)
        if getattr(app, "_agent_terminal_active", False):
            pin = getattr(app, "_agent_research_pin", None)
            snapshot = pin.snapshot if pin is not None else None
            ref = snapshot.ref if snapshot is not None else None
            short = snapshot.manifest["display_name"] if snapshot else "Legacy"
            tooltip = reference_label(ref)
        else:
            selection = read_selection(root) if root else None
            ref = selection.profile_ref if selection else None
            snapshot = profile_store().load_profile_snapshot(ref) if ref is not None else None
            short = snapshot.manifest["display_name"] if snapshot else "Legacy" if selection else "Choose profile" if root else "No case"
            tooltip = reference_label(ref) if selection else "Not yet confirmed — choose a profile or explicit Legacy before research."
        widget.set_label("Research: " + (short if len(short) <= 24 else short[:23] + "…"))
        widget.set_tooltip_text("Practice Profiles — " + tooltip)
    except (ValueError, OSError):
        widget.set_label("Research: unavailable")
        widget.set_tooltip_text("Open Practice Profiles to choose an explicit available revision. Browsing remains available.")


def open_manager(app, parent=None):
    from .profile_manager_ui import ProfileManagerWindow
    root = getattr(getattr(app, "_record_layout", None), "root", None)
    generation = getattr(app, "_case_generation", 0)
    previous = read_selection(root) if root else None
    def allowed():
        return (generation == getattr(app, "_case_generation", 0)
                and root == getattr(getattr(app, "_record_layout", None), "root", None)
                and not getattr(app, "_agent_terminal_active", False))
    def select(ref):
        nonlocal previous
        if not allowed() or root is None:
            raise ProfileError("case_changed_or_active", "selection")
        previous = apply_selection(root, ref, expected_previous=previous)
        update_indicator(app)
        window.context_group.set_description(context_description(root))
    description = context_description(root)
    if getattr(app, "_agent_terminal_active", False):
        pin = getattr(app, "_agent_research_pin", None)
        ref = pin.snapshot.ref if pin is not None and pin.snapshot is not None else None
        description += "\nLive session research pin: " + reference_label(ref)
    proposed = previous.profile_ref if previous else None
    if previous is None:
        from .practice_profiles import default_profile_candidate
        try:
            proposed = default_profile_candidate().ref
            description += "\nThe default is a proposal only. Confirm Use for this case before new profile-dependent research."
        except (ValueError, OSError):
            description += "\nThe configured default is unavailable. Explicitly choose an available alternative; no guidance was substituted."
    def customization():
        from .profile_customization import legacy_customization_editor, REVIEW_NOTICE
        return legacy_customization_editor(), REVIEW_NOTICE

    window = ProfileManagerWindow(parent or app.win, can_modify=allowed, preview=preview,
                                  on_select=select, context_text=description, selected_ref=proposed, customization=customization, can_select=lambda: root is not None)
    if getattr(app, "_agent_terminal_active", False):
        from .profile_editor_ui import button
        def end_session():
            if generation != getattr(app, "_case_generation", 0):
                return
            app._stop_agent_terminal()
            window.context_group.set_description(context_description(root))
            window.message.set_text("Session ended. Existing answers retain their recorded provenance; choose guidance for a new session.")
            update_indicator(app)
        window.body.prepend(button("End live session to change profiles", end_session))
    app._practice_profiles_window = window
    window.present()
    return window
