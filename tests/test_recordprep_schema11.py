"""Reader-only schema-11 conformance, without any RecordPrep runtime import."""
import copy
import json
import pytest
from focus import profile_contract as c
from test_recordprep_schema10 import files_for


def schema11_files():
    files = files_for(10)
    manifest = json.loads(files['profile.json'])
    manifest['schema_version'] = 11
    manifest['resources'].update(motion_naming='motion-naming.json', motions='motions.json')
    files['profile.json'] = c.json_bytes(manifest)
    files['motion-naming.json'] = c.json_bytes({'schema_version': 1, 'motions': [
        {'id': 'motion-paper', 'name': 'Motion Paper', 'naming_mode': 'source_title',
         'guidance': 'Fictional selection guidance, inert to Focus research.'}]})
    files['motions.json'] = c.json_bytes([{'id': 'requested_relief', 'title': 'Requested relief',
                                         'guidance': 'Requested relief as stated by this paper.'}])
    return files


def test_schema11_preserves_all_bytes_and_has_no_focus_instruction_authority():
    files = schema11_files(); before = copy.deepcopy(files)
    snapshot = c.validate_contents(tuple(files.items()), 'recordprep')
    assert dict(snapshot.files) == before
    assert snapshot.manifest['profile_api'] == 1
    assert snapshot.resource('motion_naming')['motions'][0]['naming_mode'] == 'source_title'
    assert c.compile_stage_profile(snapshot, 'classification_dates', core_contract=b'fixed').resources == ()
    assert c.compile_stage_profile(snapshot, 'minutes', core_contract=b'fixed').resources == ()
    with pytest.raises(c.ProfileError):
        c.compile_stage_profile(snapshot, 'research', core_contract=b'fixed')


@pytest.mark.parametrize('mutation', ['unknown-version', 'old-with-new', 'unknown-mode', 'duplicate-id',
                                      'unknown-field', 'missing-resource', 'bool-version'])
def test_schema11_rejects_invalid_motion_authority(mutation):
    files = schema11_files(); manifest = json.loads(files['profile.json'])
    naming = json.loads(files['motion-naming.json'])
    if mutation == 'unknown-version': manifest['schema_version'] = 12
    elif mutation == 'old-with-new': manifest['schema_version'] = 10
    elif mutation == 'unknown-mode': naming['motions'][0]['naming_mode'] = 'automatic_family'
    elif mutation == 'duplicate-id': naming['motions'].append(dict(naming['motions'][0], name='Other'))
    elif mutation == 'unknown-field': naming['family_grouping'] = True
    elif mutation == 'missing-resource': del files['motions.json']
    elif mutation == 'bool-version': naming['schema_version'] = True
    files['profile.json'] = c.json_bytes(manifest)
    files['motion-naming.json'] = c.json_bytes(naming)
    with pytest.raises(c.ProfileError): c.validate_contents(tuple(files.items()), 'recordprep')
