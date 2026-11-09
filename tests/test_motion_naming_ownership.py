"""Read-only compatibility with universal RecordPrep motion naming."""
import json
import pytest
from focus import profile_contract as contract
from test_practice_profiles import synthetic_files


@pytest.mark.parametrize('version', [11, 12, 13])
def test_motion_naming_schemas_are_readable_but_never_instruction_authority(version):
    files = synthetic_files('recordprep')
    manifest = json.loads(files['profile.json'])
    manifest['schema_version'] = version
    retired = (contract.RETIRED_SUMMARY_RESOURCES | contract.RETIRED_PARTICIPANT_RESOURCES |
               contract.RETIRED_OVERVIEW_RESOURCES | {'classification', 'minutes'})
    for name in retired:
        files.pop(manifest['resources'].pop(name))
    manifest['resources']['case_name'] = 'case-name.md'
    files['case-name.md'] = b'Historical caption.'
    if version < 13:
        manifest['resources']['motion_naming'] = 'motion-naming.json'
        files['motion-naming.json'] = contract.json_bytes({'schema_version': 1, 'motions': [
            {'id': 'legacy', 'name': 'Legacy', 'guidance': 'CANARY private motion selection'}]})
    if version == 11:
        manifest['resources']['motions'] = 'motions.json'
        files['motions.json'] = contract.json_bytes([{'id': 'legacy', 'title': 'Legacy', 'guidance': 'CANARY topic'}])
    files['profile.json'] = contract.json_bytes(manifest)
    before = dict(files)
    profile = contract.validate_contents(tuple(files.items()), 'recordprep')
    assert dict(profile.files) == before
    assert contract.compile_stage_profile(profile, 'motion_naming', core_contract=b'fixed').resources == ()
    assert profile.resource('naming')['guidance'] == 'Use the source title.'
    if version == 13:
        manifest['resources']['motion_naming'] = 'motion-naming.json'
        files['profile.json'] = contract.json_bytes(manifest)
        files['motion-naming.json'] = contract.json_bytes({'schema_version': 1, 'motions': []})
        with pytest.raises(contract.ProfileError):
            contract.validate_contents(tuple(files.items()), 'recordprep')
