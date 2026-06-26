import shlex

from focus.core import (
    ACTION_OBJECT_PATH,
    APPLICATION_ID,
    _action_command,
    _normalize_speech_rag_question_text,
    focus_command_items,
)


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
        "insert_current_page_citation",
        "insert_page_citation_range",
        "toggle_ai_panel",
        "focus_rag_question",
        "focus_agent_question",
        "submit_speech_rag_question",
        "submit_speech_agent_question",
        "show_shortcuts",
    ]


def test_normalize_speech_rag_question_text_trims_and_collapses_whitespace() -> None:
    assert (
        _normalize_speech_rag_question_text("  What happened\n\nat   the hearing?  ")
        == "What happened at the hearing?"
    )


def test_normalize_speech_rag_question_text_preserves_punctuation_and_case() -> None:
    assert (
        _normalize_speech_rag_question_text('Did Mother say, "I object"?')
        == 'Did Mother say, "I object"?'
    )


def test_normalize_speech_rag_question_text_empty_input() -> None:
    assert _normalize_speech_rag_question_text(" \n\t ") == ""
