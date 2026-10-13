"""Consume synthetic RecordPrep exports using only Focus's own runtime/resources.

Arguments: synthetic cases directory, independently GUI-authored Focus counterpart.
Run with isolated HOME/XDG. No Pi, model calls, sibling imports or case writes.
"""
import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from focus import agent_helper
from focus.practice_profiles import profile_store, bundled_profile_directory, validate_profile_directory
from focus.research_profiles import ResearchPin, literal_match, research_context_bytes, research_context_payload
from focus.answer_presentation import profile_context_label
from focus.profile_integration import context_description

cases = Path(sys.argv[1])
store = profile_store()
profiles = {name: validate_profile_directory(bundled_profile_directory(bundled)).draft
            for name,bundled in (("civil","general"),("dependency","california_dependency"))}
profiles["third"] = validate_profile_directory(Path(sys.argv[2])).draft
assert profiles["third"] is not None


def fingerprint(root):
    return {str(path.relative_to(root)):hashlib.sha256(path.read_bytes()).hexdigest()
            for path in root.rglob("*") if path.is_file()}


for scenario, profile in profiles.items():
    root = cases / scenario
    before = fingerprint(root)
    if scenario == "third":
        assert not store.read_registry()["heads"].get(profile.ref.specialty_id)
        result = subprocess.run([sys.executable, agent_helper.__file__, "--case-root", str(root), "context", "--json"],
                                capture_output=True, text=True, timeout=30)
        assert result.returncode == 0, result.stdout + result.stderr
        assert json.loads(result.stdout)["source_map"]["status"] == "valid"
        assert fingerprint(root) == before
    store.accept_profile(profile, expected_previous_digest=None)
    pin = ResearchPin.capture(root, profile, store=store)
    prep = pin.metadata()["preparation_provenance"]
    assert prep["profile_ref"]["application"] == "recordprep"
    assert prep["profile_ref"]["specialty_id"] == profile.ref.specialty_id
    assert prep["profile_ref"]["content_sha256"] != profile.ref.content_sha256
    if scenario == "third":
        assert literal_match("The motion was denied", profile.resource("search")["query_terms"])
        source_map = json.loads((root / "artifacts/source_map.json").read_text())
        assert any(person["role_label"] == "Independent expert" and "role_id" not in person
                   for hearing in source_map["participant_index"]["hearings"] for person in hearing["participants"])
    context = research_context_payload(research_context_bytes(pin.metadata()))
    label = profile_context_label(research_context_bytes(context))
    assert "Research:" in label and "Preparation:" in label
    assert "Different specialties" not in label
    env = pin.environment(os.environ)
    for args in (("context",), ("lookup","--file","text_pages/0006.txt"), ("search","--query","motion denied")):
        result = subprocess.run([sys.executable, agent_helper.__file__, "--case-root", str(root), *args, "--json"],
                                env=env,capture_output=True,text=True,timeout=30)
        assert result.returncode == 0, result.stdout + result.stderr
        payload = json.loads(result.stdout)
        assert "error" not in payload
        if args[0] == "context":
            assert payload["source_map"]["preparation_provenance"] == prep
        elif args[0] == "lookup":
            assert "RT 6" in result.stdout
        else:
            assert "Motion denied" in result.stdout or "motion denied" in result.stdout
    # Changing the research default cannot mutate or reinterpret preparation.
    store.set_default(profile.ref)
    pin.assert_current(root)
    assert fingerprint(root) == before
    if scenario != "dependency":
        for path in (root / "summaries").glob("*_sum_*.txt"):
            assert "Parent appearances" not in path.read_text()
    print("PROFILE CONSUMER PASSED", scenario, profile.ref.specialty_id)
mixed = ResearchPin.capture(cases / "dependency", profiles["civil"], store=store)
assert "Different specialties" in profile_context_label(research_context_bytes(mixed.metadata()))
mixed.assert_current(cases / "dependency")
print("INDEPENDENT PRODUCER/CONSUMER ACCEPTANCE PASSED")
