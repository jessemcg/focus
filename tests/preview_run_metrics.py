"""Disposable, synthetic Copy Trace removal/answer-artifact GUI acceptance.

Run with `uv run python tests/preview_run_metrics.py`. No model calls or real data.
Close only the separately titled preview window when finished.
"""
import json
import os
from pathlib import Path
import sys
import tempfile

root = Path(tempfile.mkdtemp(prefix="focus-metrics-preview-"))
for name in ("HOME", "XDG_CONFIG_HOME", "XDG_CACHE_HOME", "XDG_DATA_HOME", "XDG_STATE_HOME"):
    path = root / name.lower()
    path.mkdir(mode=0o700)
    os.environ[name] = str(path)
os.environ["GSETTINGS_BACKEND"] = "memory"
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from focus import core
from focus import app as module
from focus.agent_answer import create_focus_run_id
from test_agent_answer_polling import _artifact_payload

core.CONFIG_FILE = root / "config.json"
module.APPLICATION_ID = f"com.mcglaw.Focus.MetricsPreview.p{os.getpid()}"
bundle = root / "synthetic"
(bundle / "text_pages").mkdir(parents=True)
(bundle / "text_pages/0001.txt").write_text("Synthetic record. The sample hearing occurred today.\n")
(bundle / "case_name.txt").write_text("Synthetic metrics preview")
application = module.Focus(input_override=bundle)


def prepare():
    window = application.get_active_window()
    window.set_title("Focus — Synthetic Metrics Acceptance")
    application._set_ai_view(core.AI_VIEW_AGENT_QA)
    application._ai_panel_revealer.set_reveal_child(True)
    application._agent_run_id = create_focus_run_id()
    application._agent_answer_artifact_path = root / "answer.json"
    application._agent_terminal_active = True  # synthetic Session view; no subprocess
    for revision in (1, 2):
        text = f"Synthetic answer revision {revision}. The “sample hearing” occurred today."
        application._agent_answer_artifact_path.write_text(json.dumps(_artifact_payload(application._agent_run_id, revision, text)))
        application._agent_answer_artifact_path.chmod(0o600)
        application._poll_agent_answer()
        assert application._agent_last_answer_text == text
    assert not hasattr(application, "_agent_copy_trace_button")
    assert application._agent_answer_button.get_sensitive()
    assert application._agent_session_button.get_sensitive()
    print(f"READY pid={os.getpid()} root={root}", flush=True)
    return False


application.connect("activate", lambda _: core.GLib.timeout_add(500, prepare))
application.run([])
