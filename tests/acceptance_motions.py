"""Read a synthetic RecordPrep producer fixture in the real Focus GTK app.

First run RecordPrep/tests/prepare_motion_acceptance.py through its own disposable
environment; pass the printed --bundle path here through Focus's environment.
G_DEBUG=fatal-criticals is supported. FOCUS_MOTIONS_HOLD_MS holds the final window
for desktop observation. No provider, maintained instance or private data is used.
"""
from __future__ import annotations
import argparse
import json
import os
from pathlib import Path
import sys
import tempfile

parser = argparse.ArgumentParser()
parser.add_argument('--bundle', type=Path, required=True)
args = parser.parse_args()
bundle = args.bundle.resolve()
if (not bundle.is_relative_to(Path(tempfile.gettempdir()).resolve()) or
        (bundle / '.motion-acceptance-fixture').read_text() != 'synthetic-disposable-motion-fixture-v1\n'):
    raise SystemExit('Requires the disposable RecordPrep motion acceptance fixture, never a real case.')
root = Path(tempfile.mkdtemp(prefix='focus-motions-acceptance-'))
for name in ('HOME', 'XDG_CONFIG_HOME', 'XDG_CACHE_HOME', 'XDG_DATA_HOME', 'XDG_STATE_HOME'):
    path = root / name.lower(); path.mkdir(mode=0o700); os.environ[name] = str(path)
os.environ['GSETTINGS_BACKEND'] = 'memory'
os.environ['PI_RUN_METRICS_ENABLED'] = '0'
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from focus import core, app as module
from focus.record_categories import Category
core.CONFIG_FILE = root / 'focus-config.json'
module.APPLICATION_ID = f'com.mcglaw.Focus.MotionsAcceptance.p{os.getpid()}'
manifest = json.loads((bundle / 'manifest.json').read_text())
final = bundle / manifest['files']['summarized_motions']
before = {p: (p.read_bytes(), p.stat().st_mtime_ns) for p in bundle.rglob('*') if p.is_file()}
application = module.Focus(input_override=bundle)
failures = []


def require(condition, label):
    if not condition: failures.append(label)


def check():
    try:
        window = application.get_active_window(); window.set_title('Focus — Synthetic Motions Acceptance')
        application._ensure_ai_panel_visible()
        application._refresh_summary_availability()
        for source, button in application._summary_source_buttons.items():
            expected = source == core.SUMMARY_SOURCE_MOTIONS
            require(button.get_visible() == expected, f'button visibility {source}')
            require(button.get_parent().get_visible() == expected, f'wrapper visibility {source}')
        store = application._toc_sidebar_root_store
        sidebar_titles = [store.get_item(i).title for i in range(store.get_n_items())]
        require(sidebar_titles == ['MOTIONS'], f'filtered sidebar: {sidebar_titles!r}')
        application._open_case_tool_summary(core.SUMMARY_SOURCE_MOTIONS)
        require(application._summary_active_source == core.SUMMARY_SOURCE_MOTIONS, 'direct routing')
        require(application._summary_edition is not None, 'actual producer edition loaded')
        require(application._summary_edition.kind == 'motions', 'motion edition identity')
        require(application._summary_availability(core.SUMMARY_SOURCE_MOTIONS).available, 'nonempty motion final')
        require(all(application._category_index[p].category == Category.MOTION for p in range(1, 7)),
                'motion source-map categories')
        prior_view = (application._ai_active_view, application._summary_active_source, str(application._summary_loaded_path))
        final_bytes = final.read_bytes(); final.unlink()
        application._refresh_summary_availability()
        require(application._ai_active_view == core.AI_VIEW_AGENT_QA,
                f'unavailable fallback: before={prior_view!r}, after={application._ai_active_view!r}, '
                f'source={application._summary_active_source!r}, availability={application._summary_availability(core.SUMMARY_SOURCE_MOTIONS)!r}')
        final.write_bytes(final_bytes)
        os.utime(final, ns=(final.stat().st_atime_ns, before[final][1]))
        application._refresh_summary_availability()
        application._open_case_tool_summary(core.SUMMARY_SOURCE_MOTIONS)
        for p, value in before.items():
            require((p.read_bytes(), p.stat().st_mtime_ns) == value, f'fixture changed: {p.relative_to(bundle)}')
        # Populate every mode to exercise real wrapping. These are synthetic files.
        for kind in ('hearings', 'reports', 'minutes'):
            (bundle / manifest['files'][f'summarized_{kind}']).write_text(kind.title() + ' Summary\nFictional usable prose.\n')
        application._refresh_summary_availability()
        window.set_default_size(480, 720)
        core.Adw.StyleManager.get_default().set_color_scheme(core.Adw.ColorScheme.FORCE_LIGHT)
        core.GLib.timeout_add(700, finish)
    except Exception as exc:
        failures.append(f'{type(exc).__name__}: {exc}')
        finish()
    return False


def capture(name):
    window = application.get_active_window()
    paintable = core.Gtk.WidgetPaintable.new(window)
    snapshot = core.Gtk.Snapshot()
    paintable.snapshot(snapshot, window.get_width(), window.get_height())
    node = snapshot.to_node()
    require(node is not None, f'{name}: rendered snapshot')
    if node is not None:
        window.get_renderer().render_texture(node, None).save_to_png(str(root / f'{name}.png'))
    controls = list(application._summary_source_buttons.items())
    positions = []
    for source, widget in controls:
        ok, bounds = widget.compute_bounds(window)
        require(widget.get_mapped() and ok and bounds.get_x() >= 0
                and bounds.get_x() + bounds.get_width() <= window.get_width(),
                f'{name}: clipped/unmapped {source}')
        positions.append((source, round(bounds.get_x()), round(bounds.get_y())))
    if window.get_width() < 650:
        require(len({pos[2] for pos in positions}) > 1, f'{name}: controls did not wrap')
    print(json.dumps({'capture': name, 'width': window.get_width(), 'height': window.get_height(),
                      'controls': positions}), flush=True)


def finish():
    try:
        capture('motions-light-narrow')
        core.Adw.StyleManager.get_default().set_color_scheme(core.Adw.ColorScheme.FORCE_DARK)
        core.GLib.timeout_add(700, dark_capture)
    except Exception as exc:
        failures.append(f'capture: {type(exc).__name__}: {exc}')
        complete()
    return False


def dark_capture():
    try:
        capture('motions-dark-narrow')
        application.get_active_window().set_default_size(1280, 800)
        core.GLib.timeout_add(700, wide_capture)
    except Exception as exc:
        failures.append(f'capture: {type(exc).__name__}: {exc}')
        complete()
    return False


def wide_capture():
    try:
        capture('motions-dark-wide')
    except Exception as exc:
        failures.append(f'capture: {type(exc).__name__}: {exc}')
    complete()
    return False


def complete():
    (root / 'result.json').write_text(json.dumps({'failures': failures, 'bundle': str(bundle)}))
    print(json.dumps({'status': 'PASS' if not failures else 'FAIL', 'root': str(root), 'failures': failures}), flush=True)
    hold = int(os.environ.get('FOCUS_MOTIONS_HOLD_MS', '0'))
    if hold:
        core.GLib.timeout_add(hold, lambda: application.quit() or False)
    else:
        application.quit()
    return False


core.GLib.timeout_add(1800, check)
core.GLib.timeout_add(int(os.environ.get('FOCUS_MOTIONS_HOLD_MS', '0')) + 20000,
                      lambda: failures.append('acceptance timeout') or application.quit() or False)
application.run([])
raise SystemExit(bool(failures))
