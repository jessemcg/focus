"""Summary toolbar wrappers must not paint a second hover background."""

from types import SimpleNamespace
from unittest.mock import Mock

import gi

gi.require_version("Gtk", "4.0")
from gi.repository import Gio, Gtk

from focus.app import Focus


def test_summary_wrapper_style_is_scoped_and_preserves_controls():
    provider = Gtk.CssProvider()
    errors = []
    provider.connect("parsing-error", lambda *args: errors.append(args[-1]))
    owner = SimpleNamespace(
        _ai_settings=None,
        _font_size_pt=12,
        _record_font_family_css="sans-serif",
        _ai_font_size_pt=12,
        _color_provider=provider,
        _ensure_color_provider=Mock(),
    )
    Focus._apply_text_color(owner, "#222222")
    assert not errors
    css = provider.to_string()
    rule = css.split("flowbox.focus-summary-controls > flowboxchild {", 1)[1].split("}", 1)[0]
    assert "background-color: initial" in rule
    assert "background-image: none" in rule
    assert "box-shadow: none" in rule
    assert "outline" not in rule  # Keep keyboard focus visible.
    assert "\n  padding" not in rule  # Keep wrapping/layout unchanged.

    box = Focus._build_wrapping_controls_box(None)
    assert box.has_css_class("focus-summary-controls")
    assert box.get_selection_mode() == Gtk.SelectionMode.NONE
    owner._set_accessible_label = Focus._set_accessible_label
    pdf = Focus._build_pdf_button(owner, "Open summary PDF")
    assert pdf.get_label() is None
    assert pdf.get_tooltip_text() == "Open summary PDF"
    assert pdf.get_child().get_gicon().get_file().query_exists(None)
    assert isinstance(pdf.get_child().get_gicon(), Gio.FileIcon)
    bookmark = Gtk.Button(label="Set Bookmark")
    return_to_bookmark = Gtk.Button(label="Return")
    for button in (pdf, bookmark, return_to_bookmark):
        button.add_css_class("flat")
        box.insert(button, -1)
        assert isinstance(button.get_parent(), Gtk.FlowBoxChild)
        assert button.get_focusable()
        assert button.has_css_class("flat")
