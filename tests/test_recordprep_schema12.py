"""Reader-only schema-12/grouped-motion compatibility, fictional data only."""
import copy
import hashlib
import json
import pytest
from focus.profile_contract import validate_contents, json_bytes, ProfileError
from focus.profile_artifacts import source_map_profile_metadata
from focus.summary_availability import inspect_summary
from test_recordprep_schema11 import schema11_files


def schema11():
    return validate_contents(tuple(schema11_files().items()), 'recordprep')


def schema12():
    profile = schema11()
    files, manifest = dict(profile.files), profile.manifest
    files.pop(manifest['resources'].pop('motions'))
    manifest['schema_version'] = 12
    files['profile.json'] = json_bytes(manifest)
    return validate_contents(tuple(files.items()), 'recordprep')


def grouping():
    inventory = [{'paper_id': f'motion:{start:04d}', 'start_page': start, 'end_page': end,
                  'source_title': title, 'date': '', 'date_basis': 'unknown', 'naming_rule_id': ''}
                 for start, end, title in ((98, 99, 'Notice and Motion'), (100, 101, 'Supporting Declaration'),
                                           (102, 103, 'Separate Statement'), (104, 106, 'Memorandum'))]
    group = {'group_id': 'motion:0098', 'lead_paper_id': 'motion:0098', 'anchor_page': 98,
             'filing_role': 'motion/application', 'member_paper_ids': [p['paper_id'] for p in inventory],
             'components': [{'paper_id': p['paper_id'], 'start_page': p['start_page'], 'end_page': p['end_page'], 'role': 'lead' if i == 0 else 'support'}
                            for i, p in enumerate(inventory)], 'display_title': 'Motion to compel inspection',
             'filing_party': 'Owner', 'purpose': 'Compel inspection', 'date': '', 'date_basis': 'unknown',
             'relationship_to': '', 'relationship_notes': ''}
    return {'artifact': 'recordprep-motion-groups', 'schema_version': 1,
            'organization_contract': 'recordprep-motion-organization-1', 'inventory': inventory,
            'input_sha256': 'a' * 64, 'inputs': {}, 'groups': [group], 'findings': [], 'coverage_status': 'complete'}


def test_current_profile_omits_topics_and_retains_motion_eligibility():
    profile = schema12()
    assert 'motion_naming' in profile.manifest['resources']
    assert 'motions' not in profile.manifest['resources']
    before = profile.files
    from focus.profile_contract import compile_stage_profile
    assert compile_stage_profile(profile, 'motion_extraction', core_contract=b'Fixed motion method').resources == ()
    assert profile.files == before
    assert schema11().manifest['schema_version'] == 11


def test_schema12_rejects_reintroduced_topics():
    profile = schema12()
    files, manifest = dict(profile.files), profile.manifest
    manifest['resources']['motions'] = 'motions.json'; files['motions.json'] = json_bytes([])
    files['profile.json'] = json_bytes(manifest)
    with pytest.raises(ProfileError): validate_contents(tuple(files.items()), 'recordprep')


def test_group_context_preserves_four_physical_documents_and_exact_members():
    value = grouping()
    documents = [{'id': p['paper_id'], 'type': 'motion', 'start_page': p['start_page'], 'end_page': p['end_page']}
                 for p in value['inventory']]
    source_map = {'schema_version': 2, 'documents': documents, 'motion_groups': value}
    before = copy.deepcopy(source_map)
    assert source_map_profile_metadata(source_map) is None
    assert len(documents) == 4 and len(value['groups']) == 1
    assert source_map == before
    bad = copy.deepcopy(source_map)
    bad['motion_groups']['groups'][0]['components'][1]['end_page'] = 103
    with pytest.raises(ProfileError): source_map_profile_metadata(bad)
    bad = copy.deepcopy(source_map); bad['motion_groups']['inputs'] = {'prompt': 'CANARY'}
    with pytest.raises(ProfileError): source_map_profile_metadata(bad)


@pytest.mark.parametrize('mutation', ['coverage', 'role', 'date-basis', 'range', 'page-alias', 'document-alias', 'count', 'duplicate-document'])
def test_grouped_map_rejects_corrupt_descriptors(mutation):
    value = grouping()
    documents = [{'id': p['paper_id'], 'type': 'motion', 'start_page': p['start_page'], 'end_page': p['end_page']}
                 for p in value['inventory']]
    payload = {'schema_version': 2, 'documents': documents, 'motion_groups': value}
    if mutation == 'coverage': value['coverage_status'] = []
    elif mutation == 'role': value['groups'][0]['filing_role'] = []
    elif mutation == 'date-basis': value['inventory'][0]['date_basis'] = []
    elif mutation == 'range': documents[0]['end_page'] = None
    elif mutation == 'page-alias': payload['pages'] = [{'file_page': 98, 'motion_entries': [{'prompt': 'INSTRUCTION CANARY'}]}]
    elif mutation == 'document-alias': documents[0]['motion_group_id'] = 'motion:0100'
    elif mutation == 'count': payload['counts'] = {'motion_entries': 4}
    elif mutation == 'duplicate-document': documents.append(copy.deepcopy(documents[0]))
    with pytest.raises(ProfileError): source_map_profile_metadata(payload)


def test_group_validation_does_not_expand_large_record_ranges():
    value = grouping()
    value['inventory'][-1]['end_page'] = 10 ** 12
    value['groups'][0]['components'][-1]['end_page'] = 10 ** 12
    documents = [{'id': p['paper_id'], 'type': 'motion', 'start_page': p['start_page'], 'end_page': p['end_page']}
                 for p in value['inventory']]
    group = value['groups'][0]
    descriptor = {key: group[key] for key in ('group_id', 'display_title', 'anchor_page', 'member_paper_ids')}
    assert source_map_profile_metadata({'schema_version': 2, 'documents': documents, 'motion_groups': value,
        'pages': [{'file_page': 10 ** 12, 'motion_entries': [descriptor]}]}) is None


def test_motion_schema6_availability_empty_and_nonempty_read_only(tmp_path):
    path = tmp_path / 'motions_sum_Fictional.txt'
    for ids, body, expected in (([], '', 'empty'), (['motion:0098'], 'Motion to compel inspection\n\nThe owner seeks inspection.\n', 'available')):
        data = ('Motions Summary\nFictional\n\n' + body).encode()
        path.write_bytes(data)
        meta = {'artifact': 'recordprep-summary-final-meta', 'schema_version': 6, 'kind': 'motions',
                'item_ids': ids, 'final_text_sha256': hashlib.sha256(data).hexdigest(),
                'application_metadata': {'application_contract': 'recordprep-motion-request-reasons-1',
                                         'category_catalog': [{'id': 'request', 'title': 'Request'}, {'id': 'reasons', 'title': 'Reasons'}]}}
        path.with_suffix('.meta.json').write_text(json.dumps(meta))
        before = {p: (p.read_bytes(), p.stat().st_mtime_ns) for p in tmp_path.iterdir()}
        availability = inspect_summary(path, 'motions')
        assert availability.status == expected
        assert {p: (p.read_bytes(), p.stat().st_mtime_ns) for p in before} == before
