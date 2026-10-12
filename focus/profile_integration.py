"""Focus research profile adapters; existing answers and live pins stay frozen."""
from __future__ import annotations

from pathlib import Path
from .profile_contract import ProfileError
from .research_selection import read_selection, apply_selection
from .research_profiles import compile_research
from .practice_profiles import profile_store


def reference_label(ref):
    if ref is None:
        return "Existing settings"
    try:
        return profile_store().load_profile_snapshot(ref).manifest["display_name"]
    except (ValueError, OSError):
        return "Unavailable profile"


def context_description(root):
    if root is None:
        return "No case open."
    choice = read_selection(root)
    if choice and choice.profile_ref:
        try:
            profile_store().load_profile_snapshot(choice.profile_ref)
        except (ValueError, OSError):
            return "Selected research instructions unavailable. Browsing and saved answers remain available."
    return "Saving settings does not change this case or regenerate existing answers."


def preview(snapshot):
    compiled = compile_research(snapshot)
    return {"Research": compiled.skill}


def update_indicator(app):
    widget = getattr(app, "_title_widget", None)
    if widget is None:
        return
    try:
        root = getattr(getattr(app, "_record_layout", None), "root", None)
        active = getattr(app, "_agent_terminal_active", False)
        if active:
            pin = getattr(app, "_agent_research_pin", None)
            snapshot = pin.snapshot if pin else None
        else:
            selection = read_selection(root) if root else None
            ref = selection.profile_ref if selection else None
            snapshot = profile_store().load_profile_snapshot(ref) if ref else None
        name = snapshot.manifest["display_name"] if snapshot else "Existing settings" if (active or (root and selection)) else "Choose profile" if root else "No case"
        text = name
        notice = ""
        if snapshot:
            from .practice_profiles import profile_catalog
            current = next((item.snapshot for item in profile_catalog() if item.snapshot.ref.specialty_id == snapshot.ref.specialty_id), None)
            if current and current.ref != snapshot.ref:
                notice = "This case uses earlier settings."
        widget.set_subtitle(text)
        widget.set_tooltip_text(name + ("\n" + notice if notice else ""))
    except (ValueError, OSError):
        widget.set_subtitle("Unavailable profile")


def open_manager(app, parent=None):
    from .profile_manager_ui import ProfileManagerWindow
    root = getattr(getattr(app, "_record_layout", None), "root", None)
    generation = getattr(app, "_case_generation", 0)
    from .profile_editor_ui import unavailable
    try:
        previous = read_selection(root) if root else None
    except (ValueError, OSError):
        unavailable(parent or app.win)
        return None
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
    proposed = previous.profile_ref if previous else None
    if previous is None:
        from .practice_profiles import default_profile_candidate
        try:
            proposed = default_profile_candidate().ref
        except (ValueError, OSError):
            pass
    try:
        window = ProfileManagerWindow(parent or app.win, can_modify=allowed, preview=preview, on_select=select,
                                      selected_ref=proposed, case_ref=previous.profile_ref if previous else None, case_confirmed=previous is not None,
                                      can_select=lambda: root is not None, settings=parent is not None)
    except (ValueError, OSError):
        unavailable(parent or app.win)
        return None
    if getattr(app, "_agent_terminal_active", False):
        from .profile_editor_ui import button
        def end_session():
            if generation != getattr(app, "_case_generation", 0):
                return
            app._stop_agent_terminal()
            update_indicator(app)
        window.body.prepend(button("End live session", end_session))
    app._practice_profiles_window = window
    return window
