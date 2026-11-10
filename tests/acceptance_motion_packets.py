"""Read-only real-GTK schema-2 bundle acceptance, separate synthetic Focus instance."""
import argparse
import json
import os
from pathlib import Path
import sys
import tempfile

parser = argparse.ArgumentParser(); parser.add_argument('--bundle', type=Path, required=True); args = parser.parse_args()
bundle = args.bundle.resolve()
assert bundle.is_relative_to(Path(tempfile.gettempdir()).resolve()) and (bundle / '.continuous-motion-fixture').read_text() == 'fictional-only\n'
base = Path(tempfile.mkdtemp(prefix='focus-motion-packets-'))
for key in ('HOME', 'XDG_CONFIG_HOME', 'XDG_DATA_HOME', 'XDG_STATE_HOME', 'XDG_CACHE_HOME', 'PI_CODING_AGENT_DIR'):
    directory = base / key.lower(); directory.mkdir(mode=0o700); os.environ[key] = str(directory)
os.environ.update(PI_RUN_METRICS_ENABLED='0', GSETTINGS_BACKEND='memory')
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from focus import app as module, core, agent_helper
from focus.profile_artifacts import source_map_profile_metadata
core.CONFIG_FILE = base / 'config.json'
module.APPLICATION_ID = f'com.mcglaw.Focus.PacketAcceptance.p{os.getpid()}'
application = module.Focus(input_override=bundle)
before = {p: (p.read_bytes(), p.stat().st_mtime_ns) for p in bundle.rglob('*') if p.is_file()}
failures = []


def check():
    try:
        application.get_active_window().set_title('Focus — Synthetic Continuous Motion Packets')
        store = application._toc_sidebar_root_store
        assert [store.get_item(i).title for i in range(store.get_n_items())] == ['MOTIONS']
        motions = store.get_item(0)
        children = motions.get_children_model()
        assert [children.get_item(i).title for i in range(children.get_n_items())] == [
            'Request to Change Fictional Order', 'Separate Named Motion']
        application._toc_sidebar_tree_model.get_item(0).set_expanded(True)
        application.get_active_window().maximize()
        # Keep literal prepared TOC unchanged.
        toc = (bundle / 'artifacts/toc.txt').read_text()
        assert toc.count('Request to Change Fictional Order') == 1 and 'Unnamed' not in toc
        application._ensure_ai_panel_visible(); application._refresh_summary_availability()
        application._open_case_tool_summary(core.SUMMARY_SOURCE_MOTIONS)
        assert application._summary_edition.kind == 'motions'
        assert ('page', '11') in application._summary_link_tag_lookup.values()
        assert ('page', '21') in application._summary_link_tag_lookup.values()
        assert ('page', '14') not in application._summary_link_tag_lookup.values()
        assert ('phrase', 'distinct inspection phrase') in application._summary_link_tag_lookup.values()
        application._activate_link(('page', '11')); assert application.pages[application.current_index] == 11
        application._activate_link(('phrase', 'distinct inspection phrase'))
        source_map = agent_helper._load_source_map(bundle); source_map_profile_metadata(source_map)
        assert source_map['counts']['motions'] == 3 and source_map['counts']['motion_entries'] == 2
        matches = agent_helper._page_match_payloads(bundle, agent_helper._lookup_pages_for_file(source_map, 'text_pages/0015.txt'))
        assert matches[0]['motion_entries'][0]['group_id'] == 'motion:0011'
        assert matches[0]['document_ids'] == ['motion:0014']
        assert {p: (p.read_bytes(), p.stat().st_mtime_ns) for p in before} == before
        print(json.dumps(dict(status='PASS', pid=os.getpid(), checks=['schema2 sidebar', 'two summary headings', 'lead page links', 'continuation quote link', 'physical unnamed context', 'counts', 'no bundle writes'])), flush=True)
    except Exception as exc:
        failures.append(f'{type(exc).__name__}: {exc}'); print(json.dumps(dict(status='FAIL', failures=failures)), flush=True)
    hold = int(os.environ.get('FOCUS_MOTIONS_HOLD_MS', '0'))
    core.GLib.timeout_add(hold or 100, lambda: application.quit() or False)
    return False


core.GLib.timeout_add(1800, check)
core.GLib.timeout_add(int(os.environ.get('FOCUS_MOTIONS_HOLD_MS', '0')) + 20000, lambda: failures.append('timeout') or application.quit() or False)
application.run([])
raise SystemExit(bool(failures))
