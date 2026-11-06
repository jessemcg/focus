"""Schema 9 metadata compatibility only; never RecordPrep instruction authority."""
import json
import pytest
from focus import profile_contract as c
from test_recordprep_schema7 import schema7_files


def schema9_files():
    files=schema7_files(8)
    manifest=json.loads(files['profile.json'])
    manifest['schema_version']=9
    files.pop(manifest['resources'].pop('classification_tasks'))
    files['profile.json']=c.json_bytes(manifest)
    return files


def test_schema9_no_classification_resources_and_no_runtime_imports():
    files=schema9_files();snapshot=c.validate_contents(tuple(files.items()),'recordprep')
    assert snapshot.manifest['profile_api']==1
    assert c.validate_contents(snapshot.files,'recordprep').files==snapshot.files
    assert 'classification_tasks' not in snapshot.manifest['resources']
    for stage in ('classification','classification_basic','classification_advanced','classification_corrected','classification_dates'):
        assert c.compile_stage_profile(snapshot,stage,core_contract=b'fixed application rules').resources==()
    assert c.compile_stage_profile(snapshot,'naming',core_contract=b'fixed naming').resources
    with pytest.raises(c.ProfileError):c.compile_stage_profile(snapshot,'research',core_contract=b'fixed Focus method')


@pytest.mark.parametrize('version',[1,2,3,4])
def test_schema9_preserves_all_naming_formats(version):
    files=schema9_files();manifest=json.loads(files['profile.json'])
    values={1:{'mode':'source_title','report_titles':[],'form_titles':[],'guidance':'Literal old prose.'},
            2:{'schema_version':2,'mode':'approved_titles','report_titles':['Synthetic Report'],
               'form_rules':[{'name':'Synthetic Form','title':'A heading','code':'SYN-1'}],
               'report_guidance':'Literal report prose.','form_guidance':'Literal form prose.'},
            3:{'schema_version':3,'report_guidance':'- **Synthetic Report**\nLiteral.','form_guidance':'Literal.'}}
    if version!=4:files[manifest['resources']['naming']]=c.json_bytes(values[version])
    snapshot=c.validate_contents(tuple(files.items()),'recordprep')
    assert dict(snapshot.files)==files


@pytest.mark.parametrize('mutation',['retired-resource','unknown-schema','missing-naming','wrong-api','unsupported-name'])
def test_schema9_rejects_unknown_contracts(mutation):
    files=schema9_files();manifest=json.loads(files['profile.json'])
    if mutation=='retired-resource':
        manifest['resources']['classification_tasks']='tasks.json';files['tasks.json']=b'{}\n'
    if mutation=='unknown-schema':manifest['schema_version']=11
    if mutation=='missing-naming':files.pop(manifest['resources'].pop('naming'))
    if mutation=='wrong-api':manifest['profile_api']=2
    if mutation=='unsupported-name':files[manifest['resources']['naming']]=b'{"schema_version":5}'
    files['profile.json']=c.json_bytes(manifest)
    with pytest.raises(c.ProfileError):c.validate_contents(tuple(files.items()),'recordprep')
