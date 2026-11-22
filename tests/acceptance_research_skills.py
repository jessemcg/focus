"""Native GTK, VTE, and real Pi against a loopback-only synthetic provider.

Run in a disposable checkout: python tests/acceptance_research_skills.py
Use --preview 690 (or 950) for a temporary window intended for keyboard testing.
"""
from __future__ import annotations

from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import os
from pathlib import Path
import shutil
import sys
import tempfile
import threading
import time

PI = shutil.which("pi")
if PI is None:
    raise SystemExit("Pi must be installed for this offline acceptance.")
TEMP = tempfile.TemporaryDirectory(prefix="focus-skills-gtk-")
ROOT = Path(TEMP.name)
for key in ("HOME", "XDG_CONFIG_HOME", "XDG_DATA_HOME", "XDG_CACHE_HOME", "XDG_STATE_HOME",
            "XDG_RUNTIME_DIR", "PI_CODING_AGENT_DIR", "FOCUS_CONFIG_DIR"):
    path = ROOT / key.lower()
    path.mkdir(mode=0o700)
    os.environ[key] = str(path)
os.environ.update(GSETTINGS_BACKEND="memory", PI_RUN_METRICS_ENABLED="0", PI_OFFLINE="1")
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from focus import app as module, core
from focus.agent_followup import FollowUpClient, FollowUpError
from focus.research_skills import SkillPreferences, discover_skills, read_preferences, save_preferences
from focus.saved_answers import list_saved_answers

REQUEST = "# Inspection timeline\n\n## Scheduling\nExplain who was notified.\n\n## Outcome\nSeparate recorded outcomes from gaps in the examined material.\n"
QUOTE1 = "notice was delivered before the scheduled site inspection"
QUOTE2 = "the inspection was postponed until the gate reopened"
ANSWER = (f"# Inspection Was Postponed\n*Access was unavailable*\n\n## Scheduling\nThe clerk confirmed “{QUOTE1}”."
          f"\n\n## Outcome\nThe supervisor wrote that “{QUOTE2}”.")
requests = []
blocked = threading.Event()
blocked.set()
partial = threading.Event()


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *args):
        pass

    def do_POST(self):
        payload = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
        requests.append(payload)
        blocked.wait(10)
        last = next(message for message in reversed(payload["messages"]) if message["role"] == "user")
        if not any(message["role"] == "tool" for message in payload["messages"]):
            name, arguments = "read", {"path": "0001.txt"}
        else:
            name, arguments = "submit_focus_answer", {"answer_kind": "answered", "markdown": ANSWER}
        if partial.is_set() and ("Follow-up" in str(last) or "partial" in str(last)):
            delta, reason = {"role": "assistant", "content": ANSWER}, "length"
        else:
            delta, reason = {"role": "assistant", "tool_calls": [{
                "index": 0, "id": f"call_{len(requests)}", "type": "function",
                "function": {"name": name, "arguments": json.dumps(arguments)},
            }]}, "tool_calls"
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream")
        self.end_headers()
        try:
            for update, end in ((delta, None), ({}, reason)):
                event = {"id": "synthetic", "object": "chat.completion.chunk", "created": 1,
                         "model": payload["model"], "choices": [{"index": 0, "delta": update, "finish_reason": end}]}
                self.wfile.write(("data: " + json.dumps(event) + "\n\n").encode())
            self.wfile.write(b"data: [DONE]\n\n")
            self.wfile.flush()
        except (BrokenPipeError, ConnectionResetError):
            pass


server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
threading.Thread(target=server.serve_forever, daemon=True).start()
agent = Path(os.environ["PI_CODING_AGENT_DIR"])
models = [{"id": name, "name": "Fixture Flash", "reasoning": True, "contextWindow": 32768,
           "maxTokens": 1024, "input": ["text"], "compat": {"supportsDeveloperRole": False}}
          for name in ("ordinary-fast", "skill-standard")]
(agent / "models.json").write_text(json.dumps({"providers": {"synthetic": {
    "baseUrl": f"http://127.0.0.1:{server.server_port}/v1", "api": "openai-completions",
    "apiKey": "SYNTHETIC_NOT_A_CREDENTIAL", "models": models,
}}}))
# The controlled shim can drop --model only for the VTE invocation, simulating
# an identity change after the independently authenticated RPC catalog check.
shim = ROOT / "pi-fixture"
shim.write_text(f'''#!{sys.executable}
import os, sys
from pathlib import Path
args = sys.argv[1:]
if "rpc" not in args and Path({str(ROOT / 'mismatch')!r}).exists() and "--model" in args:
    args[args.index("--model") + 1] = "ordinary-fast"
os.execv({PI!r}, [{PI!r}, *args])
''')
shim.chmod(0o700)
module.PROJECT_PI_SETTINGS_PATH.parent.mkdir()
ordinary = b'{ "defaultProvider": "synthetic", "defaultModel": "ordinary-fast", "defaultThinkingLevel": "off", "retry": {"enabled": false} }\n'
module.PROJECT_PI_SETTINGS_PATH.write_bytes(ordinary)
core.CONFIG_FILE.write_text(json.dumps({"pi_agent_command": str(shim)}))
case = ROOT / "record"
(case / "text_pages").mkdir(parents=True)
(case / "artifacts").mkdir()
(case / "case_name.txt").write_text("Synthetic Research Skills")
(case / "text_pages/0001.txt").write_text(f"The clerk said {QUOTE1}.\nThe supervisor wrote that {QUOTE2}.\n")
(case / "artifacts/source_map.json").write_text(json.dumps({"schema_version": 2, "documents": [], "pages": [
    {"file_page": 1, "text_path": "text_pages/0001.txt", "citation_label": "RT 1"}]}))
folder = ROOT / "skills"
folder.mkdir()
skill_file = folder / "inspection.md"
skill_file.write_text("---\nmodel: ignored\n---\n" + REQUEST)
(folder / "alternate").mkdir()
(folder / "alternate/SKILL.md").write_text("# Inspection timeline\n\nCompare two notices.\n")
application_preferences = SkillPreferences(str(folder), ("synthetic", "skill-standard"), "low")
save_preferences(application_preferences, "missing")
module.APPLICATION_ID = f"com.mcglaw.Focus.ResearchSkillsTest.p{os.getpid()}"
app = module.Focus(input_override=case)
width = int(sys.argv[2]) if len(sys.argv) > 2 and sys.argv[1] == "--preview" else int(os.getenv("FOCUS_TEST_WIDTH", "690"))
build_window = app._ensure_window


def build_at_width():
    build_window()
    app.win.set_default_size(width, 740)


app._ensure_window = build_at_width
errors = []


def bridge_ready():
    if not app._agent_followup_endpoint:
        return False
    try:
        return FollowUpClient(app._agent_followup_endpoint, timeout=0.5).status() == "ready"
    except FollowUpError:
        return False


def choose():
    skill = next(skill for skill in discover_skills(str(folder)).skills if skill.key == "inspection.md")
    app._start_research_skill(str(folder), skill)


def ready_for(count):
    return len(requests) >= count and app._agent_live_snapshot is not None and bridge_ready()


def ordinary_question(text):
    app._agent_question_entry.set_text(text)
    app._agent_question_entry.emit("activate")


def verify_links():
    state = app._get_ai_output_state(core.AI_VIEW_AGENT_QA)
    for quote in (QUOTE1, QUOTE2):
        link = next(link for link in state.link_lookup.values() if link[1] == quote)
        app._activate_link(link)
        yield lambda: app._grep_phrase_raw == quote and bool(app._grep_hits)
        assert app._matching_pages == [1], app._matching_pages
        app._clear_grep_state()


def scenario():
    picker = app._research_skills_picker
    yield lambda: picker.get_width() > 0
    assert app.win.get_width() == width
    assert picker.get_width() < 100
    assert app._agent_question_entry.get_width() > 200 and app._agent_followup_entry.get_width() > 200
    toggle = picker.get_first_child()
    assert toggle.grab_focus() and toggle.activate()  # GTK's default menu button keyboard action
    yield lambda: picker._list.get_row_at_index(1) is not None
    assert app.win.get_focus().is_ancestor(picker._search)
    picker._search.set_text("inspection.md")
    assert picker._list.get_row_at_index(1) is None
    assert not requests
    # Down moves from search to the result; Gtk.Widget.activate is the row's Enter action.
    assert picker._on_search_key(None, core.Gdk.KEY_Down, 0, 0)
    row = picker._list.get_row_at_index(0)
    assert app.win.get_focus() is row
    skill_file.write_text(REQUEST + "Edited after browsing.\n")
    assert row.activate()
    yield lambda: picker._popover.get_mapped() and picker._list.get_row_at_index(1) is not None
    assert not requests and not app._agent_terminal_active
    picker.popdown()
    skill_file.write_text("---\nmodel: ignored\n---\n" + REQUEST)

    blocked.clear()
    ordinary_question("What does the record show?")
    yield lambda: len(requests) == 1
    ordinary_run = app._agent_run_id
    app._agent_question_entry.set_text("Keep this draft")
    choose()
    choose()  # double activation
    yield lambda: app._skill_replacement_dialog is not None
    assert app._skill_replacement_dialog.get_default_response() == "cancel"
    app._skill_replacement_dialog.response("cancel")
    assert app._agent_run_id == ordinary_run and app._agent_question_entry.get_text() == "Keep this draft"
    blocked.set()
    yield lambda: ready_for(2)
    app._on_save_answer_clicked(None)
    yield lambda: bool(app._agent_saved_ids)
    first_saved = app._agent_live_snapshot.answer_id

    # An idle session with an already saved answer is replaced without a dialog.
    choose()
    yield lambda: ready_for(4) and app._agent_run_id != ordinary_run
    assert app._skill_replacement_dialog is None
    assert app._agent_live_snapshot.question == "Research skill: Inspection timeline"
    assert len(list_saved_answers(case).answers) == 1  # no implicit save
    yield from verify_links()
    app._on_save_answer_clicked(None)
    skill_answer = app._agent_live_snapshot.answer_id
    yield lambda: skill_answer in app._agent_saved_ids
    assert skill_file.read_text().endswith(REQUEST)  # wrapper did not get source path

    partial.set()
    blocked.clear()
    app._agent_followup_entry.set_text("Follow-up: What remains unclear?")
    app._agent_followup_entry.emit("activate")
    yield lambda: len(requests) == 5
    app._on_saved_answer_selected(first_saved)
    blocked.set()
    yield lambda: app._agent_live_snapshot.status == "partial" and bridge_ready()
    assert app._agent_displayed_snapshot.answer_id == first_saved
    assert app._latest_answer_pending
    # Unsaved latest live answer must be noticed even while viewing the older saved answer.
    choose()
    yield lambda: app._skill_replacement_dialog is not None
    app._skill_replacement_dialog.response("cancel")
    assert app._agent_displayed_snapshot.answer_id == first_saved
    assert len(requests) == 5

    partial.clear()
    ordinary_question("What does the original notice say?")
    yield lambda: ready_for(7)
    assert [p["model"] for p in requests] == ["ordinary-fast"] * 2 + ["skill-standard"] * 3 + ["ordinary-fast"] * 2
    for payload in requests:
        assert {tool["function"]["name"] for tool in payload["tools"]} == {"read", "focus_record", "submit_focus_answer"}
    for payload in requests[2:5]:
        user = json.dumps([m for m in payload["messages"] if m["role"] == "user"], ensure_ascii=False)
        assert json.dumps(REQUEST, ensure_ascii=False)[1:-1] in user
        assert "continuous, verbatim source quotations normally containing 6–12 words" in user
        assert "explicitly requested report" in user
        assert "model: ignored" not in user
    assert any(m["role"] == "tool" and QUOTE1 in str(m["content"]) for m in requests[3]["messages"])

    unavailable = SkillPreferences(str(folder), ("synthetic", "nonexistent"))
    save_preferences(unavailable, read_preferences()[1])
    ordinary_run = app._agent_run_id
    choose()
    yield lambda: app._skill_launch_token is None
    assert len(requests) == 7 and app._agent_run_id == ordinary_run
    save_preferences(application_preferences, read_preferences()[1])
    (ROOT / "mismatch").touch()
    choose()
    yield lambda: app._skill_replacement_dialog is not None
    app._skill_replacement_dialog.response("start")
    yield lambda: "Research not sent" in app._agent_answer_status and not app._agent_terminal_active
    assert len(requests) == 7
    (ROOT / "mismatch").unlink()

    choose()
    other_case = ROOT / "other-record"
    shutil.copytree(case, other_case, ignore=shutil.ignore_patterns(".focus"))
    app._apply_input_dir(other_case, persist=False)  # invalidates the queued preflight
    assert app._skill_launch_token is None and not app._agent_terminal_active
    app._apply_input_dir(case, persist=False)
    # Reopen after removing the skill; rendered quote links still resolve.
    skill_file.unlink()
    app._on_saved_answer_selected(skill_answer)
    yield lambda: app._agent_displayed_snapshot and app._agent_displayed_snapshot.answer_id == skill_answer
    yield from verify_links()
    assert len(requests) == 7
    save_preferences(SkillPreferences(str(folder)), read_preferences()[1])
    inherited, = discover_skills(str(folder)).skills
    app._start_research_skill(str(folder), inherited)
    yield lambda: ready_for(9)
    assert [payload["model"] for payload in requests[7:]] == ["ordinary-fast"] * 2
    assert app._skill_replacement_dialog is None
    assert module.PROJECT_PI_SETTINGS_PATH.read_bytes() == ordinary
    app._stop_agent_terminal()
    workspace_parent = Path(os.environ["XDG_CACHE_HOME"]) / "focus-agent-workspaces"
    yield lambda: not list(workspace_parent.glob("workspace.*"))
    previous = app._agent_displayed_snapshot
    build_terminal = app._build_agent_terminal

    def unspawnable_terminal():
        terminal = build_terminal()

        def fail(*_args):
            assert any(workspace_parent.glob("workspace.*/tmp*"))  # prepared prompt copy
            raise OSError("synthetic VTE launch failure")

        terminal.spawn_async = fail
        return terminal

    app._build_agent_terminal = unspawnable_terminal
    ordinary_question("This must fail before inference.")
    assert app._agent_displayed_snapshot is previous
    assert not list(workspace_parent.glob("workspace.*")) and len(requests) == 9
    print(f"PASS ({width}px): native Skills, confirmation and cancellation, two models and follow-up, zero-request preflight/recheck, partial and saved answers, linked source matches")


def begin():
    app._ensure_ai_panel_visible()
    app._set_ai_view(core.AI_VIEW_AGENT_QA)
    app._research_skills_picker.grab_focus()
    if "--preview" in sys.argv:
        print(f"Preview {width}px: {ROOT}", flush=True)
        return False
    checks = scenario()
    predicate = None
    deadline = 0

    def tick():
        nonlocal predicate, deadline
        try:
            if predicate is not None and not predicate():
                assert time.monotonic() < deadline, (predicate.__code__.co_firstlineno, len(requests), app._agent_answer_status,
                                                      app._agent_terminal.get_text_format(module.Vte.Format.TEXT))
                return True
            predicate = next(checks)
            deadline = time.monotonic() + 20
            return True
        except StopIteration:
            app.quit()
        except BaseException as exc:
            import traceback
            traceback.print_exc()
            errors.append(exc)
            app._stop_agent_terminal()
            app.quit()
        return False

    core.GLib.timeout_add(80, tick)
    return False


app.connect_after("activate", lambda *_: core.GLib.idle_add(begin))
try:
    app.run([sys.argv[0]])
finally:
    blocked.set()
    server.shutdown()
    server.server_close()
    TEMP.cleanup()
if errors:
    raise SystemExit(1)
