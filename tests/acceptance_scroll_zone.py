"""Synthetic native scroll-zone preview; exits after 5 minutes, no real config/case.

Run with the maintained Focus project-env Python. Click the blank right rail:
left advances, right reverses, middle does nothing, wheel retains its directions.
Right clicks in the transcript must not navigate. Check the hint wraps in the rail.
"""
from pathlib import Path
import os
import shutil
import sys
import tempfile
import traceback

root = Path(tempfile.mkdtemp(prefix="focus-scroll-zone-"))
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
from gi.repository import Gdk, GLib, Gtk

core.CONFIG_FILE = sandbox / "config.json"
module.APPLICATION_ID = f"com.mcglaw.Focus.ScrollAcceptance.p{os.getpid()}"
bundle = root / "synthetic"
(bundle / "text_pages").mkdir(parents=True)
for index in range(1, 5):
    (bundle / "text_pages" / f"{index:04d}.txt").write_text(
        f"SYNTHETIC PAGE {index}\n\nScroll-zone navigation test.\n"
    )
application = module.Focus(input_override=bundle)


def ready():
    app = application
    if app.win is None or app._right_scroll_zone is None:
        return True
    app.win.set_title("Synthetic Focus Scroll Zone")
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
    print("PASS: scoped secondary controller, hint, left/right/wheel and boundaries", flush=True)
    return False

failed = False


def checked_ready():
    global failed
    try:
        return ready()
    except Exception:
        failed = True
        traceback.print_exc()
        application.quit()
        return False


GLib.timeout_add(1000, checked_ready)
GLib.timeout_add_seconds(300, lambda: application.quit() or False)
status = application.run([])
raise SystemExit(1 if failed else status)
