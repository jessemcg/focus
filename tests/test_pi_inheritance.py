"""Preference inheritance and private workflow settings; no real Pi or data."""
import json
from pathlib import Path
import subprocess
import sys
from unittest.mock import patch

import pytest
from focus import pi_runtime as pi
from focus.ui.settings import AiSettingsWindow
from test_pi_model_settings_ui import model_window


def test_fresh_catalog_is_not_a_selection_and_refresh_failure_preserves_effort():
    window = model_window(None, None)
    model = pi.PiModel('synthetic', 'model', 'Synthetic')
    with patch('focus.ui.settings.Gtk.StringList.new', side_effect=list):
        AiSettingsWindow._finish_pi_model_load(window, 1, [model], '', None, '')
        assert window._selected_pi_model() is None
        assert not window._pi_model_selection_changed
        assert not window._pi_thinking_selection_changed
        window.pi_model_row.selected = 1
        AiSettingsWindow._on_pi_model_selected(window, None, None)
        assert window._pi_model_selection_changed
        assert not window._pi_thinking_selection_changed
        window.pi_thinking_row.selected = window._pi_thinking_options.index('high')
        AiSettingsWindow._on_pi_thinking_selected(window, None, None)
        AiSettingsWindow._finish_pi_model_load(window, 1, [], 'offline', model.settings_key, 'high')
        assert window._selected_pi_thinking_level() == 'high'
        assert window._pi_thinking_selection_changed


def test_catalog_capability_display_does_not_change_a_saved_effort():
    model = pi.PiModel('synthetic', 'model', 'Synthetic', supported_thinking_levels=('off',))
    window = model_window(model.settings_key, 'high')
    with patch('focus.ui.settings.Gtk.StringList.new', side_effect=list):
        AiSettingsWindow._finish_pi_model_load(window, 1, [model], '', model.settings_key, 'high')
    assert window._selected_pi_thinking_level() == 'off'
    assert not window._pi_thinking_selection_changed


def test_model_only_save_preserves_existing_unrelated_values_and_effort(tmp_path):
    path = tmp_path / 'pi/settings.json'
    model = pi.PiModel('synthetic', 'new', 'New')
    pi.save_project_pi_model(model, path)
    assert json.loads(path.read_text()) == {'defaultProvider': 'synthetic', 'defaultModel': 'new'}
    data = {'defaultProvider': 'synthetic', 'defaultModel': 'new', 'defaultThinkingLevel': 'high', 'unrelated': {'keep': 1}}
    path.write_text(json.dumps(data))
    # A fresh UI/application owns a fresh read baseline.
    from focus import _model_store
    _model_store._BASELINES.clear()
    pi.save_project_pi_model(pi.PiModel('synthetic', 'next', 'Next'), path)
    data['defaultModel'] = 'next'
    assert json.loads(path.read_text()) == data


@pytest.mark.parametrize('content', ['[]', '{bad'])
def test_bad_preferences_do_not_become_inheritance(tmp_path, content):
    path = tmp_path / 'settings.json'
    path.write_text(content)
    with pytest.raises(pi.PiSettingsError):
        pi.current_project_pi_model(path)
    assert path.read_text() == content


def test_private_skill_requirement_does_not_seed_preferences(tmp_path):
    script = Path(__file__).resolve().parents[1] / 'scripts/stage-pi-settings.py'
    prefs = tmp_path / 'absent/settings.json'
    staged = tmp_path / 'staged.json'
    subprocess.run([sys.executable, str(script), str(prefs), str(staged)], check=True)
    assert json.loads(staged.read_text()) == {'enableSkillCommands': True}
    assert not prefs.parent.exists()
    staged.unlink()
    prefs.parent.mkdir()
    prefs.write_text('{"enableSkillCommands":false,"unrelated":1}')
    original = prefs.read_bytes()
    subprocess.run([sys.executable, str(script), str(prefs), str(staged)], check=True)
    assert json.loads(staged.read_text()) == {'enableSkillCommands': True, 'unrelated': 1}
    assert prefs.read_bytes() == original
