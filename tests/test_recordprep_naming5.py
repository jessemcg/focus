"""Naming rule metadata remains descriptive in Focus, never research instructions."""
import json
import pytest
from focus import profile_contract as c
from test_recordprep_schema10 import files_for


def naming_files(version=5, mode='source_title'):
    files = files_for(10)
    path = json.loads(files['profile.json'])['resources']['naming']
    files[path] = c.json_bytes({'schema_version':version,
        'reports':[{'id':'expert','name':'Expert Report','guidance':'Court-directed expert evaluation.',
                    'naming_mode':mode}],
        'forms':[{'id':'fixed','name':'Standard Request','guidance':'Required title and code.'}]})
    return files


@pytest.mark.parametrize('mode', ['source_title','fixed'])
def test_naming5_is_readable_literal_and_not_minute_authority(mode):
    files = naming_files(mode=mode)
    snapshot = c.validate_contents(tuple(files.items()),'recordprep')
    assert dict(snapshot.files) == files
    assert snapshot.resource('naming')['reports'][0]['naming_mode'] == mode
    assert c.compile_stage_profile(snapshot,'minutes',core_contract=b'fixed minutes').resources == ()
    assert c.compile_stage_profile(snapshot,'classification',core_contract=b'fixed recognition').resources == ()


@pytest.mark.parametrize('version,mode', [(4,'source_title'),(6,'source_title'),(5,'arbitrary'),(5,None)])
def test_naming5_keeps_version_and_policy_validation(version,mode):
    with pytest.raises(c.ProfileError):
        c.validate_contents(tuple(naming_files(version,mode).items()),'recordprep')
