"""Read independent synthetic RecordPrep exports with no Focus counterpart profile.

Argument: synthetic cases directory with civil/dependency/third exports. No model
calls, sibling imports, bundle writes, private stores, or regeneration.
"""
import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from focus import agent_helper
from focus.research_runtime import ResearchPin, compile_research
from focus.research_context import research_context_bytes, research_context_payload
from focus.answer_presentation import research_context_label

cases = Path(sys.argv[1])
component = compile_research().component_sha256


def fingerprint(root):
    return {str(path.relative_to(root)): hashlib.sha256(path.read_bytes()).hexdigest()
            for path in root.rglob("*") if path.is_file()}


for scenario in ("civil", "dependency", "third"):
    root = cases / scenario
    before = fingerprint(root)
    pin = ResearchPin.capture(root)
    assert pin.research_component_sha256 == component
    prep = pin.metadata()["preparation_provenance"]
    assert prep["profile_ref"]["application"] == "recordprep"
    if scenario == "third":
        source_map = json.loads((root / "artifacts/source_map.json").read_text())
        assert any(person["role_label"] == "Independent expert" and "role_id" not in person
                   for hearing in source_map["participant_index"]["hearings"] for person in hearing["participants"])
    context = research_context_payload(research_context_bytes(pin.metadata()))
    label = research_context_label(research_context_bytes(context))
    assert "Focus method:" in label and "RecordPrep preparation:" in label
    assert "Different specialties" not in label
    env = pin.environment(os.environ)
    for args in (("context",), ("lookup", "--file", "text_pages/0006.txt"), ("search", "--query", "motion denied")):
        result = subprocess.run([sys.executable, agent_helper.__file__, "--case-root", str(root), *args, "--json"],
                                env=env, capture_output=True, text=True, timeout=30)
        assert result.returncode == 0, result.stdout + result.stderr
        payload = json.loads(result.stdout)
        assert "error" not in payload
        if args[0] == "context":
            assert payload["source_map"]["preparation_provenance"] == prep
        elif args[0] == "lookup":
            assert "RT 6" in result.stdout
        else:
            assert "Motion denied" in result.stdout or "motion denied" in result.stdout
    pin.assert_current(root)
    assert fingerprint(root) == before
    print("BUNDLE CONSUMER PASSED", scenario, prep["profile_ref"]["specialty_id"])
print("INDEPENDENT PRODUCER/CONSUMER ACCEPTANCE PASSED")
