import json
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from focus import app as ui, research_runtime as runtime


def setup_case(tmp_path, monkeypatch):
    root = tmp_path / "case"
    (root / "text_pages").mkdir(parents=True)
    (root / "artifacts").mkdir()
    (root / "text_pages/0001.txt").write_text("The court denied the motion.")
    (root / "artifacts/source_map.json").write_text(json.dumps({"schema_version": 2, "pages": [], "documents": []}))
    monkeypatch.setattr(ui, "Vte", object())
    monkeypatch.setattr(ui, "load_ai_settings", lambda: SimpleNamespace(pi_agent_command="/usr/bin/true"))
    owner = SimpleNamespace(_agent_terminal=object(), _record_layout=SimpleNamespace(root=root),
                            _agent_question_entry=Mock(get_text=lambda: "Synthetic question?"),
                            _agent_terminal_unavailable=Mock(), _ai_transient_toast=Mock(),
                            _resolve_agent_command=ui.Focus._resolve_agent_command,
                            _capture_question_pin=ui.Focus._capture_question_pin,
                            _start_agent_terminal=Mock())
    return root, owner


def test_fresh_question_needs_no_profile_and_failed_preflight_preserves_answer(tmp_path, monkeypatch):
    root, owner = setup_case(tmp_path, monkeypatch)
    ui.Focus._launch_agent_question(owner)
    owner._start_agent_terminal.assert_called_once()
    question, label, case, pin, argv = owner._start_agent_terminal.call_args.args
    assert (question, label, case, argv) == ("Synthetic question?", "Synthetic question?", root, ["/usr/bin/true"])
    assert pin.metadata()["research_method"]["id"] == "focus-record-qa"
    (root / "artifacts/source_map.json").write_text("invalid map")
    ui.Focus._launch_agent_question(owner)
    assert owner._start_agent_terminal.call_count == 1


@pytest.mark.parametrize("changed", ["source", "map", "overview", "method", "wrong_case"])
def test_followup_rechecks_before_transport(tmp_path, monkeypatch, changed):
    root, owner = setup_case(tmp_path, monkeypatch)
    ui.Focus._launch_agent_question(owner)
    pin = owner._start_agent_terminal.call_args.args[3]
    owner._on_agent_followup_result = Mock()
    client = Mock()
    client.return_value.submit.return_value = "submitted"
    monkeypatch.setattr(ui, "FollowUpClient", client)
    monkeypatch.setattr(ui.GLib, "idle_add", lambda callback, *args: callback(*args))
    endpoint = object()
    ui.Focus._agent_followup_worker(owner, endpoint, 1, "Synthetic follow-up", pin, root)
    client.assert_called_once_with(endpoint)
    assert owner._on_agent_followup_result.call_args.args[-1] == ""
    if changed == "method":
        compiled = runtime.compile_research()
        from dataclasses import replace
        monkeypatch.setattr(runtime, "compile_research", lambda: replace(compiled, component_sha256="0" * 64))
    elif changed == "wrong_case":
        root = tmp_path
    else:
        target = {"source": "text_pages/0001.txt", "map": "artifacts/source_map.json", "overview": "artifacts/case_overview.md"}[changed]
        (root / target).write_text("Changed input")
    ui.Focus._agent_followup_worker(owner, endpoint, 1, "Do not send", pin, root)
    assert client.call_count == 1
    assert owner._on_agent_followup_result.call_args.args[-1] == "research_changed"
