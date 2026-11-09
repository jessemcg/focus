"""Fixed hearing metadata and schema-14 compatibility; synthetic read-only inputs."""
import copy
import hashlib
import json
import pytest
from focus import profile_contract as contract
from focus.profile_artifacts import summary_application_metadata
from focus.summary_availability import inspect_summary
from test_practice_profiles import synthetic_files


def metadata():
    return {'application_contract': 'recordprep-hearing-topics-1', 'category_catalog': [
        {'id': 'parent_appearances', 'title': 'Appearances'},
        {'id': 'evidence_considered', 'title': 'Evidence Considered'},
        {'id': 'testimony', 'title': 'Testimony'},
        {'id': 'disputed_legal_issues', 'title': 'Disputed Legal Issues'},
        {'id': 'party_positions_and_reasons', 'title': 'Party Positions and Reasons'},
        {'id': 'court_orders_and_reasons', 'title': 'Court Orders and Reasons'}]}


def test_schema14_omits_hearing_topics_but_retains_report_topics():
    files = synthetic_files('recordprep'); manifest = json.loads(files['profile.json'])
    manifest['schema_version'] = 14
    for name in (contract.RETIRED_SUMMARY_RESOURCES | contract.RETIRED_PARTICIPANT_RESOURCES |
                 contract.RETIRED_OVERVIEW_RESOURCES | {'classification', 'minutes', 'hearings'}):
        files.pop(manifest['resources'].pop(name))
    manifest['resources']['case_name'] = 'case-name.md'; files['case-name.md'] = b'Historical caption'
    files['profile.json'] = contract.json_bytes(manifest)
    before = dict(files)
    profile = contract.validate_contents(tuple(files.items()), 'recordprep')
    assert dict(profile.files) == before
    assert profile.resource('reports')
    for stage in ('hearing_extraction', 'hearing_synthesis'):
        assert contract.compile_stage_profile(profile, stage, core_contract=b'fixed').resources == ()
    manifest['resources']['hearings'] = 'hearings.json'; files['hearings.json'] = b'[]'
    files['profile.json'] = contract.json_bytes(manifest)
    with pytest.raises(contract.ProfileError):
        contract.validate_contents(tuple(files.items()), 'recordprep')


def test_hearing_application_descriptors_are_strict_and_instruction_free():
    value = metadata()
    assert summary_application_metadata(value, 'hearings') == value
    for mutate in ('title', 'guidance', 'contract', 'kind'):
        bad = copy.deepcopy(value)
        if mutate == 'title': bad['category_catalog'][0]['title'] = 'Parent Appearances'
        if mutate == 'guidance': bad['category_catalog'][0]['guidance'] = 'Private instructions'
        if mutate == 'contract': bad['application_contract'] = 'unknown'
        with pytest.raises(contract.ProfileError):
            summary_application_metadata(bad, 'reports' if mutate == 'kind' else 'hearings')


def test_hearing_availability_reads_empty_and_nonempty_without_writes(tmp_path):
    path = tmp_path / 'hearings_sum.txt'; sidecar = path.with_suffix('.meta.json')
    for ids, text in (([], 'Hearings Summary\n'), (['hearing:0001'], 'Hearings Summary\n\nThe court denied the request.\n')):
        path.write_text(text)
        sidecar.write_text(json.dumps({'artifact': 'recordprep-summary-final-meta', 'schema_version': 6,
            'kind': 'hearings', 'item_ids': ids, 'application_metadata': metadata(),
            'final_text_sha256': hashlib.sha256(path.read_bytes()).hexdigest()}))
        before = [(p.read_bytes(), p.stat().st_mtime_ns) for p in (path, sidecar)]
        result = inspect_summary(path, 'hearing')
        assert result.available == bool(ids)
        assert not result.diagnostics
        assert before == [(p.read_bytes(), p.stat().st_mtime_ns) for p in (path, sidecar)]
