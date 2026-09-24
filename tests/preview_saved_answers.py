"""Disposable, synthetic saved-answer GUI acceptance for Focus.

Run with `uv run python tests/preview_saved_answers.py`.  It uses a temporary
HOME/XDG configuration, a unique application id, a synthetic bundle, and no
model calls.  It never touches a real case, real settings, or the production
application instance.  Close only the separately titled preview window.
"""
import json
import os
from pathlib import Path
import sys
import tempfile

root = Path(tempfile.mkdtemp(prefix="focus-saved-preview-"))
for name in ("HOME", "XDG_CONFIG_HOME", "XDG_CACHE_HOME", "XDG_DATA_HOME", "XDG_STATE_HOME"):
    path = root / name.lower()
    path.mkdir(mode=0o700)
    os.environ[name] = str(path)
os.environ["GSETTINGS_BACKEND"] = "memory"
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from focus import core
from focus import app as module
from focus.answer_metadata import parse_answer_metadata
from focus.saved_answers import (
    AgentAnswerSnapshot,
    SavedAnswer,
    SAVED_ANSWERS_SCHEMA_VERSION,
    new_answer_id,
    save_saved_answer,
    saved_answers_dir,
)

core.CONFIG_FILE = root / "config.json"
module.APPLICATION_ID = f"com.mcglaw.Focus.SavedPreview.p{os.getpid()}"

bundle = root / "synthetic"
(bundle / "text_pages").mkdir(parents=True)
(bundle / "text_pages" / "0001.txt").write_text(
    "Synthetic record. The sample hearing occurred today with weekly supervised visits.\n"
)
(bundle / "case_name.txt").write_text("Synthetic saved-answer preview")

for index in range(1, 6):
    markup = f"# Synthetic Answer {index}\n*Bottom line {index}*\n\nSynthetic body {index}.\n"
    snapshot = AgentAnswerSnapshot(
        answer_id=new_answer_id(),
        markdown=markup,
        title=f"Synthetic Answer {index}",
        subtitle=f"Bottom line {index}",
        status="partial" if index == 3 else "complete",
        capture="submit_tool",
        answer_kind="answered",
        stop_reason="length" if index == 3 else "toolUse",
        question=f"Question {index}?",
    )
    save_saved_answer(bundle, snapshot.to_saved())

application = module.Focus(input_override=bundle)


def prepare():
    window = application.get_active_window()
    window.set_title("Focus — Synthetic Saved-Answer Acceptance")
    application._set_ai_view(core.AI_VIEW_AGENT_QA)
    application._ai_panel_revealer.set_reveal_child(True)

    markup = "# Weekly Visits Continued\n*Still supervised*\n\nThe record says \u201cweekly supervised visits\u201d.\n"
    metadata = parse_answer_metadata(markup, question="Are visits supervised?", partial=False)
    live = AgentAnswerSnapshot(
        answer_id=new_answer_id(),
        markdown=markup,
        title=metadata.title,
        subtitle=metadata.subtitle,
        status="complete",
        capture="submit_tool",
        answer_kind="answered",
        stop_reason="toolUse",
        question="Are visits supervised?",
    )
    application._agent_live_snapshot = live
    application._display_agent_snapshot(live, is_saved=False)
    application._agent_initial_question = "Are visits supervised?"

    # Show the saved-answer library, including a partial entry.
    application._reload_saved_answers()
    library = saved_answers_dir(bundle)
    count = len(list(library.glob("*.json")))
    assert count == 5, count
    application._saved_answers_popover.popover.popup()

    def _select_newest() -> bool:
        listing = application._saved_answers_listing
        if listing.answers:
            application._on_saved_answer_selected(listing.answers[0].answer_id)
            print("SELECTED newest saved answer", flush=True)
        return False

    core.GLib.timeout_add(1500, _select_newest)
    print(f"READY pid={os.getpid()} root={root} saved={count}", flush=True)
    return False


application.connect("activate", lambda _: core.GLib.timeout_add(600, prepare))
application.run([])
