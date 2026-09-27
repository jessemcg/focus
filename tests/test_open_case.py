"""Synthetic, configuration-isolated picker and current-case defaults coverage."""

import importlib
from pathlib import Path
from types import SimpleNamespace

import gi

gi.require_version("Gtk", "4.0")
from gi.repository import Gio, GLib, Gtk

import focus.app as app_module
import focus.core as core
import focus.current_case as current_case
from focus.app import Focus


def test_home_defaults_and_open_before_closed(monkeypatch, tmp_path):
    with monkeypatch.context() as patch:
        patch.setattr(Path, "home", classmethod(lambda cls: tmp_path))
        helper = importlib.reload(current_case)
    base = tmp_path / "Dropbox" / "MCGLAW"
    args = helper.parse_args([])
    assert args.current_case_file == base / "config_files/scripts/misc/currently_selected_case"
    assert args.open_root == base / "OPEN_CASES"
    assert args.closed_root == base / "CLOSED_CASES"
    for root in (args.open_root, args.closed_root):
        (root / "Example" / "0_record" / "case_bundle").mkdir(parents=True)
    assert helper.resolve_case_dir("Example", [args.open_root, args.closed_root]) == args.open_root / "Example"
    override = helper.parse_args(["--open-root", str(args.closed_root), "--closed-root", str(args.open_root),
                                  "--current-case-file", str(tmp_path / "selected"), "--config", str(tmp_path / "cfg")])
    assert override.current_case_file == tmp_path / "selected"
    assert override.config == tmp_path / "cfg"
    assert helper.resolve_case_dir("Example", [override.open_root, override.closed_root]) == args.closed_root / "Example"
    importlib.reload(current_case)


def test_header_and_menu_share_existing_action():
    button = Focus._build_open_case_button()
    menu = Focus._build_document_menu()
    assert button.get_action_name() == "app.choose_input"
    assert button.has_css_class("flat") and button.get_focusable()
    assert "existing record folder" in button.get_tooltip_text()
    children = button.get_child()
    labels = []
    child = children.get_first_child()
    while child is not None:
        if isinstance(child, Gtk.Label):
            labels.append(child.get_label())
        child = child.get_next_sibling()
    assert labels == ["Open Case…"]
    assert any(
        menu.get_item_attribute_value(i, Gio.MENU_ATTRIBUTE_LABEL).get_string() == "Open Case…"
        and menu.get_item_attribute_value(i, Gio.MENU_ATTRIBUTE_ACTION).get_string()
        == button.get_action_name()
        for i in range(menu.get_n_items())
    )


def test_picker_singleflight_cancel_errors_and_selection(monkeypatch, tmp_path):
    case_a = tmp_path / "A"
    case_b = tmp_path / "B"
    for case in (case_a, case_b):
        (case / "text_pages").mkdir(parents=True)
        (case / "text_pages" / "0001.txt").write_text(case.name)
        (case / "case_name.txt").write_text(case.name)
    app = Focus(input_override=case_a)
    app.win = object()
    notices = []
    app._transient_toast = notices.append
    dialogs = []

    class Dialog:
        def __init__(self):
            dialogs.append(self)

        def set_title(self, value):
            assert value == "Open Case Folder"

        def set_modal(self, value):
            assert value

        def set_initial_folder(self, value):
            pass

        def select_folder(self, *args):
            self.callback = args[-1]

        def select_folder_finish(self, result):
            if isinstance(result, Exception):
                raise result
            return result

    monkeypatch.setattr(app_module.Gtk, "FileDialog", Dialog)
    action = None
    app._on_choose_input_dir(action, None)
    app._on_choose_input_dir(action, None)
    assert len(dialogs) == 1
    cancel = GLib.Error.new_literal(Gio.io_error_quark(), "cancel", Gio.IOErrorEnum.CANCELLED)
    dialogs[-1].callback(dialogs[-1], cancel)
    assert app.input_dir == case_a and not notices and app._input_dir_dialog is None
    app._on_choose_input_dir(action, None)
    failure = GLib.Error.new_literal(Gio.io_error_quark(), "failed", Gio.IOErrorEnum.FAILED)
    dialogs[-1].callback(dialogs[-1], failure)
    assert "failed" in notices[-1]
    app._on_choose_input_dir(action, None)
    dialogs[-1].callback(dialogs[-1], SimpleNamespace(get_path=lambda: None))
    assert "nonlocal" in notices[-1]
    app._on_choose_input_dir(action, None)
    dialogs[-1].callback(dialogs[-1], SimpleNamespace(get_path=lambda: str(tmp_path / "missing")))
    assert app.input_dir == case_a
    assert not core.CONFIG_FILE.exists()
    # Exercise the existing reset/reload path without a running GUI window.
    app.win = None
    app._stop_grep_search_if_running = lambda: None
    app._set_show_image = lambda *a, **kw: None
    app._close_transcript_breakdown_window = lambda: None
    resets = []
    app._reset_view_states = lambda: resets.append(app.input_dir)
    app._reload_saved_answers = lambda: None
    app._refresh_transcript_breakdown_action = lambda: None
    app._load_toc_from_disk_async = lambda: None
    app._load_current = lambda: None
    app._persist_active_view_state = lambda: None
    app._on_input_dir_dialog_response = Focus._on_input_dir_dialog_response.__get__(app)
    app._input_dir_dialog = dialogs[-1]
    dialogs[-1].callback(dialogs[-1], SimpleNamespace(get_path=lambda: str(case_b)))
    assert resets == [case_a]
    assert app.input_dir == case_b and app.pages == [1]
    assert app._case_name == "B"
    assert core.load_input_dir_from_config() == case_b
    assert Focus().input_dir == case_b
    assert Focus(input_override=case_a).input_dir == case_a
    empty = tmp_path / "empty"
    empty.mkdir()
    app._update_header = lambda: None
    app._set_window_title = lambda title: None
    messages = []
    app._set_text = messages.append
    app._apply_input_dir(empty)
    assert "text_pages/" in messages[-1] and "Open Case…" in messages[-1]
    assert resets == [case_a, case_b]
