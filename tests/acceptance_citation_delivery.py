"""Bounded real Focus -> Prose action -> private Writer/clipboard acceptance.

Run with system Python (UNO), passing an explicitly provisioned disposable Focus:
  /usr/bin/python3 tests/acceptance_citation_delivery.py \
    --focus-project /tmp/.../Focus --focus-environment /tmp/.../env \
    --prose-source /absolute/path/to/Prose

Copies only Prose source/prompts and its isolation support, never settings. Owns
one private Xwayland display/clipboard, D-Bus session, LO profile and dynamic port.
No production listener, model, document, clipboard, or Prose changes are used.
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import shutil
import signal
import subprocess
import sys
import tempfile
import time

HELPER = Path("/home/jesse/Dropbox/MCGLAW/config_files/scripts/PROJECTS/UvEnvironments/project-env")


def pump_until(predicate, timeout=20):
    from gi.repository import GLib
    deadline = time.monotonic() + timeout
    context = GLib.MainContext.default()
    while not predicate():
        while context.pending():
            context.iteration(False)
        if time.monotonic() > deadline:
            raise TimeoutError("Acceptance deadline exceeded")
        time.sleep(.02)


def client(root: Path, mode: str):
    # Executed ONLY by the explicitly selected disposable Focus environment.
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from focus.app import Focus
    from focus.core import TranscriptPageIndex, TranscriptPageLabel
    from gi.repository import Gtk, Gdk
    Gtk.init()

    class Delivery:
        for name in ("_deliver_citation", "_copy_text_to_clipboard",
                     "_send_text_to_prose_record_citations_action",
                     "_prose_record_citations_action_available",
                     "_insert_current_page_citation_in_prose_or_clipboard",
                     "_insert_page_citation_range_in_prose_or_clipboard",
                     "_resolve_current_citation_range", "_current_page_citation_for_clipboard"):
            locals()[name] = getattr(Focus, name)

        def __init__(self):
            self.pages = [1, 2, 3]
            self.page = 1
            self._page_citation_range_start = None
            self.messages = []
            self._transcript_page_index = TranscriptPageIndex({p: TranscriptPageLabel(
                p, p + 44, "RT", f"RT {p + 44}", f"rt {p + 44}",
                "reporter_transcript", "rt", "RT", "official") for p in self.pages}, {}, {})

        def _current_page_number(self):
            return self.page

        def _current_transcript_page_label(self):
            return self._transcript_page_index.by_file_page[self.page]

        def _transient_toast(self, message):
            self.messages.append(message)

        def _sync_citation_buttons(self):
            pass

        def _clear_citation_extent(self):
            self._page_citation_range_start = None

    app = Delivery()
    if mode == "range":
        assert app._insert_page_citation_range_in_prose_or_clipboard()
        assert not app.messages
        # Backwards range uses the actual app-owned validation/action methods.
        app.page = 3
        app._page_citation_range_start = app._current_transcript_page_label()
        app.page = 1
        ok = app._insert_page_citation_range_in_prose_or_clipboard()
    else:
        ok = app._insert_current_page_citation_in_prose_or_clipboard()
    assert ok
    (root / f"{mode}.ready").write_text(json.dumps(app.messages))
    # Keep the clipboard owner alive until a distinct process has read it.
    pump_until(lambda: (root / f"{mode}.ack").exists())
    assert Gdk.Display.get_default() is not None


def worker(args):
    root = args.root
    prose_copy = root / "Prose"
    for folder in ("prose", "prompts"):
        shutil.copytree(args.prose_source / folder, prose_copy / folder,
                        ignore=shutil.ignore_patterns("__pycache__"))
    support = prose_copy / "tests"
    support.mkdir()
    shutil.copy2(args.prose_source / "tests/remap_acceptance_support.py", support)
    sys.path[:0] = [str(prose_copy), str(support)]
    import gi
    gi.require_version("Gtk", "4.0")
    gi.require_version("Gdk", "4.0")
    from gi.repository import Gdk, Gtk
    Gtk.init()
    from remap_acceptance_support import isolated_writer
    from prose import app as prose_app

    def run_client(mode, expected, expected_feedback, document=None, writer_text=None):
        log = (root / f"focus-{mode}.log").open("w")
        command = [str(HELPER), "--project", str(args.focus_project), "--environment",
                   str(args.focus_environment), "run", "Focus", "python",
                   "tests/acceptance_citation_delivery.py", "--client", mode, "--root", str(root)]
        process = subprocess.Popen(command, stdout=log, stderr=log)
        try:
            ready = root / f"{mode}.ready"
            pump_until(lambda: ready.exists() or process.poll() is not None)
            assert ready.exists(), (root / f"focus-{mode}.log").read_text()
            assert json.loads(ready.read_text()) == [expected_feedback]
            readback = []
            def read_done(clipboard, result):
                readback.append(clipboard.read_text_finish(result))
            Gdk.Display.get_default().get_clipboard().read_text_async(None, read_done)
            pump_until(lambda: bool(readback))
            assert readback == [expected], readback
            primary = []
            def primary_done(clipboard, result):
                primary.append(clipboard.read_text_finish(result))
            Gdk.Display.get_default().get_primary_clipboard().read_text_async(None, primary_done)
            pump_until(lambda: bool(primary))
            assert primary == ["Synthetic PRIMARY sentinel"]
            if document is not None:
                pump_until(lambda: document.Text.String == writer_text)
                assert document.Text.String == writer_text
                assert document.Text.String.count(expected) == 1
            (root / f"{mode}.ack").touch()
            pump_until(lambda: process.poll() is not None)
            assert process.returncode == 0
            print(f"PASS {mode}: independent clipboard={expected!r}; {expected_feedback}", flush=True)
        finally:
            if process.poll() is None:
                process.terminate()
                process.wait(timeout=5)
            log.close()

    # Seed PRIMARY independently; citation delivery must never replace it.
    Gdk.Display.get_default().get_primary_clipboard().set("Synthetic PRIMARY sentinel")
    # No Prose registered: a successful clipboard must not require it.
    run_client("absent", "(RT 45.)", "Citation copied.")
    with isolated_writer(root) as port:
        assert port != 2004
        prose_app.UNO_BRIDGE_URL = (
            f"uno:socket,host=127.0.0.1,port={port};urp;StarOffice.ComponentContext"
        )
        prose_app.LIBREOFFICE_PROFILE = root / "lo-profile"
        # Fail closed instead of ever falling back to Prose's production launcher.
        def forbidden_listener(self):
            raise AssertionError("Acceptance must use only the private listener")
        prose_app.ProseWindow._start_listener = forbidden_listener
        application = prose_app.ProseApp()
        assert application.register(None)
        application.activate()
        window = application._window
        assert window is not None and window._connect_desktop(retries=5, delay=.1)
        desktop = window._desktop
        doc = desktop.loadComponentFromURL("private:factory/swriter", "_blank", 0, ())
        doc.Text.String = "LEFT RIGHT"
        doc.storeAsURL((root / "synthetic.odt").as_uri(), ())
        cursor = doc.CurrentController.ViewCursor
        cursor.gotoStart(False)
        cursor.goRight(5, False)
        window._active_doc = doc
        run_client("page", "(RT 45.)", "Citation copied and sent to Prose.", doc,
                   "LEFT (RT 45.) RIGHT")
        run_client("range", "(RT 45–47.)", "Citation copied and sent to Prose.", doc,
                   "LEFT (RT 45.) (RT 45–47.) RIGHT")
        assert doc.isModified()  # The citation action did not save the ODT.
        doc.Text.String = "LEFT TARGET RIGHT"
        cursor.gotoStart(False)
        cursor.goRight(5, False)
        cursor.goRight(6, True)
        run_client("selection", "(RT 45.)", "Citation copied and sent to Prose.", doc,
                   "LEFT (RT 45.) RIGHT")
        doc.close(True)
        window._active_doc = None
        notices = []
        original_toast = window._show_toast
        window._show_toast = lambda message: (notices.append(message), original_toast(message))
        run_client("nodoc", "(RT 45.)", "Citation copied and sent to Prose.")
        assert "Open a Writer document (File → Launch Writer)." in notices
        window.destroy()
        application.quit()
    print("PASS real Prose action, exactly-once Writer text and trailing spaces; no-document dispatch != insertion", flush=True)


def stop(process):
    if process.poll() is None:
        os.killpg(process.pid, signal.SIGTERM)
        try:
            process.wait(timeout=8)
        except subprocess.TimeoutExpired:
            os.killpg(process.pid, signal.SIGKILL)
            process.wait(timeout=5)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--focus-project", type=Path)
    parser.add_argument("--focus-environment", type=Path)
    parser.add_argument("--prose-source", type=Path)
    parser.add_argument("--root", type=Path)
    parser.add_argument("--worker", action="store_true")
    parser.add_argument("--client", choices=("absent", "page", "range", "selection", "nodoc"))
    args = parser.parse_args()
    if args.client:
        client(args.root, args.client)
        return
    if args.worker:
        def terminate(_signal, _frame):
            raise SystemExit("Acceptance terminated; cleaning private Writer")
        signal.signal(signal.SIGTERM, terminate)
        worker(args)
        return
    assert args.focus_project and args.focus_environment and args.prose_source
    for path in (args.focus_project, args.focus_environment):
        if not path.resolve().is_relative_to(Path(tempfile.gettempdir()).resolve()):
            raise ValueError("Acceptance requires disposable Focus source and environment under the system temp directory")
    root = Path(tempfile.mkdtemp(prefix="focus-prose-citation-"))
    print("Synthetic integration evidence:", root, flush=True)
    env = dict(os.environ, GDK_BACKEND="x11", GSETTINGS_BACKEND="memory", PI_RUN_METRICS_ENABLED="0")
    for key in ("HOME", "XDG_CONFIG_HOME", "XDG_CACHE_HOME", "XDG_DATA_HOME", "XDG_STATE_HOME"):
        folder = root / key
        folder.mkdir(mode=0o700)
        env[key] = str(folder)
    # Xwayland is an isolated X server, not the user's display/clipboard. It uses
    # the local compositor only to display its synthetic root window.
    read_fd, write_fd = os.pipe()
    with (root / "display.log").open("w") as log:
        display = subprocess.Popen(["Xwayland", "-displayfd", str(write_fd), "-ac", "-nolisten", "tcp",
                                    "-noreset", "-geometry", "1200x900", "-glamor", "off"],
                                   pass_fds=(write_fd,), stdout=log, stderr=log, start_new_session=True)
        os.close(write_fd)
        try:
            import select
            assert select.select([read_fd], [], [], 15)[0], "Private Xwayland failed to start"
            number = os.read(read_fd, 100).decode().strip()
            assert number.isdigit(), "Private Xwayland did not report its display"
            env["DISPLAY"] = f":{number}"
            env.pop("WAYLAND_DISPLAY", None)
            command = ["dbus-run-session", "--", "/usr/bin/python3", str(Path(__file__).resolve()),
                       "--worker", "--root", str(root), "--focus-project", str(args.focus_project),
                       "--focus-environment", str(args.focus_environment), "--prose-source", str(args.prose_source)]
            process = subprocess.Popen(command, env=env)
            try:
                assert process.wait(timeout=120) == 0, "Private integration worker failed"
            finally:
                if process.poll() is None:
                    process.terminate()
                    try:
                        process.wait(timeout=20)
                    except subprocess.TimeoutExpired:
                        process.kill()
                        process.wait(timeout=5)
        finally:
            os.close(read_fd)
            stop(display)


if __name__ == "__main__":
    main()
