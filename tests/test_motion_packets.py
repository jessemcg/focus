"""Schema-2 continuity compatibility only; research method is unchanged."""
import copy
import json
import pytest
from focus.profile_artifacts import validate_motion_groups, source_map_profile_metadata, MOTION_CONTINUITY_EXPLANATION
from test_recordprep_schema12 import grouping


def packet():
    value = grouping()
    value.update(schema_version=2, organization_contract='recordprep-motion-organization-2')
    value['inventory'][1]['source_title'] = ''
    group = value['groups'][0]
    group.update(filing_role='motion packet', display_title=value['inventory'][0]['source_title'],
                 filing_party='', purpose='', relationship_notes=MOTION_CONTINUITY_EXPLANATION)
    for i, component in enumerate(group['components']): component['role'] = 'lead' if i == 0 else 'continuation'
    return value


def test_roundtrip_unnamed_components_and_old_semantics_read_only(tmp_path):
    for value in (grouping(), packet()):
        path = tmp_path / 'group.json'; path.write_text(json.dumps(value))
        before = path.read_bytes(), path.stat().st_mtime_ns
        assert validate_motion_groups(json.loads(path.read_bytes())) == value
        assert (path.read_bytes(), path.stat().st_mtime_ns) == before
    historical = grouping()
    historical['inventory'][0]['end_page'] = 98
    historical['groups'][0]['components'][0]['end_page'] = 98
    historical['groups'][0].update(group_id='motion:0102', lead_paper_id='motion:0102', anchor_page=102,
                                  date='Historical recovered date', coverage_status='ignored')
    historical['groups'][0].pop('coverage_status')
    historical['coverage_status'] = 'incomplete'
    assert validate_motion_groups(historical) == historical


@pytest.mark.parametrize('mutation', ['contract', 'version', 'title', 'date', 'basis', 'lead', 'role', 'party', 'unnamed-lead', 'gap', 'duplicate', 'range', 'component-role', 'split'])
def test_invalid_new_contracts_fail_closed(mutation):
    value = packet(); group = value['groups'][0]
    if mutation == 'contract': value['organization_contract'] = 'recordprep-motion-organization-1'
    elif mutation == 'version': value['schema_version'] = 3
    elif mutation == 'title': group['display_title'] = 'Other title'
    elif mutation == 'date': group['date'] = 'New date'
    elif mutation == 'basis': group['date_basis'] = 'filed'
    elif mutation == 'lead': group.update(lead_paper_id='motion:0102', group_id='motion:0102', anchor_page=102)
    elif mutation == 'role': group['filing_role'] = 'motion/application'
    elif mutation == 'party': group['filing_party'] = 'Assumed party'
    elif mutation == 'unnamed-lead': value['inventory'][0]['source_title'] = ''
    elif mutation == 'gap':
        value['inventory'][0]['end_page'] = 98; group['components'][0]['end_page'] = 98
    elif mutation == 'duplicate': group['member_paper_ids'].append(group['member_paper_ids'][0])
    elif mutation == 'range': group['components'][0]['end_page'] = 100
    elif mutation == 'component-role': group['components'][1]['role'] = 'support'
    elif mutation == 'split':
        value['inventory'][1]['source_title'] = 'Independent opposition'
        second = copy.deepcopy(group); lead = value['inventory'][1]
        second.update(group_id=lead['paper_id'], lead_paper_id=lead['paper_id'], anchor_page=lead['start_page'], display_title=lead['source_title'])
        second['member_paper_ids'] = group['member_paper_ids'][1:]; second['components'] = group['components'][1:]
        second['components'][0]['role'] = 'lead'
        group['member_paper_ids'] = group['member_paper_ids'][:1]; group['components'] = group['components'][:1]
        value['groups'].append(second)
    with pytest.raises(ValueError): validate_motion_groups(value)


def test_v2_reader_map_preserves_physical_and_logical_counts():
    value = packet(); group = value['groups'][0]
    documents = [dict(id=p['paper_id'], type='motion', start_page=p['start_page'], end_page=p['end_page'],
                      motion_group_id=group['group_id'], motion_entry_title=group['display_title'],
                      motion_name=p['source_title'], motion_date=p['date'], motion_date_basis=p['date_basis'],
                      aliases=[p['paper_id'], group['group_id'], group['display_title']]) for p in value['inventory']]
    pages = [dict(file_page=n, document_ids=[p['paper_id']], motion_entries=[{k: group[k] for k in
             ('group_id', 'display_title', 'anchor_page', 'member_paper_ids')}])
             for p in value['inventory'] for n in range(p['start_page'], p['end_page'] + 1)]
    payload = dict(schema_version=2, documents=documents, pages=pages, motion_groups=value, counts={'motions': 4, 'motion_entries': 1})
    original = copy.deepcopy(payload)
    assert source_map_profile_metadata(payload) is None
    assert payload == original
    mutations = [
        lambda p: p['counts'].update(motions=1),
        lambda p: p['counts'].pop('motion_entries'),
        lambda p: p['documents'][1].update(motion_name='Invented source title'),
        lambda p: p['documents'][1].update(aliases=[]),
        lambda p: p['documents'][1].pop('motion_group_id'),
        lambda p: p['pages'][2].update(motion_entries=[]),
        lambda p: p['pages'][2].update(document_ids=['motion:9999']),
        lambda p: p['pages'].pop(),
        lambda p: p['pages'].append(copy.deepcopy(p['pages'][0])),
    ]
    for mutation in mutations:
        bad = copy.deepcopy(original); mutation(bad)
        with pytest.raises(ValueError): source_map_profile_metadata(bad)
