import json
from types import SimpleNamespace
from unittest.mock import Mock

from focus import app as ui
from focus import practice_profiles as api
from focus import research_selection
from focus.profile_store import ProfileStore


def setup_case(tmp_path, monkeypatch):
    root = tmp_path / "case"
    (root / "text_pages").mkdir(parents=True)
    (root / "artifacts").mkdir()
    (root / "text_pages/0001.txt").write_text("The court denied the motion.")
    (root / "artifacts/source_map.json").write_text(json.dumps({"schema_version": 2, "pages": [], "documents": []}))
    store = ProfileStore("focus", config_root=tmp_path / "config", data_root=tmp_path / "data")
    monkeypatch.setattr(api, "profile_store", lambda: store)
    monkeypatch.setattr(research_selection, "profile_store", lambda: store)
    monkeypatch.setattr(ui, "Vte", object())
    monkeypatch.setattr(ui, "load_ai_settings", lambda: SimpleNamespace())
    owner = SimpleNamespace(_agent_terminal=object(), _record_layout=SimpleNamespace(root=root),
                            _agent_question_entry=Mock(get_text=lambda: "Synthetic question?"),
                            _agent_followup_entry=Mock(), _agent_terminal_unavailable=Mock(),
                            _ai_transient_toast=Mock(), _open_practice_profiles=Mock(),
                            _stop_agent_terminal=Mock(), _stop_agent_answer_polling=Mock(),
                            _clear_agent_answer=Mock(), _set_agent_subview=Mock(),
                            _write_agent_prompt_file=Mock(return_value=tmp_path / "synthetic-prompt"),
                            _compose_agent_prompt=Mock(return_value="Synthetic prompt"), _start_agent_terminal=Mock())
    return root, store, owner


def test_actual_question_controller_requires_confirmation_before_clearing_answer(tmp_path, monkeypatch):
    root, store, owner = setup_case(tmp_path, monkeypatch)
    ui.Focus._launch_agent_question(owner)
    owner._open_practice_profiles.assert_called_once()
    owner._clear_agent_answer.assert_not_called()
    owner._stop_agent_terminal.assert_not_called()
    assert not list(store.config_root.glob("**/*"))
    profile = api.validate_profile_directory(api.bundled_profile_directory("general")).draft
    store.accept_profile(profile, expected_previous_digest=None)
    research_selection.apply_selection(root, profile.ref, expected_previous=None, store=store)
    ui.Focus._launch_agent_question(owner)
    owner._clear_agent_answer.assert_called_once()
    owner._start_agent_terminal.assert_called_once()
    pin = owner._agent_research_pin
    assert pin.snapshot.ref == profile.ref
    # A new default never retargets an already captured research pin.
    dependency = api.validate_profile_directory(api.bundled_profile_directory("california_dependency")).draft
    store.accept_profile(dependency, expected_previous_digest=None)
    store.set_default(dependency.ref)
    pin.assert_current(root)
    assert pin.snapshot.ref == profile.ref
    # Missing accepted guidance rejects a new question BEFORE clearing old output.
    instruction = next(path for path, _data in profile.files if path.endswith(".md"))
    (store.data_root / "snapshots" / profile.ref.content_sha256 / instruction).unlink()
    ui.Focus._launch_agent_question(owner)
    assert owner._clear_agent_answer.call_count == 1
    assert owner._start_agent_terminal.call_count == 1


def test_actual_followup_worker_rechecks_pinned_sources_before_transport(tmp_path, monkeypatch):
    root, store, owner = setup_case(tmp_path, monkeypatch)
    research_selection.apply_selection(root, None, expected_previous=None, store=store)
    ui.Focus._launch_agent_question(owner)
    pin = owner._agent_research_pin
    assert pin.snapshot is None  # Explicit legacy sessions are also source-pinned.
    owner._on_agent_followup_result = Mock()
    client = Mock()
    client.return_value.submit.return_value = "submitted"
    monkeypatch.setattr(ui, "FollowUpClient", client)
    monkeypatch.setattr(ui.GLib, "idle_add", lambda callback, *args: callback(*args))
    endpoint = object()
    ui.Focus._agent_followup_worker(owner, endpoint, 1, "Synthetic follow-up", pin, root)
    client.assert_called_once_with(endpoint)
    assert owner._on_agent_followup_result.call_args.args[-1] == ""
    (root / "text_pages/0001.txt").write_text("Source changed after the session began.")
    ui.Focus._agent_followup_worker(owner, endpoint, 1, "Do not send this", pin, root)
    assert client.call_count == 1
    assert owner._on_agent_followup_result.call_args.args[-1] == "research_changed"
