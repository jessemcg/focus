#!/usr/bin/env python3
"""Synthetic Focus GUI, never reads the user's config or case data.

uv run python scripts/preview-record-categories.py [--check] [--dark] [--high-contrast]
--check exercises the real widgets/navigation and exits; otherwise leaves a preview.
All output/config/data stays in the printed new temporary directory. F6 toggles
light/dark chrome; F7 runs appearance-preservation checks; ordinary Focus keys work.
High contrast is an actual process-local Adwaita debug preference (not a system write).
--screenshots re-launches on a PRIVATE Xvfb display, saves synthetic screenshots
there, then exits (requires xvfb-run and ImageMagick import). No desktop capture.
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import traceback


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--dark", action="store_true")
    parser.add_argument("--high-contrast", action="store_true")
    parser.add_argument("--screenshots", action="store_true")
    args = parser.parse_args()
    if args.screenshots and os.environ.get("FOCUS_CATEGORY_PRIVATE_DISPLAY") != "1":
        return subprocess.run(
            ["xvfb-run", "-a", "-s", "-screen 0 1200x900x24", sys.executable,
             str(Path(__file__).resolve()), *sys.argv[1:]],
            env=dict(os.environ, GDK_BACKEND="x11", FOCUS_CATEGORY_PRIVATE_DISPLAY="1"),
            check=False,
        ).returncode
    root = Path(tempfile.mkdtemp(prefix="focus-categories-"))
    for name in ("HOME", "XDG_CONFIG_HOME", "XDG_CACHE_HOME", "XDG_DATA_HOME", "XDG_STATE_HOME"):
        path = root / name.lower()
        path.mkdir()
        os.environ[name] = str(path)
    os.environ["GSETTINGS_BACKEND"] = "memory"
    os.environ["ADW_DEBUG_HIGH_CONTRAST"] = "1" if args.high_contrast else "0"
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from focus import core
    from focus import app as module
    from focus.record_categories import Category
    core.CONFIG_FILE = root / "config.json"
    module.APPLICATION_ID = f"com.mcglaw.Focus.CategoryPreview.p{os.getpid()}"
    Gtk, Adw, GLib, Gdk = core.Gtk, core.Adw, core.GLib, core.Gdk
    bundle = root / "synthetic"
    for name in ("text_pages", "image_pages", "artifacts", "summaries"):
        (bundle / name).mkdir(parents=True)
    (bundle / "manifest.json").write_text('{"schema_version":2}')
    (bundle / "case_name.txt").write_text("Synthetic category preview")
    tokens = ["RT_body_first_page", "RT_body", "CT_report", "CT_minute_order_first_page",
              "CT_minute_order", "CT_form_first_page", "CT_form", "CT_index", None, None]
    entries = []
    for page, token in enumerate(tokens, 1):
        title = ["Hearing", "Hearing continuation", "Report", "Minute order", "Minute continuation",
                 "Form", "Form continuation", "Index / Other", "Exact TOC fallback", "Unclassified"][page - 1]
        text = f"{title}\n\nThis is synthetic record text, not client material.\n\n"
        text += "\n".join(f"{line:02d}  Sample testimony and findings. Search phrase remains readable."
                          for line in range(1, 65))
        (bundle / "text_pages" / f"{page:04d}.txt").write_text(text)
        pixbuf = core.GdkPixbuf.Pixbuf.new(core.GdkPixbuf.Colorspace.RGB, False, 8, 480, 640)
        pixbuf.fill(0xF6F6F6FF)
        pixbuf.savev(str(bundle / "image_pages" / f"{page:04d}.png"), "png", [], [])
        entries.append({"file_page": page, "page_type": token,
                        "record_type": "RT" if page <= 2 else "CT" if page <= 8 else "",
                        "transcript_page_number": 100 + page, "status": "selected"})
    artifacts = bundle / "artifacts"
    (artifacts / "transcript_page_numbers.json").write_text(json.dumps({"entries": entries}))
    (artifacts / "hearing_boundaries.json").write_text('[{"date":"2026-01-01","start_page":1,"end_page":2}]')
    (artifacts / "minutes_boundaries.json").write_text('[{"date":"2026-01-01","start_page":4,"end_page":5}]')
    toc = ("Hearings\n    Hearing with a deliberately long descriptive title that wraps in a narrow sidebar 1\n"
           "Reports\n    Report on synthetic findings 3\n"
           "Minute orders\n    Minute order from the matching hearing 4\n"
           "Forms\n    Form with a very long title for testing wrapping and ellipsis while keeping headings readable 6\n"
           "    Exact-page fallback form 9\n")
    (artifacts / "toc.txt").write_text(toc)
    application = module.Focus(input_override=bundle)
    manager = Adw.StyleManager.get_default()
    manager.set_color_scheme(Adw.ColorScheme.FORCE_DARK if args.dark else Adw.ColorScheme.FORCE_LIGHT)
    assert manager.get_high_contrast() == args.high_contrast
    errors = []
    failed = []

    def drain():
        deadline = time.monotonic() + .4
        context = GLib.MainContext.default()
        while time.monotonic() < deadline:
            while context.pending():
                context.iteration(False)
            time.sleep(.005)

    def expand():
        model = application._toc_sidebar_tree_model
        i = 0
        while i < model.get_n_items():
            row = model.get_item(i)
            if row.get_item().kind == "category":
                row.set_expanded(True)
            i += 1

    def snapshot_state():
        buffer = application.textview.get_buffer()
        model = application._toc_sidebar_tree_model
        return (buffer, buffer.get_text(*buffer.get_bounds(), True),
                tuple(i.get_offset() for i in buffer.get_selection_bounds()),
                application._current_page_number(), application.scroller.get_vadjustment().get_value(),
                model, tuple(model.get_item(i).get_expanded() for i in range(model.get_n_items())),
                buffer.get_tag_table().get_size(), tuple(application._link_tags))

    def theme_checks():
        buffer = application.textview.get_buffer()
        buffer.select_range(buffer.get_iter_at_offset(12), buffer.get_iter_at_offset(35))
        drain()  # let prior grep/selection scroll animations finish first
        application.scroller.get_vadjustment().set_value(120)
        drain()
        before = snapshot_state()
        original = manager.get_color_scheme()
        for scheme in (Adw.ColorScheme.FORCE_DARK, Adw.ColorScheme.FORCE_LIGHT, original):
            manager.set_color_scheme(scheme)
            drain()
            after = snapshot_state()
            assert after == before, f"theme changed fields: {[(i, a, b) for i, (a, b) in enumerate(zip(before, after)) if a != b]}"
        # Notify the real watched HC property too; actual HC on/off is exercised
        # in separate process invocations, without changing desktop settings.
        manager.notify("high-contrast")
        drain()
        assert snapshot_state() == before
        assert not errors, errors
        print("PASS theme: buffer/text/selection/page/scroll/model/expansion/tags/links", flush=True)

    def checks():
        app = application
        expected = [Category.HEARING, Category.HEARING, Category.REPORT, Category.MINUTE_ORDER,
                    Category.MINUTE_ORDER, Category.FORM, Category.FORM, Category.UNKNOWN,
                    Category.FORM, Category.UNKNOWN]
        for page, category in enumerate(expected, 1):
            app._show_page_from_link(str(page))
            assert app._category_index[page].category == category
            assert not hasattr(app, "_category_caption")
            if category != Category.UNKNOWN:
                assert app.scroller.has_css_class(f"focus-doc-{category.value}")
        app._show_page_from_link("1")
        app._on_page_forward_one_clicked(None)
        assert app._current_page_number() == 2
        app._page_number_entry.set_text("CT 103")
        app._on_page_number_activate(app._page_number_entry)
        assert app._current_page_number() == 3 and app.scroller.has_css_class("focus-doc-report")
        # Use an actual bound TOC bookmark row's activation path.
        model = app._toc_sidebar_tree_model
        for i in range(model.get_n_items()):
            item = model.get_item(i).get_item()
            if item.kind == "bookmark" and item.page == 6:
                row = app._toc_list_view.get_row_at_index(i)
                app._on_sidebar_row_activated(app._toc_list_view, row)
                assert app._current_page_number() == 6
                # Rebinding must remove the previous rail, including on neutral rows.
                app._bind_sidebar_row(row, model.get_item(0))
                assert row._focus_row.has_css_class("focus-doc-hearing")
                assert not row._focus_row.has_css_class("focus-doc-form")
                app._bind_sidebar_row(row, model.get_item(i))
                break
        app._show_page_from_link("1")
        app._set_show_image(True)
        app._toggle_minute_order_view()
        assert app._current_page_number() == 4 and not app._show_image
        app._set_show_image(True)
        assert app.scroller.has_css_class("focus-doc-minute_order")
        app._show_page_from_link("6")
        app._toggle_minute_order_view()
        assert app._current_page_number() == 1 and not app._show_image
        missing = app.page_to_path[4]
        missing.rename(missing.with_suffix(".hold"))
        app._toggle_minute_order_view()
        assert app._current_page_number() == 1 and app._minute_order_return_page is None
        app._show_page_from_link("4")
        assert not any(app.scroller.has_css_class(f"focus-doc-{c.value}") for c in Category)
        missing.with_suffix(".hold").rename(missing)
        app._show_page_from_link("1")
        app._apply_grep("Search phrase")
        deadline = time.monotonic() + 5
        while app._grep_search_thread and app._grep_search_thread.is_alive() and time.monotonic() < deadline:
            drain()
        drain()
        assert app._grep_hits
        app._navigate_grep_match(1, wrap=True)
        category = app._category_index[app._current_page_number()].category
        assert app.scroller.has_css_class(f"focus-doc-{category.value}")
        theme_checks()
        before = snapshot_state()
        # Only accepted TOC may affect classification; callback never reloads text.
        generation = app._toc_load_generation
        app._on_toc_text_loaded(generation - 1, "Forms\n    wrong 1", None, bundle)
        app._on_toc_text_loaded(generation, "Forms\n    wrong 1", None, root)
        assert snapshot_state() == before
        app._on_toc_text_loaded(generation, toc, None, bundle)
        after = snapshot_state()
        assert after[:5] == before[:5]
        # Case-switch early return invalidates both indexes and pending TOC.
        app._record_layout = core._resolve_record_layout(root / "missing-case")
        app.input_dir = root / "missing-case"
        app._scan_pages()
        app._load_current()
        assert not app._category_index and not app._category_base_index
        assert not any(app.scroller.has_css_class(f"focus-doc-{c.value}") for c in Category)
        app._on_toc_text_loaded(generation, toc, None, bundle)
        assert not app._category_index
        assert not errors, errors
        print("PASS production navigation, shortcut, missing target, rows, grep, TOC guards, case reset", flush=True)

    def capture_screenshots():
        # This branch is only reached in the private Xvfb subprocess. Never use
        # gnome-screenshot: its D-Bus service can capture the user's real desktop.
        destination = root / "screenshots"
        destination.mkdir()
        for scheme, name in ((Adw.ColorScheme.FORCE_LIGHT, "light"),
                             (Adw.ColorScheme.FORCE_DARK, "dark")):
            manager.set_color_scheme(scheme)
            for page, label in ((1, "hearing"), (3, "report"), (4, "minute-order"),
                                (6, "form"), (8, "index"), (10, "unclassified")):
                application._show_page_from_link(str(page))
                drain()
                path = destination / f"{name}-{'hc-' if args.high_contrast else ''}{label}.png"
                subprocess.run(["import", "-display", os.environ["DISPLAY"], "-window", "root",
                                str(path)], check=True)
        application._show_page_from_link("1")
        application._apply_grep("Search phrase")
        deadline = time.monotonic() + 5
        while (application._grep_search_thread and application._grep_search_thread.is_alive()
               and time.monotonic() < deadline):
            drain()
        application.textview.grab_focus()
        buffer = application.textview.get_buffer()
        buffer.select_range(buffer.get_iter_at_offset(12), buffer.get_iter_at_offset(35))
        drain()
        subprocess.run(["import", "-display", os.environ["DISPLAY"], "-window", "root",
                        str(destination / "search-selection.png")], check=True)
        application._apply_grep("")
        application._show_page_from_link("6")
        application.win.set_default_size(780, 760)
        application._toc_list_view.get_row_at_index(2).grab_focus()
        drain()
        subprocess.run(["import", "-display", os.environ["DISPLAY"], "-window", "root",
                        str(destination / "narrow-focus.png")], check=True)
        application.win.set_default_size(1100, 850)
        drain()
        print(f"SCREENSHOTS {destination}", flush=True)

    def ready():
        try:
            application.on_toc_text_updated(toc)  # invalidates the startup worker
            application.win.unmaximize()
            application.win.set_default_size(1100, 850)
            application._category_provider.connect("parsing-error", lambda _p, _s, e: errors.append(str(e)))
            application._refresh_category_theme()
            expand()
            drain()
            if args.screenshots:
                capture_screenshots()
            if args.check:
                checks()
            if args.check or args.screenshots:
                application.quit()
                return False
            controller = Gtk.EventControllerKey()
            def key_pressed(_controller, keyval, _keycode, _state):
                if keyval == Gdk.KEY_F6:
                    manager.set_color_scheme(Adw.ColorScheme.FORCE_LIGHT if manager.get_dark()
                                             else Adw.ColorScheme.FORCE_DARK)
                    return True
                if keyval == Gdk.KEY_F7:
                    theme_checks()
                    return True
                return False
            controller.connect("key-pressed", key_pressed)
            application.win.add_controller(controller)
            print(f"READY pid={os.getpid()} app={module.APPLICATION_ID} root={root}", flush=True)
        except Exception:
            failed.append(traceback.format_exc())
            print(failed[-1], file=sys.stderr, flush=True)
            application.quit()
        return False

    application.connect("activate", lambda *_: GLib.timeout_add(500, ready))
    print(f"ARTIFACTS {root}", flush=True)
    application.run([sys.argv[0]])
    return 1 if failed or errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
