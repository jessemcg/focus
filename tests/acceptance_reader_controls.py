"""Synthetic reader-control acceptance; no live Prose, clipboard, case or config.

Run: G_DEBUG=fatal-criticals uv run python tests/acceptance_reader_controls.py
Copies only source and checked-in PI resources into a disposable source tree
before importing Focus (HOME alone does not isolate source-relative settings).
Screenshots and measurements are left in the printed temporary directory.
"""
from __future__ import annotations

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
for name in ("SYSTEM.md", "extensions", "skills"):
    origin = source / ".pi" / name
    target = sandbox / ".pi" / name
    target.parent.mkdir(parents=True, exist_ok=True)
    if origin.is_dir():
        shutil.copytree(origin, target)
    else:
        shutil.copy2(origin, target)
for name in ("HOME", "XDG_CONFIG_HOME", "XDG_CACHE_HOME", "XDG_DATA_HOME", "XDG_STATE_HOME"):
    path = root / name
    path.mkdir(mode=0o700)
    os.environ[name] = str(path)
os.environ["GSETTINGS_BACKEND"] = "memory"
sys.path.insert(0, str(sandbox))

from focus import app as module, core  # noqa: E402
from gi.repository import Adw, GLib, Gtk  # noqa: E402
import cairo  # noqa: E402

core.CONFIG_FILE = sandbox / "config.json"
module.APPLICATION_ID = f"com.mcglaw.Focus.ReaderAcceptance.p{os.getpid()}"
bundle = root / "synthetic"
(bundle / "text_pages").mkdir(parents=True)
(bundle / "image_pages").mkdir()
(bundle / "summaries").mkdir()
for index in range(1, 4):
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
context.show_text("Synthetic image page 1")
surface.write_to_png(str(bundle / "image_pages" / "0001.png"))
(bundle / "image_pages" / "0002.png").write_bytes(b"corrupt image")

application = module.Focus(input_override=bundle)
sent = []
application._send_text_to_prose_record_citations_action = lambda text: sent.append(text) or True
application._copy_text_to_clipboard = lambda text: sent.append(text) or True


def current_label():
    page = application.current_index + 1
    return core.TranscriptPageLabel(
        file_page=page, transcript_page_number=page, citation_prefix="RT",
        citation_label=f"RT {page}", citation_key=f"rt {page}",
        record_type="reporter_transcript", series_id="rt", series_description="RT",
        status="official",
    )


application._current_transcript_page_label = current_label
application._current_page_citation_for_clipboard = lambda: f"(RT {application.current_index + 1}.)"
labels = {}
for index in range(3):
    application.current_index = index
    labels[index + 1] = current_label()
application.current_index = 0
application._transcript_page_index = core.TranscriptPageIndex(labels, {}, {})


def capture(name):
    window = application.win
    paintable = Gtk.WidgetPaintable.new(window)
    snapshot = Gtk.Snapshot()
    paintable.snapshot(snapshot, window.get_width(), window.get_height())
    texture = window.get_renderer().render_texture(snapshot.to_node(), None)
    texture.save_to_png(str(root / f"{name}.png"))
    group = application._current_page_citation_button.get_parent()
    print(name, "window", window.get_width(), window.get_height(),
          "controls", group.get_width(), group.get_height(),
          "full action group", group.get_parent().get_width(), flush=True)


def steps():
    app = application
    app._transcript_page_index = core.TranscriptPageIndex(labels, {}, {})
    app._sync_citation_buttons()
    app.win.set_title("Synthetic Focus Reader Acceptance")
    app.win.unmaximize()
    app.win.set_size_request(1100, 800)
    app.win.set_default_size(1100, 800)
    Adw.StyleManager.get_default().set_color_scheme(Adw.ColorScheme.FORCE_LIGHT)
    yield
    assert not app._back_to_text_button.get_visible()
    capture("light-wide")
    toolbar_height = app._current_page_citation_button.get_parent().get_height()
    app._current_page_citation_button.emit("clicked")
    assert sent == ["(RT 1.)"]
    ok, plus_bounds = app._citation_more_button.compute_bounds(app.win)
    assert ok
    plus_x = plus_bounds.get_x()
    for expected in ("+1", "+2"):
        app._citation_more_button.emit("clicked")
        yield  # Check after GTK has allocated the newly visible/wider preview.
        ok, bounds = app._citation_more_button.compute_bounds(app.win)
        assert ok and abs(bounds.get_x() - plus_x) < 1
        assert app._citation_count_entry.get_text() == expected
    preview = app._citation_preview_label
    assert preview.has_css_class("dim-label")
    assert app._page_total_label.has_css_class("dim-label")
    assert app._record_boundary_date_label.has_css_class("dim-label")
    assert preview.get_next_sibling() is app._current_page_citation_button.get_parent()
    # Active Cite is a low-profile chip, without shrinking the toolbar row.
    cite = app._current_page_citation_button
    search_chip = Gtk.Label(label="Cite")
    search_chip.add_css_class("focus-search-chip")
    ok, cite_bounds = cite.compute_bounds(app.win)
    assert ok
    assert cite_bounds.get_height() == search_chip.measure(Gtk.Orientation.VERTICAL, -1)[0]
    assert cite_bounds.get_height() < toolbar_height
    assert cite.get_parent().get_height() == toolbar_height
    capture("anchored-at-start")
    assert app._citation_count_entry.get_text() == "+2"
    assert app._citation_preview_label.get_label() == "RT 1–3"
    assert not app._citation_more_button.get_sensitive()
    app._show_page_from_link("2")
    yield
    assert app._citation_count_entry.get_text() == "+2"
    assert app._citation_preview_label.get_label() == "RT 1–3"
    assert app._citation_end_here_button.get_visible()
    capture("anchored-browsing")
    app.activate_action("insert_current_page_citation", None)
    assert sent[-1] == "(RT 2.)"
    assert app._page_citation_range_start.file_page == 1
    assert app._citation_count_entry.get_text() == "+2"
    app._citation_end_here_button.grab_focus()
    app._citation_end_here_button.emit("clicked")
    assert app._citation_count_entry.get_text() == "+1"
    app._current_page_citation_button.emit("clicked")
    assert sent[-1] == "(RT 1–2.)"
    assert app._page_citation_range_start is None
    assert app._citation_count_entry.get_text() == "+0"
    assert not app._citation_end_here_button.get_visible()
    assert not app._citation_end_here_button.has_focus()
    app.activate_action("insert_page_citation_range", None)
    app._show_page_from_link("3")
    app.activate_action("insert_page_citation_range", None)
    assert sent[-1] == "(RT 2–3.)"
    app._show_page_from_link("1")
    yield  # Let the navigation scroll-to-top idle settle first.
    app.scroller.get_vadjustment().set_value(200)
    app._image_preview_button.emit("clicked")
    assert app._show_image
    assert app._back_to_text_button.get_visible()
    app._back_to_text_button.grab_focus()
    yield
    capture("image")
    app._back_to_text_button.emit("clicked")
    assert not app._show_image
    assert not app._back_to_text_button.has_focus()
    assert app.textview.has_focus()
    yield
    assert abs(app.scroller.get_vadjustment().get_value() - 200) < 1
    app.activate_action("toggle_show_image", None)
    assert app._show_image
    app.activate_action("toggle_show_image", None)
    assert not app._show_image
    for index in (1, 2):  # Corrupt and missing PNGs.
        app.current_index = index
        assert not app._set_show_image(True)
        assert not app._back_to_text_button.get_visible()
        assert app._content_stack.get_visible_child_name() == "text"
    app.current_index = 0
    app._citation_count_entry.set_text("2")
    app._citation_count_entry.emit("activate")
    assert app._citation_count_entry.get_text() == "+2"
    app._show_page_from_link("2")
    app.win.set_size_request(-1, -1)
    app.win.set_default_size(900, 700)
    yield
    capture("light-narrow-pending")
    Adw.StyleManager.get_default().set_color_scheme(Adw.ColorScheme.FORCE_DARK)
    yield
    capture("dark-narrow-pending")
    app.win.set_size_request(1100, 800)
    app.win.set_default_size(1100, 800)
    yield
    capture("dark-wide-pending")
    print("PASS; synthetic screenshots:", root, flush=True)


failed = False
sequence = steps()


def advance():
    global failed
    try:
        next(sequence)
        return True
    except StopIteration:
        application.quit()
    except Exception:
        failed = True
        traceback.print_exc()
        application.quit()
    return False


application.connect("activate", lambda *_: GLib.timeout_add(900, advance))
application.run([])
sys.exit(1 if failed else 0)
