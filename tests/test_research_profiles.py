import json
from dataclasses import asdict

import pytest

from focus import agent_helper as helper
from focus.profile_contract import ProfileError
from focus.profile_store import ProfileStore
from focus.practice_profiles import bundled_profile_directory, validate_profile_directory
from focus.research_profiles import (
    INPUTS_ENV, PROFILE_REF_ENV, ResearchPin, compile_research, literal_match,
    selected_snapshot_from_environment, assert_environment_inputs,
)


def bundled(name="general"):
    result = validate_profile_directory(bundled_profile_directory(name))
    assert result.draft is not None
    return result.draft


def case(root):
    (root / "text_pages").mkdir(parents=True)
    (root / "text_pages/0001.txt").write_text("The court denied the motion.")
    (root / "artifacts").mkdir()
    (root / "artifacts/source_map.json").write_text(json.dumps({"schema_version": 2, "pages": [], "documents": []}))
    return root


def test_general_ranking_has_no_dependency_preferences():
    general = bundled().resource("search")
    dependency = bundled("california_dependency").resource("search")
    document = [{"type": "report", "label": "Detention Report", "name": "", "date": ""}]
    assert helper._document_rank("Why removal?", document)[2] == 0
    assert helper._document_rank("Why removal?", document, general)[2] == 1
    assert helper._document_rank("Why removal?", document, dependency)[2] == 0
    assert helper._document_rank("Why removal?", document, general)[2] == 1
    assert literal_match("The A+B evaluation", ["a+b"])
    assert not literal_match("The aaab evaluation", ["a+b"])
    assert not literal_match("removed", ["remove"])


def test_profile_compiler_keeps_core_and_guidance_separate():
    general = compile_research(bundled())
    dependency = compile_research(bundled("california_dependency"))
    assert "Never modify case files" in general.skill
    assert "two-to-five-word" in general.skill
    assert "submit_focus_answer" in general.skill
    assert general.component_sha256 != dependency.component_sha256
    assert "Practice research guidance (subordinate)" in general.skill


def test_only_accepted_focus_reference_authorizes_helper_guidance(tmp_path, monkeypatch):
    store = ProfileStore("focus", config_root=tmp_path / "config", data_root=tmp_path / "data")
    profile = bundled()
    monkeypatch.setattr("focus.research_profiles.profile_store", lambda: store)
    monkeypatch.delenv(PROFILE_REF_ENV, raising=False)
    assert selected_snapshot_from_environment() is None
    monkeypatch.setenv(PROFILE_REF_ENV, json.dumps(asdict(profile.ref)))
    with pytest.raises((ProfileError, OSError)):
        selected_snapshot_from_environment()
    store.accept_profile(profile, expected_previous_digest=None)
    assert selected_snapshot_from_environment().ref == profile.ref
    monkeypatch.setenv(PROFILE_REF_ENV, json.dumps(asdict(profile.ref) | {"application": "recordprep"}))
    with pytest.raises(ProfileError, match="wrong_application"):
        selected_snapshot_from_environment()


def test_pin_records_consumed_inputs_without_instructions_and_detects_changes(tmp_path):
    root = case(tmp_path / "case")
    store = ProfileStore("focus", config_root=tmp_path / "config", data_root=tmp_path / "data")
    profile = bundled()
    store.accept_profile(profile, expected_previous_digest=None)
    pin = ResearchPin.capture(root, profile, store=store)
    pin.assert_current(root)
    metadata = pin.metadata()
    assert metadata["research_profile_ref"] == asdict(profile.ref)
    assert metadata["preparation_provenance"] is None
    assert str(root) not in json.dumps(metadata)
    assert profile.resource("research") not in json.dumps(metadata)
    # A changed selection is not evidence that the consumed map changed.
    (root / ".recordprep").mkdir()
    (root / ".recordprep/practice-profile.json").write_text("{}")
    pin.assert_current(root)
    (root / "text_pages/0001.txt").write_text("The court granted the motion.")
    with pytest.raises(ProfileError, match="preparation_changed"):
        pin.assert_current(root)


def test_legacy_pin_clears_inherited_profile_and_helper_rejects_changed_inputs(tmp_path, monkeypatch):
    root = case(tmp_path / "case")
    pin = ResearchPin.capture(root, None)
    env = pin.environment({PROFILE_REF_ENV: "untrusted-inherited-value", "PATH": "/synthetic"})
    assert PROFILE_REF_ENV not in env
    assert env["PATH"] == "/synthetic"
    monkeypatch.setenv(INPUTS_ENV, env[INPUTS_ENV])
    assert_environment_inputs(root)
    (root / "artifacts/case_overview.md").write_text("Navigation changed.")
    with pytest.raises(ProfileError, match="preparation_changed"):
        assert_environment_inputs(root)


def test_selections_are_explicit_private_cas_and_not_case_writes(tmp_path):
    from focus.research_selection import read_selection, apply_selection, resolve_selection
    root = case(tmp_path / "case")
    store = ProfileStore("focus", config_root=tmp_path / "config", data_root=tmp_path / "data")
    before = sorted(str(path.relative_to(root)) for path in root.rglob("*"))
    assert read_selection(root, store=store) is None
    assert not store.config_root.exists()
    profile = bundled()
    store.accept_profile(profile, expected_previous_digest=None)
    chosen = apply_selection(root, profile.ref, expected_previous=None, store=store)
    assert resolve_selection(root, store=store).ref == profile.ref
    with pytest.raises(ProfileError, match="stale_research_selection"):
        apply_selection(root, None, expected_previous=None, store=store)
    legacy = apply_selection(root, None, expected_previous=chosen, store=store)
    assert legacy is not None and legacy.profile_ref is None
    assert read_selection(root, store=store) == legacy
    assert sorted(str(path.relative_to(root)) for path in root.rglob("*")) == before


def test_pin_cannot_be_reused_for_another_identical_case(tmp_path):
    first = case(tmp_path / "first")
    second = case(tmp_path / "second")
    pin = ResearchPin.capture(first, None)
    with pytest.raises(ProfileError, match="preparation_changed"):
        pin.assert_current(second)


def test_saved_context_roundtrip_needs_no_installed_profile_and_cannot_downgrade(tmp_path, monkeypatch):
    from dataclasses import replace
    from test_saved_answers import _answer
    from focus.saved_answers import save_saved_answer, load_saved_answer, saved_answers_dir, AgentAnswerSnapshot
    from focus.research_profiles import research_context_bytes
    root = case(tmp_path / "case")
    store = ProfileStore("focus", config_root=tmp_path / "config", data_root=tmp_path / "data")
    profile = bundled()
    store.accept_profile(profile, expected_previous_digest=None)
    pin = ResearchPin.capture(root, profile, store=store)
    answer = replace(_answer(), schema_version=2, research_context=research_context_bytes(pin.metadata()))
    assert save_saved_answer(root, answer).error == ""
    def no_instructions():
        raise AssertionError("Recorded metadata must not resolve profile instructions")
    monkeypatch.setattr("focus.research_profiles.profile_store", no_instructions)
    loaded = load_saved_answer(root, answer.answer_id)
    assert loaded.error == ""
    assert loaded.answer == answer
    from focus.answer_presentation import profile_context_label
    label = profile_context_label(loaded.answer.research_context)
    assert "Research: general-court-record" in label
    assert "Preparation: legacy / unassigned" in label
    assert "Different specialties" not in label
    assert profile_context_label(None) == "Legacy / unassigned profile provenance"
    assert "unavailable" in profile_context_label(b"not json")
    context = pin.metadata()
    context["preparation_provenance"] = {
        "schema_version": 1, "profile_ref": asdict(profile.ref) | {"application": "recordprep", "version": "independent", "content_sha256": "a" * 64},
        "components": {"overview": "b" * 64},
    }
    assert "Different specialties" not in profile_context_label(research_context_bytes(context))
    context["preparation_provenance"]["profile_ref"]["specialty_id"] = "synthetic-third-specialty"
    assert "Different specialties" in profile_context_label(research_context_bytes(context))
    assert AgentAnswerSnapshot.from_saved(loaded.answer).to_saved() == answer
    assert save_saved_answer(root, replace(answer, schema_version=1)).error == "invalid_research_context"
    path = saved_answers_dir(root) / (answer.answer_id + ".json")
    malformed = answer.to_payload() | {"schema_version": 1}
    path.write_text(json.dumps(malformed))
    assert load_saved_answer(root, answer.answer_id).error == "unsupported_schema"


def test_profile_era_map_requires_explicit_choice_without_default_or_counterpart(tmp_path):
    from focus.research_selection import requires_confirmation, apply_selection
    root = case(tmp_path / "case")
    store = ProfileStore("focus", config_root=tmp_path / "config", data_root=tmp_path / "data")
    assert requires_confirmation(root, store=store)
    payload = json.loads((root / "artifacts/source_map.json").read_text())
    payload.update({"schema_version": 3, "preparation_provenance": {
        "schema_version": 1, "profile_ref": asdict(bundled().ref) | {"application": "recordprep"},
        "components": {"overview": "a" * 64}}})
    (root / "artifacts/source_map.json").write_text(json.dumps(payload))
    assert requires_confirmation(root, store=store)
    assert not store.config_root.exists()
    apply_selection(root, None, expected_previous=None, store=store)
    assert not requires_confirmation(root, store=store)


def test_staged_resources_and_actual_helper_share_the_pin(tmp_path, monkeypatch):
    import os
    import subprocess
    import sys
    from focus.practice_profiles import profile_store
    from focus.research_profiles import stage_research_resources, COMPONENT_ENV
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "config"))
    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path / "data"))
    store = profile_store()
    profile = bundled()
    store.accept_profile(profile, expected_previous_digest=None)
    root = case(tmp_path / "case")
    pin = ResearchPin.capture(root, profile, store=store)
    workspace = tmp_path / "workspace"
    workspace.mkdir(mode=0o700)
    staged = stage_research_resources(pin, workspace)
    assert (staged / "skills/focus-answer-record-questions/SKILL.md").read_text() == compile_research(profile).skill
    assert "court-record investigator" in (staged / "SYSTEM.md").read_text()
    assert (staged / "extensions/focus-record-agent.ts").read_bytes() == (helper.Path(helper.__file__).parent / "agent_resources/extensions/focus-record-agent.ts").read_bytes()
    command = [sys.executable, helper.__file__, "--case-root", str(root), "context", "--json"]
    env = pin.environment(os.environ)
    success = subprocess.run(command, env=env, text=True, capture_output=True)
    assert success.returncode == 0, success.stdout + success.stderr
    assert "error" not in json.loads(success.stdout)
    env[COMPONENT_ENV] = "0" * 64
    rejected = subprocess.run(command, env=env, text=True, capture_output=True)
    assert rejected.returncode == 1
    assert json.loads(rejected.stdout)["error_code"] == "research_contract_changed"


def test_manifest_selected_overview_and_symlinked_sources(tmp_path):
    root = case(tmp_path / "case")
    (root / "custom.md").write_text("Navigation only.")
    (root / "manifest.json").write_text(json.dumps({"files": {"case_overview": "custom.md"}}))
    pin = ResearchPin.capture(root, None)
    (root / "custom.md").write_text("New navigation.")
    with pytest.raises(ProfileError, match="preparation_changed"):
        pin.assert_current(root)
    (root / "text_pages/0002.txt").symlink_to(root / "custom.md")
    with pytest.raises((ProfileError, OSError)):
        ResearchPin.capture(root, None)
