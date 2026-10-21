"""Bounded offline literal-reader acceptance with disposable source/HOME/bundle.

Run with project-env's explicit disposable source/environment overrides. Set
FOCUS_READING_INSPECT_SECONDS (max 300) to hold the synthetic window for desktop
inspection after assertions. No clipboard/Prose/model calls or settings saves.
"""
from __future__ import annotations

import gc
import json
import os
import weakref
from pathlib import Path
import shutil
import sys
import tempfile
import traceback

from transcript_reading_fixtures import FOOTER, detached_page, flattened_page, short_flattened_page

root = Path(tempfile.mkdtemp(prefix="focus-reading-acceptance-"))
source = Path(__file__).resolve().parents[1]
sandbox = root / "Focus"
shutil.copytree(source / "focus", sandbox / "focus", ignore=shutil.ignore_patterns("__pycache__"))
for name in ("HOME", "XDG_CONFIG_HOME", "XDG_CACHE_HOME", "XDG_DATA_HOME", "XDG_STATE_HOME"):
    path = root / name
    path.mkdir(mode=0o700)
    os.environ[name] = str(path)
os.environ["GSETTINGS_BACKEND"] = "memory"
sys.path.insert(0, str(sandbox))

from focus import app as module, core  # noqa: E402
from gi.repository import GLib, Gtk  # noqa: E402
import cairo  # noqa: E402

core.CONFIG_FILE = sandbox / "config.json"
module.APPLICATION_ID = f"com.mcglaw.Focus.ReadingAcceptance.p{os.getpid()}"
bundle = root / "synthetic"
for name in ("text_pages", "image_pages", "artifacts", "summaries"):
    (bundle / name).mkdir(parents=True)
source_text = (
    "SUPERIOR COURT\nCASE NO. JV-140\nDIRECT EXAMINATION\n"
    " 1 | BY MS. SAMPLE:\n 2 | Q. DID YOU SEE\n 3 | THE DOCUMENT?\n"
    " 4 | A. I DID NOT.\n 5 | THE COURT: **NO ORDER** IS MADE.\n"
    " 6 | (THE WITNESS\n 7 | WAS EXCUSED.)\n"
    + "\n".join(f"{i:2} | THE COURT: THIS IS NOT AN ORDER. THE DOCUMENT REMAINS SEALED."
                 for i in range(8, 29))
)
texts = [source_text, "A mixed-case clerk's document.\n\n1. Keep this list.",
         "NAME | DATE | AMOUNT\nTOTAL | TODAY | $20", "THE COURT: I DO NOT AGREE.",
         detached_page(), flattened_page(), short_flattened_page(),
         "THE COURT: There are 21 items and 24 photos. MS. SAMPLE: Correct. THE COURT: They remain."]
for page, text in enumerate(texts, 1):
    (bundle / "text_pages" / f"{page:04}.txt").write_text(text)
(bundle / "artifacts/transcript_page_numbers.json").write_text(json.dumps({"entries": [
    {"file_page": p, "page_type": t, "record_type": "CT" if p == 2 else "RT",
     "transcript_page_number": p, "citation_prefix": "CT" if p == 2 else "RT"}
    for p, t in enumerate(("RT_body_first_page", "CT_report", "RT_body", "RT_body", "RT_body", "RT_body", "RT_body", "RT_body"), 1)
]}))
surface = cairo.ImageSurface(cairo.FORMAT_RGB24, 400, 600)
context = cairo.Context(surface)
context.set_source_rgb(1, 1, 1)
context.paint()
surface.write_to_png(str(bundle / "image_pages/0001.png"))
summary = bundle / "summaries/hearing_summaries.md"
summary.write_text("# Synthetic summary\n\n**Keep Markdown** in summaries.")
app = module.Focus(input_override=bundle)
failed = False
scrolls = []
real_scroll = app._scroll_textview_to_offset
app._scroll_textview_to_offset = lambda offset: (scrolls.append(offset), real_scroll(offset))[-1]


def text():
    buf = app.textview.get_buffer()
    return buf.get_text(buf.get_start_iter(), buf.get_end_iter(), False)


def choose_view(view):
    app.lookup_action("transcript-view").activate(GLib.Variant("s", view))
    app._reading_controls.popdown()
    assert app._reading_view_action.get_state().get_string() == view
    assert app._reading_controls.get_label() == view.title()
    assert app._reading_mode == (view == "readable")


def assert_selector_style():
    def labels(widget):
        if isinstance(widget, Gtk.Label):
            yield widget
        child = widget.get_first_child()
        while child:
            yield from labels(child)
            child = child.get_next_sibling()

    # Inspect only the collapsed button, not the popover's separate menu labels.
    label, = labels(app._reading_controls.get_first_child())
    assert label.get_text() == app._reading_controls.get_label()
    assert label.get_pango_context().get_font_description().get_weight() == module.Pango.Weight.NORMAL
    assert app._reading_controls.get_opacity() == 1.0  # Focus/hover stays undimmed.


def assert_speaker_tags():
    buffer = app.textview.get_buffer()
    tag = buffer.get_tag_table().lookup("transcript-speaker")
    assert tag.get_property("weight") == module.Pango.Weight.BOLD
    assert buffer.get_tag_table().lookup("transcript-spacing").get_property("pixels-inside-wrap") == 2
    for start, end in app._reading_presentation.styles:
        assert tag in buffer.get_iter_at_offset(start).get_tags()
        assert tag in buffer.get_iter_at_offset(end - 1).get_tags()
        assert tag not in buffer.get_iter_at_offset(end).get_tags()


def steps():
    app.win.set_title("Synthetic Focus Transcript Reading")
    app.win.unmaximize()
    app.win.set_default_size(1400, 900)
    yield
    assert app._reading_pages == frozenset({1, 3, 4, 5, 6, 7, 8})
    assert app._reading_controls.get_visible()
    assert isinstance(app._reading_controls, Gtk.MenuButton)
    assert app._reading_controls.has_css_class("flat")
    assert app._reading_controls.has_css_class("focus-reading-view")
    assert_selector_style()
    menu = app._reading_controls.get_menu_model()
    assert menu.get_n_items() == 2
    for i, view in enumerate(("readable", "original")):
        assert menu.get_item_attribute_value(i, "label", None).get_string() == view.title()
        assert menu.get_item_attribute_value(i, "action", None).get_string() == "app.transcript-view"
        assert menu.get_item_attribute_value(i, "target", None).get_string() == view
    initial = app._reading_presentation
    choose_view("readable")  # The current choice must not reload or move text.
    app._reading_view_action.change_state(GLib.Variant("s", "unsupported"))
    assert app._reading_presentation is initial
    assert app._reading_controls.get_label() == "Readable"
    del initial
    assert "Q. DID YOU SEE THE DOCUMENT?" in text()
    assert "**NO ORDER**" in text()  # Literal punctuation, never Markdown.
    assert "(THE WITNESS WAS EXCUSED.)" in text()
    assert_speaker_tags()
    buf = app.textview.get_buffer()
    a = text().index("DID YOU")
    b = text().index("?", a) + 1
    buf.select_range(buf.get_iter_at_offset(a), buf.get_iter_at_offset(b))
    visible = app._get_main_text_selection()
    assert visible == "DID YOU SEE THE DOCUMENT?"
    # Let Wayland's initial PRIMARY ownership round trip settle, just as the
    # separate selection and toolbar-click input events do in normal use.
    yield
    app._reading_controls.popup()
    yield
    assert app._reading_controls.get_popover().get_visible()
    choose_view("original")
    yield
    assert not app._reading_controls.get_popover().get_visible()
    assert text() == source_text
    assert_selector_style()
    assert "DID YOU" in app._get_main_text_selection()
    app._reading_controls.popup()
    yield
    choose_view("readable")
    yield
    assert app._get_main_text_selection() == visible
    cited = core.append_page_citation_to_selected_text(
        visible, app._get_main_text_selection(), 1, app._transcript_page_index)
    assert cited == visible + " (RT 1.)"
    app._on_grep_search_highlighted_clicked(app._grep_highlighted_button)
    for _ in range(10):
        if app._grep_active:
            break
        yield
    assert app._grep_active and len(app._grep_match_order) == 1
    identity = (app.current_index, list(app._grep_match_order), app._grep_current_match_index)
    hit = app._grep_hits[1][0]
    display = app._reading_presentation.mapping.display_span(*hit)
    app._scroll_to_current_grep_match()
    yield
    assert scrolls[-1] == display[0]
    buf = app.textview.get_buffer()
    tag = buf.get_tag_table().lookup("match-highlight")
    assert tag in buf.get_iter_at_offset(display[0]).get_tags()
    choose_view("original")
    yield
    assert identity == (app.current_index, app._grep_match_order, app._grep_current_match_index)
    app._scroll_to_current_grep_match()
    yield
    assert scrolls[-1] == hit[0]
    assert app._set_show_image(True)
    app._on_back_to_text_clicked(app._back_to_text_button)
    assert not app._reading_mode and text() == source_text
    choose_view("readable")
    app._font_size_pt = 17  # display only; no Settings Save
    app._apply_text_color(app._current_text_color)
    app.win.set_default_size(900, 700)
    yield
    assert "Q. DID YOU SEE THE DOCUMENT?" in text()
    assert_selector_style()  # Reloading display CSS must retain the quiet style.
    reading = app._reading_presentation
    app._load_summary_from_path(summary)
    yield
    assert app._reading_presentation is reading and "**NO ORDER**" in text()
    from focus.saved_answers import AgentAnswerSnapshot, new_answer_id
    snapshot = AgentAnswerSnapshot(
        answer_id=new_answer_id(), markdown="# Saved answer\n\n**Keep Markdown** here.",
        title="Saved answer", subtitle="", status="complete", capture="submit_tool",
        answer_kind="answered", stop_reason="toolUse", question="Synthetic?",
    )
    app._display_agent_snapshot(snapshot, is_saved=True)
    yield
    assert app._reading_presentation is reading and "**NO ORDER**" in text()
    app.current_index = 1
    app._load_current()
    assert not app._reading_controls.get_visible() and app._reading_presentation is None
    app.current_index = 2
    app._load_current()
    assert app._reading_status.get_visible()
    assert app._reading_controls.get_label() == "Readable"
    assert text() == texts[2]
    choose_view("original")
    assert not app._reading_status.get_visible() and text() == texts[2]
    app.current_index = 1
    app._load_current()
    assert not app._reading_controls.get_visible()
    app.current_index = 2
    app._load_current()
    assert app._reading_controls.get_visible() and app._reading_controls.get_label() == "Original"
    assert not app._reading_mode and text() == texts[2]
    choose_view("readable")
    assert app._reading_status.get_visible() and text() == texts[2]
    for page in (5, 6):
        app.current_index = app.pages.index(page)
        app._load_current()
        assert "SOURCE AND NO BASIS" in text() and "12 MONTHS" in text()
        assert_speaker_tags()
        assert text().endswith("\n\n" + FOOTER)
        assert len(app._reading_presentation.removed) == (28 if page == 5 else 23)
        assert not app._reading_status.get_visible()
    assert len(text().split("\n\n")) == 7
    app._apply_grep("source and no basis")
    for _ in range(10):
        if app._grep_active:
            break
        yield
    assert set(app._grep_hits) == {5, 6}
    assert app.pages[app.current_index] == 5
    app._navigate_grep_match(1)
    yield
    assert app.pages[app.current_index] == 6
    a, b = app._reading_presentation.mapping.display_span(*app._grep_hits[6][0])
    assert text()[a:b] == "SOURCE AND NO BASIS"
    assert scrolls[-1] == a
    choose_view("original")
    yield
    assert text() == texts[5] and app.pages[app.current_index] == 6
    choose_view("readable")
    yield
    assert "SOURCE AND NO BASIS" in text() and "A PERIOD OF 12 MONTHS" in text()
    app._clear_grep_state()
    app.current_index = app.pages.index(7)
    app._load_current()
    assert len(app._reading_presentation.styles) == 4
    assert len(text().split("\n\n")) == 7
    assert "\n\n(A BRIEF PAUSE OCCURRED WITHOUT FURTHER TESTIMONY.)\n\nTHE COURT:" in text()
    assert_speaker_tags()
    a = text().index("SECTION 742 REMAINS")
    visible = "SECTION 742 REMAINS IN THE RECORD."
    buffer = app.textview.get_buffer()
    buffer.select_range(buffer.get_iter_at_offset(a), buffer.get_iter_at_offset(a + len(visible)))
    yield
    choose_view("original")
    yield
    assert text() == texts[6]
    assert "28" in app._get_main_text_selection()
    choose_view("readable")
    yield
    assert app._get_main_text_selection() == visible
    app._on_grep_search_highlighted_clicked(app._grep_highlighted_button)
    for _ in range(10):
        if app._grep_active:
            break
        yield
    assert set(app._grep_hits) == {7}
    a, b = app._reading_presentation.mapping.display_span(*app._grep_hits[7][0])
    assert text()[a:b] == visible
    assert scrolls[-1] == a
    assert_speaker_tags()
    app._clear_grep_state()
    app.current_index = app.pages.index(8)
    app._load_current()
    assert not app._reading_presentation.removed
    assert len(app._reading_presentation.styles) == 3
    assert "21 items and 24 photos.\n\nMS. SAMPLE: Correct.\n\nTHE COURT: They remain." in text()
    assert_speaker_tags()
    app.current_index = 3
    app._load_current()
    assert text() == "THE COURT: I DO NOT AGREE."
    assert not app._reading_status.get_visible()
    # A source snapshot change cannot retain the preceding mapping.
    (bundle / "text_pages/0004.txt").write_text("THE COURT: NO.")
    app._load_current()
    assert text() == "THE COURT: NO."
    (bundle / "text_pages/0004.txt").unlink()
    app._load_current()
    assert app._reading_presentation is None and not app._reading_controls.get_visible()
    app._scan_pages()
    assert app._reading_presentation is None
    app.current_index = 0
    app._load_current()
    app.win.set_default_size(1400, 900)
    yield
    references = []
    for visit in range(240):
        app.current_index = visit % 2
        app._load_current()
        if app._reading_presentation:
            references.append(weakref.ref(app._reading_presentation))
    del reading
    gc.collect()
    assert sum(ref() is not None for ref in references) <= 1
    empty = root / "empty-case"
    (empty / "text_pages").mkdir(parents=True)
    app._apply_input_dir(empty, persist=False)
    assert app._reading_presentation is None and not app._reading_controls.get_visible()
    (empty / "text_pages/0001.txt").write_text("UNKNOWN CASE TEXT.")
    app._apply_input_dir(empty, persist=False)
    assert not app._reading_pages and app._reading_presentation is None
    assert text() == "UNKNOWN CASE TEXT."
    app._apply_input_dir(bundle, persist=False)
    yield
    assert app._reading_presentation is not None and "Q. DID YOU SEE THE DOCUMENT?" in text()
    assert not core.CONFIG_FILE.exists()
    print("PASS transcript reading; disposable state:", root, flush=True)
    hold = min(300, max(0, int(os.environ.get("FOCUS_READING_INSPECT_SECONDS", "0"))))
    if hold:
        app.current_index = app.pages.index(7)
        app._load_current()
        app.win.set_title("Synthetic Focus Structural Reading")
        GLib.timeout_add_seconds(hold, lambda: app.quit() or False)
        while True:
            yield


sequence = steps()


def advance():
    global failed
    try:
        next(sequence)
        return True
    except StopIteration:
        app.quit()
    except Exception:
        failed = True
        traceback.print_exc()
        app.quit()
    return False


app.connect("activate", lambda *_: GLib.timeout_add(350, advance))
GLib.timeout_add_seconds(340, lambda: app.quit() or False)
app.run([])
sys.exit(1 if failed else 0)
