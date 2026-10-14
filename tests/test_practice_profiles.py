"""Retained historical snapshot/artifact contract conformance, not management."""
import dataclasses
import json
import os
from unittest.mock import patch

import pytest

from focus import profile_contract as contract


def synthetic_files(application="focus"):
    resources = {name: f"resources/{name}.{suffix}"
                 for name, suffix in contract.RESOURCE_TYPES[application].items()
                 if name not in {"classification_tasks", "case_name"}}
    manifest = {"schema_version": 1, "profile_api": 1, "specialty_id": "synthetic-employment",
                "application": application, "display_name": "Synthetic Employment",
                "description": "Synthetic fixture only.", "version": "1.0",
                "required_capabilities": sorted(contract.CAPABILITIES[application]),
                "resources": resources}
    catalog = [{"id": "material_facts", "title": "Material facts", "guidance": "Attribute material facts."}]
    roles = [{"id": role, "label": role.title(), "guidance": "Use explicit source evidence."}
             for role in ("plaintiff", "defendant", "unknown", "other")]
    structured = {"hearings": catalog, "reports": catalog,
                  "roles": {"counsel": roles, "participants": roles},
                  "policies": {"report_scope": "include_attributed_proposals", "attendance": "explicit_complete_order"},
                  "naming": {"mode": "source_title", "report_titles": [], "form_titles": [], "guidance": "Use the source title."},
                  "search": {"query_terms": ["termination"], "document_terms": ["order"],
                             "passage_terms": [], "later_history_terms": []}}
    return {"profile.json": contract.json_bytes(manifest)} | {
        path: contract.json_bytes(structured[name]) if name in structured else b"  Preserve custom whitespace.\n\n"
        for name, path in resources.items()}


def draft(files=None, app="focus"):
    return contract.validate_contents(tuple((files or synthetic_files(app)).items()), app)


def test_historical_contract_is_independent_immutable_and_byte_sensitive():
    files = synthetic_files()
    original = draft(files)
    assert original.ref == draft(dict(reversed(list(files.items())))).ref
    assert original.ref != draft(files | {"resources/research.md": b"changed"}).ref
    assert original.ref.content_sha256 != draft(app="recordprep").ref.content_sha256
    original.manifest["version"] = "changed"
    original.resource("search")["query_terms"].append("injected")
    assert original.manifest["version"] == "1.0"
    assert original.resource("search")["query_terms"] == ["termination"]
    with pytest.raises(dataclasses.FrozenInstanceError):
        original.files = ()


@pytest.mark.parametrize("changes", [
    {"schema_version": True}, {"profile_api": 2}, {"command": "do-not-execute"},
    {"required_capabilities": ["shell"]}, {"required_capabilities": [["nested"]]},
    {"specialty_id": "../escape"}, {"application": "recordprep"},
])
def test_historical_manifest_rejects_unknown_or_unsafe_fields(changes):
    files = synthetic_files()
    files["profile.json"] = contract.json_bytes(json.loads(files["profile.json"]) | changes)
    with pytest.raises(contract.ProfileError):
        draft(files)


@pytest.mark.parametrize("data", [b'{"query_terms":[],"query_terms":[]}', b'{"value":NaN}',
                                  b'"\xff"', b'{"private-client-text":', b'[' * 2000])
def test_historical_json_is_strict_and_errors_are_sanitized(data):
    with pytest.raises(contract.ProfileError) as caught:
        draft(synthetic_files() | {"resources/search.json": data})
    assert "private-client-text" not in str(caught.value)


@pytest.mark.parametrize("path", ["/tmp/x.md", "../x.md", "a/../x.md", "a//x.md", "./x.md", "a\\x.md", "x.py"])
def test_historical_paths_cannot_authorize_execution(path):
    files = synthetic_files()
    manifest = json.loads(files["profile.json"])
    manifest["resources"]["research"] = path
    files["profile.json"] = contract.json_bytes(manifest)
    with pytest.raises(contract.ProfileError):
        draft(files)


def test_historical_missing_duplicate_extra_and_size_bounds():
    files = synthetic_files()
    variants = [files | {"secret.txt": b"not allowed"},
                {key: value for key, value in files.items() if key != "resources/search.json"},
                files | {"resources/research.md": b"x" * (contract.MAX_FILE_BYTES + 1)},
                files | {"resources/research.md": b"\xff"}]
    manifest = json.loads(files["profile.json"])
    manifest["resources"]["answer_guidance"] = manifest["resources"]["research"]
    variants.append(files | {"profile.json": contract.json_bytes(manifest)})
    for variant in variants:
        with pytest.raises(contract.ProfileError):
            draft(variant)
    with patch.object(contract, "MAX_TOTAL_BYTES", 10), pytest.raises(contract.ProfileError):
        draft(files)


@pytest.mark.parametrize("kind", ["symlink", "hardlink", "executable", "fifo", "directory", "root"])
def test_historical_file_reader_retains_link_and_mode_guards(tmp_path, kind):
    root = tmp_path / "profile"
    for relative, data in synthetic_files().items():
        target = root / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)
    assert contract.validate_profile_directory(root, "focus").draft == draft()
    target = root / "resources/research.md"
    external = tmp_path / "external"
    external.write_bytes(target.read_bytes())
    if kind in ("symlink", "hardlink", "fifo"):
        target.unlink()
        if kind == "symlink":
            target.symlink_to(external)
        elif kind == "hardlink":
            os.link(external, target)
        else:
            os.mkfifo(target)
    elif kind == "executable":
        target.chmod(0o700)
    elif kind == "directory":
        (root / "resources").rename(tmp_path / "moved")
        (root / "resources").symlink_to(tmp_path / "moved", target_is_directory=True)
    else:
        link = tmp_path / "link"
        link.symlink_to(root, target_is_directory=True)
        root = link
    assert contract.validate_profile_directory(root, "focus").draft is None


def test_golden_historical_contract():
    from pathlib import Path
    fixture = json.loads((Path(__file__).parent / "fixtures/practice_profiles/conformance-v1.json").read_text())
    for app, expected in fixture["synthetic_profile_digests"].items():
        assert draft(app=app).ref.content_sha256 == expected


def test_identity_exchange_has_no_instruction_authority():
    value = contract.parse_identity_descriptor(contract.identity_descriptor(draft()))
    assert set(value) == {"schema_version", "specialty_id", "display_name", "description"}
    for extra in ("instructions", "path", "application", "command"):
        with pytest.raises(contract.ProfileError):
            contract.parse_identity_descriptor(contract.json_bytes(value | {extra: "not allowed"}))


def test_historical_naming_v2_v3_and_invalid_structures():
    files = synthetic_files("recordprep")
    legacy = draft(files, "recordprep")
    naming = {"schema_version": 2, "mode": "approved_titles", "report_titles": ["Synthetic Report"],
              "form_rules": [{"name": "Output", "title": "Heading", "code": "XY-10"}],
              "report_guidance": "Require heading.", "form_guidance": "Require heading and code."}
    assert draft(files | {"resources/naming.json": contract.json_bytes(naming)}, "recordprep").ref != legacy.ref
    for bad in (naming | {"schema_version": True}, naming | {"form_rules": naming["form_rules"] * 2},
                naming | {"form_rules": [{"name": "Output", "title": "Heading"}]},
                naming | {"form_guidance": ""}):
        with pytest.raises(contract.ProfileError):
            draft(files | {"resources/naming.json": contract.json_bytes(bad)}, "recordprep")
    current = {"schema_version": 3, "report_guidance": "- **Synthetic Report**",
               "form_guidance": "- **Synthetic Form** — required code: XY-10."}
    assert draft(files | {"resources/naming.json": contract.json_bytes(current)}, "recordprep").resource("naming") == current
    assert contract.naming_prompt_titles(current["form_guidance"]) == ("Synthetic Form",)
    for bad in (current | {"mode": "source_title"}, current | {"report_titles": ["Hidden name"]},
                current | {"schema_version": 3.0}, current | {"report_guidance": "- **Unclosed"},
                current | {"report_guidance": "- **Same**\n- **same**"}):
        with pytest.raises(contract.ProfileError):
            draft(files | {"resources/naming.json": contract.json_bytes(bad)}, "recordprep")


def test_retired_recordprep_resources_remain_readable_but_inert():
    files = synthetic_files("recordprep")
    old = draft(files, "recordprep")
    compiled = contract.compile_stage_profile(old, "report_extraction", core_contract=b"core")
    assert "policies" not in dict(compiled.resources)
    policies = old.resource("policies")
    for value in (policies | {"report_scope": "exclude_formal_proposals"}, {"attendance": policies["attendance"]}):
        changed = draft(files | {"resources/policies.json": contract.json_bytes(value)}, "recordprep")
        after = contract.compile_stage_profile(changed, "report_extraction", core_contract=b"core")
        assert compiled.resources == after.resources
        assert compiled.component_sha256 == after.component_sha256
    manifest = json.loads(files["profile.json"])
    manifest["schema_version"] = 3
    for name in contract.RETIRED_SUMMARY_RESOURCES:
        files.pop(manifest["resources"].pop(name))
    manifest["resources"].update(classification_tasks="tasks.json", case_name="caption.md")
    files["tasks.json"] = contract.json_bytes({key: "Synthetic task." for key in
        ("rt", "ct", "first_hearing", "first_minute", "first_form", "date_hearing", "date_minute")})
    files["caption.md"] = b"Historical caption."
    files["profile.json"] = contract.json_bytes(manifest)
    current = draft(files, "recordprep")
    for stage in ("classification_basic", "classification_advanced", "classification_dates"):
        assert contract.compile_stage_profile(current, stage, core_contract=b"core").resources
    assert contract.validate_contents(old.files, "recordprep").files == old.files
