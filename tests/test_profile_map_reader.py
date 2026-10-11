import copy
import json
import subprocess
import sys
from pathlib import Path

from focus import agent_helper
from test_profile_artifacts import participant, provenance


def test_modern_context_and_actual_script_entry_point(tmp_path):
    (tmp_path / "artifacts").mkdir()
    payload = {"schema_version": 3, "pages": [], "documents": [],
               "preparation_provenance": provenance(), "participant_index": participant()}
    path = tmp_path / "artifacts/source_map.json"
    path.write_text(json.dumps(payload))
    before = path.read_bytes()
    context = agent_helper._source_map_context_payload(tmp_path)
    assert context["available"]
    assert context["practice_profile_status"] == "recorded"
    assert context["preparation_provenance"] == provenance()
    assert context["participant_index_schema_version"] == 3
    completed = subprocess.run([sys.executable, str(Path(agent_helper.__file__)), "--case-root", str(tmp_path),
                                "map", "--json"], capture_output=True, text=True)
    assert completed.returncode == 0, completed.stderr
    assert "plaintiff" in completed.stdout
    assert path.read_bytes() == before


def test_unsupported_profile_metadata_does_not_authorize_research(tmp_path):
    (tmp_path / "artifacts").mkdir()
    path = tmp_path / "artifacts/source_map.json"
    data = {"schema_version": 3, "pages": [], "preparation_provenance": provenance(),
            "participant_index": participant()}
    for mutate in (lambda p: p.update(schema_version=9),
                   lambda p: p["preparation_provenance"].update(path="/untrusted/profile"),
                   lambda p: p["participant_index"]["hearings"][0]["participants"][0].update(role_id="invented")):
        payload = copy.deepcopy(data)
        mutate(payload)
        path.write_text(json.dumps(payload))
        assert not agent_helper._source_map_context_payload(tmp_path)["available"]
        try:
            agent_helper._load_source_map(tmp_path)
        except agent_helper.RecordError as exc:
            assert exc.code == "map_unsupported"
        else:
            raise AssertionError("Unsupported map accepted")


def test_legacy_map_has_no_inferred_specialty(tmp_path):
    (tmp_path / "artifacts").mkdir()
    (tmp_path / "artifacts/source_map.json").write_text(json.dumps({"pages": [], "schema_version": 2}))
    context = agent_helper._source_map_context_payload(tmp_path)
    assert context["available"]
    assert context["practice_profile_status"] == "legacy_unassigned"
    assert context["preparation_provenance"] is None
