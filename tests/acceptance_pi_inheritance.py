"""Isolated native Settings acceptance. Run only in a disposable source/environment.

Control buttons exercise inherited state, unrelated Save, explicit model-only Save,
refresh failure and reopen. --auto runs the same checks without desktop input.
"""
import json
import os
from pathlib import Path
import sys
import tempfile
from unittest.mock import Mock, patch

os.umask(0o077)
ROOT = Path(tempfile.mkdtemp(prefix='focus-inheritance-'))
for key, directory in {'HOME': 'home', 'XDG_CONFIG_HOME': 'config', 'XDG_DATA_HOME': 'data',
                       'XDG_STATE_HOME': 'state', 'XDG_CACHE_HOME': 'cache',
                       'PI_CODING_AGENT_DIR': 'pi', 'FOCUS_CONFIG_DIR': 'app'}.items():
    os.environ[key] = str(ROOT / directory)
os.environ['GSETTINGS_BACKEND'] = 'memory'
from focus.ui import settings as ui
from focus import pi_runtime as runtime
PREFS = ROOT / 'app/pi/settings.json'
MODEL = ui.PiModel('synthetic', 'chosen', 'Synthetic choice')
app = ui.Adw.Application(application_id='org.synthetic.Focus.PiInheritance')
patches = []


def activate(application):
    application.get_font_preferences = lambda: (12, 12, 12)
    application.get_record_font_family_name = lambda: ui.RECORD_FONT_FAMILY_OPTIONS[0][0]
    application.update_font_sizes = Mock()
    application.on_ai_settings_saved = Mock()
    for name, value in (
        ('current_project_pi_model', lambda: runtime.current_project_pi_model(PREFS)),
        ('current_project_pi_thinking_level', lambda: runtime.current_project_pi_thinking_level(PREFS)),
        ('save_project_pi_runtime', lambda m, t: runtime.save_project_pi_runtime(m, t, PREFS)),
        ('load_ai_settings', lambda: ui.AiSettings(speech_agent_source_file='/synthetic/speech', highlight_phrases=['Keep literal'], grep_highlight_color=ui.DEFAULT_MATCH_COLOR, phrase_highlight_color=ui.DEFAULT_HIGHLIGHT_COLOR, search_chip_color=ui.DEFAULT_SEARCH_CHIP_COLOR)),
        ('save_ai_settings', lambda s: (ROOT / 'saved-display.json').write_text(json.dumps({'phrases': s.highlight_phrases}))),
    ):
        p = patch.object(ui, name, value); p.start(); patches.append(p)
    p = patch.object(ui.AiSettingsWindow, '_load_pi_models', lambda self: None)
    p.start(); patches.append(p)
    windows = []

    def reopen():
        if windows:
            windows.pop().destroy()
        w = ui.AiSettingsWindow(application)
        w.set_title('Synthetic Focus Pi inheritance')
        w._finish_pi_model_load(0, [MODEL], '', w._original_pi_model_key, w._original_pi_thinking_level or '')
        from focus.ui.settings_navigation import descendants
        for row in descendants(w):
            if isinstance(row, ui.Adw.ExpanderRow) and row.get_title() == 'Agent':
                row.set_expanded(True)
        windows.append(w); w.present()
        return w

    reopen()
    controls = ui.Adw.ApplicationWindow(application=application, title='Focus inheritance controls')
    box = ui.Gtk.Box(orientation=ui.Gtk.Orientation.VERTICAL, spacing=8)
    controls.set_content(box)
    steps = []

    def inherited_save():
        w = windows[0]
        assert w._selected_pi_model() is None
        assert not w._pi_model_selection_changed and not w._pi_thinking_selection_changed
        w._on_save_clicked(None)
        assert not PREFS.exists()
        assert json.loads((ROOT / 'saved-display.json').read_text()) == {'phrases': ['Keep literal']}
        print('PASS inherited/unrelated Save', flush=True)

    def choose_and_fail():
        w = windows[0]; w.pi_model_row.set_selected(1)
        assert not w._pi_thinking_selection_changed
        w._finish_pi_model_load(0, [], 'Synthetic refresh failure; selection retained', MODEL.settings_key, '')
        assert w._selected_pi_model().settings_key == MODEL.settings_key
        print('PASS explicit draft survives refresh failure', flush=True)

    def save_reopen():
        windows[0]._on_save_clicked(None)
        assert json.loads(PREFS.read_text()) == {'defaultProvider': 'synthetic', 'defaultModel': 'chosen'}
        w = reopen()
        assert w._selected_pi_model().settings_key == MODEL.settings_key
        assert not w._pi_thinking_selection_changed
        print('PASS model-only Save/reopen; reasoning inherited', flush=True)

    steps.extend([inherited_save, choose_and_fail, save_reopen])
    for label, callback in zip(('1 Save inherited', '2 Choose and fail refresh', '3 Save and reopen'), steps):
        button = ui.Gtk.Button(label=label)
        button.connect('clicked', lambda _, f=callback: f())
        box.append(button)
    done = ui.Gtk.Button(label='Finish acceptance')
    done.connect('clicked', lambda _: application.quit()); box.append(done)
    controls.present()
    print(f'ROOT={ROOT} PID={os.getpid()}', flush=True)
    if '--auto' in sys.argv:
        def run():
            for step in steps: step()
            application.quit()
            return False
        ui.GLib.timeout_add(500, run)


app.connect('activate', activate)
app.run([])
