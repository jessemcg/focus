"""Actual GTK answer-artifact display acceptance; synthetic data, no models.

FOCUS_RELIABILITY_HOLD_SECONDS optionally keeps the uniquely titled preview open
for desktop observation after assertions. Tests never open the production app.
"""
import os
from pathlib import Path
import sys
import tempfile

root = Path(tempfile.mkdtemp(prefix='focus-reliability-display-'))
for key in ('HOME','XDG_CONFIG_HOME','XDG_CACHE_HOME','XDG_DATA_HOME','XDG_STATE_HOME'):
    target = root / key.lower()
    target.mkdir(mode=0o700)
    os.environ[key] = str(target)
os.environ['GSETTINGS_BACKEND'] = 'memory'
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from focus import app as module, core
from focus.agent_answer import create_focus_run_id
from focus.saved_answers import AgentAnswerSnapshot, new_answer_id, save_saved_answer
from test_agent_answer_polling import _artifact_payload, _write

core.CONFIG_FILE = root/'config.json'
module.APPLICATION_ID = f'com.mcglaw.Focus.Reliability.p{os.getpid()}'
bundle = root/'bundle'
(bundle/'text_pages').mkdir(parents=True)
(bundle/'text_pages/0001.txt').write_text('The agency recommended continued supervised visitation.\n')
(bundle/'case_name.txt').write_text('Synthetic reliability acceptance')
app = module.Focus(input_override=bundle)
result = {'ok':False}


def prepare():
    try:
        app.get_active_window().set_title('Focus — Synthetic Reliability Acceptance')
        app._set_ai_view(core.AI_VIEW_AGENT_QA)
        app._ai_panel_revealer.set_reveal_child(True)
        app._agent_run_id = create_focus_run_id()
        app._agent_answer_artifact_path = root/'runtime/answer.json'
        app._agent_answer_revision = 0
        app._agent_terminal_active = True
        app._agent_question_queue = ['Initial synthetic question','Synthetic follow-up','Second follow-up']
        first = '# Initial Answer\n*Partial evidence*\n\nThe agency recommended “continued supervised visitation”.'
        payload = _artifact_payload(app._agent_run_id,1,first,capture='assistant_fallback',status='partial')
        payload['diagnostics']['stop_reason'] = 'length'
        _write(app._agent_answer_artifact_path,payload)
        app._poll_agent_answer()
        initial = app._agent_displayed_snapshot
        assert initial.status == 'partial' and initial.question == 'Initial synthetic question'
        output = app._ai_outputs[core.AI_VIEW_AGENT_QA]
        assert any(value == ('phrase','continued supervised visitation') for value in output.link_lookup.values())
        second = '# Follow-up Answer\n*Best available text*\n\nThe agency recommended “continued supervised visitation”.'
        _write(app._agent_answer_artifact_path,_artifact_payload(app._agent_run_id,2,second,capture='assistant_fallback'))
        app._poll_agent_answer()
        followup = app._agent_displayed_snapshot
        assert followup.answer_id != initial.answer_id
        assert followup.question == 'Synthetic follow-up'
        assert 'Best' in app._agent_answer_status or 'best' in app._agent_answer_status
        saved = AgentAnswerSnapshot(answer_id=new_answer_id(),markdown=first,title='Synthetic saved',
            subtitle='Historical partial',status='partial',capture='assistant_fallback',answer_kind='answered',
            stop_reason='length',question='Saved synthetic question')
        save_saved_answer(bundle,saved.to_saved())
        stored = bundle/'.focus/saved-answers'/f'{saved.answer_id}.json'
        before = stored.read_bytes()
        app._display_agent_snapshot(saved,is_saved=True)
        third = '# Latest Answer\n*Source text verified*\n\nThe agency recommended “continued supervised visitation”.'
        _write(app._agent_answer_artifact_path,_artifact_payload(app._agent_run_id,3,third))
        app._poll_agent_answer()
        assert app._agent_displayed_snapshot.answer_id == saved.answer_id
        assert app._agent_live_snapshot.markdown == third
        assert stored.read_bytes() == before
        assert list(stored.parent.glob('*.json')) == [stored]
        app._display_agent_snapshot(app._agent_live_snapshot,is_saved=False)
        assert app._agent_displayed_snapshot.answer_id != followup.answer_id
        assert app._agent_subview_name == core.AGENT_SUBVIEW_ANSWER
        result['ok'] = True
        print('RELIABILITY DISPLAY PASS: revisions, partial/best-effort, quote links, saved isolation',flush=True)
    except Exception:
        import traceback
        traceback.print_exc()
    core.GLib.timeout_add(max(1,int(os.environ.get('FOCUS_RELIABILITY_HOLD_SECONDS','0')))*1000, stop)
    return False


def stop():
    app._agent_terminal_active = False
    app.quit()
    return False


app.connect('activate',lambda _app:core.GLib.timeout_add(500,prepare))
app.run([])
sys.exit(0 if result['ok'] else 1)
