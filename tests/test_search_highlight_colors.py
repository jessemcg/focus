"""Independent reader highlights and theme-owned chips; synthetic data only."""
import json
from types import SimpleNamespace

import gi

gi.require_version('Gtk', '4.0')
from gi.repository import Gtk, Pango

from focus import core
from focus.app import Focus


def test_old_chip_choice_is_not_a_search_preference():
    core.CONFIG_FILE.write_text(json.dumps({'search_chip_color': '#123456'}))
    before = core.CONFIG_FILE.read_bytes()
    settings = core.load_ai_settings()
    assert settings.search_highlight_color == core.DEFAULT_SEARCH_HIGHLIGHT_COLOR
    assert core.CONFIG_FILE.read_bytes() == before
    settings.search_highlight_color = settings.grep_highlight_color = '#abcdef'
    core.save_ai_settings(settings)
    saved = core.load_ai_settings()
    assert saved.search_highlight_color == saved.grep_highlight_color == '#abcdef'
    assert json.loads(core.CONFIG_FILE.read_text())['search_chip_color'] == '#123456'


def test_search_tags_refresh_in_place_and_keep_current_match_distinct():
    settings = core.load_ai_settings()
    buffer = Gtk.TextBuffer()
    buffer.set_text('Synthetic search text')
    harness = SimpleNamespace(_ai_settings=settings, _summary_buffer=buffer,
                              _summary_search_tag=None, _summary_search_current_tag=None)
    for color in ('#12ab34', '#bc45de'):
        settings.search_highlight_color = color
        Focus._ensure_summary_search_tags(harness)
        for tag in (harness._summary_search_tag, harness._summary_search_current_tag):
            expected = core.Gdk.RGBA()
            expected.parse(color)
            assert tag.get_property('background-rgba').equal(expected)
        assert harness._summary_search_current_tag.get_property('underline') == Pango.Underline.SINGLE
        assert buffer.get_text(buffer.get_start_iter(), buffer.get_end_iter(), False) == 'Synthetic search text'


def test_chip_css_uses_system_accent_not_reader_preferences():
    for selector in ('label.focus-search-chip', 'button.focus-citation-range-active:active',
                     'button.focus-minute-order-return-active:active'):
        rule = core.APP_CHROME_CSS.split(selector + ' {', 1)[1].split('}', 1)[0]
        assert 'background-color: @accent_bg_color;' in rule
        assert 'color: @accent_fg_color;' in rule
    harness = SimpleNamespace(_font_size_pt=12, _record_font_family_css='Sans',
                              _ai_font_size_pt=12, _color_provider=Gtk.CssProvider(),
                              _ensure_color_provider=lambda: None)
    Focus._apply_text_color(harness, '#123456')
    css = harness._color_provider.to_string()
    assert 'focus-search-chip' not in css
    assert 'focus-citation-range-active' not in css
