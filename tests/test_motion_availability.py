import hashlib
import json
from pathlib import Path

import pytest

from focus.summary_availability import discover_summary, inspect_summary
from focus.record_categories import Category, PALETTE, PAGE_TYPES, heading_category, sidebar_category_rank


@pytest.mark.parametrize('source,title', [('hearing', 'Hearings Summary'), ('reports', 'Reports Summary'),
                                         ('motions', 'Motions Summary'), ('minutes', 'Minutes Summary'),
                                         ('minutes', 'Minute Orders Summary')])
def test_empty_and_real_document_heading(tmp_path, source, title):
    path = tmp_path / 'summary.txt'
    for text in ('', title + '\n', title + '\nFictional Case\n', '# ' + title + '\nFictional Case\n'):
        path.write_text(text)
        assert inspect_summary(path, source, case_name='Fictional Case').status == 'empty'
    path.write_text(title + '\nFictional Case\n\nMotion for a protective order\n')
    assert inspect_summary(path, source, case_name='Fictional Case').available
    path.write_text('Legacy substantive account without modern headings or metadata.')
    assert inspect_summary(path, source).available


def test_matching_final_metadata_zero_and_stale_or_corrupt_fallback(tmp_path):
    path = tmp_path / 'motions_sum.txt'
    path.write_text('Motions Summary\nFictional Case\n')
    meta = {'artifact': 'recordprep-summary-final-meta', 'schema_version': 5, 'kind': 'motions',
            'item_ids': [], 'final_text_sha256': hashlib.sha256(path.read_bytes()).hexdigest()}
    sidecar = path.with_suffix('.meta.json')
    sidecar.write_text(json.dumps(meta))
    assert inspect_summary(path, 'motions').status == 'empty'
    path.write_text('Motion for a protective order\nThe movant requested a limited inspection.')
    result = inspect_summary(path, 'motions')
    assert result.available and result.diagnostics == ('metadata_unusable_or_stale',)
    sidecar.write_text('{')
    result = inspect_summary(path, 'motions')
    assert result.available and result.diagnostics == ('metadata_unreadable_or_corrupt',)
    path.write_bytes(b'\xff')
    assert inspect_summary(path, 'motions').status == 'unreadable'


def test_discovery_precedence_empty_current_cache_refresh_and_case_identity(tmp_path):
    summaries = tmp_path / 'summaries'
    summaries.mkdir()
    legacy = summaries / 'motions_sum_organized.txt'
    legacy.write_text('Substantive historical motion narrative.')
    current = summaries / 'motions_sum_Case.txt'
    current.write_text('Motions Summary\n')
    manifest = tmp_path / 'manifest.json'
    manifest.write_text(json.dumps({'files': {'summarized_motions': str(current)}}))
    cache = {}
    def discover(root=tmp_path):
        return discover_summary(root, 'motions', root / 'manifest.json', ('summarized_motions',), (), ('motion',), cache=cache)
    assert discover().status == 'empty'
    current.write_text('Motions Summary\n\nMotion for protective order\nThe movant requested relief.')
    assert discover().available
    assert len(cache) == 1
    other = tmp_path / 'other'
    other.mkdir()
    (other / 'manifest.json').write_text('{}')
    assert discover(other).status == 'missing'
    assert discover().path == current
    current.unlink()
    assert discover().path == legacy


def test_intermediate_not_final_and_corrupt_not_empty(tmp_path):
    summaries = tmp_path / 'summaries'
    summaries.mkdir()
    (summaries / 'motions_digests_Case.md').write_text('Technical store')
    (summaries / 'motions_sum_renamed.md').write_text('<!-- recordprep:digest-document -->')
    args = (tmp_path, 'motions', None, (), (), ('motion',))
    assert discover_summary(*args).status == 'missing'
    (summaries / 'motions_sum.txt').write_bytes(b'\xff')
    assert discover_summary(*args).status == 'unreadable'
    (summaries / 'motions_sum.txt').write_text('Readable legacy narrative')
    assert discover_summary(*args).available


def test_case_name_keyword_never_reclassifies_another_summary_family(tmp_path):
    summaries = tmp_path / 'summaries'; summaries.mkdir()
    (summaries / 'hearings_sum_Fictional_Motion.txt').write_text('Hearings Summary\nFictional prose.')
    args = (tmp_path, 'motions', None, (), (), ('motion',))
    assert discover_summary(*args).status == 'missing'
    from focus.app import Focus
    from types import SimpleNamespace
    harness = SimpleNamespace(input_dir=tmp_path)
    assert Focus._infer_summary_source(harness, Path('motions_sum_Fictional_Hearing.txt')) == 'motions'
    assert Focus._infer_summary_source(harness, Path('minutes_sum_Motion_and_Report.txt')) == 'minutes'


def test_actual_minute_metadata_and_stale_zero_fallback(tmp_path):
    path = tmp_path / 'minutes_sum.txt'
    path.write_text('Arbitrary stale heading still correctly described by matching zero metadata.')
    meta = {'artifact': 'recordprep-minute-summary', 'schema_version': 5, 'inputs': {},
            'final_sha256': hashlib.sha256(path.read_bytes()).hexdigest()}
    path.with_suffix('.meta.json').write_text(json.dumps(meta))
    assert inspect_summary(path, 'minutes').status == 'empty'
    path.write_text('Real minute order: a substantive ruling appears here.')
    result = inspect_summary(path, 'minutes')
    assert result.available and result.diagnostics == ('metadata_unusable_or_stale',)


def test_motion_display_contract():
    assert PAGE_TYPES['ct_motion'] == PAGE_TYPES['ct_motion_first_page'] == Category.MOTION
    assert heading_category('MOTIONS') == Category.MOTION
    assert Category.MOTION in PALETTE
    assert [sidebar_category_rank(x) for x in ('FORMS', 'HEARINGS', 'REPORTS', 'MOTIONS', 'MINUTE ORDERS')] == list(range(5))
