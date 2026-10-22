"""Isolated synthetic GTK citation/reader acceptance (no real delivery).

Use project-env with paired disposable source/environment overrides. Run under
G_DEBUG=fatal-criticals dbus-run-session -- xvfb-run -a for isolated rendering.
FOCUS_READER_NATIVE=1 keeps the final synthetic window for native input checks.
"""
from __future__ import annotations

from dataclasses import replace
import os
from pathlib import Path
import shutil
import sys
import tempfile
import traceback

root = Path(tempfile.mkdtemp(prefix="focus-reader-acceptance-"))
source = Path(__file__).resolve().parents[1]
sandbox = root / "source"
shutil.copytree(source / "focus", sandbox / "focus", ignore=shutil.ignore_patterns("__pycache__"))
for name in ("HOME", "XDG_CONFIG_HOME", "XDG_CACHE_HOME", "XDG_DATA_HOME", "XDG_STATE_HOME"):
    path = root / name
    path.mkdir(mode=0o700)
    os.environ[name] = str(path)
os.environ["GSETTINGS_BACKEND"] = "memory"
sys.path.insert(0, str(sandbox))

from focus import app as module, core  # noqa: E402
from gi.repository import Adw, Gio, GLib, Gtk  # noqa: E402
import cairo  # noqa: E402

core.CONFIG_FILE = sandbox / "config.json"
module.APPLICATION_ID = f"com.mcglaw.Focus.ReaderAcceptance.p{os.getpid()}"
bundle = root / "synthetic"
(bundle / "text_pages").mkdir(parents=True)
(bundle / "image_pages").mkdir()
for index in range(1, 5):
    (bundle / "text_pages" / f"{index:04d}.txt").write_text(
        f"SYNTHETIC RECORD — page {index}\n\n"
        + "\n".join(f"{line:02}  Sample testimony for reader-control acceptance." for line in range(1, 100))
    )
surface = cairo.ImageSurface(cairo.FORMAT_RGB24, 600, 800)
context = cairo.Context(surface)
context.set_source_rgb(1, 1, 1)
context.paint()
context.set_source_rgb(0, 0, 0)
context.set_font_size(25)
context.move_to(40, 80)
context.show_text("Synthetic image page")
for index in (1, 2, 3):
    surface.write_to_png(str(bundle / "image_pages" / f"{index:04d}.png"))
(bundle / "image_pages" / "0004.png").write_bytes(b"corrupt image")

application = module.Focus(input_override=bundle)
copied, dispatched = [], []
application._send_text_to_prose_record_citations_action = lambda text: dispatched.append(text) or True
application._copy_text_to_clipboard = lambda text: copied.append(text) or True
labels = {page: core.TranscriptPageLabel(
    file_page=page, transcript_page_number=page + 44, citation_prefix="RT",
    citation_label=f"RT {page + 44}", citation_key=f"rt {page + 44}",
    record_type="reporter_transcript", series_id="rt", series_description="RT", status="official",
) for page in range(1, 5)}


def install_labels(values=labels):
    application._transcript_page_index = core.TranscriptPageIndex(values.copy(), {}, {})
    application._sync_citation_buttons()


def populated():
    # Stress the complete header, not an empty record's lightweight controls.
    application._record_boundary_date_label.set_label("September 25, 2026")
    application._record_boundary_date_label.set_visible(True)
    application._reading_controls.set_visible(True)
    application._page_total_label.set_label("/ 99999")


def capture(name):
    window = application.win
    paintable = Gtk.WidgetPaintable.new(window)
    snapshot = Gtk.Snapshot()
    paintable.snapshot(snapshot, window.get_width(), window.get_height())
    texture = window.get_renderer().render_texture(snapshot.to_node(), None)
    texture.save_to_png(str(root / f"{name}.png"))
    toolbar = application._citation_range_button.get_parent().get_parent().get_parent()
    print(name, "window", window.get_width(), window.get_height(),
          "toolbar", toolbar.get_width(), toolbar.get_height(),
          "minimum", toolbar.measure(Gtk.Orientation.HORIZONTAL, -1)[0], flush=True)


def bounds(widget):
    ok, result = widget.compute_bounds(application.win)
    assert ok
    return result


def check_allocations(height):
    app = application
    toolbar = app._citation_range_button.get_parent().get_parent().get_parent()
    assert toolbar.get_height() == height
    controls = [app._page_number_entry, app._page_total_label,
                app._record_boundary_date_label, app._reading_controls,
                app._grep_entry, app._grep_hit_label, app._grep_prev_hit_button,
                app._grep_next_hit_button, app._current_page_citation_button,
                app._citation_range_button, app._citation_cancel_button, app._back_to_text_button]
    previous = None
    for widget in controls:
        if not widget.get_visible():
            continue
        rect = bounds(widget)
        assert rect.get_width() > 0, type(widget).__name__
        assert rect.get_x() >= 0 and rect.get_x() + rect.get_width() <= app.win.get_width() + 1
        if previous:
            assert previous.get_x() + previous.get_width() <= rect.get_x() + 1, (previous, rect)
        previous = rect
    assert app._citation_range_label.get_width() >= 60  # Never just "C…".


def steps():
    app = application
    install_labels()
    app.win.set_title("Synthetic Focus Reader Acceptance")
    app.win.unmaximize()
    app.win.set_size_request(1100, 800)
    app.win.set_default_size(1100, 800)
    Adw.StyleManager.get_default().set_color_scheme(Adw.ColorScheme.FORCE_LIGHT)
    populated()
    yield
    range_button = app._citation_range_button
    cancel = app._citation_cancel_button
    toolbar = range_button.get_parent().get_parent().get_parent()
    height = toolbar.get_height()
    assert height == 34
    assert app._current_page_citation_button.get_label() == "Cite page"
    assert app._current_page_citation_button.get_visible() and not cancel.get_visible()
    assert app._citation_range_label.get_label() == "Start range"
    check_allocations(height)
    capture("light-wide-idle")
    app.win.set_size_request(-1, -1)
    app._current_page_citation_button.emit("clicked")
    assert copied == dispatched == ["(RT 45.)"]
    range_button.grab_focus()
    range_button.emit("clicked")
    yield
    assert range_button.is_focus() and app._citation_range_button is range_button
    assert not app._current_page_citation_button.get_visible() and cancel.get_visible()
    assert app._citation_range_label.get_label() == "Cite RT 45"
    assert copied == dispatched == ["(RT 45.)"]
    assert range_button.has_css_class("focus-citation-range-active")
    assert bounds(range_button).get_height() == 26
    app._grep_entry.grab_focus()
    app._show_page_from_link("3")
    populated()
    yield
    assert app._citation_range_label.get_label() == "Cite RT 45–47"
    assert app._grep_entry.is_focus() or app._grep_entry.get_focus_child() is not None
    assert "3 pages" in range_button.get_tooltip_text()
    focus_before = app.win.get_focus()
    app.activate_action("insert_current_page_citation", None)
    yield
    assert app.win.get_focus() is focus_before
    assert copied[-1] == dispatched[-1] == "(RT 47.)"
    assert app._page_citation_range_start.file_page == 1
    range_button.emit("clicked")
    assert copied[-1] == dispatched[-1] == "(RT 45–47.)"
    assert app._page_citation_range_start is None
    app.activate_action("insert_page_citation_range", None)  # Anchor 3, backwards.
    app._show_page_from_link("1")
    app.activate_action("insert_page_citation_range", None)
    assert copied[-1] == dispatched[-1] == "(RT 45–47.)"
    range_button.emit("clicked")
    app._show_page_from_link("3")
    # Invalid interior, then recovery by navigation, without restarting.
    app._transcript_page_index.by_file_page[2] = replace(labels[2], series_id="other")
    app._sync_citation_buttons()
    assert not range_button.get_sensitive() and cancel.get_visible()
    assert app._citation_range_label.get_label() == "From RT 45…"
    assert "series" in range_button.get_tooltip_text()
    app._show_page_from_link("1")
    assert range_button.get_sensitive()
    before = len(copied)
    cancel.grab_focus()
    assert cancel.activate()  # GTK's normal button activation, not a custom key handler.
    yield
    assert range_button.is_focus() and not cancel.is_focus()
    assert len(copied) == len(dispatched) == before
    install_labels()
    assert range_button.activate()
    yield
    assert app._page_citation_range_start.file_page == 1
    assert range_button.activate()
    yield
    assert copied[-1] == dispatched[-1] == "(RT 45.)"
    range_button.emit("clicked")
    app._go_next()
    assert app._citation_range_label.get_label() == "Cite RT 45–46"
    app._page_number_entry.set_text("file 3")
    app._page_number_entry.emit("activate")
    assert app._citation_range_label.get_label() == "Cite RT 45–47"
    toc_store = Gio.ListStore(item_type=core.FocusSidebarItem)
    toc_store.append(core.FocusSidebarItem("Synthetic TOC", 2, kind="bookmark"))
    toc_model = Gtk.TreeListModel.new(toc_store, False, True, lambda _item: None)
    toc_row = Gtk.ListBoxRow()
    toc_row._focus_tree_row = toc_model.get_item(0)
    app._on_sidebar_row_activated(None, toc_row)
    assert app._citation_range_label.get_label() == "Cite RT 45–46"
    app._go_prev()
    assert app._citation_range_label.get_label() == "Cite RT 45"
    # View changes preserve the anchor and underlying page.
    app._reading_view_action.change_state(GLib.Variant("s", "original"))
    app._reading_view_action.change_state(GLib.Variant("s", "readable"))
    assert app._page_citation_range_start.file_page == 1
    yield
    app.scroller.get_vadjustment().set_value(200)
    app._image_preview_button.emit("clicked")
    yield
    assert app._show_image and app._back_to_text_button.get_visible()
    assert app._page_citation_range_start.file_page == 1
    capture("image-selection")
    app._back_to_text_button.grab_focus()
    app._back_to_text_button.emit("clicked")
    yield
    assert app.textview.is_focus() and not app._show_image
    assert abs(app.scroller.get_vadjustment().get_value() - 200) < 1
    app._set_show_image(True)
    app._go_next()
    assert app._show_image and app._citation_range_label.get_label() == "Cite RT 45–46"
    app._go_prev()
    assert app._show_image and app._citation_range_label.get_label() == "Cite RT 45"
    app._set_show_image(False)
    # Grep hit navigation goes through the same load/preview synchronization.
    app._grep_entry.set_text("SYNTHETIC RECORD")
    app._on_grep_entry_activate(app._grep_entry)
    yield
    yield
    assert app._grep_active and app._grep_next_hit_button.get_visible()
    app._on_grep_next_hit_clicked(None)
    assert app.current_index == 1
    assert app._page_citation_range_start.file_page == 1
    assert app._citation_range_label.get_label().startswith("Cite RT")
    app._show_page_from_link("3")
    assert app._citation_range_label.get_label() == "Cite RT 45–47"
    # Long volume/page labels, populated metadata/search, image return control.
    long_labels = {page: replace(label, citation_prefix="12345 RT", series_id="long",
                                citation_label=f"12345 RT {98764 + page}",
                                transcript_page_number=98764 + page)
                   for page, label in labels.items()}
    app._clear_citation_extent()
    install_labels(long_labels)
    app._show_page_from_link("1")
    range_button.emit("clicked")
    app._show_page_from_link("3")
    app._apply_grep("SYNTHETIC RECORD")
    yield
    yield
    app._on_grep_next_hit_clicked(None)
    app._on_grep_next_hit_clicked(None)
    assert app.current_index == 2 and app._grep_active
    app._set_show_image(True)
    populated()
    yield
    for width, height_px in [(1100, 800), (900, 700), (780, 700), (665, 700)]:
        app.win.set_default_size(width, height_px)
        yield
        assert app.win.get_width() == width, (width, app.win.get_width())
        for scheme, name in [(Adw.ColorScheme.FORCE_LIGHT, "light"),
                             (Adw.ColorScheme.FORCE_DARK, "dark")]:
            Adw.StyleManager.get_default().set_color_scheme(scheme)
            yield
            check_allocations(height)
            assert "12345 RT 98765–98767" in range_button.get_tooltip_text()
            capture(f"{name}-{width}-long-image")
    app._set_show_image(False)
    app._clear_citation_extent()
    app._apply_grep("")
    install_labels()
    app._show_page_from_link("1")
    populated()
    for width, height_px in [(1100, 800), (900, 700)]:
        app.win.set_default_size(width, height_px)
        yield
        for scheme, name in [(Adw.ColorScheme.FORCE_LIGHT, "light"),
                             (Adw.ColorScheme.FORCE_DARK, "dark")]:
            Adw.StyleManager.get_default().set_color_scheme(scheme)
            yield
            assert app.win.get_width() == width and app.win.get_height() == height_px
            check_allocations(height)
            capture(f"{name}-{width}-idle")
    range_button.emit("clicked")
    # Inventory reload and case-reset paths explicitly discard selection.
    app._scan_pages()
    assert app._page_citation_range_start is None
    install_labels()
    range_button.emit("clicked")
    app._reset_view_states()
    assert app._page_citation_range_start is None
    install_labels()
    app.pages = []
    app._sync_citation_buttons()
    assert not range_button.get_sensitive() and not app._current_page_citation_button.get_sensitive()
    app.pages = [1, 2, 3, 4]
    app.current_index = 0
    install_labels()
    # Leave a coherent long-label synthetic selection for optional desktop checks.
    if os.environ.get("FOCUS_READER_NATIVE"):
        install_labels(long_labels)
        app._show_page_from_link("1")
        range_button.emit("clicked")
        app._show_page_from_link("3")
        app._set_show_image(True)
        populated()
    print("PASS; synthetic screenshots:", root, flush=True)


failed = False
sequence = steps()


def advance():
    global failed
    try:
        next(sequence)
        return True
    except StopIteration:
        if os.environ.get("FOCUS_READER_NATIVE"):
            print("READY for native input; synthetic window only", flush=True)
        else:
            application.quit()
    except Exception:
        failed = True
        traceback.print_exc()
        application.quit()
    return False


application.connect("activate", lambda *_: GLib.timeout_add(500, advance))
application.run([])
sys.exit(1 if failed else 0)
