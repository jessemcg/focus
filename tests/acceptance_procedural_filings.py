"""Real GTK, synthetic bundle, no providers; optional FOCUS_FILINGS_HOLD_MS."""
import json
import os
from pathlib import Path
import sys
import tempfile

root = Path(tempfile.mkdtemp(prefix='focus-procedural-ui-'))
for key in ('HOME', 'XDG_CONFIG_HOME', 'XDG_CACHE_HOME', 'XDG_DATA_HOME', 'XDG_STATE_HOME', 'PI_CONFIG'):
    p = root/key; p.mkdir(mode=0o700); os.environ[key] = str(p)
os.environ['GSETTINGS_BACKEND'] = 'memory'
os.environ['PI_RUN_METRICS_ENABLED'] = '0'
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from focus import core, app as module
from focus.record_categories import Category

bundle = root/'bundle'
(bundle/'text_pages').mkdir(parents=True)
(bundle/'artifacts').mkdir()
for page, text in enumerate(('Address notification', 'Request to change an existing order',
                              'Declaration supporting that request'), 1):
    (bundle/f'text_pages/{page:04d}.txt').write_text('Fictional test document: '+text+'\n')
(bundle/'manifest.json').write_text('{"schema_version":2}')
(bundle/'artifacts/toc.txt').write_text('FORMS\n    Address notification 1\nMOTIONS\n    Request and supporting declaration 2\n')
(bundle/'artifacts/transcript_page_numbers.json').write_text(json.dumps({'entries': [
    {'file_page': 1, 'page_type': 'CT_form_first_page', 'record_type': 'CT'},
    {'file_page': 2, 'page_type': 'CT_motion_first_page', 'record_type': 'CT'},
    {'file_page': 3, 'page_type': 'CT_motion', 'record_type': 'CT'}]}))
before = {p: (p.read_bytes(), p.stat().st_mtime_ns) for p in bundle.rglob('*') if p.is_file()}
core.CONFIG_FILE = root/'synthetic-config.json'
module.APPLICATION_ID = f'com.mcglaw.Focus.ProceduralAcceptance.p{os.getpid()}'
application = module.Focus(input_override=bundle)
failures = []


def descendants(widget):
    yield widget
    child = widget.get_first_child()
    while child:
        yield from descendants(child)
        child = child.get_next_sibling()


def check():
    try:
        window = application.get_active_window()
        window.set_title('Focus — Synthetic Procedural Filings')
        store = application._toc_sidebar_root_store
        assert store.get_n_items() == 2
        first = store.get_item(0)
        assert first.title == 'FORMS' and first.display_title == 'PROC. FILINGS'
        assert first.document_category == Category.FORM
        assert application._sidebar_item_key(first) == 'FORMS::'
        labels = [w.get_text() for w in descendants(window) if isinstance(w, core.Gtk.Label)]
        assert 'PROC. FILINGS' in labels and 'FORMS' not in labels
        heading = next(w for w in descendants(window)
                       if isinstance(w, core.Gtk.Label) and w.get_text() == 'PROC. FILINGS')
        assert heading.get_layout().get_line_count() == 1
        assert application._category_index[1].caption == 'Procedural filing · CT'
        assert application._category_index[2].caption == application._category_index[3].caption == 'Motion · CT'
        # Rebind from current spelling in memory, without touching canonical TOC.
        application._update_toc_from_text('Procedural filings\n    Address notification 1\nMOTIONS\n    Request and supporting declaration 2\n')
        assert store.get_item(0).display_title == 'PROC. FILINGS'
        assert store.get_item(0).document_category == Category.FORM
        assert before == {p: (p.read_bytes(), p.stat().st_mtime_ns) for p in bundle.rglob('*') if p.is_file()}
    except Exception as exc:
        failures.append(f'{type(exc).__name__}: {exc}')
    print(json.dumps({'status': 'FAIL' if failures else 'PASS', 'failures': failures, 'root': str(root)}), flush=True)
    hold = int(os.environ.get('FOCUS_FILINGS_HOLD_MS', '0'))
    core.GLib.timeout_add(max(hold, 100), lambda: application.quit() or False)
    return False


core.GLib.timeout_add(1800, check)
core.GLib.timeout_add(int(os.environ.get('FOCUS_FILINGS_HOLD_MS', '0')) + 15000,
                      lambda: failures.append('timeout') or application.quit() or False)
application.run([])
raise SystemExit(bool(failures))
