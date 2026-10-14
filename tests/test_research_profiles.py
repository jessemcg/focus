"""Neutral runtime and historical context compatibility (no profile lookup)."""
import json
import os
import shutil
import subprocess
import sys
from dataclasses import replace
from pathlib import Path

import pytest

from focus import agent_helper as helper, research_runtime as runtime
from focus.profile_contract import ProfileError
from focus.research_context import research_context_bytes, research_context_payload
from focus.answer_presentation import research_context_label
from test_profile_artifacts import provenance


def case(root, specialty=None):
    (root / "text_pages").mkdir(parents=True)
    (root / "text_pages/0001.txt").write_text("The court denied the motion.")
    (root / "artifacts").mkdir()
    payload = {"schema_version": 2, "pages": [], "documents": []}
    if specialty:
        prep = provenance()
        prep["profile_ref"]["specialty_id"] = specialty
        payload.update(schema_version=3, preparation_provenance=prep)
    (root / "artifacts/source_map.json").write_text(json.dumps(payload))
    return root


@pytest.mark.parametrize("legacy", [None, "not json", "{}", '{"application":"recordprep"}'])
def test_neutral_method_invariant_and_retired_stores_inert(tmp_path, monkeypatch, legacy):
    config = tmp_path / "config"
    config.mkdir()
    sentinel = config / "profiles.json"
    sentinel.write_text("corrupt retired store")
    monkeypatch.setenv("FOCUS_CONFIG_DIR", str(config))
    if legacy is not None:
        monkeypatch.setenv(runtime.PROFILE_REF_ENV, legacy)
    else:
        monkeypatch.delenv(runtime.PROFILE_REF_ENV, raising=False)
    compiled = runtime.compile_research()
    for specialty in ("synthetic-civil", "california-juvenile-dependency", "arbitrary-third"):
        root = case(tmp_path / specialty, specialty)
        pin = runtime.ResearchPin.capture(root)
        assert pin.research_component_sha256 == compiled.component_sha256
        assert runtime.compile_research().skill == compiled.skill
        assert runtime.PROFILE_REF_ENV not in pin.environment(os.environ)
        pin.assert_current(root)
    assert sentinel.read_text() == "corrupt retired store"
    assert set(config.iterdir()) == {sentinel}
    assert "two-to-five-word" in compiled.skill and "submit_focus_answer" in compiled.skill
    assert "Practice research guidance" not in compiled.skill


@pytest.mark.parametrize("changed", ["source", "map", "overview", "manifest", "inventory", "selected_overview"])
def test_pin_rejects_changed_consumed_inputs(tmp_path, monkeypatch, changed):
    root = case(tmp_path / "case")
    if changed == "selected_overview":
        (root / "custom.md").write_text("Navigation only.")
        (root / "manifest.json").write_text(json.dumps({"files": {"case_overview": "custom.md"}}))
    pin = runtime.ResearchPin.capture(root)
    for key, value in pin.environment().items():
        monkeypatch.setenv(key, value)
    runtime.assert_environment_inputs(root)
    targets = {"source": "text_pages/0001.txt", "map": "artifacts/source_map.json",
               "overview": "artifacts/case_overview.md", "manifest": "manifest.json",
               "inventory": "text_pages/0002.txt", "selected_overview": "custom.md"}
    (root / targets[changed]).write_text("Changed input")
    with pytest.raises((ProfileError, OSError)):
        pin.assert_current(root)
    with pytest.raises((ProfileError, OSError)):
        runtime.assert_environment_inputs(root)


def test_wrong_case_and_unsafe_source_rejected(tmp_path):
    first, second = case(tmp_path / "first"), case(tmp_path / "second")
    pin = runtime.ResearchPin.capture(first)
    with pytest.raises(ProfileError, match="preparation_changed"):
        pin.assert_current(second)
    (first / "text_pages/0002.txt").symlink_to(second / "text_pages/0001.txt")
    with pytest.raises((ProfileError, OSError)):
        runtime.ResearchPin.capture(first)


@pytest.mark.parametrize("relative", ["agent_resources/SYSTEM.md", "agent_resources/skills/focus-answer-record-questions/SKILL.md",
                                     "agent_helper.py", "agent_answer.py", "research_context.py",
                                     "agent_resources/extensions/focus-record-agent.ts", "agent_followup.py"])
def test_real_method_bytes_are_pinned(tmp_path, monkeypatch, relative):
    source = Path(runtime.__file__).parent
    package = tmp_path / "source/focus"
    shutil.copytree(source, package)
    monkeypatch.setattr(runtime, "__file__", str(package / "research_runtime.py"))
    root = case(tmp_path / "case")
    pin = runtime.ResearchPin.capture(root)
    target = package / relative
    target.write_bytes(target.read_bytes() + b"\n")
    with pytest.raises(ProfileError, match="research_contract_changed"):
        pin.assert_current(root)


def test_staging_and_actual_helper_share_pin(tmp_path):
    root = case(tmp_path / "case")
    pin = runtime.ResearchPin.capture(root)
    workspace = tmp_path / "workspace"
    workspace.mkdir(mode=0o700)
    staged = runtime.stage_research_resources(pin, workspace)
    assert (staged / "skills/focus-answer-record-questions/SKILL.md").read_text() == runtime.compile_research().skill
    for path in staged.rglob("*"):
        assert path.stat().st_mode & 0o077 == 0
    command = [sys.executable, helper.__file__, "--case-root", str(root), "context", "--json"]
    env = pin.environment(os.environ)
    assert subprocess.run(command, env=env, capture_output=True).returncode == 0
    env[runtime.COMPONENT_ENV] = "0" * 64
    rejected = subprocess.run(command, env=env, text=True, capture_output=True)
    assert rejected.returncode == 1
    assert json.loads(rejected.stdout)["error_code"] == "research_contract_changed"
    env.pop(runtime.INPUTS_ENV)
    rejected = subprocess.run(command, env=env, text=True, capture_output=True)
    assert json.loads(rejected.stdout)["error_code"] == "invalid_research_pin"


@pytest.mark.parametrize("change", ["inventory", "source", "map"])
def test_collection_time_changes_rejected(tmp_path, monkeypatch, change):
    root = case(tmp_path / "case")
    original = runtime.read_file_at
    changed = False
    def changing_reader(fd, relative, **kwargs):
        nonlocal changed
        data = original(fd, relative, **kwargs)
        if relative == "text_pages/0001.txt" and not changed:
            changed = True
            target = {"inventory": "text_pages/0002.txt", "source": "text_pages/0001.txt",
                      "map": "artifacts/source_map.json"}[change]
            (root / target).write_text("Changed during collection")
        return data
    monkeypatch.setattr(runtime, "read_file_at", changing_reader)
    with pytest.raises(ProfileError, match="preparation_changed"):
        runtime.preparation_inputs(root)


def test_staging_rejects_broad_permissions_and_symlink_ancestors(tmp_path):
    pin = runtime.ResearchPin.capture(case(tmp_path / "case"))
    workspace = tmp_path / "workspace"
    workspace.mkdir(mode=0o755)
    with pytest.raises(ProfileError, match="store_permissions"):
        runtime.stage_research_resources(pin, workspace)
    workspace.chmod(0o700)
    linked = tmp_path / "linked"
    linked.symlink_to(workspace, target_is_directory=True)
    with pytest.raises(ProfileError, match="unsafe_store_directory"):
        runtime.stage_research_resources(pin, linked)


def historical_context():
    return {"schema_version": 1, "research_profile_ref": provenance()["profile_ref"] | {"application": "focus"},
            "preparation_provenance": provenance(), "inputs_sha256": "0" * 64,
            "research_component_sha256": "c" * 64}


@pytest.mark.parametrize("version", [1, 2, 3])
def test_saved_schemas_coexist_without_lookup_or_relabeling(tmp_path, version):
    from test_saved_answers import _answer
    from focus.saved_answers import save_saved_answer, load_saved_answer, AgentAnswerSnapshot
    root = case(tmp_path / "case")
    value = historical_context() if version == 2 else runtime.ResearchPin.capture(root).metadata()
    context = None if version == 1 else research_context_bytes(value)
    answer = replace(_answer(), schema_version=version, research_context=context)
    assert save_saved_answer(root, answer).error == ""
    loaded = load_saved_answer(root, answer.answer_id)
    assert loaded.answer == answer
    assert AgentAnswerSnapshot.from_saved(answer).to_saved() == answer
    label = research_context_label(context)
    assert "Different specialties" not in label
    assert ("Focus method:" in label) == (version == 3)
    assert "unavailable" in research_context_label(b"not json")
    if context:
        assert research_context_payload(context) == value
        wrong = 3 if version == 2 else 2
        assert save_saved_answer(root, replace(answer, schema_version=wrong)).error == "invalid_research_context"


@pytest.mark.parametrize("mutation", [lambda v: v.update(schema_version=99),
                                      lambda v: v["research_method"].update(id="unknown"),
                                      lambda v: v["research_method"].update(version=True),
                                      lambda v: v.update(inputs_sha256="bad"),
                                      lambda v: v.update(prompt="must not load")])
def test_invalid_method_metadata_is_never_replaced(tmp_path, mutation):
    value = runtime.ResearchPin.capture(case(tmp_path / "case")).metadata()
    mutation(value)
    with pytest.raises(ProfileError):
        research_context_bytes(value)


def test_unassigned_historical_context_stays_historical(tmp_path):
    from test_saved_answers import _answer
    from focus.saved_answers import save_saved_answer, load_saved_answer, AgentAnswerSnapshot
    value = historical_context() | {"research_profile_ref": None, "research_component_sha256": None}
    context = research_context_bytes(value)
    root = case(tmp_path / "case")
    answer = replace(_answer(), schema_version=2, research_context=context)
    assert save_saved_answer(root, answer).error == ""
    loaded = load_saved_answer(root, answer.answer_id).answer
    assert loaded == answer
    assert AgentAnswerSnapshot.from_saved(loaded).to_saved() == answer
    assert "Historical research profile: legacy / unassigned" in research_context_label(context)
    assert "Focus method:" not in research_context_label(context)


def test_unknown_structural_map_fails(tmp_path):
    root = case(tmp_path / "case")
    (root / "artifacts/source_map.json").write_text(json.dumps({"schema_version": 99, "pages": []}))
    with pytest.raises(ProfileError, match="unsupported"):
        runtime.ResearchPin.capture(root)
