import shlex

from focus import ACTION_OBJECT_PATH, APPLICATION_ID, _action_command, focus_command_items


def test_action_command_formats_gapplication_activate_call() -> None:
    command = _action_command("focus_grep")

    assert shlex.split(command) == [
        "gdbus",
        "call",
        "--session",
        "--dest",
        APPLICATION_ID,
        "--object-path",
        ACTION_OBJECT_PATH,
        "--method",
        "org.gtk.Actions.Activate",
        "focus_grep",
        "[]",
        "{}",
    ]


def test_focus_command_items_cover_shortcut_actions_once() -> None:
    action_names = [command.action_name for command in focus_command_items()]

    assert len(action_names) == len(set(action_names))
    assert action_names == [
        "prev",
        "next",
        "first",
        "last",
        "focus_page_number",
        "toggle_toc_sidebar",
        "toggle_show_image",
        "focus_grep",
        "grep_next_hit",
        "grep_prev_hit",
        "toggle_ai_panel_detached",
        "summarize_current_page",
        "toggle_ai_panel",
        "focus_rag_question",
        "show_shortcuts",
    ]
