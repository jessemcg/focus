"""Actual GTK neutral-method acceptance; synthetic state and simulated launch only.

FOCUS_NEUTRAL_HOLD_MS holds the owned preview for native observation. No model calls.
"""
import json
import os
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace
from unittest.mock import Mock, patch

TEMP = tempfile.TemporaryDirectory(prefix="focus-neutral-gtk-")
ROOT = Path(TEMP.name)
for key in ("HOME", "XDG_CONFIG_HOME", "XDG_DATA_HOME", "XDG_CACHE_HOME", "XDG_STATE_HOME"):
    directory = ROOT / key.lower()
    directory.mkdir(mode=0o700)
    os.environ[key] = str(directory)
os.environ["FOCUS_CONFIG_DIR"] = str(ROOT / "focus-config")
os.environ["GSETTINGS_BACKEND"] = "memory"
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from focus import core, app as module
from focus.research_runtime import stage_research_resources
from test_profile_artifacts import provenance

bundle = ROOT / "bundle"
(bundle / "text_pages").mkdir(parents=True)
(bundle / "artifacts").mkdir()
(bundle / "text_pages/0001.txt").write_text("THE COURT: Motion denied because access was refused.")
(bundle / "case_name.txt").write_text("Synthetic neutral acceptance")
prep = provenance()
prep["profile_ref"]["specialty_id"] = "unknown-third-specialty"
(bundle / "artifacts/source_map.json").write_text(json.dumps({
    "schema_version": 3, "preparation_provenance": prep,
    "pages": [{"file_page": 1, "text_path": "text_pages/0001.txt", "citation_label": "RT 1"}],
    "documents": []}))
retired = ROOT / "xdg_config_home/focus/practice-profiles/registry.json"
retired.parent.mkdir(parents=True)
retired.write_text("CORRUPT RETIRED STORE SENTINEL")
original = {p: p.read_bytes() for p in bundle.rglob("*") if p.is_file()}
module.APPLICATION_ID = "com.mcglaw.Focus.NeutralAcceptance"
application = module.Focus(input_override=bundle)
errors = []


def unhandled(kind, exception, trace):
    errors.append(exception)
    sys.__excepthook__(kind, exception, trace)
    application.quit()


sys.excepthook = unhandled


def widgets(widget):
    yield widget
    child = widget.get_first_child()
    while child:
        yield from widgets(child)
        child = child.get_next_sibling()


def finish():
    try:
        assert not errors
        assert retired.read_text() == "CORRUPT RETIRED STORE SENTINEL"
        for path, data in original.items():
            assert path.read_bytes() == data
        assert not hasattr(application, "_practice_profiles_window")
        print("ACTUAL GTK NEUTRAL ACCEPTANCE PASSED: fresh question, fixed pin/staging, hamburger menu to Settings, quote navigation, preserved prior answer/stores", flush=True)
    except BaseException as exc:
        errors.append(exc)
        print(repr(exc), flush=True)
    application.quit()
    return False


def run():
    try:
        assert not application._title_widget.get_subtitle()
        assert not hasattr(application, "_profile_menu_button")
        application.win.set_default_size(1050, 850)
        application._ensure_ai_panel_visible()
        application._set_ai_view(core.AI_VIEW_AGENT_QA)
        launches = []
        real_start = application._start_agent_terminal
        def simulated_start(prompt):
            pin = application._agent_research_pin
            pin.assert_current(bundle)
            workspace = ROOT / f"workspace-{len(launches)}"
            workspace.mkdir(mode=0o700)
            resources = stage_research_resources(pin, workspace)
            assert "unknown-third-specialty" not in (resources / "skills/focus-answer-record-questions/SKILL.md").read_text()
            launches.append(pin)
            application._clear_agent_answer()
        application._start_agent_terminal = simulated_start
        application._agent_question_entry.set_text("Why was the motion denied?")
        application._launch_agent_question()
        assert len(launches) == 1
        artifact = SimpleNamespace(markdown='# Access Was Refused\n*Motion was denied*\n\nThe court denied the motion because “access was refused”.',
                                   diagnostics={"stop_reason": "stop"}, status="complete", capture="submit_tool", answer_kind="answered")
        snapshot = application._build_live_snapshot(artifact, revision=1, question="Why was the motion denied?")
        assert snapshot.to_saved().schema_version == 3
        application._agent_live_snapshot = snapshot
        application._display_agent_snapshot(snapshot, is_saved=False)
        assert not hasattr(application, "_agent_context_label")
        header_children = list(widgets(application._agent_output_header))
        assert not any(isinstance(w, core.Gtk.Label) and "Focus method:" in w.get_text()
                       for w in header_children)
        assert snapshot.research_context, "Internal research metadata must remain intact"
        application._activate_link(("grep", "access was refused"))
        assert application._grep_phrase_raw == "access was refused"
        application._clear_grep_state()
        application._set_ai_view(core.AI_VIEW_AGENT_QA)
        # Exercise the real launch controller's second pin check, before spawn.
        # /usr/bin/true is an offline sentinel, never Pi or a live model.
        source_page = bundle / "text_pages/0001.txt"
        source_page.write_text("Changed between capture and launch")
        from dataclasses import replace
        previous_settings = application._ai_settings
        sentinel_settings = replace(previous_settings, pi_agent_command="/usr/bin/true")
        with patch.object(module, "load_ai_settings", return_value=sentinel_settings):
            real_start(ROOT / "unused-synthetic-prompt")
        application._ai_settings = previous_settings
        assert application._agent_displayed_snapshot is snapshot
        assert application._agent_workspace_path is None
        source_page.write_bytes(original[source_page])
        # Unknown map schema preflight must retain the displayed immutable answer.
        (bundle / "artifacts/source_map.json").write_text('{"schema_version":99,"pages":[]}')
        application._launch_agent_question()
        assert len(launches) == 1
        assert application._agent_displayed_snapshot is snapshot
        (bundle / "artifacts/source_map.json").write_bytes(original[bundle / "artifacts/source_map.json"])
        # Test the actual header entry point, not a direct Settings callback.
        menu_button = next(w for w in widgets(application.win)
                           if isinstance(w, core.Gtk.MenuButton)
                           and w.get_icon_name() == "open-menu-symbolic")
        menu_model = menu_button.get_menu_model()
        assert menu_model is not None, "Hamburger menu model is unattached"
        # Separate sections produce the two separators: settings, record tools, references.
        assert menu_model.get_n_items() == 3
        section_items = []
        for index in range(menu_model.get_n_items()):
            section = menu_model.get_item_link(index, core.Gio.MENU_LINK_SECTION)
            assert section is not None
            section_items.append([
                (section.get_item_attribute_value(item, core.Gio.MENU_ATTRIBUTE_LABEL).get_string(),
                 section.get_item_attribute_value(item, core.Gio.MENU_ATTRIBUTE_ACTION).get_string())
                for item in range(section.get_n_items())
            ])
        assert section_items == [
            [("Settings", "app.open_ai_settings")],
            [("Transcript Page Breakdown", "app.show_transcript_breakdown"),
             ("Print Images", "app.print_images")],
            [("Keyboard Shortcuts", "app.show_shortcuts"),
             ("D-Bus Commands", "app.show_dbus_commands")],
        ], section_items
        popover = menu_button.get_popover()
        assert popover is not None, "Hamburger button has no popover"
        menu_button.popup()
        assert popover.get_visible(), "Hamburger menu did not open"
        menu_labels = [w.get_label() for w in widgets(popover) if isinstance(w, core.Gtk.Label)]
        assert "Open Case…" not in menu_labels
        open_button = next(w for w in widgets(application.win)
                           if isinstance(w, core.Gtk.Button)
                           and w.get_action_name() == "app.choose_input")
        assert open_button.get_visible() and open_button.get_sensitive()
        assert application.lookup_action("choose_input").get_enabled()
        assert "Settings" in menu_labels
        assert "D-Bus Commands" in menu_labels
        assert "Keyboard Shortcuts" in menu_labels
        assert not any("Profile" in text or "Practice profiles" in text for text in menu_labels)
        settings_item = next(w for w in widgets(popover)
                             if w.get_css_name() == "modelbutton"
                             and any(isinstance(child, core.Gtk.Label) and child.get_label() == "Settings"
                                     for child in widgets(w)))
        with patch("focus.ui.settings.available_pi_models", return_value=[]):
            assert settings_item.activate(), "Settings menu item did not activate"
        window = application._ai_settings_window
        assert window.get_visible(), "Settings window did not open from the menu"
        assert window.get_title() == "Settings"
        agent_row = next(w for w in widgets(window)
                         if isinstance(w, core.Adw.ExpanderRow) and w.get_title() == "Agent")
        agent_row.set_expanded(True)
        agent_titles = [w.get_title() for w in widgets(agent_row)
                        if isinstance(w, core.Adw.PreferencesRow) and w.get_title() != "Agent"]
        assert agent_titles == [
            "PI command", "Speech-to-text question file", "PI Model", "Reasoning Effort",
        ], agent_titles
        labels = [w.get_label() for w in widgets(window) if isinstance(w, core.Gtk.Label)]
        assert not any("Profile" in text or "Practice profiles" in text for text in labels)
        assert not application._title_widget.get_subtitle()
        core.GLib.timeout_add(max(300, int(os.environ.get("FOCUS_NEUTRAL_HOLD_MS", "0"))), finish)
    except BaseException as exc:
        errors.append(exc)
        import traceback
        traceback.print_exc()
        application.quit()
    return False


application.connect("activate", lambda _app: core.GLib.timeout_add(600, run))
application.run([])
TEMP.cleanup()
sys.exit(bool(errors))
