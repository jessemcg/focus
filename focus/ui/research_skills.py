"""Searchable keyboard-accessible launcher for local Research Skills."""
from __future__ import annotations

import threading

from gi.repository import Gdk, GLib, Gtk, Pango

from focus.research_skills import ResearchSkill, SkillListing, discover_skills


class ResearchSkillsPicker(Gtk.MenuButton):
    def __init__(self, activate):
        super().__init__(label="Skills", has_frame=False, always_show_arrow=True)
        self.add_css_class("flat")
        self.add_css_class("no-bold")
        self.set_tooltip_text("Run a Research Skill as a new question")
        self._activate = activate
        self._folder = ""
        self._generation = 0
        self._listing = SkillListing()
        self._popover = Gtk.Popover()
        self._popover.connect("map", self._on_map)
        self._popover.connect("unmap", self._on_unmap)
        self.set_popover(self._popover)
        content = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        content.set_size_request(280, -1)
        for edge in ("top", "bottom", "start", "end"):
            getattr(content, f"set_margin_{edge}")(6)
        self._popover.set_child(content)
        self._search = Gtk.SearchEntry(placeholder_text="Search skills…")
        self._search.connect("changed", self._filter)
        key = Gtk.EventControllerKey()
        key.connect("key-pressed", self._on_search_key)
        self._search.add_controller(key)
        content.append(self._search)

        scroller = Gtk.ScrolledWindow(hscrollbar_policy=Gtk.PolicyType.NEVER,
                                      propagate_natural_height=True, max_content_height=320)
        content.append(scroller)
        results = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        scroller.set_child(results)
        self._list = Gtk.ListBox(selection_mode=Gtk.SelectionMode.NONE)
        self._list.add_css_class("boxed-list")
        self._list.connect("row-activated", self._on_activate)
        results.append(self._list)
        self._notice = Gtk.Label(xalign=0, wrap=True, wrap_mode=Pango.WrapMode.WORD_CHAR,
                                 max_width_chars=38)
        self._notice.add_css_class("dim-label")
        results.append(self._notice)

    def set_folder(self, folder: str) -> None:
        if folder != self._folder:
            self.reset()
        self._folder = folder
        self.set_visible(bool(folder))

    def reset(self) -> None:
        self._generation += 1
        self._popover.popdown()
        self._listing = SkillListing()
        self._filter()

    def refresh(self) -> None:
        if self.get_visible() and self.get_root() is not None:
            if self._popover.get_mapped():
                self._scan()
            else:
                self.popup()

    def _on_map(self, _popover: Gtk.Popover) -> None:
        self._search.set_text("")
        self._search.grab_focus()
        self._scan()

    def _on_unmap(self, _popover: Gtk.Popover) -> None:
        self._generation += 1

    def _scan(self) -> None:
        self._generation += 1
        generation, folder = self._generation, self._folder
        self._listing = SkillListing(notices=("Reading Research Skills…",))
        self._filter()

        def scan() -> None:
            GLib.idle_add(self._on_scan_complete, generation, discover_skills(folder))

        threading.Thread(target=scan, daemon=True, name="focus-research-skills").start()

    def _on_scan_complete(self, generation: int, listing: SkillListing) -> bool:
        if generation == self._generation and self._popover.get_mapped():
            self._listing = listing
            self._filter()
        return GLib.SOURCE_REMOVE

    def _filter(self, *_args: object) -> None:
        while (row := self._list.get_first_child()) is not None:
            self._list.remove(row)
        query = self._search.get_text().casefold().split()
        count = 0
        for skill in self._listing.skills:
            if not all(word in f"{skill.title} {skill.key}".casefold() for word in query):
                continue
            count += 1
            row = Gtk.ListBoxRow(activatable=True, focusable=True)
            row.skill = skill
            labels = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
            for edge in ("top", "bottom", "start", "end"):
                getattr(labels, f"set_margin_{edge}")(6)
            for text, style in ((skill.title, "heading"), (skill.key, "dim-label")):
                label = Gtk.Label(label=text, xalign=0, wrap=True,
                                  wrap_mode=Pango.WrapMode.WORD_CHAR, max_width_chars=38)
                label.add_css_class(style)
                labels.append(label)
            row.set_child(labels)
            row.set_tooltip_text(f"Run {skill.title} ({skill.key})")
            self._list.append(row)
        self._list.set_visible(bool(count))
        notices = self._listing.notices
        if not count and not notices:
            notices = ("No matching skills." if query else "No Markdown skills found.",)
        self._notice.set_label("\n".join(notices))
        self._notice.set_visible(bool(notices))

    def _on_search_key(self, _controller, keyval: int, _keycode: int, _state) -> bool:
        if keyval in (Gdk.KEY_Down, Gdk.KEY_KP_Down):
            row = self._list.get_row_at_index(0)
            return bool(row is not None and row.grab_focus())
        return False

    def _on_activate(self, _list: Gtk.ListBox, row: Gtk.ListBoxRow) -> None:
        skill: ResearchSkill = row.skill
        self._popover.popdown()
        self._activate(self._folder, skill)
