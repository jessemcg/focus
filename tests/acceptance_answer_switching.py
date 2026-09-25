"""Bounded synthetic GTK acceptance harness for Focus answer switching.

Run with::

    FOCUS_ACCEPT_TRANSITIONS=320 uv run python tests/acceptance_answer_switching.py

Optionally run under fatal diagnostics to prove no GTK critical is emitted::

    G_DEBUG=fatal-criticals FOCUS_ACCEPT_TRANSITIONS=320 \
        uv run python tests/acceptance_answer_switching.py

It uses a temporary HOME/XDG configuration, a unique application id, a
synthetic bundle (saved answers plus a paginated hearing edition and a
continuous report summary), and no model calls.  It never touches a real
case, real settings, or the production application instance.
"""

from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path

root = Path(tempfile.mkdtemp(prefix="focus-acceptance-"))
for name in ("HOME", "XDG_CONFIG_HOME", "XDG_CACHE_HOME", "XDG_DATA_HOME", "XDG_STATE_HOME"):
    path = root / name.lower()
    path.mkdir(mode=0o700)
    os.environ[name] = str(path)
os.environ["GSETTINGS_BACKEND"] = "memory"
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import test_summary_editions as edition_fixture  # noqa: E402

from focus import core  # noqa: E402
from focus import app as module  # noqa: E402
from focus.answer_metadata import parse_answer_metadata  # noqa: E402
from focus.saved_answers import (  # noqa: E402
    AgentAnswerSnapshot,
    new_answer_id,
    save_saved_answer,
)

core.CONFIG_FILE = root / "config.json"
module.APPLICATION_ID = f"com.mcglaw.Focus.Acceptance.p{os.getpid()}"

TRANSITIONS = int(os.environ.get("FOCUS_ACCEPT_TRANSITIONS", "320"))
ANSWER_COUNT = 12

bundle = root / "synthetic"
(bundle / "text_pages").mkdir(parents=True)
for index in range(1, 8):
    (bundle / "text_pages" / f"{index:04d}.txt").write_text(
        f"Synthetic record page {index}. The record says the sample hearing occurred today.\n",
        encoding="utf-8",
    )
(bundle / "case_name.txt").write_text("Synthetic acceptance case", encoding="utf-8")

# A validated paginated hearing edition (schema v1, structured links) and a
# legacy continuous report summary.
edition_fixture._build_edition(
    bundle,
    focus_source="hearing",
    summary_name="hearings_sum_IsoCase.txt",
    source_text="First paragraph.\n\nSecond paragraph.\n",
    schema_version=2,
    layout_id="recordprep-summary-letter-v3",
    pages_spec=[
        {
            "text": "The record says weekly supervised visits continue.",
            "first": 1,
            "last": 1,
            "quotes": [
                {
                    "start": 16,
                    "end": 40,
                    "label": "weekly supervised visits",
                    "phrase": "weekly supervised visits",
                }
            ],
        },
        {"text": "Second paragraph.", "first": 3, "last": 3, "quotes": []},
    ],
)
summaries = bundle / "summaries"
summaries.mkdir(parents=True, exist_ok=True)
(summaries / "reports_sum_IsoCase.txt").write_text(
    "Report paragraph one.\n\nReport paragraph two.\n",
    encoding="utf-8",
)

answer_ids: list[str] = []
for index in range(ANSWER_COUNT):
    body = (
        f"# Synthetic Answer {index}\n"
        f"*Bottom line {index}*\n\n"
        + "\n\n".join(
            f"Paragraph {line} of synthetic answer {index} with \u201ca quoted phrase\u201d."
            for line in range(12)
        )
        + "\n"
    )
    metadata = parse_answer_metadata(
        body,
        question=f"Question {index}?",
        partial=(index % 4 == 0),
    )
    snapshot = AgentAnswerSnapshot(
        answer_id=new_answer_id(),
        markdown=body,
        title=metadata.title,
        subtitle=metadata.subtitle,
        status="partial" if index % 4 == 0 else "complete",
        capture="assistant_fallback" if index % 3 == 0 else "submit_tool",
        answer_kind="answered",
        stop_reason="length" if index % 4 == 0 else "toolUse",
        question=f"Question {index}?",
    )
    saved = snapshot.to_saved()
    save_saved_answer(bundle, saved)
    answer_ids.append(saved.answer_id)

application = module.Focus(input_override=bundle)

render_counts = {"answer": 0, "summary": 0, "structured": 0}
original_apply_output = module.Focus._apply_ai_output_links
original_apply_summary = module.Focus._apply_summary_links
original_apply_structured = module.Focus._apply_structured_summary_page


def _counting_output(self, text, state):  # type: ignore[no-untyped-def]
    render_counts["answer"] += 1
    return original_apply_output(self, text, state)


def _counting_summary(self, text):  # type: ignore[no-untyped-def]
    render_counts["summary"] += 1
    return original_apply_summary(self, text)


def _counting_structured(self, display):  # type: ignore[no-untyped-def]
    render_counts["structured"] += 1
    return original_apply_structured(self, display)


module.Focus._apply_ai_output_links = _counting_output
module.Focus._apply_summary_links = _counting_summary
module.Focus._apply_structured_summary_page = _counting_structured

critical_count = {"n": 0}


def _log_handler(_domain, level, message, _user_data=None):  # type: ignore[no-untyped-def]
    if level & (core.GLib.LogLevelFlags.LEVEL_CRITICAL | core.GLib.LogLevelFlags.LEVEL_WARNING):
        critical_count["n"] += 1
        print(f"GTK-LOG level={int(level)} {message}", flush=True)


core.GLib.log_set_handler(
    "Gtk",
    core.GLib.LogLevelFlags.LEVEL_CRITICAL | core.GLib.LogLevelFlags.LEVEL_WARNING,
    _log_handler,
    None,
)


def prepare():  # type: ignore[no-untyped-def]
    window = application.get_active_window()
    window.set_title("Focus — Synthetic Answer-Switching Acceptance")
    application._set_ai_view(core.AI_VIEW_AGENT_QA)
    application._ai_panel_revealer.set_reveal_child(True)

    # Start a live snapshot so Session/Latest transitions are meaningful.
    live_markup = "# Live Answer\n*Still live*\n\nLive body paragraph.\n"
    metadata = parse_answer_metadata(live_markup, question="Live question?", partial=False)
    live = AgentAnswerSnapshot(
        answer_id=new_answer_id(),
        markdown=live_markup,
        title=metadata.title,
        subtitle=metadata.subtitle,
        status="complete",
        capture="submit_tool",
        answer_kind="answered",
        stop_reason="toolUse",
        question="Live question?",
    )
    application._agent_live_snapshot = live
    application._display_agent_snapshot(live, is_saved=False)

    application._reload_saved_answers()

    state = {"index": 0, "failures": []}
    style_manager = core.Adw.StyleManager.get_default()

    def step() -> bool:
        i = state["index"]
        if i >= TRANSITIONS:
            _finish(state)
            return False
        answers = application._saved_answers_listing.answers
        saved = answers[i % len(answers)]
        application._on_saved_answer_selected(saved.answer_id)
        if i % 2 == 0:
            application._set_ai_view(core.AI_VIEW_FILE)
            application._set_ai_view(core.AI_VIEW_AGENT_QA)
        if i % 3 == 0:
            application._set_agent_subview(core.AGENT_SUBVIEW_SESSION)
            application._set_agent_subview(core.AGENT_SUBVIEW_ANSWER)
        if i % 5 == 0:
            style_manager.set_color_scheme(
                core.Adw.ColorScheme.FORCE_DARK
                if style_manager.get_dark()
                else core.Adw.ColorScheme.FORCE_LIGHT
            )
        if i % 7 == 0:
            window.set_default_size(600 + (i % 40) * 10, 500 + (i % 30) * 10)
        if i % 11 == 0:
            application._ensure_ai_panel_visible()
        state["index"] = i + 1
        return True

    position_result = {"fraction": None, "ok": False}

    def position_scroll() -> bool:
        output_state = application._ai_outputs.get(core.AI_VIEW_AGENT_QA)
        vadj = output_state.scroller.get_vadjustment()
        total = vadj.get_upper() - vadj.get_lower() - vadj.get_page_size()
        vadj.set_value(vadj.get_lower() + 0.5 * total)
        core.GLib.timeout_add(120, position_leave)
        return False

    def position_leave() -> bool:
        answers = application._saved_answers_listing.answers
        application._on_saved_answer_selected(answers[1].answer_id)
        core.GLib.timeout_add(120, position_return)
        return False

    def position_return() -> bool:
        answers = application._saved_answers_listing.answers
        application._on_saved_answer_selected(answers[0].answer_id)
        core.GLib.timeout_add(200, position_verify)
        return False

    def position_verify() -> bool:
        output_state = application._ai_outputs.get(core.AI_VIEW_AGENT_QA)
        vadj = output_state.scroller.get_vadjustment()
        total = vadj.get_upper() - vadj.get_lower() - vadj.get_page_size()
        fraction = 0.0 if total <= 0 else (vadj.get_value() - vadj.get_lower()) / total
        position_result["fraction"] = fraction
        position_result["ok"] = abs(fraction - 0.5) < 0.15
        state["position"] = position_result
        core.GLib.timeout_add(1, step)
        return False

    def position_start() -> bool:
        answers = application._saved_answers_listing.answers
        application._on_saved_answer_selected(answers[0].answer_id)
        core.GLib.timeout_add(250, position_scroll)
        return False

    def wait_for_listing() -> bool:
        if len(application._saved_answers_listing.answers) < ANSWER_COUNT:
            return True
        core.GLib.timeout_add(100, position_start)
        return False

    core.GLib.timeout_add(50, wait_for_listing)
    return False


def _finish(state: dict) -> None:  # type: ignore[no-untyped-def]
    application._on_saved_answer_selected(application._saved_answers_listing.answers[0].answer_id)
    visible = application._ai_view_stack.get_visible_child_name()
    displayed = application._agent_displayed_snapshot
    expected = application._saved_answers_listing.answers[0]
    position = state.get("position")
    position_ok = bool(position and position.get("ok"))
    ok = (
        visible == core.AI_VIEW_AGENT_QA
        and displayed is not None
        and displayed.answer_id == expected.answer_id
        and critical_count["n"] == 0
        and position_ok
    )
    transitions = state["index"]
    renders = render_counts["answer"] + render_counts["summary"] + render_counts["structured"]
    print(
        f"ACCEPTANCE transitions={transitions} view={visible} "
        f"renders={renders} (answer={render_counts['answer']} "
        f"summary={render_counts['summary']} structured={render_counts['structured']}) "
        f"gtk_criticals={critical_count['n']} "
        f"position_fraction={None if position is None else round(position.get('fraction', -1), 3)} "
        f"position_ok={position_ok} ok={ok}",
        flush=True,
    )
    application._quit_result = 0 if ok else 1
    application.quit()


application.connect("activate", lambda _app: core.GLib.timeout_add(400, prepare))
application.run([])
sys.exit(getattr(application, "_quit_result", 1))
