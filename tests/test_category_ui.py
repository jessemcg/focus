from pathlib import Path
from types import SimpleNamespace

import pytest

from focus.app import Focus
from focus.core import RecordBoundary, FocusSidebarItem, TocCategory, TocBookmark, category_css
from focus.record_categories import Category as C, Classification


class Widget:
    def __init__(self):
        self.classes = set()
        self.text = ""

    def add_css_class(self, name):
        self.classes.add(name)

    def remove_css_class(self, name):
        self.classes.discard(name)

    def set_text(self, text):
        self.text = text


class AppearanceHarness:
    _refresh_category_appearance = Focus._refresh_category_appearance
    _set_category_class = staticmethod(Focus._set_category_class)
    _current_page_number = Focus._current_page_number
    _on_toc_text_loaded = Focus._on_toc_text_loaded
    _update_toc_from_text = Focus._update_toc_from_text

    def __init__(self, tmp_path):
        self.pages = [1, 2, 3, 4, 5]
        self.current_index = 0
        self.page_to_path = {}
        for page in self.pages:
            path = tmp_path / f"{page:04d}.txt"
            path.write_text("synthetic")
            self.page_to_path[page] = path
        self._category_index = {p: Classification(c, "transcript", "classified")
                                for p, c in zip(self.pages, C)}
        self._category_base_index = {5: Classification()}
        self.scroller = Widget()
        self._toc_load_generation = 3
        self.input_dir = tmp_path
        self.rebuilds = 0

    def _rebuild_toc_sidebar(self):
        self.rebuilds += 1

    def _transient_toast(self, message):
        raise AssertionError(message)


def test_class_transitions_empty_missing_and_rebind(tmp_path):
    app = AppearanceHarness(tmp_path)
    for index, category in enumerate(C):
        app.current_index = index
        app._refresh_category_appearance()
        assert app.scroller.classes == ({f"focus-doc-{category}"} if category != C.UNKNOWN else set())
    app.current_index = 0
    app._refresh_category_appearance()
    app.page_to_path[1].unlink()
    app._refresh_category_appearance()
    assert app.scroller.classes == set()
    app.pages.clear()
    app._refresh_category_appearance()
    assert app.scroller.classes == set()


def test_async_toc_guards_and_appearance_only(tmp_path):
    app = AppearanceHarness(tmp_path)
    app.current_index = 4
    text = "Forms\n    Synthetic form 5\n"
    original_index = app._category_index.copy()
    app._on_toc_text_loaded(2, text, None, tmp_path)
    app._on_toc_text_loaded(3, text, None, tmp_path / "other")
    assert app.rebuilds == 0
    assert app._category_index == original_index
    app._on_toc_text_loaded(3, text, None, tmp_path)
    assert app.rebuilds == 1
    assert app._category_index[5] == Classification(C.FORM, "toc", "classified")
    assert app.scroller.classes == {"focus-doc-form"}
    # The accepted callback has no text-loading or buffer method available.
    assert app.current_index == 4


def test_sidebar_kind_independent_of_document_category():
    section = TocCategory(" REPORTS ", None, [TocBookmark("really a form", 12)])
    item = FocusSidebarItem.from_category(section, {12: Classification(C.FORM)})
    assert item.kind == "category" and item.document_category == C.REPORT
    child = item.get_children_model().get_item(0)
    assert child.kind == "bookmark" and child.document_category == C.FORM


class SidebarRebuildHarness:
    _rebuild_toc_sidebar = Focus._rebuild_toc_sidebar

    def __init__(self, categories):
        from focus.core import Gio

        self._toc_sidebar_root_store = Gio.ListStore(item_type=FocusSidebarItem)
        self._toc_categories = categories
        self._category_index = {}
        self._current_view_state = lambda: SimpleNamespace()
        self.placeholder_calls = []

    def _update_sidebar_placeholder(self, has_items):
        self.placeholder_calls.append(has_items)

    def _apply_sidebar_expansion_state(self, _state):
        pass

    def _sync_sidebar_active_page(self):
        pass

    def titles(self):
        store = self._toc_sidebar_root_store
        return [store.get_item(index).title for index in range(store.get_n_items())]


def test_sidebar_categories_follow_case_tools_order():
    categories = [
        TocCategory("FORMS", None, []),
        TocCategory("REPORTS", None, []),
        TocCategory("MINUTE ORDERS", None, []),
        TocCategory("HEARINGS", None, []),
    ]
    harness = SidebarRebuildHarness(categories)

    harness._rebuild_toc_sidebar()

    assert harness.titles() == [
        "FORMS",
        "HEARINGS",
        "REPORTS",
        "MINUTE ORDERS",
    ]
    assert harness.placeholder_calls == [True]


def test_sidebar_unknown_categories_follow_known_ones():
    categories = [
        TocCategory("REPORTS", None, []),
        TocCategory("MISCELLANY", None, []),
        TocCategory("HEARINGS", None, []),
    ]
    harness = SidebarRebuildHarness(categories)

    harness._rebuild_toc_sidebar()

    assert harness.titles() == ["HEARINGS", "REPORTS", "MISCELLANY"]


class MinuteHarness:
    _toggle_minute_order_view = Focus._toggle_minute_order_view

    def __init__(self, tmp_path, image):
        path = tmp_path / "0003.txt"
        path.write_text("Minute order")
        self.pages = [1, 3, 5]
        self.page_to_path = {3: path}
        self.page = 1
        self._show_image = image
        self._minute_order_return_page = None
        self._minute_order_return_boundary = None
        self.events = []
        self.target = RecordBoundary("2026-01-01", 3, 4)

    def _viewing_return_minute_order(self):
        return self._minute_order_return_page is not None

    def _current_page_number(self):
        return self.page

    def _current_minute_order_boundary(self):
        return self.target

    def _set_show_image(self, enabled, **kwargs):
        self._show_image = enabled
        self.events.append(("image", enabled))

    def _show_page_from_link(self, page):
        assert not self._show_image  # prevents transient image load
        self.page = int(page)
        self.events.append(("page", self.page))

    def _transient_toast(self, text):
        self.events.append(("toast", text))


@pytest.mark.parametrize("image", [False, True])
def test_minute_text_and_return_after_browsing(tmp_path, image):
    app = MinuteHarness(tmp_path, image)
    app._toggle_minute_order_view()
    assert app.events == [("image", False), ("page", 3)]
    assert app._minute_order_return_page == 1
    app.page = 5
    app._show_image = True  # manually opening an image must not lose pending return
    app._toggle_minute_order_view()
    assert app.page == 1
    assert not app._show_image
    assert app._minute_order_return_page is None


@pytest.mark.parametrize("missing", ["map", "disk", "pages"])
def test_missing_minute_does_not_change_state(tmp_path, missing):
    app = MinuteHarness(tmp_path, True)
    if missing == "map":
        app.page_to_path.clear()
    elif missing == "disk":
        app.page_to_path[3].unlink()
    else:
        app.pages.remove(3)
    app._toggle_minute_order_view()
    assert app.page == 1 and app._show_image
    assert app._minute_order_return_page is None
    assert app.events == [("toast", "Minute-order text is unavailable.")]


@pytest.mark.parametrize("dark", [False, True])
def test_category_tint_leaves_text_nodes_transparent(dark):
    # Opaque inner text nodes paint square corners over the rounded scroller.
    css = category_css(dark=dark, high_contrast=False)
    assert "#page-text" not in css
    assert "background-color: mix(white," in css


@pytest.mark.parametrize("dark", [False, True])
def test_high_contrast_suppresses_palette_but_preserves_indicators(dark):
    css = category_css(dark=dark, high_contrast=True)
    assert "mix(" not in css
    assert "alpha(" not in css
    assert "outline: 2px" in css and "font-weight: 700" in css
    assert "outline: 1px" not in css
    assert "border-left-color: @window_fg_color" in css
