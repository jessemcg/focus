"""GTK-independent metadata-7 controls. These do not validate native clicks."""
from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest

from focus.profile_artifacts import quotation_navigation_hash
from focus.quote_navigation import load_summary_navigation, normalize_source_display, revalidate_destination

FIXTURE = json.loads((Path(__file__).parent / 'fixtures/topic_quote_navigation.json').read_text())


def bundle(tmp_path, kind='hearings'):
    assert FIXTURE['fictional'] is True
    root = tmp_path / 'bundle'
    (root / 'text_pages').mkdir(parents=True)
    (root / 'summaries').mkdir()
    (root / 'text_pages/0012.txt').write_bytes(FIXTURE['source'].encode('utf-8'))
    summary = root / 'summaries' / f'{kind}_sum_Fictional.txt'
    summary.write_bytes(FIXTURE['cases'][kind]['text'].encode('utf-8'))
    meta = copy.deepcopy(FIXTURE['cases'][kind]['metadata'])
    summary.with_suffix('.meta.json').write_text(json.dumps(meta))
    return root, summary, meta


def load(root, summary, pages=(12,)):
    return load_summary_navigation(summary_path=summary, bundle_root=root, permitted_pages=pages)


@pytest.mark.parametrize('kind', ['hearings', 'reports', 'motions'])
def test_exact_saved_page_and_retained_span_not_phrase_search(tmp_path, kind):
    root, summary, meta = bundle(tmp_path, kind)
    result = load(root, summary)
    assert result.mode == 'anchored'
    assert not result.legacy_phrase_links
    first, second = result.occurrences
    assert first.display_text == 'Notice before entry'
    destination = first.destination
    assert destination is not None
    source = FIXTURE['source']
    assert destination.source_start == source.index('notice before entry')
    assert destination.source_start > source.lower().index('notice before entry')
    assert source[destination.source_start:destination.source_end] == 'notice before entry'
    displayed, _ = normalize_source_display(source)
    assert displayed[destination.display_start:destination.display_end] == 'notice before entry'
    assert destination.file_page == 12
    assert second.destination is None
    assert second.warning == 'quotation_unverified'
    assert result.unresolved_count == 1
    assert revalidate_destination(summary_path=summary, bundle_root=root, permitted_pages=[12],
        navigation_sha256=meta['navigation_sha256'], occurrence_id=first.occurrence_id) == destination


def test_raw_codepoints_not_utf16_or_bytes_and_newline_mapping():
    raw = '😀 A\r\nB\rC\nD'
    displayed, mapping = normalize_source_display(raw)
    assert displayed == '😀 A\nB\nC\nD'
    assert len(mapping) == len(raw) + 1
    assert mapping[raw.index('B')] == displayed.index('B') == 4
    assert displayed[mapping[raw.index('B')]:mapping[raw.index('D')+1]] == 'B\nC\nD'


def test_source_bytes_changed_disables_only_affected_destinations(tmp_path):
    root, summary, meta = bundle(tmp_path)
    first = load(root, summary).occurrences[0]
    (root / 'text_pages/0012.txt').write_bytes(FIXTURE['source'].replace('\r\n', '\n').encode())
    result = load(root, summary)
    assert result.mode == 'anchored'
    assert all(q.destination is None for q in result.occurrences)
    assert result.occurrences[0].warning == 'quotation_source_stale_or_invalid'
    assert not result.legacy_phrase_links
    assert revalidate_destination(summary_path=summary, bundle_root=root, permitted_pages=[12],
        navigation_sha256=meta['navigation_sha256'], occurrence_id=first.occurrence_id) is None


def test_metadata_only_anchor_change_invalidates_old_click_identity(tmp_path):
    root, summary, meta = bundle(tmp_path)
    old = load(root, summary)
    # Even a still source-valid destination with a changed diagnostic binding
    # must require reloading the navigation revision, not trust a stale tag.
    meta['quote_occurrences'][0]['initial_case'] = 'preserve'
    meta['navigation_sha256'] = quotation_navigation_hash(meta)
    summary.with_suffix('.meta.json').write_text(json.dumps(meta))
    assert meta['navigation_sha256'] != old.navigation_sha256
    assert revalidate_destination(summary_path=summary, bundle_root=root, permitted_pages=[12],
        navigation_sha256=old.navigation_sha256, occurrence_id=old.occurrences[0].occurrence_id) is None


@pytest.mark.parametrize('damage', ['text', 'hash', 'offset', 'unknown_contract', 'malformed_json', 'missing_offset', 'bad_source_path'])
def test_new_contract_damage_never_falls_back_to_legacy_heuristics(tmp_path, damage):
    root, summary, meta = bundle(tmp_path)
    if damage == 'text':
        summary.write_text('Changed summary')
    elif damage == 'hash':
        meta['navigation_sha256'] = '0'*64
    elif damage == 'offset':
        meta['quote_occurrences'][0]['start'] += 1
        meta['navigation_sha256'] = quotation_navigation_hash(meta)
    elif damage == 'unknown_contract':
        meta['schema_version'] = 8
    elif damage == 'missing_offset':
        del meta['quote_occurrences'][0]['anchor']['source_start']
        meta['navigation_sha256'] = quotation_navigation_hash(meta)
    elif damage == 'bad_source_path':
        meta['source_identities']['hearing:0012'][0]['path'] = '../elsewhere.txt'
        meta['navigation_sha256'] = quotation_navigation_hash(meta)
    sidecar = summary.with_suffix('.meta.json')
    sidecar.write_text('{' if damage == 'malformed_json' else json.dumps(meta))
    result = load(root, summary)
    assert result.mode == 'disabled'
    assert not result.legacy_phrase_links
    assert result.warnings


def test_outside_physical_inventory_source_link_is_not_trusted(tmp_path):
    root, summary, _ = bundle(tmp_path)
    result = load(root, summary, [19])
    assert result.mode == 'anchored'
    assert result.occurrences[0].destination is None
    assert not result.legacy_phrase_links


def test_symlinked_source_metadata_and_summary_are_not_trusted(tmp_path):
    root, summary, _ = bundle(tmp_path)
    source = root / 'text_pages/0012.txt'
    moved = root / 'moved.txt'
    source.rename(moved)
    source.symlink_to(moved)
    assert load(root, summary).occurrences[0].destination is None
    source.unlink()
    moved.rename(source)
    sidecar = summary.with_suffix('.meta.json')
    sidecar.rename(root / 'metadata.json')
    sidecar.symlink_to(root / 'metadata.json')
    assert load(root, summary).mode == 'disabled'


@pytest.mark.parametrize('version', [1, 2, 3, 4, 5, 6])
def test_historical_contract_retains_phrase_search_without_writes(tmp_path, version):
    root, summary, _ = bundle(tmp_path)
    sidecar = summary.with_suffix('.meta.json')
    sidecar.write_text(json.dumps({'schema_version': version}))
    before = {p: (p.read_bytes(), p.stat().st_mtime_ns) for p in root.rglob('*') if p.is_file()}
    assert load(root, summary).legacy_phrase_links
    after = {p: (p.read_bytes(), p.stat().st_mtime_ns) for p in root.rglob('*') if p.is_file()}
    assert before == after


def test_missing_sidecar_historical_and_marker_prevents_version_downgrade(tmp_path):
    root, summary, _ = bundle(tmp_path)
    sidecar = summary.with_suffix('.meta.json')
    sidecar.unlink()
    assert load(root, summary).legacy_phrase_links
    sidecar.write_text(json.dumps({'schema_version': 6, 'navigation_contract': 'damaged-new-contract'}))
    assert load(root, summary).mode == 'disabled'


def test_expected_new_contract_missing_meta_never_enables_legacy(tmp_path):
    root, summary, _ = bundle(tmp_path)
    summary.with_suffix('.meta.json').unlink()
    result = load_summary_navigation(summary_path=summary, bundle_root=root, permitted_pages=[12], new_contract_expected=True)
    assert result.mode == 'disabled'
    assert result.warnings == ('navigation_metadata_missing',)


def test_interrupted_publication_with_prior_historical_sidecar_disables_navigation(tmp_path):
    root, summary, _ = bundle(tmp_path)
    summary.with_suffix('.meta.json').write_text(json.dumps({'schema_version': 6, 'final_text_sha256': '0'*64}))
    assert load(root, summary).mode == 'disabled'


def test_summary_outside_bundle_is_not_navigation_authority(tmp_path):
    root, summary, _ = bundle(tmp_path)
    assert load(root, tmp_path / 'other.txt').mode == 'disabled'


def test_new_contract_read_and_activation_never_write(tmp_path):
    root, summary, meta = bundle(tmp_path)
    before = {p: (p.read_bytes(), p.stat().st_mtime_ns) for p in root.rglob('*') if p.is_file()}
    current = load(root, summary)
    revalidate_destination(summary_path=summary, bundle_root=root, permitted_pages=[12],
        navigation_sha256=meta['navigation_sha256'], occurrence_id=current.occurrences[0].occurrence_id)
    after = {p: (p.read_bytes(), p.stat().st_mtime_ns) for p in root.rglob('*') if p.is_file()}
    assert before == after
