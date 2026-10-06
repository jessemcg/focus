"""Synthetic coverage and boundary regressions. Never uses private bundles."""
import argparse
import json
from pathlib import Path

import pytest

from focus import agent_helper as helper
from test_focus_record_agent import _write_case_bundle


def search(root, **kwargs):
    values = dict(case_root=root, query=['placement', 'medication'], document=None,
                  hearing_date=None, witness=None, counsel_role=None, max_results=6,
                  include_attribution_detail=False)
    values.update(kwargs)
    return helper._search_payload(argparse.Namespace(**values))


def mutate(root, change):
    path = root / 'artifacts/source_map.json'
    data = json.loads(path.read_text())
    change(data)
    path.write_text(json.dumps(data))


@pytest.mark.parametrize('version', [1, 2])
def test_document_union_overlap_repeat_and_filter_intersection(tmp_path, version):
    root = _write_case_bundle(tmp_path)
    mutate(root, lambda d: d.update(schema_version=version))
    baseline = search(root)
    both = search(root, document=['hearing:0001', 'report:0002', 'hearing:0001'])
    assert both['matches'] == baseline['matches']
    assert both['candidate_pages'] == 2
    mutate(root, lambda d: d['documents'].append(dict(id='overlap', start_page=1, end_page=2)))
    assert search(root, document=['overlap', 'hearing:0001'])['candidate_pages'] == 2
    for scope in ({'hearing_date': 'January 2, 2025'}, {'witness': 'Mother'},
                  {'counsel_role': 'mothers_counsel'}):
        result = search(root, document=['hearing:0001', 'report:0002'], **scope)
        assert result['candidate_pages'] == 1
        assert result['matches'][0]['file_page'] == 1
    empty = search(root, document=['report:0002'], hearing_date='January 2, 2025')
    assert empty['scope_status'] == 'empty'
    assert empty['coverage']['complete'] is True
    assert empty['coverage']['candidate_pages'] == 0


def test_unknown_and_unavailable_scopes_never_broaden(tmp_path):
    root = _write_case_bundle(tmp_path)
    with pytest.raises(helper.RecordError, match='Unknown document'):
        search(root, document=['unknown', 'hearing:0001'])
    mutate(root, lambda d: d.pop('participant_index'))
    for scope in ({'witness': 'Mother'}, {'counsel_role': 'mothers_counsel'}):
        with pytest.raises(helper.RecordError, match='metadata is unavailable'):
            search(root, **scope)
    # Known metadata but no matching date is an explicit empty scope.
    assert search(root, hearing_date='January 1, 2000')['scope_status'] == 'empty'


@pytest.mark.parametrize('failure', ['missing', 'unreadable', 'decode', 'outside', 'traversal', 'symlink', 'directory', 'image', 'root-symlink'])
def test_unusable_pages_are_disclosed_and_never_escape(tmp_path, monkeypatch, failure):
    root = _write_case_bundle(tmp_path)
    page = root / 'text_pages/0002.txt'
    expected = {'missing': 'missing_pages', 'unreadable': 'unreadable_pages',
                'decode': 'decoding_warnings'}.get(failure, 'rejected_paths')
    if failure == 'missing':
        page.unlink()
    elif failure == 'unreadable':
        original = Path.read_bytes
        def unreadable(self):
            if self == page:
                raise PermissionError('synthetic unreadable')
            return original(self)
        monkeypatch.setattr(Path, 'read_bytes', unreadable)
    elif failure == 'decode':
        page.write_bytes(b'medication \xff compliance')
    elif failure in ('outside', 'traversal'):
        (root / 'summaries').mkdir()
        (root / 'summaries/0002.txt').write_text('medication')
        value = 'summaries/0002.txt' if failure == 'outside' else 'text_pages/../summaries/0002.txt'
        mutate(root, lambda d: d['pages'][1].update(text_path=value))
    elif failure == 'symlink':
        page.unlink()
        external = tmp_path / 'outside.txt'
        external.write_text('medication')
        page.symlink_to(external)
    elif failure == 'directory':
        page.unlink()
        page.mkdir()
    elif failure == 'image':
        mutate(root, lambda d: d['pages'][1].update(text_path='image_pages/0001.png'))
    else:
        text_root = root / 'text_pages'
        text_root.rename(tmp_path / 'external-text')
        text_root.symlink_to(tmp_path / 'external-text', target_is_directory=True)
    result = search(root, query=['nonexistent term'])
    coverage = result['coverage']
    assert result['total_matches'] == 0
    assert coverage['complete'] is False
    assert coverage[expected] == (2 if failure == 'root-symlink' else 1)
    assert coverage['candidate_pages'] == sum(coverage[k] for k in
        ('scanned_pages', 'missing_pages', 'unreadable_pages', 'rejected_paths'))
    lookup = helper._page_match_payload(root, json.loads((root / 'artifacts/source_map.json').read_text())['pages'][1])
    if failure not in ('decode', 'unreadable'):
        assert lookup['text_exists'] is False
    assert helper._page_match_payload(root, {'image_path':'image_pages/0001.png'})['image_exists'] is True


@pytest.mark.parametrize('scope', ['hearing_date', 'witness', 'counsel_role'])
def test_matching_but_unusable_scope_metadata_is_not_empty_evidence(tmp_path, scope):
    root = _write_case_bundle(tmp_path)
    if scope == 'witness':
        mutate(root, lambda d: d['participant_index']['hearings'][0]['witnesses'][0].update(examinations=[]))
        value = 'Mother'
    elif scope == 'counsel_role':
        mutate(root, lambda d: d['participant_index']['hearings'][0].update(end_page=0))
        value = 'mothers_counsel'
    else:
        mutate(root, lambda d: d['documents'][0].update(end_page=0))
        value = 'January 2, 2025'
    with pytest.raises(helper.RecordError, match='no usable'):
        search(root, **{scope:value})


def test_complete_negative_and_citation_collision(tmp_path):
    root = _write_case_bundle(tmp_path)
    result = search(root, query=['absent words'])
    assert result['matches'] == []
    assert result['scope_status'] == 'resolved'
    assert result['coverage'] == dict(candidate_pages=2, scanned_pages=2, missing_pages=0,
                                    unreadable_pages=0, rejected_paths=0, decoding_warnings=0,
                                    complete=True)
    mutate(root, lambda d: d['lookup']['by_citation_key'].update({'CT:1':['0001.txt','0002.txt']}))
    data = helper._load_source_map(root)
    assert len(helper._lookup_pages_for_citation(data, 'CT 1')) == 2
    assert len(search(root)['matches']) == 2
