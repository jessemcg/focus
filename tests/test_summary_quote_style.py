"""Neutral quote-matched summary emphasis and retired color setting; fiction only."""
import json
from types import SimpleNamespace
from unittest.mock import Mock

from gi.repository import Adw, Gdk, Gio, Gtk, Pango

from focus import core
from focus.app import Focus
from focus.summary_editions import SummaryPageDisplay
from focus.ui import settings as settings_module


TEXT = ('May 7, 2030 — Review\nAppearances: Applicant present.\n'
        'Orders: Work remains on hold pending repairs.\nNext: Review June 4.')


def test_labels_match_real_quote_tags_and_refresh_without_replacing_text():
    Adw.init()
    manager = Adw.StyleManager.get_default()
    original_scheme = manager.get_color_scheme()
    buffer = Gtk.TextBuffer()
    view = Gtk.TextView.new_with_buffer(buffer)
    # An existing old-style tag must lose both its accent and size boost.
    old_tag = buffer.create_tag('summary-entry-emphasis', foreground='#f6c65b', weight=Pango.Weight.BOLD, scale=1.08)
    harness = SimpleNamespace(
        _summary_buffer=buffer, _summary_view=view, _summary_scroller=None,
        _summary_active_source=core.SUMMARY_SOURCE_MINUTES, _summary_loaded_path=None,
        _summary_link_tags=[], _summary_link_tag_lookup={}, _ai_outputs={},
        _rgba_luminance=Focus._rgba_luminance,
        _recolor_link_tags=Focus._recolor_link_tags,
    )
    harness._resolve_ai_quote_color = lambda v: Focus._resolve_ai_quote_color(harness, v)
    harness._ensure_summary_emphasis_tag = lambda b: Focus._ensure_summary_emphasis_tag(harness, b)
    harness._apply_structured_summary_emphasis = lambda d: Focus._apply_structured_summary_emphasis(harness, d)
    phrase = 'pending repairs'; start = TEXT.index(phrase)
    display = SummaryPageDisplay(TEXT, ((start, start + len(phrase), phrase),))
    try:
        manager.set_color_scheme(Adw.ColorScheme.FORCE_LIGHT)
        Focus._apply_structured_summary_page(harness, display)
        quote = harness._summary_link_tags[0]
        assert harness._summary_link_tag_lookup == {quote: ('phrase', phrase)}
        for scheme in (Adw.ColorScheme.FORCE_DARK, Adw.ColorScheme.FORCE_LIGHT):
            manager.set_color_scheme(scheme)
            buffer.select_range(buffer.get_iter_at_offset(start), buffer.get_iter_at_offset(start + len(phrase)))
            Focus._refresh_ai_quote_colors(harness)
            tag = buffer.get_tag_table().lookup('summary-entry-emphasis')
            assert tag is old_tag
            assert tag.get_property('foreground-rgba').equal(quote.get_property('foreground-rgba'))
            assert tag.get_property('weight') == quote.get_property('weight') == Pango.Weight.MEDIUM
            assert tag.get_property('scale') == quote.get_property('scale') == 1.0
            assert tag.get_property('underline') == quote.get_property('underline')
            assert tag not in harness._summary_link_tag_lookup
            assert len(harness._summary_link_tags) == 1
            assert buffer.get_text(buffer.get_start_iter(), buffer.get_end_iter(), False) == TEXT
            a, b = buffer.get_selection_bounds()
            assert buffer.get_text(a, b, False) == phrase
    finally:
        manager.set_color_scheme(original_scheme)


def test_retired_color_stays_ignored_and_preserved_on_explicit_save():
    for value in ('#ff00ff', 'not-a-color', {'keep': 'historical value'}):
        core.CONFIG_FILE.write_text(json.dumps({'summary_emphasis_color': value}))
        before = (core.CONFIG_FILE.read_bytes(), core.CONFIG_FILE.stat().st_mtime_ns)
        settings = core.load_ai_settings()
        assert not hasattr(settings, 'summary_emphasis_color')
        assert (core.CONFIG_FILE.read_bytes(), core.CONFIG_FILE.stat().st_mtime_ns) == before
        core.save_ai_settings(settings)  # Synthetic config only, never production.
        assert json.loads(core.CONFIG_FILE.read_text())['summary_emphasis_color'] == value
    core.CONFIG_FILE.write_text('{}')
    core.save_ai_settings(core.load_ai_settings())
    assert 'summary_emphasis_color' not in json.loads(core.CONFIG_FILE.read_text())


def test_real_settings_window_omits_color_and_save_does_not_reintroduce_it(monkeypatch):
    Adw.init()
    core.CONFIG_FILE.write_text(json.dumps({'summary_emphasis_color': '#f6c65b'}))
    app = Adw.Application(application_id='com.mcglaw.Focus.SettingsQuoteStyleTest', flags=Gio.ApplicationFlags.NON_UNIQUE)
    app.register(None)
    app.get_font_preferences = lambda: (12, 12, 12)
    app.get_record_font_family_name = lambda: core.RECORD_FONT_FAMILY_OPTIONS[0][0]
    app.get_ai_settings = core.load_ai_settings
    app.update_font_sizes = Mock()
    app.on_ai_settings_saved = Mock()
    monkeypatch.setattr(settings_module, 'ensure_project_pi_settings', lambda: None)
    monkeypatch.setattr(settings_module, 'current_project_pi_model', lambda: None)
    monkeypatch.setattr(settings_module, 'current_project_pi_thinking_level', lambda: 'high')
    monkeypatch.setattr(settings_module.AiSettingsWindow, '_load_pi_models', lambda _self: None)
    before = (core.CONFIG_FILE.read_bytes(), core.CONFIG_FILE.stat().st_mtime_ns)
    window = settings_module.AiSettingsWindow(app)
    try:
        assert not hasattr(window, '_summary_emphasis_color_control')
        titles = []
        def walk(widget):
            if isinstance(widget, Adw.PreferencesRow):
                titles.append(widget.get_title())
            child = widget.get_first_child()
            while child:
                walk(child)
                child = child.get_next_sibling()
        walk(window)
        assert 'Summary Emphasis Color' not in titles
        assert 'Grep Highlight Color' in titles
        assert 'Phrase Highlight Color' in titles
        assert 'Search and Cite Chip Color' in titles
        assert (core.CONFIG_FILE.read_bytes(), core.CONFIG_FILE.stat().st_mtime_ns) == before
        window._on_save_clicked(None)
        assert json.loads(core.CONFIG_FILE.read_text())['summary_emphasis_color'] == '#f6c65b'
        saved = app.on_ai_settings_saved.call_args.args[0]
        assert not hasattr(saved, 'summary_emphasis_color')
        app.update_font_sizes.assert_called_once()
    finally:
        window.destroy()
        app.quit()
