"""Offline production boundary checks: wrapper -> adapter -> SDK -> collector.

Only disposable bundles/settings/artifacts. No credentials or live providers.
"""
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

import pytest

from test_focus_record_agent import _write_case_bundle

PROJECT = Path(__file__).resolve().parents[1]
COLLECTOR = PROJECT.parent / 'PiRunMetrics/run-collector.ts'


def _test_environment():
    # Do not give the offline SDK/helper real provider credentials or inherited tags.
    keys = ('PATH', 'HOME', 'XDG_STATE_HOME', 'XDG_CACHE_HOME', 'XDG_CONFIG_HOME',
            'XDG_RUNTIME_DIR', 'TMPDIR', 'PI_METRICS_TEST_SDK')
    return {key: os.environ[key] for key in keys if key in os.environ}


def test_actual_extension_contract(tmp_path):
    node = shutil.which('node')
    if not node:
        pytest.skip('Installed Pi/Node required')
    result = subprocess.run([node, str(PROJECT / 'tests/focus_extension_contract.mjs')],
                            cwd=PROJECT / 'tests', env=dict(_test_environment(), FOCUS_CONTRACT_ROOT=str(tmp_path)),
                            capture_output=True, text=True, timeout=30)
    assert result.returncode == 0, result.stderr


def setup(tmp_path):
    node = shutil.which('node')
    if not node or not COLLECTOR.is_file():
        pytest.skip('Installed Pi SDK and sibling PiRunMetrics required')
    case = _write_case_bundle(tmp_path)
    project = tmp_path / 'pi-project'
    shutil.copytree(PROJECT / '.pi/extensions', project / 'extensions')
    skill = project / 'skills/focus-answer-record-questions'
    skill.mkdir(parents=True)
    (skill / 'SKILL.md').write_text('---\nname: focus-answer-record-questions\ndescription: Synthetic test\n---\nSynthetic instructions.\n')
    (project / 'SYSTEM.md').write_text('Synthetic Focus system prompt.')
    (project / 'settings.json').write_text('{}')
    env = dict(_test_environment(), FOCUS_AGENT_CASE_ROOT=str(case), FOCUS_PI_PROJECT_DIR=str(project),
               FOCUS_AGENT_WORKSPACE=str(tmp_path / 'workspace'),
               FOCUS_AGENT_PROMPT_FILE=str(tmp_path / 'prompt.txt'),
               FOCUS_AGENT_ANSWER_PROTOCOL=str(PROJECT / 'focus/agent_answer.py'),
               FOCUS_AGENT_RUN_ID='abcdefghijklmnopqrstuvwx',
               FOCUS_RECORD_AGENT_PYTHON=sys.executable,
               FOCUS_RECORD_AGENT_HELPER=str(PROJECT / 'focus/agent_helper.py'),
               FOCUS_AGENT_COMMAND_ARGC='2', FOCUS_AGENT_COMMAND_ARG_0=node,
               FOCUS_AGENT_COMMAND_ARG_1=str(PROJECT / 'tests/focus_metrics_sdk_fixture.mjs'),
               PI_CODING_AGENT_DIR=str(tmp_path / 'synthetic-agent'),
               PI_RUN_METRICS_APP='stale', PI_RUN_METRICS_WORKFLOW='PRIVATE_CANARY',
               PI_RUN_METRICS_PI_VERSION='99.99.99', PI_RUN_METRICS_REVISION='PRIVATE_CANARY',
               PI_RUN_METRICS_BUILD_PROVENANCE='PRIVATE_CANARY',
               PI_RUN_METRICS_LAUNCH_CONFIGURATION='PRIVATE_CANARY')
    env.pop('PI_CODING_AGENT_SESSION_DIR', None)
    env.pop('PI_RUN_METRICS_DEFAULT_ROOT', None)
    return env


def run_variant(tmp_path, env, variant, scenario):
    runtime = tmp_path / 'runtime'
    runtime.mkdir(mode=0o700, exist_ok=True)
    # Reuse identical paths across comparisons; clear only this synthetic artifact.
    previous = runtime / 'answer.json'
    if previous.is_dir():
        previous.rmdir()
    else:
        previous.unlink(missing_ok=True)
    env = dict(env, FOCUS_AGENT_RUNTIME_DIR=str(runtime), FOCUS_AGENT_ANSWER_ARTIFACT=str(runtime / 'answer.json'),
               FOCUS_TEST_CAPTURE=str(tmp_path / ('capture-' + variant + '.json')),
               FOCUS_TEST_SCENARIO=scenario, PI_RUN_METRICS_ROOT=str(tmp_path / ('archive-' + variant)),
               PI_RUN_METRICS_ENABLED='0' if variant == 'disabled' else '1',
               PI_RUN_METRICS_COLLECTOR=str(tmp_path / 'missing.ts') if variant == 'missing' else str(COLLECTOR))
    if variant == 'unwritable':
        env['PI_RUN_METRICS_ROOT'] = '/dev/null/runs'
    if variant == 'relative':
        env['PI_RUN_METRICS_ROOT'] = 'relative'
    if variant in ('unsupported', 'unrecognized'):
        env['FOCUS_TEST_PI_VERSION'] = '0.87.0' if variant == 'unsupported' else 'PRIVATE_CANARY'
    else:
        # Controlled reproduction: package exports are import-only; tag must win.
        env['FOCUS_TEST_PI_VERSION'] = '0.99.1'
    Path(env['FOCUS_AGENT_PROMPT_FILE']).write_text('CANARY synthetic question')
    result = subprocess.run(['bash', str(PROJECT / 'scripts/focus-agent-vte.sh')],
                            env=env, capture_output=True, text=True, timeout=45)
    assert result.returncode == 0, result.stderr
    assert not Path(env['FOCUS_AGENT_WORKSPACE']).exists()
    assert not Path(env['FOCUS_AGENT_PROMPT_FILE']).exists()
    if variant not in ('enabled', 'disabled'):
        assert 'Pi run metrics: collection incomplete or unavailable.' in result.stderr
    capture = json.loads(Path(env['FOCUS_TEST_CAPTURE']).read_text())
    version = capture.pop('version', None)
    assert all(value in (None, '') for value in capture.pop('provenanceTags').values())
    # Shell adapter output may clear to empty strings; neither claims provenance.
    if variant in ('enabled', 'unwritable'):
        assert version == '0.99.1'
    else:
        assert version in (None, '')  # inherited version is replaced even if disabled
    files = sorted((tmp_path / ('archive-' + variant)).glob('*/*.jsonl'))
    if variant != 'enabled':
        assert files == []
        return capture, []
    assert len(files) == 2
    records = []
    for path in files:
        raw = path.read_text()
        for canary in ('CANARY', 'placement safe', '0001.txt', 'case_bundle', 'answer.json'):
            assert canary not in raw
        start, end = map(json.loads, raw.splitlines())
        assert start['pi_version'] == end['pi_version'] == '0.99.1'
        assert end['collector_version'] == '0.3.0'
        assert end['app'] == 'focus' and end['workflow'] == 'record_question'
        assert end['incomplete'] is False
        assert path.stat().st_mode & 0o777 == 0o600
        records.append(end)
    first = next(r for r in records if r['cycles'] == 2)
    assert first['focus_record_execution_errors'] == {'search': 2, 'lookup': 1, 'document': 1, 'map': 1}
    assert first['tools']['focus_record']['execution_errors'] == 5
    assert first['tools']['focus_record']['calls'] == 13
    helper = first['app_observations']['focus_record_helper']
    guard = first['app_observations']['focus_read_guard']
    assert helper['incomplete'] is False and guard['incomplete'] is False
    assert helper['calls'] == helper['observed_calls'] == 13
    assert guard['calls'] == guard['observed_calls'] == 5
    assert helper['counts']['record.arguments_rejected'] == 4
    assert helper['counts']['record.unclassified_execution_failure'] == 1
    assert guard['counts'] == {'read.permitted': 1, 'read.missing_path': 1,
                              'read.outside_boundary': 1, 'read.invalid_target': 1,
                              'read.unclassified_execution_failure': 1}
    assert records[0]['run_id'] != records[1]['run_id']
    followup = next(r for r in records if r['cycles'] == 1)
    assert followup['focus_record_execution_errors'] == {}
    assert followup['app_observations']['focus_read_guard']['calls'] == 0
    assert followup['app_observations']['focus_read_guard']['incomplete'] is False
    # Run the production reader on only these synthetic records; new fields are
    # additive and old totals remain valid, not malformed component records.
    import importlib.util
    spec = importlib.util.spec_from_file_location('synthetic_metrics_reader', COLLECTOR.parent / 'analyze_runs.py')
    sys.path.insert(0, str(COLLECTOR.parent))
    try:
        reader = importlib.util.module_from_spec(spec)
        sys.modules[spec.name] = reader
        spec.loader.exec_module(reader)
        for record in records:
            reader.validate(record)
    finally:
        sys.path.pop(0)
        sys.modules.pop(spec.name, None)
    return capture, records


@pytest.mark.parametrize('scenario', ['submit', 'fallback', 'partial', 'empty', 'cancel', 'artifact-failure'])
def test_wrapper_sdk_context_artifact_and_settlement_passivity(tmp_path, scenario):
    env = setup(tmp_path)
    enabled, records = run_variant(tmp_path, env, 'enabled', scenario)
    disabled, _ = run_variant(tmp_path, env, 'disabled', scenario)
    assert enabled == disabled
    assert enabled['settled'] == 2
    assert set(enabled['tools']) == {'read', 'focus_record', 'submit_focus_answer'}
    first = enabled['artifacts'][0]
    if scenario == 'artifact-failure':
        assert enabled['artifacts'] == [None, None]
        assert next(r for r in records if r['cycles'] == 2)['tools']['submit_focus_answer']['execution_errors'] == 1
    else:
        assert [a['revision'] for a in enabled['artifacts']] == [1, 2]
        assert first['capture'] == ('submit_tool' if scenario == 'submit' else 'assistant_fallback')
        assert first['status'] == ('partial' if scenario in ('partial', 'cancel', 'empty') else 'complete')
        assert bool(first['markdown']) == (scenario != 'empty')


def test_wrapper_fail_open_complete_boundary(tmp_path):
    env = setup(tmp_path)
    expected, _ = run_variant(tmp_path, env, 'enabled', 'submit')
    for variant in ('disabled', 'missing', 'unwritable', 'relative', 'unsupported', 'unrecognized'):
        capture, _ = run_variant(tmp_path, env, variant, 'submit')
        assert capture == expected


@pytest.mark.parametrize('invalid', [False, True])
def test_actual_extension_missing_or_invalid_map_is_application_error_not_health(tmp_path, invalid):
    env = setup(tmp_path)
    source_map = Path(env['FOCUS_AGENT_CASE_ROOT']) / 'artifacts/source_map.json'
    if invalid:
        source_map.write_text('{malformed')
    else:
        source_map.unlink()
    capture, records = run_variant(tmp_path, env, 'enabled', 'fallback')
    first = next(r for r in records if r['cycles'] == 2)
    assert first['diagnostics']['focus.context.ok'] == 1
    assert first['tools']['focus_record']['application_errors'] > 0
    assert first['focus_record_execution_errors'] == {'search': 2, 'lookup': 1, 'document': 1, 'map': 1}
    assert capture['artifacts'][0]['markdown']
    assert first['app_observations']['focus_record_helper']['counts']['record.map_unavailable'] > 0


def test_incomplete_coverage_observation_and_baseline_passivity(tmp_path):
    env = setup(tmp_path)
    (Path(env['FOCUS_AGENT_CASE_ROOT']) / 'text_pages/0002.txt').unlink()
    enabled, records = run_variant(tmp_path, env, 'enabled', 'submit')
    disabled, _ = run_variant(tmp_path, env, 'disabled', 'submit')
    assert enabled == disabled
    first = next(r for r in records if r['cycles'] == 2)
    counts = first['app_observations']['focus_record_helper']['counts']
    assert counts['record.incomplete_coverage'] == 1
    assert counts['record.document_not_found'] == 1
    assert counts['record.scope_unavailable'] == 1
    assert counts['record.empty_scope'] == 1
