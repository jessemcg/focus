"""Reader-only schemas 7/8 conformance; Focus research instructions stay fixed."""
import json
import pytest
from focus import profile_contract as c
from test_practice_profiles import synthetic_files


def schema7_files(version=7):
    files=synthetic_files('recordprep');m=json.loads(files['profile.json']);m['schema_version']=version
    for key in c.RETIRED_SUMMARY_RESOURCES | c.RETIRED_PARTICIPANT_RESOURCES | c.RETIRED_OVERVIEW_RESOURCES | {'classification'}:
        files.pop(m['resources'].pop(key))
    m['resources'].update(classification_tasks='tasks.json',case_name='caption.md')
    files['profile.json']=c.json_bytes(m);files['caption.md']=b'Inert caption history.'
    files['tasks.json']=c.json_bytes({'schema_version':3 if version==8 else 2,'page_types':{side:{key:'Recognition description.' for key in keys} for side,keys in c.CLASSIFICATION_PAGE_TYPES.items()},'first_pages':{key:'Start clues.' for key in c.HISTORICAL_FIRST_PAGE_TASKS[3 if version==8 else 2]}})
    files[m['resources']['naming']]=c.json_bytes({'schema_version':4,'reports':[{'id':'report-1','name':'Synthetic Report','guidance':''}],'forms':[]})
    return files


@pytest.mark.parametrize('version',[7,8])
def test_schema7_and_legacy_schemas_are_readable_without_instruction_authority(version):
    files=schema7_files(version);s=c.validate_contents(tuple(files.items()),'recordprep')
    assert s.manifest['schema_version']==version
    assert c.compile_stage_profile(s,'classification_dates',core_contract=b'fixed dates').resources==()
    for version in range(1,7):
        old=synthetic_files('recordprep');m=json.loads(old['profile.json']);m['schema_version']=version
        if version>=2:
            m['resources'].update(classification_tasks='tasks.json',case_name='caption.md')
            old['tasks.json']=c.json_bytes({key:'Historical prose.' for key in ('rt','ct','first_hearing','first_minute','first_form','date_hearing','date_minute')})
            old['caption.md']=b'Inert caption.'
        retired=(c.RETIRED_SUMMARY_RESOURCES if version>=3 else set()) | (c.RETIRED_PARTICIPANT_RESOURCES if version>=4 else set()) | (c.RETIRED_OVERVIEW_RESOURCES if version>=5 else set()) | ({'classification'} if version>=6 else set())
        for key in retired:old.pop(m['resources'].pop(key))
        old['profile.json']=c.json_bytes(m)
        assert c.validate_contents(tuple(old.items()),'recordprep').manifest['schema_version']==version
    assert s.resource('naming')['reports'][0]['guidance']==''


@pytest.mark.parametrize('version',[7,8])
@pytest.mark.parametrize('mutation',['cross-side','missing','extra','duplicate-name','duplicate-id','priority','date','first-report'])
def test_schema7_rejects_malformed_resources(mutation,version):
    files=schema7_files(version);tasks=json.loads(files['tasks.json']);naming=json.loads(files['resources/naming.json'])
    if mutation=='cross-side':tasks['page_types']['rt']['CT_report']='No.'
    if mutation=='missing':del tasks['page_types']['ct']['CT_certificate']
    if mutation=='extra':tasks['page_types']['ct']['CT_custom']='No.'
    if mutation=='duplicate-name':naming['reports'].append({'id':'report-2','name':'synthetic report','guidance':''})
    if mutation=='duplicate-id':naming['reports'].append({'id':'report-1','name':'Different','guidance':''})
    if mutation=='priority':tasks['priority']=['CT_report']
    if mutation=='date':tasks['date_hearing']='Inactive legacy text not allowed in structured resources.'
    if mutation=='first-report':
        if version==8:del tasks['first_pages']['first_report']
        else:tasks['first_pages']['first_report']='Not supported in v2.'
    files['tasks.json']=c.json_bytes(tasks);files['resources/naming.json']=c.json_bytes(naming)
    with pytest.raises(c.ProfileError):c.validate_contents(tuple(files.items()),'recordprep')


def test_schema8_lossless_legacy_editor_variant_is_inert_to_focus_research():
    files=schema7_files(8)
    tasks={key:'Literal α {json} {{quote:source}}' for key in c.LEGACY_CLASSIFICATION_TASKS}
    tasks.update(schema_version=3,first_report='Report-opening clues.')
    files['tasks.json']=c.json_bytes(tasks)
    snapshot=c.validate_contents(tuple(files.items()),'recordprep')
    assert snapshot.resource('classification_tasks')==tasks
    assert c.compile_stage_profile(snapshot,'classification_advanced',core_contract=b'fixed').resources==()
    with pytest.raises(c.ProfileError):c.compile_stage_profile(snapshot,'research',core_contract=b'fixed')
