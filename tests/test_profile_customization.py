from pathlib import Path

from focus.profile_customization import legacy_customization_editor
from focus.profile_workflows import export_profile, checked_folder


def test_explicit_legacy_copy_preserves_prose_without_runtime_config(tmp_path):
    resources = tmp_path / "resources"
    skill = resources / "skills/focus-answer-record-questions/SKILL.md"
    skill.parent.mkdir(parents=True)
    raw = "  Private synthetic guidance.\n\nKeep this spacing.\t\n"
    system = "\nPrivate synthetic answer style.  \n"
    skill.write_text(raw)
    (resources / "SYSTEM.md").write_text(system)
    (resources / "auth.json").write_text('{"api_key":"CREDENTIAL_CANARY"}')
    (resources / "settings.json").write_text('{"model":"MODEL_CANARY"}')
    before = {path.relative_to(resources): path.read_bytes() for path in resources.rglob("*") if path.is_file()}
    editor = legacy_customization_editor(resources_root=resources)
    assert editor.resources["research"].endswith(raw)
    assert editor.resources["answer_guidance"].endswith(system)
    assert list(tmp_path.iterdir()) == [resources]  # Cancel has no publication effects.
    snapshot = editor.snapshot()
    assert b"CANARY" not in b"".join(data for _, data in snapshot.files)
    output = tmp_path / "review-copy"
    export_profile(snapshot, output)
    loaded = checked_folder(output, "focus")
    assert loaded.resource("research").endswith(raw)
    assert loaded.resource("answer_guidance").endswith(system)
    assert before == {path.relative_to(resources): path.read_bytes() for path in resources.rglob("*") if path.is_file()}
