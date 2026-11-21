"""Synthetic native navigation preview, with no real config or case.

Run with disposable Focus project-env Python. Pass --check to exit after the
assertions; otherwise the preview stays open for five minutes. On the right
rail, left advances, right reverses, middle does nothing, and wheel navigates.
Right clicks in the transcript must not navigate. Check the hint wraps in the rail.
Open the thumbnail and try left/right near image edges before and after resizing.
Middle-click, wheel and blank margins must not page; Back to text still works.
"""
from pathlib import Path
import os
import shutil
import sys
import tempfile
import traceback

import cairo

check_only = sys.argv[1:] == ["--check"]
workspace = tempfile.TemporaryDirectory(prefix="focus-scroll-zone-")
root = Path(workspace.name)
source = Path(__file__).resolve().parents[1]
sandbox = root / "source"
shutil.copytree(source / "focus", sandbox / "focus", ignore=shutil.ignore_patterns("__pycache__"))
for name in ("HOME", "XDG_CONFIG_HOME", "XDG_CACHE_HOME", "XDG_DATA_HOME", "XDG_STATE_HOME"):
    path = root / name
    path.mkdir(mode=0o700)
    os.environ[name] = str(path)
os.environ["GSETTINGS_BACKEND"] = "memory"
sys.path.insert(0, str(sandbox))
from focus import app as module, core
from gi.repository import Gdk, GdkPixbuf, Gio, GLib, Gtk

core.CONFIG_FILE = sandbox / "config.json"
module.APPLICATION_ID = f"com.mcglaw.Focus.ScrollAcceptance.p{os.getpid()}"
bundle = root / "synthetic"
(bundle / "text_pages").mkdir(parents=True)
for index in range(1, 5):
    (bundle / "text_pages" / f"{index:04d}.txt").write_text(
        f"SYNTHETIC PAGE {index}\n\nScroll-zone navigation test.\n"
    )
colors = {1: (0, 255, 255), 2: (255, 255, 0), 4: (255, 0, 255)}
(bundle / "image_pages").mkdir()
for page, color in colors.items():
    surface = cairo.ImageSurface(cairo.FORMAT_RGB24, 440, 580)
    cr = cairo.Context(surface)
    cr.set_source_rgb(*(channel / 255 for channel in color))
    cr.paint()
    cr.set_source_rgb(0, 0, 0)
    cr.set_font_size(72)
    cr.move_to(60, 120)
    cr.show_text(f"Page {page}")
    surface.write_to_png(str(bundle / "image_pages" / f"{page:04d}.png"))
application = module.Focus(input_override=bundle)


def ready():
    app = application
    if app.win is None or app._right_scroll_zone is None:
        return True
    zone = app._right_scroll_zone
    controllers = zone.observe_controllers()
    secondary = [controllers.get_item(i) for i in range(controllers.get_n_items())
                 if isinstance(controllers.get_item(i), Gtk.GestureClick)
                 and controllers.get_item(i).get_button() == Gdk.BUTTON_SECONDARY]
    assert len(secondary) == 1
    assert secondary[0].get_propagation_phase() == Gtk.PropagationPhase.CAPTURE
    assert secondary[0].get_widget() is zone
    label = zone.get_child().get_last_child()
    assert label.get_text() == "Scroll · Left-click next · Right-click back"
    assert label.get_wrap()
    # Exercise real navigation, including first/last-page clamping.
    assert app.current_index == 0
    app._on_right_scroll_zone_right_pressed(secondary[0], 1, 10, 10)
    assert app.current_index == 0
    zone.emit("clicked")
    assert app.current_index == 1
    app._on_right_scroll_zone_right_pressed(secondary[0], 1, 10, 10)
    assert app.current_index == 0
    for _ in range(5):
        zone.emit("clicked")
    assert app.current_index == 3
    for _ in range(2):
        app._on_right_scroll_zone_scroll(None, 0, -1)
    assert app.current_index == 1
    print("PASS: scoped rail controller, hint, left/right/wheel and boundaries", flush=True)
    assert app._image_preview_button.get_visible()
    app._image_preview_button.emit("clicked")
    GLib.timeout_add(250, checked_ready, check_image_navigation)
    return False


def check_image_navigation():
    global completed
    app = application
    picture = app._image_picture
    model = picture.observe_controllers()

    def gestures():
        return [item for item in model if isinstance(item, Gtk.GestureClick)]

    clicks = gestures()
    assert sorted(click.get_button() for click in clicks) == [Gdk.BUTTON_PRIMARY, Gdk.BUTTON_SECONDARY]
    assert all(click.get_widget() is picture for click in clicks)
    by_button = {click.get_button(): click for click in clicks}
    left = by_button[Gdk.BUTTON_PRIMARY]
    right = by_button[Gdk.BUTTON_SECONDARY]

    def assert_image(page):
        assert app.current_index == page - 1
        assert app._page_number_entry.get_text() == str(page)
        assert app._show_image and app._content_stack.get_visible_child_name() == "image"
        assert picture.get_alternative_text() == f"Page {page:04d} image"
        texture = picture.get_paintable()
        assert isinstance(texture, Gdk.Texture)
        stream = Gio.MemoryInputStream.new_from_bytes(texture.save_to_png_bytes())
        pixels = GdkPixbuf.Pixbuf.new_from_stream(stream, None).get_pixels()
        assert tuple(pixels[:3]) == colors[page]

    assert_image(2)
    right.emit("pressed", 1, 5.0, 5.0)
    assert_image(1)
    right.emit("pressed", 1, 5.0, 5.0)
    assert_image(1)
    for _ in range(2):
        left.emit("pressed", 1, 5.0, 5.0)
        assert_image(2)
        right.emit("pressed", 1, 5.0, 5.0)
        assert_image(1)
    assert gestures() == clicks

    left.emit("pressed", 1, 5.0, 5.0)
    assert_image(2)
    left.emit("pressed", 1, 5.0, 5.0)
    assert app.current_index == 2
    assert not app._show_image and app._content_stack.get_visible_child_name() == "text"
    assert picture.get_paintable() is None
    buffer = app.textview.get_buffer()
    assert buffer.get_text(*buffer.get_bounds(), False).startswith("SYNTHETIC PAGE 3")

    app._go_next()
    app._image_preview_button.emit("clicked")
    assert gestures() == clicks
    assert_image(4)
    left.emit("pressed", 1, 5.0, 5.0)
    assert_image(4)
    app._back_to_text_button.emit("clicked")
    assert app.current_index == 3 and app._content_stack.get_visible_child_name() == "text"
    print("PASS: thumbnail, image clicks, stable controllers, boundaries and text fallback", flush=True)
    completed = True
    if check_only:
        app.quit()
    else:
        app._go_first()
    return False


failed = False
completed = False


def checked_ready(check):
    global failed
    try:
        return check()
    except Exception:
        failed = True
        traceback.print_exc()
        application.quit()
        return False


GLib.timeout_add(1000, checked_ready, ready)
GLib.timeout_add_seconds(300, lambda: application.quit() or False)
status = application.run([])
workspace.cleanup()
raise SystemExit(1 if failed or not completed else status)
