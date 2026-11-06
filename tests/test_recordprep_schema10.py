"""Reader-only schema 10 compatibility; no preparation/research runtime changes."""
import json
import pytest
from focus import profile_contract as c
from test_practice_profiles import synthetic_files
from test_recordprep_schema7 import schema7_files
from test_recordprep_schema9 import schema9_files


def files_for(version):
    if version in (7, 8):
        return schema7_files(version)
    if version >= 9:
        files = schema9_files()
        manifest = json.loads(files['profile.json'])
        manifest['schema_version'] = version
        if version >= 10:
            files.pop(manifest['resources'].pop('minutes'))
        files['profile.json'] = c.json_bytes(manifest)
        return files
    files = synthetic_files('recordprep')
    manifest = json.loads(files['profile.json'])
    manifest['schema_version'] = version
    if version >= 2:
        manifest['resources'].update(classification_tasks='tasks.json', case_name='caption.md')
        files['tasks.json'] = c.json_bytes({key: 'Literal history.' for key in c.LEGACY_CLASSIFICATION_TASKS})
        files['caption.md'] = b'Historical caption.'
    retired = ((c.RETIRED_SUMMARY_RESOURCES if version >= 3 else set())
               | (c.RETIRED_PARTICIPANT_RESOURCES if version >= 4 else set())
               | (c.RETIRED_OVERVIEW_RESOURCES if version >= 5 else set())
               | ({'classification'} if version >= 6 else set()))
    for key in retired:
        files.pop(manifest['resources'].pop(key))
    files['profile.json'] = c.json_bytes(manifest)
    return files


@pytest.mark.parametrize('version', range(1, 11))
def test_all_supported_schemas_preserve_bytes_and_compile_no_minute_resources(version):
    files = files_for(version)
    snapshot = c.validate_contents(tuple(files.items()), 'recordprep')
    assert dict(snapshot.files) == files
    assert snapshot.manifest['profile_api'] == 1
    compiled = c.compile_stage_profile(snapshot, 'minutes', core_contract=b'fixed application minutes')
    assert compiled.resources == ()
    current = c.validate_contents(tuple(files_for(10).items()), 'recordprep')
    assert compiled.component_sha256 == c.compile_stage_profile(
        current, 'minutes', core_contract=b'fixed application minutes').component_sha256
    assert ('minutes' in snapshot.manifest['resources']) == (version < 10)


@pytest.mark.parametrize('mutation', ['minutes', 'unknown-schema', 'wrong-api'])
def test_schema10_rejects_reintroduced_minute_authority_and_unknown_versions(mutation):
    files = files_for(10)
    manifest = json.loads(files['profile.json'])
    if mutation == 'minutes':
        manifest['resources']['minutes'] = 'minutes.md'
        files['minutes.md'] = b'Not an allowed schema-10 resource.'
    elif mutation == 'unknown-schema':
        manifest['schema_version'] = 11
    else:
        manifest['profile_api'] = 2
    files['profile.json'] = c.json_bytes(manifest)
    with pytest.raises(c.ProfileError):
        c.validate_contents(tuple(files.items()), 'recordprep')
