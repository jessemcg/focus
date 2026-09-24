"""Saved-answer popover menu for Focus Agent Q&A.

The widget owns only presentation and filtering.  All filesystem work and
answer persistence stay in :mod:`focus.saved_answers` so GTK callbacks never do
blocking I/O.
"""

from __future__ import annotations

from collections.abc import Callable

from gi.repository import Adw, GLib, Gtk, Pango

from ..answer_presentation import answer_quality_label, format_saved_at
from ..saved_answers import SavedAnswer, SavedAnswerListing

PREFERRED_CONTENT_WIDTH = 480
LIST_MAX_HEIGHT = 320
_POPULATE_BATCH = 40


def _row_labels(answer: SavedAnswer) -> tuple[str, str]:
    title = answer.title.strip() or "Saved record answer"
    subtitle = answer.subtitle.strip() or "Saved answer"
    quality = answer_quality_label(
        status=answer.status,
        stop_reason=answer.stop_reason,
        capture=answer.capture,
    )
    if quality:
        subtitle = f"{subtitle} · {quality}"
    saved = format_saved_at(answer.saved_at)
    if saved:
        subtitle = f"{subtitle} · Saved {saved}"
    return title, subtitle


class SavedAnswersPopover:
    """Owns the ``Saved Answers`` menu button and its popover content."""

    def __init__(
        self,
        *,
        on_select: Callable[[str], None],
        on_delete: Callable[[str], None],
        on_opened: Callable[[], None] | None = None,
    ) -> None:
        self._on_select = on_select
        self._on_delete = on_delete
        self._on_opened = on_opened
        self._answers: list[SavedAnswer] = []
        self._filtered: list[SavedAnswer] = []
        self._pending: list[SavedAnswer] = []
        self._batch_source_id: int | None = None
        self._load_error = False
        self._case_label = ""

        self.button = Gtk.MenuButton()
        self.button.add_css_class("flat")
        self.button.add_css_class("no-bold")
        self.button.add_css_class("focus-pill-segment")
        self.button.set_valign(Gtk.Align.CENTER)
        self.button.set_tooltip_text("Saved Answers — browse and reopen saved Agent answers")
        # Icon-only keeps the pinned tool strip compact; the star plus tooltip
        # and accessible label identify the per-case saved-answer menu.
        icon = Gtk.Image.new_from_icon_name("starred-symbolic")
        icon.set_pixel_size(16)
        icon.set_valign(Gtk.Align.CENTER)
        self.button.set_child(icon)
        self._set_accessible_label(self.button, "Saved Answers")

        self.popover = Gtk.Popover()
        self.popover.set_autohide(True)
        self.popover.connect("show", self._on_show)
        self.button.set_popover(self.popover)

        root = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        root.set_margin_top(10)
        root.set_margin_bottom(10)
        root.set_margin_start(10)
        root.set_margin_end(10)
        root.set_size_request(PREFERRED_CONTENT_WIDTH, -1)

        self._heading = Gtk.Label(label="Saved answers", xalign=0)
        self._heading.add_css_class("heading")
        self._heading.set_wrap(True)
        self._heading.set_wrap_mode(Pango.WrapMode.WORD_CHAR)
        root.append(self._heading)

        self._search = Gtk.SearchEntry()
        self._search.set_placeholder_text("Search saved answers")
        self._search.connect("search-changed", self._on_search_changed)
        self._search.connect("stop-search", self._on_search_changed)
        root.append(self._search)

        self._scroller = Gtk.ScrolledWindow()
        self._scroller.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        self._scroller.set_propagate_natural_height(True)
        self._scroller.set_propagate_natural_width(False)
        self._scroller.set_max_content_height(LIST_MAX_HEIGHT)
        self._scroller.set_visible(False)

        self._listbox = Gtk.ListBox()
        self._listbox.set_selection_mode(Gtk.SelectionMode.SINGLE)
        self._listbox.set_activate_on_single_click(True)
        self._listbox.add_css_class("focus-saved-answers-list")
        self._listbox.connect("row-activated", self._on_row_activated)
        self._scroller.set_child(self._listbox)
        root.append(self._scroller)

        self._status = Gtk.Label(label="", xalign=0)
        self._status.add_css_class("dim-label")
        self._status.set_wrap(True)
        self._status.set_wrap_mode(Pango.WrapMode.WORD_CHAR)
        root.append(self._status)

        self._warning = Gtk.Label(label="", xalign=0)
        self._warning.add_css_class("dim-label")
        self._warning.set_wrap(True)
        self._warning.set_wrap_mode(Pango.WrapMode.WORD_CHAR)
        self._warning.set_visible(False)
        root.append(self._warning)

        self.popover.set_child(root)
        self._refresh_filter()

    # -- content ---------------------------------------------------------

    def set_case_label(self, case_name: str) -> None:
        self._case_label = (case_name or "").strip()
        self._update_heading()

    def show_load_error(self) -> None:
        self._load_error = True
        self._answers = []
        self._filtered = []
        self._clear_listbox()
        self._scroller.set_visible(False)
        self._status.set_text("Saved answers could not be loaded for this case.")
        self._status.set_visible(True)
        self._update_heading()
        self._update_warning(())

    def show_listing(self, listing: SavedAnswerListing) -> None:
        self._load_error = False
        self._answers = list(listing.answers)
        self._search.set_text("")
        self._update_warning(listing.issues)
        self._refresh_filter()

    def _update_heading(self) -> None:
        count = len(self._answers)
        case = self._case_label or "this case"
        if count == 1:
            noun = "saved answer"
        else:
            noun = "saved answers"
        self._heading.set_text(f"{case} · {count} {noun}")

    def _update_warning(self, issues: tuple) -> None:
        if not issues:
            self._warning.set_visible(False)
            return
        broad = [issue for issue in issues if issue.code == "broad_permissions"]
        other = [issue for issue in issues if issue.code != "broad_permissions"]
        parts: list[str] = []
        if other:
            parts.append(f"{len(other)} saved-answer file(s) could not be read.")
        if broad:
            parts.append(f"{len(broad)} file(s) have broad permissions; they opened unchanged.")
        self._warning.set_text(" ".join(parts))
        self._warning.set_visible(bool(parts))

    # -- filtering and population ---------------------------------------

    def _on_show(self, *_args: object) -> None:
        self._search.grab_focus()
        if self._on_opened is not None:
            self._on_opened()

    def _on_search_changed(self, *_args: object) -> None:
        self._refresh_filter()

    def _refresh_filter(self) -> None:
        query = self._search.get_text().strip().casefold()
        if query:
            filtered = [
                answer
                for answer in self._answers
                if query in answer.title.casefold() or query in answer.subtitle.casefold()
            ]
        else:
            filtered = list(self._answers)
        self._filtered = filtered
        self._clear_listbox()
        self._pending = list(filtered)
        if not filtered:
            self._scroller.set_visible(False)
            self._update_empty_state(query)
        else:
            self._status.set_visible(False)
            self._scroller.set_visible(True)
            self._schedule_populate()

    def _update_empty_state(self, query: str) -> None:
        if self._load_error:
            message = "Saved answers could not be loaded for this case."
        elif query:
            message = "No saved answers match your search."
        elif not self._answers:
            message = "No saved answers for this case. Use Save Answer on an Agent result."
        else:
            message = "No saved answers match your search."
        self._status.set_text(message)
        self._status.set_visible(True)

    def _schedule_populate(self) -> None:
        if self._batch_source_id is None:
            self._batch_source_id = GLib.idle_add(self._populate_batch)

    def _populate_batch(self) -> bool:
        batch = self._pending[:_POPULATE_BATCH]
        del self._pending[:_POPULATE_BATCH]
        for answer in batch:
            self._listbox.append(self._build_row(answer))
        if self._pending:
            return True
        self._batch_source_id = None
        return False

    def _clear_listbox(self) -> None:
        while (child := self._listbox.get_first_child()) is not None:
            self._listbox.remove(child)

    def _build_row(self, answer: SavedAnswer) -> Adw.ActionRow:
        title, subtitle = _row_labels(answer)
        row = Adw.ActionRow()
        row.set_title(title)
        row.set_title_lines(2)
        row.set_subtitle(subtitle)
        row.set_subtitle_lines(2)
        row.set_activatable(True)
        row.set_focusable(True)
        row.set_use_markup(False)
        row.set_tooltip_text(f"{title}\n{subtitle}")
        self._set_accessible_label(row, f"{title}. {subtitle}")

        delete_button = Gtk.Button()
        delete_button.add_css_class("flat")
        delete_button.set_valign(Gtk.Align.CENTER)
        delete_button.set_tooltip_text(f"Delete saved answer: {title}")
        self._set_accessible_label(delete_button, f"Delete saved answer: {title}")
        delete_button.set_child(Gtk.Image.new_from_icon_name("user-trash-symbolic"))
        delete_button.connect("clicked", self._on_delete_clicked, answer.answer_id)
        row.add_suffix(delete_button)

        row.answer_id = answer.answer_id  # type: ignore[attr-defined]
        return row

    @staticmethod
    def _set_accessible_label(widget: Gtk.Widget, label: str) -> None:
        try:
            widget.update_property([Gtk.AccessibleProperty.LABEL], [label])
        except (AttributeError, TypeError):
            pass

    def _on_row_activated(self, _listbox: Gtk.ListBox, row: Adw.ActionRow) -> None:
        answer_id = getattr(row, "answer_id", "")
        if answer_id:
            self._on_select(answer_id)

    def _on_delete_clicked(self, _button: Gtk.Button, answer_id: str) -> None:
        self._on_delete(answer_id)

    def close(self) -> None:
        self.popover.popdown()
