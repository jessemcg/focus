import json
from pathlib import Path

from focus.preparation_context import preparation_context
from test_profile_artifacts import provenance


def test_open_is_read_only_and_never_infers_legacy_subject(tmp_path):
    assert list(tmp_path.iterdir()) == []
    value = preparation_context(tmp_path, None)
    assert value["selected_profile_ref"] is None
    assert value["published_provenance"] is None
    assert value["notices"] == []
    assert list(tmp_path.iterdir()) == []


def test_selection_is_not_published_provenance_or_instruction_acceptance(tmp_path):
    (tmp_path / ".recordprep").mkdir()
    selection = tmp_path / ".recordprep/practice-profile.json"
    selection.write_text(json.dumps({"schema_version": 1, "profile_ref": provenance()["profile_ref"]}))
    before = selection.read_bytes()
    value = preparation_context(tmp_path, None)
    assert value["selected_profile_ref"] == provenance()["profile_ref"]
    assert value["map_provenance"] is None
    assert "selected_preparation_differs_from_map" in value["notices"]
    assert selection.read_bytes() == before
    # No registry/snapshot is necessary or created to read the metadata.
    assert sorted(p.name for p in tmp_path.iterdir()) == [".recordprep"]


def test_published_and_selected_are_compared_with_consumed_map(tmp_path):
    (tmp_path / ".recordprep").mkdir()
    (tmp_path / "artifacts").mkdir()
    (tmp_path / ".recordprep/practice-profile.json").write_text(json.dumps({
        "schema_version": 1, "profile_ref": provenance()["profile_ref"]}))
    publication = tmp_path / "artifacts/practice_profile_provenance.json"
    publication.write_text(json.dumps(provenance()))
    assert preparation_context(tmp_path, provenance())["notices"] == []
    changed = provenance()
    changed["profile_ref"]["content_sha256"] = "c" * 64
    notices = preparation_context(tmp_path, changed)["notices"]
    assert "selected_preparation_differs_from_map" in notices
    assert "published_preparation_differs_from_map" in notices


def test_sidecars_are_bounded_and_cannot_redirect_to_resources(tmp_path):
    (tmp_path / ".recordprep").mkdir()
    path = tmp_path / ".recordprep/practice-profile.json"
    path.write_text(json.dumps({"schema_version": 1, "profile_ref": provenance()["profile_ref"],
                                "path": "/must/not/load"}))
    assert preparation_context(tmp_path, None)["selection_status"] == "invalid"
    path.write_text("x" * (256 * 1024 + 1))
    assert preparation_context(tmp_path, None)["selection_status"] == "invalid"
    path.unlink()
    target = tmp_path / "target.json"
    target.write_text(json.dumps({"schema_version": 1, "profile_ref": provenance()["profile_ref"]}))
    path.symlink_to(target)
    assert preparation_context(tmp_path, None)["selection_status"] == "invalid"
