from __future__ import annotations

import threading

from .settings_navigation import SettingsNavigation, SettingsSession

from focus.core import *  # noqa: F401,F403
from focus.research_skills import SkillPreferences, read_preferences, save_preferences
from focus.pi_runtime import (
    PiModel,
    PiRuntimeError,
    PiSettingsError,
    available_pi_models,
    clamp_pi_thinking_level,
    current_project_pi_model,
    current_project_pi_thinking_level,
    save_project_pi_runtime,
)


PI_MODEL_DROPDOWN_WIDTH_CHARS = 64
PI_MODEL_DROPDOWN_MAX_WIDTH_CHARS = 80


def _format_pi_thinking_level(level: str) -> str:
    return "XHigh" if level == "xhigh" else level.title()


def _setup_pi_model_list_item(
    _factory: Gtk.SignalListItemFactory,
    list_item: Gtk.ListItem,
) -> None:
    label = Gtk.Label(xalign=0)
    label.set_width_chars(PI_MODEL_DROPDOWN_WIDTH_CHARS)
    label.set_max_width_chars(PI_MODEL_DROPDOWN_MAX_WIDTH_CHARS)
    label.set_wrap(True)
    label.set_wrap_mode(Pango.WrapMode.WORD_CHAR)
    label.set_margin_top(6)
    label.set_margin_bottom(6)
    label.set_margin_start(12)
    label.set_margin_end(12)
    list_item.set_child(label)


def _bind_pi_model_list_item(
    _factory: Gtk.SignalListItemFactory,
    list_item: Gtk.ListItem,
) -> None:
    item = list_item.get_item()
    label = list_item.get_child()
    if isinstance(item, Gtk.StringObject) and isinstance(label, Gtk.Label):
        label.set_label(item.get_string())


@dataclass
class AgentSettingsWidgets:
    pi_agent_command_row: Adw.EntryRow
    speech_agent_source_row: Adw.EntryRow


class AiSettingsWindow(Adw.ApplicationWindow):
    def __init__(self, app: Focus):
        super().__init__(application=app)
        self.app = app

        self._toast_overlay: Adw.ToastOverlay | None = None
        self._record_font_size_row: Adw.SpinRow | None = None
        self._table_font_size_row: Adw.SpinRow | None = None
        self._ai_font_size_row: Adw.SpinRow | None = None
        self._record_font_family_row: Adw.ComboRow | None = None
        self._record_font_family_values: list[str] = []
        self._grep_highlight_color_control: Gtk.Widget | None = None
        self._search_highlight_color_control: Gtk.Widget | None = None
        self._agent_widgets: AgentSettingsWidgets | None = None
        self._pi_model_options: list[PiModel | None] = []
        self._pi_available_model_keys: set[tuple[str, str]] = set()
        self._pi_thinking_options: list[str] = []
        self._pi_model_generation = 0
        self._pi_model_applying = False
        self._pi_model_selection_changed = False
        self._pi_thinking_selection_changed = False
        self._pi_model_closed = False
        self._skill_chooser: Gio.Cancellable | None = None
        self._skill_catalog: dict[tuple[str, str], PiModel] = {}
        self._skill_catalog_status = "Loading models authorized in Pi…"
        self._skill_model_options: list[tuple[str, str] | None] = []
        self._skill_effort_options: list[str | None] = []
        self._skill_applying = False
        self._skill_error = ""
        try:
            self._skill_preferences, self._skill_revision = read_preferences()
        except (OSError, ValueError) as exc:
            self._skill_preferences, self._skill_revision = SkillPreferences(), ""
            self._skill_error = f"Cannot read Research Skills settings: {exc}. Reopen Settings after resolving the error."
        self._skill_draft = self._skill_preferences
        try:
            self._original_pi_model_key = current_project_pi_model()
            self._original_pi_thinking_level = current_project_pi_thinking_level()
            self._pi_model_settings_error = ""
        except PiSettingsError as exc:
            self._original_pi_model_key = None
            self._original_pi_thinking_level = None
            self._pi_model_settings_error = str(exc)

        self.set_title("Settings")
        self.set_default_size(900, 720)
        self.set_resizable(True)
        self.connect("close-request", self._on_settings_close_request)
        self._build_ui()
        self._load_settings()
        self._session = SettingsSession(self, self._draft_snapshot)
        self._load_pi_models()

    def _build_ui(self) -> None:
        self._navigation = SettingsNavigation(lambda: self._on_save_clicked(None), lambda: self._pi_model_closed)

        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        box.set_margin_top(18)
        box.set_margin_bottom(12)
        box.set_margin_start(18)
        box.set_margin_end(18)


        appearance_group = Adw.PreferencesGroup()
        appearance_group.add_css_class("list-stack")
        appearance_group.set_hexpand(True)
        box.append(appearance_group)

        display_row = Adw.ExpanderRow(
            title="Display",
            subtitle="Fonts and text sizes",
        )
        display_row.set_expanded(False)
        appearance_group.add(display_row)

        ai_font_adjustment = Gtk.Adjustment(
            value=self.app.get_font_preferences()[1],
            lower=8,
            upper=48,
            step_increment=1,
            page_increment=2,
        )
        self._ai_font_size_row = Adw.SpinRow(
            title="AI Panel Font Size (pt)",
            adjustment=ai_font_adjustment,
        )
        self._ai_font_size_row.set_digits(0)
        display_row.add_row(self._ai_font_size_row)

        base_font_adjustment = Gtk.Adjustment(
            value=self.app.get_font_preferences()[0],
            lower=8,
            upper=48,
            step_increment=1,
            page_increment=2,
        )
        self._record_font_size_row = Adw.SpinRow(
            title="Record Font Size (pt)",
            adjustment=base_font_adjustment,
        )
        self._record_font_size_row.set_digits(0)
        display_row.add_row(self._record_font_size_row)

        self._record_font_family_values = [name for name, _css in RECORD_FONT_FAMILY_OPTIONS]
        self._record_font_family_row = Adw.ComboRow(title="Record Font (Non-Table)")
        self._record_font_family_row.set_model(
            Gtk.StringList.new(self._record_font_family_values)
        )
        display_row.add_row(self._record_font_family_row)

        table_font_adjustment = Gtk.Adjustment(
            value=self.app.get_font_preferences()[2],
            lower=8,
            upper=48,
            step_increment=1,
            page_increment=2,
        )
        self._table_font_size_row = Adw.SpinRow(
            title="Table Font Size (pt)",
            adjustment=table_font_adjustment,
        )
        self._table_font_size_row.set_digits(0)
        display_row.add_row(self._table_font_size_row)

        highlight_row = Adw.ExpanderRow(
            title="Highlights",
            subtitle="Search and grep highlight colors",
        )
        highlight_row.set_expanded(False)
        appearance_group.add(highlight_row)

        grep_color_row, self._grep_highlight_color_control = self._build_color_row(
            "Grep Highlight Color",
            DEFAULT_MATCH_COLOR,
        )
        highlight_row.add_row(grep_color_row)

        search_row, self._search_highlight_color_control = self._build_color_row(
            "Search Highlight Color",
            DEFAULT_SEARCH_HIGHLIGHT_COLOR,
        )
        highlight_row.add_row(search_row)

        agent_row = self._build_agent_settings_page()
        appearance_group.add(agent_row)

        scrolled = Gtk.ScrolledWindow()
        scrolled.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        scrolled.set_hexpand(True)
        scrolled.set_vexpand(True)
        scrolled.set_child(box)

        self._toast_overlay = Adw.ToastOverlay()
        self._navigation.pages["home"].get_child().set_content(scrolled)
        self._toast_overlay.set_child(self._navigation.view)
        self.set_content(self._toast_overlay)

    def _build_color_row(self, title: str, default: str) -> tuple[Gtk.Widget, Gtk.Widget]:
        color_dialog_cls = getattr(Gtk, "ColorDialog", None)
        color_dialog_button_cls = getattr(Gtk, "ColorDialogButton", None)
        if color_dialog_cls is not None and color_dialog_button_cls is not None:
            row = Adw.ActionRow(title=title)
            dialog = color_dialog_cls()
            if hasattr(dialog, "set_with_alpha"):
                dialog.set_with_alpha(True)
            button = color_dialog_button_cls.new(dialog)
            if hasattr(button, "add_css_class"):
                button.add_css_class("flat")
            row.add_suffix(button)
            row.set_activatable_widget(button)
            self._set_color_control_value(button, default, default)
            return row, button

        color_button_cls = getattr(Gtk, "ColorButton", None)
        if color_button_cls is not None:
            row = Adw.ActionRow(title=title)
            button = color_button_cls()
            if hasattr(button, "add_css_class"):
                button.add_css_class("flat")
            row.add_suffix(button)
            row.set_activatable_widget(button)
            self._set_color_control_value(button, default, default)
            return row, button
        fallback = Adw.EntryRow(title=title)
        fallback.set_hexpand(True)
        fallback.set_text(default)
        return fallback, fallback

    def _set_color_control_value(self, control: Gtk.Widget | None, value: str, default: str) -> None:
        if control is None:
            return
        normalized = _coerce_color_value(value, default)
        if hasattr(control, "set_rgba"):
            rgba = Gdk.RGBA()
            rgba.parse(normalized)
            control.set_rgba(rgba)
            return
        if hasattr(control, "set_text"):
            control.set_text(normalized)

    def _read_color_control_value(self, control: Gtk.Widget | None, default: str) -> str:
        if control is None:
            return default
        if hasattr(control, "get_rgba"):
            rgba = control.get_rgba()
            if rgba is not None:
                return _coerce_color_value(rgba.to_string(), default)
            return default
        if hasattr(control, "get_text"):
            return _coerce_color_value(control.get_text(), default)
        return default

    def _build_agent_settings_page(self) -> Adw.ExpanderRow:
        agent_row = Adw.ExpanderRow(
            title="Agent",
            subtitle="PI must be installed to answer Agent questions.",
        )
        agent_row.set_expanded(False)

        pi_agent_command_row = Adw.EntryRow(title="PI command")
        pi_agent_command_row.set_hexpand(True)
        agent_row.add_row(pi_agent_command_row)

        speech_agent_source_row = Adw.EntryRow(
            title="Speech-to-text question file",
        )
        speech_agent_source_row.set_tooltip_text(
            "Used by the submit_speech_agent_question D-Bus action."
        )
        speech_agent_source_row.set_hexpand(True)
        agent_row.add_row(speech_agent_source_row)

        self.pi_model_row = Adw.ComboRow(
            title="PI Model",
            subtitle=(
                self._pi_model_settings_error
                or "Loading models authorized in PI..."
            ),
        )
        self.pi_model_row.set_model(Gtk.StringList.new(["Loading PI models..."]))
        pi_model_list_factory = Gtk.SignalListItemFactory()
        pi_model_list_factory.connect("setup", _setup_pi_model_list_item)
        pi_model_list_factory.connect("bind", _bind_pi_model_list_item)
        self.pi_model_row.set_list_factory(pi_model_list_factory)
        self.pi_model_row.set_sensitive(False)
        self.pi_model_row.connect(
            "notify::selected",
            self._on_pi_model_selected,
        )
        self.pi_model_refresh_button = Gtk.Button(
            icon_name="view-refresh-symbolic",
        )
        self.pi_model_refresh_button.add_css_class("flat")
        self.pi_model_refresh_button.set_tooltip_text(
            "Refresh available PI models"
        )
        self.pi_model_refresh_button.connect(
            "clicked",
            self._on_refresh_pi_models,
        )
        add_model_suffix = getattr(self.pi_model_row, "add_suffix", None)
        if callable(add_model_suffix):
            add_model_suffix(self.pi_model_refresh_button)
        agent_row.add_row(self.pi_model_row)

        self.pi_thinking_row = Adw.ComboRow(
            title="Reasoning Effort",
            subtitle=(
                self._pi_model_settings_error
                or "Loading reasoning levels for the selected model..."
            ),
        )
        self.pi_thinking_row.set_model(Gtk.StringList.new(["Use Pi default"]))
        self.pi_thinking_row.set_sensitive(False)
        self.pi_thinking_row.connect(
            "notify::selected",
            self._on_pi_thinking_selected,
        )
        agent_row.add_row(self.pi_thinking_row)
        self._add_research_skill_rows(agent_row)

        self._agent_widgets = AgentSettingsWidgets(
            pi_agent_command_row=pi_agent_command_row,
            speech_agent_source_row=speech_agent_source_row,
        )
        return agent_row

    def _add_research_skill_rows(self, parent: Adw.ExpanderRow) -> None:
        self.skill_folder_row = Adw.ActionRow(title="Research skills folder", use_markup=False)
        choose = Gtk.Button(icon_name="folder-open-symbolic", valign=Gtk.Align.CENTER)
        self.skill_clear_button = Gtk.Button(icon_name="edit-clear-symbolic", valign=Gtk.Align.CENTER)
        for button, label, handler in (
            (choose, "Choose Research skills folder", self._choose_skill_folder),
            (self.skill_clear_button, "Clear Research skills folder", self._clear_skill_folder),
        ):
            button.add_css_class("flat")
            button.set_tooltip_text(label)
            button.update_property([Gtk.AccessibleProperty.LABEL], [label])
            button.connect("clicked", handler)
            self.skill_folder_row.add_suffix(button)
        self.skill_folder_row.set_activatable_widget(choose)
        self.skill_folder_row.set_sensitive(not self._skill_error)
        parent.add_row(self.skill_folder_row)
        self.skill_model_row = Adw.ComboRow(title="Skill model", use_markup=False)
        factory = Gtk.SignalListItemFactory()
        factory.connect("setup", _setup_pi_model_list_item)
        factory.connect("bind", _bind_pi_model_list_item)
        self.skill_model_row.set_list_factory(factory)
        self.skill_model_row.connect("notify::selected", self._on_skill_model_selected)
        parent.add_row(self.skill_model_row)
        self.skill_effort_row = Adw.ComboRow(title="Skill reasoning effort", use_markup=False)
        self.skill_effort_row.connect("notify::selected", self._on_skill_effort_selected)
        parent.add_row(self.skill_effort_row)
        self._sync_skill_rows()

    def _choose_skill_folder(self, _button: Gtk.Button) -> None:
        if self._skill_chooser is not None:
            return
        dialog = Gtk.FileDialog(title="Choose Research skills folder", modal=True)
        if self._skill_draft.folder:
            dialog.set_initial_folder(Gio.File.new_for_path(self._skill_draft.folder))
        cancellable = Gio.Cancellable()
        self._skill_chooser = cancellable
        dialog.select_folder(self, cancellable, self._on_skill_folder_chosen)

    def _on_skill_folder_chosen(self, dialog: Gtk.FileDialog, result: Gio.AsyncResult) -> None:
        cancellable, self._skill_chooser = self._skill_chooser, None
        if self._pi_model_closed or (cancellable is not None and cancellable.is_cancelled()):
            return
        try:
            folder = dialog.select_folder_finish(result).get_path()
        except GLib.Error:
            return  # Dismissed or cancelled.
        if not folder:
            self._show_status_toast("Choose a local folder for Research Skills.")
            return
        old = self._skill_draft
        self._set_skill_draft(SkillPreferences(folder, old.model_key, old.effort))

    def _clear_skill_folder(self, _button: Gtk.Button) -> None:
        if self._skill_chooser is not None:
            self._skill_chooser.cancel()
        self._set_skill_draft(SkillPreferences())

    def _set_skill_draft(self, draft: SkillPreferences) -> None:
        self._skill_draft = draft
        self._sync_skill_rows()

    def _sync_skill_rows(self) -> None:
        draft = self._skill_draft
        self.skill_folder_row.set_subtitle(self._skill_error or draft.folder or "Off · Choose a folder of Markdown questions")
        self.skill_clear_button.set_visible(bool(draft.folder))
        self.skill_model_row.set_visible(bool(draft.folder))
        self.skill_effort_row.set_visible(bool(draft.folder))
        self._skill_applying = True
        try:
            keys = [None, *self._skill_catalog]
            if draft.model_key and draft.model_key not in keys:
                keys.insert(1, draft.model_key)
            self._skill_model_options = keys
            labels = ["Use Agent Q&A model"]
            for key in keys[1:]:
                model = self._skill_catalog.get(key)
                exact = f"{key[0]} / {key[1]}"
                labels.append(f"{model.name} — {exact}" if model else f"{exact} (unavailable)")
            self.skill_model_row.set_model(Gtk.StringList.new(labels))
            self.skill_model_row.set_selected(keys.index(draft.model_key))
            # Even offline, a retained override can be explicitly reset to inherit.
            self.skill_model_row.set_sensitive(len(keys) > 1 and not self._skill_error)
        finally:
            self._skill_applying = False
        self._update_skill_model_subtitle()
        self._sync_skill_effort()

    def _update_skill_model_subtitle(self) -> None:
        key = self._skill_draft.model_key
        self.skill_model_row.set_subtitle(self._skill_catalog_status or (
            f"{key[0]} / {key[1]}" if key else "Inherit the ordinary Agent model and reasoning effort."))

    def _sync_skill_effort(self) -> None:
        draft = self._skill_draft
        model = self._skill_catalog.get(draft.model_key)
        self._skill_applying = True
        try:
            levels = [None, *(model.supported_thinking_levels if model else ())]
            if draft.effort and draft.effort not in levels:
                levels.append(draft.effort)
            self._skill_effort_options = levels
            self.skill_effort_row.set_model(Gtk.StringList.new([
                "Use Agent Q&A effort" if level is None else _format_pi_thinking_level(level)
                for level in levels
            ]))
            self.skill_effort_row.set_selected(levels.index(draft.effort))
            self.skill_effort_row.set_sensitive(len(levels) > 1 and not self._skill_error)
            self.skill_effort_row.set_subtitle(
                "Select a skill model to override reasoning." if draft.model_key is None else
                "Selected effort is unavailable; choose a supported effort or inherit."
                if model is not None and draft.effort and draft.effort not in model.supported_thinking_levels else
                "Applies to new skill sessions, not ordinary questions."
            )
        finally:
            self._skill_applying = False

    def _on_skill_model_selected(self, row: Adw.ComboRow, _param: object) -> None:
        selected = int(row.get_selected())
        if not self._skill_applying and selected < len(self._skill_model_options):
            model_key = self._skill_model_options[selected]
            draft = self._skill_draft
            if model_key != draft.model_key:
                self._skill_draft = SkillPreferences(draft.folder, model_key, draft.effort if model_key else None)
                self._update_skill_model_subtitle()
                self._sync_skill_effort()

    def _on_skill_effort_selected(self, row: Adw.ComboRow, _param: object) -> None:
        selected = int(row.get_selected())
        if not self._skill_applying and selected < len(self._skill_effort_options):
            draft = self._skill_draft
            effort = self._skill_effort_options[selected]
            if effort != draft.effort:
                self._skill_draft = SkillPreferences(draft.folder, draft.model_key, effort)

    def _on_settings_close_request(self, *_args: object) -> bool:
        if hasattr(self, "_session") and self._session.close_request():
            return True
        self._pi_model_closed = True
        self._pi_model_generation += 1
        if self._skill_chooser is not None:
            self._skill_chooser.cancel()
        return False

    def _draft_snapshot(self):
        model = self._selected_pi_model()
        key = model.settings_key if self._pi_model_selection_changed and model else self._original_pi_model_key
        effort = self._selected_pi_thinking_level() if self._pi_thinking_selection_changed else self._original_pi_thinking_level
        base = (self._agent_widgets.pi_agent_command_row.get_text(), self._agent_widgets.speech_agent_source_row.get_text(),
                self._record_font_size_row.get_value(), self._ai_font_size_row.get_value(), self._table_font_size_row.get_value(),
                int(self._record_font_family_row.get_selected()),
                *(self._read_color_control_value(w, default) for w, default in (
                    (self._grep_highlight_color_control, DEFAULT_MATCH_COLOR),
                    (self._search_highlight_color_control, DEFAULT_SEARCH_HIGHLIGHT_COLOR))))
        return base, (key, effort), self._skill_draft

    def _selected_pi_model(self) -> PiModel | None:
        selected = int(self.pi_model_row.get_selected())
        if 0 <= selected < len(self._pi_model_options):
            return self._pi_model_options[selected]
        return None

    def _selected_pi_thinking_level(self) -> str:
        selected = int(self.pi_thinking_row.get_selected())
        if 0 <= selected < len(self._pi_thinking_options):
            return self._pi_thinking_options[selected]
        return ""

    def _populate_pi_thinking_row(self, preferred: str) -> None:
        model = self._selected_pi_model()
        requested = preferred or ""
        self._pi_model_applying = True
        try:
            if model is None:
                self._pi_thinking_options = [requested]
                self.pi_thinking_row.set_model(
                    Gtk.StringList.new([_format_pi_thinking_level(requested) if requested else "Use Pi default"])
                )
                self.pi_thinking_row.set_selected(0)
                self.pi_thinking_row.set_sensitive(False)
                self.pi_thinking_row.set_subtitle(
                    "Select an available PI model to choose reasoning effort."
                )
                self._pi_thinking_selection_changed = False
                return

            if model.settings_key not in self._pi_available_model_keys:
                self._pi_thinking_options = [requested]
                self.pi_thinking_row.set_model(
                    Gtk.StringList.new([_format_pi_thinking_level(requested) if requested else "Use Pi default"])
                )
                self.pi_thinking_row.set_selected(0)
                self.pi_thinking_row.set_sensitive(False)
                self.pi_thinking_row.set_subtitle(
                    "The configured model is unavailable; this value is preserved."
                )
                self._pi_thinking_selection_changed = requested != (self._original_pi_thinking_level or "")
                return

            effective = clamp_pi_thinking_level(model, requested) if requested else ""
            levels = list(model.supported_thinking_levels or ("off",))
            if not requested:
                levels.insert(0, "")
            self._pi_thinking_options = levels
            self.pi_thinking_row.set_model(
                Gtk.StringList.new(
                    [_format_pi_thinking_level(level) if level else "Use Pi default" for level in levels]
                )
            )
            self.pi_thinking_row.set_selected(levels.index(effective))
            self.pi_thinking_row.set_sensitive(True)
            self._pi_thinking_selection_changed = (
                effective != (self._original_pi_thinking_level or "")
                and (self._pi_model_selection_changed or self._pi_thinking_selection_changed)
            )
            if not requested:
                self.pi_thinking_row.set_subtitle("Inherit Pi reasoning; no app effort override.")
            elif effective != requested:
                self.pi_thinking_row.set_subtitle(
                    f"{_format_pi_thinking_level(requested)} is unsupported by "
                    f"this model; PI will use {_format_pi_thinking_level(effective)}."
                )
            else:
                self.pi_thinking_row.set_subtitle(
                    "New Agent sessions start with "
                    f"{_format_pi_thinking_level(effective)} reasoning."
                )
        finally:
            self._pi_model_applying = False

    def _update_pi_model_subtitle(self) -> None:
        model = self._selected_pi_model()
        if model is None:
            return
        self.pi_model_row.set_subtitle(
            f"Project-wide setting: {model.provider} / {model.model_id}"
        )

    def _on_pi_model_selected(
        self,
        _row: Adw.ComboRow,
        _parameter: object,
    ) -> None:
        if self._pi_model_applying:
            return
        model = self._selected_pi_model()
        if model is None:
            return
        self._pi_model_selection_changed = (
            model.settings_key != self._original_pi_model_key
        )
        self._update_pi_model_subtitle()
        preferred = self._selected_pi_thinking_level()
        self._populate_pi_thinking_row(preferred)

    def _on_pi_thinking_selected(
        self,
        _row: Adw.ComboRow,
        _parameter: object,
    ) -> None:
        if self._pi_model_applying:
            return
        thinking_level = self._selected_pi_thinking_level()
        self._pi_thinking_selection_changed = (
            thinking_level != (self._original_pi_thinking_level or "")
        )
        self.pi_thinking_row.set_subtitle(
            "New Agent sessions start with "
            f"{_format_pi_thinking_level(thinking_level)} reasoning."
            if thinking_level else "Inherit Pi reasoning; no app effort override."
        )

    def _on_refresh_pi_models(self, _button: Gtk.Button) -> None:
        self._load_pi_models()

    def _load_pi_models(self) -> None:
        if self._pi_model_closed:
            return
        if self._pi_model_settings_error:
            try:
                self._original_pi_model_key = current_project_pi_model()
                self._original_pi_thinking_level = (
                    current_project_pi_thinking_level()
                )
                self._pi_model_settings_error = ""
            except PiSettingsError as exc:
                self.pi_model_row.set_subtitle(str(exc))
                self.pi_model_row.set_sensitive(False)
                self.pi_thinking_row.set_subtitle(str(exc))
                self.pi_thinking_row.set_sensitive(False)
                self.pi_model_refresh_button.set_sensitive(True)

        selected = self._selected_pi_model()
        desired_key = (
            selected.settings_key
            if self._pi_model_selection_changed and selected is not None
            else self._original_pi_model_key
        )
        selected_thinking = self._selected_pi_thinking_level()
        desired_thinking = (
            selected_thinking
            if self._pi_thinking_selection_changed
            else self._original_pi_thinking_level or ""
        )
        self._pi_model_generation += 1
        generation = self._pi_model_generation
        command = (
            self._agent_widgets.pi_agent_command_row.get_text().strip()
            if self._agent_widgets is not None
            else DEFAULT_PI_AGENT_COMMAND
        )
        try:
            command_argv = resolve_pi_agent_argv(
                command or DEFAULT_PI_AGENT_COMMAND,
                path_env=os.environ.get("PATH"),
            )
        except ValueError as exc:
            self._finish_pi_model_load(
                generation,
                [],
                f"Invalid PI command: {exc}",
                desired_key,
                desired_thinking,
            )
            return
        if not command_argv:
            self._finish_pi_model_load(
                generation,
                [],
                "PI command is empty.",
                desired_key,
                desired_thinking,
            )
            return
        incompatible_flag = incompatible_pi_agent_flag(command_argv)
        if incompatible_flag:
            self._finish_pi_model_load(
                generation,
                [],
                (
                    f"PI option {incompatible_flag} is incompatible with "
                    "the embedded session."
                ),
                desired_key,
                desired_thinking,
            )
            return

        self.pi_model_row.set_sensitive(False)
        self.pi_model_row.set_subtitle("Loading models authorized in PI...")
        self.pi_thinking_row.set_sensitive(False)
        self.pi_thinking_row.set_subtitle(
            "Loading reasoning levels for the selected model..."
        )
        self.pi_model_refresh_button.set_sensitive(False)
        self._skill_catalog_status = "Loading models authorized in Pi…"
        self._sync_skill_rows()

        def worker() -> None:
            try:
                models = available_pi_models(command_argv)
                error = ""
            except PiRuntimeError as exc:
                models = []
                error = str(exc)
            GLib.idle_add(
                self._finish_pi_model_load,
                generation,
                models,
                error,
                desired_key,
                desired_thinking,
            )

        threading.Thread(
            target=worker,
            name="focus-pi-models",
            daemon=True,
        ).start()

    def _finish_pi_model_load(
        self,
        generation: int,
        models: list[PiModel],
        error: str,
        desired_key: tuple[str, str] | None,
        desired_thinking: str,
    ) -> bool:
        if self._pi_model_closed or generation != self._pi_model_generation:
            return False
        self.pi_model_refresh_button.set_sensitive(True)
        self._skill_catalog = {model.settings_key: model for model in models}
        self._skill_catalog_status = error or ("" if models else "No authenticated Pi models found.")
        self._sync_skill_rows()
        if self._pi_model_settings_error:
            self.pi_model_row.set_subtitle(self._pi_model_settings_error)
            self.pi_thinking_row.set_subtitle(self._pi_model_settings_error)
            return False
        if error:
            self._pi_available_model_keys = set()
            current = desired_key
            if current is None:
                self._pi_model_options = [None]
                labels = ["PI models unavailable"]
            else:
                current_model = PiModel(
                    provider=current[0],
                    model_id=current[1],
                    name=current[1],
                )
                self._pi_model_options = [current_model]
                labels = [f"{current_model.label} (currently configured)"]
            self._pi_model_applying = True
            self.pi_model_row.set_model(Gtk.StringList.new(labels))
            self.pi_model_row.set_selected(0)
            self._pi_model_applying = False
            self._pi_model_selection_changed = current != self._original_pi_model_key
            self.pi_model_row.set_sensitive(False)
            self.pi_model_row.set_subtitle(error)
            self._populate_pi_thinking_row(desired_thinking)
            self.pi_thinking_row.set_subtitle(error)
            return False

        available_keys = {model.settings_key for model in models}
        self._pi_available_model_keys = available_keys
        options: list[PiModel | None] = []
        labels: list[str] = []
        current = desired_key
        if current is not None and current not in available_keys:
            unavailable = PiModel(
                provider=current[0],
                model_id=current[1],
                name=current[1],
            )
            options.append(unavailable)
            labels.append(
                f"{unavailable.label} (currently configured; unavailable)"
            )
        if current is None:
            options.append(None)
            labels.append("Use Pi default (inherited)")
        options.extend(models)
        labels.extend(model.label for model in models)
        if not options:
            options = [None]
            labels = ["No authenticated PI models found"]

        selected_index = 0
        if desired_key is not None:
            for index, model in enumerate(options):
                if model is not None and model.settings_key == desired_key:
                    selected_index = index
                    break
        self._pi_model_options = options
        self._pi_model_applying = True
        self.pi_model_row.set_model(Gtk.StringList.new(labels))
        self.pi_model_row.set_selected(selected_index)
        self._pi_model_applying = False
        selected_model = self._selected_pi_model()
        self._pi_model_selection_changed = bool(
            selected_model is not None
            and selected_model.settings_key != self._original_pi_model_key
        )
        self.pi_model_row.set_sensitive(bool(models))
        if selected_model is None:
            self.pi_model_row.set_subtitle(
                "Inherit Pi's current model. Install Pi, use /login and select an available model if unconfigured."
            )
        else:
            self._update_pi_model_subtitle()
        self._populate_pi_thinking_row(desired_thinking)
        return False

    def _load_settings(self) -> None:
        settings = load_ai_settings()
        if self._agent_widgets is not None:
            self._agent_widgets.pi_agent_command_row.set_text(settings.pi_agent_command)
            self._agent_widgets.speech_agent_source_row.set_text(
                settings.speech_agent_source_file or DEFAULT_SPEECH_AGENT_SOURCE_FILE
            )

        if self._ai_font_size_row:
            _, ai_font, _ = self.app.get_font_preferences()
            self._ai_font_size_row.set_value(float(ai_font))
        if self._record_font_size_row:
            base_font, _, _ = self.app.get_font_preferences()
            self._record_font_size_row.set_value(float(base_font))
        if self._table_font_size_row:
            _, _, table_font = self.app.get_font_preferences()
            self._table_font_size_row.set_value(float(table_font))
        if self._record_font_family_row:
            family = self.app.get_record_font_family_name()
            if family in self._record_font_family_values:
                self._record_font_family_row.set_selected(
                    self._record_font_family_values.index(family)
                )
            else:
                self._record_font_family_row.set_selected(0)
        self._set_color_control_value(
            self._grep_highlight_color_control,
            settings.grep_highlight_color,
            DEFAULT_MATCH_COLOR,
        )
        self._set_color_control_value(
            self._search_highlight_color_control,
            settings.search_highlight_color,
            DEFAULT_SEARCH_HIGHLIGHT_COLOR,
        )

    def _show_status_toast(self, text: str) -> None:
        if not self._toast_overlay or not text:
            return
        toast = Adw.Toast.new(text)
        toast.set_timeout(5)
        self._toast_overlay.add_toast(toast)

    def _on_save_clicked(self, _btn: Gtk.Button) -> None:
        if self._agent_widgets is None:
            return

        speech_agent_source_file = self._agent_widgets.speech_agent_source_row.get_text().strip()
        pi_agent_command = self._agent_widgets.pi_agent_command_row.get_text().strip()

        grep_highlight_color = self._read_color_control_value(
            self._grep_highlight_color_control,
            DEFAULT_MATCH_COLOR,
        )
        search_highlight_color = self._read_color_control_value(
            self._search_highlight_color_control,
            DEFAULT_SEARCH_HIGHLIGHT_COLOR,
        )

        record_font_size = (
            int(round(self._record_font_size_row.get_value()))
            if self._record_font_size_row
            else self.app.get_font_preferences()[0]
        )
        ai_font_size = (
            int(round(self._ai_font_size_row.get_value()))
            if self._ai_font_size_row
            else self.app.get_font_preferences()[1]
        )
        table_font_size = (
            int(round(self._table_font_size_row.get_value()))
            if self._table_font_size_row
            else self.app.get_font_preferences()[2]
        )
        selected_font_family_index = (
            int(self._record_font_family_row.get_selected())
            if self._record_font_family_row
            else -1
        )
        if 0 <= selected_font_family_index < len(self._record_font_family_values):
            record_font_family_name = self._record_font_family_values[selected_font_family_index]
        else:
            record_font_family_name = self.app.get_record_font_family_name()
        settings = AiSettings(
            speech_agent_source_file=(
                speech_agent_source_file or DEFAULT_SPEECH_AGENT_SOURCE_FILE
            ),
            pi_agent_command=pi_agent_command or DEFAULT_PI_AGENT_COMMAND,
            grep_highlight_color=grep_highlight_color,
            search_highlight_color=search_highlight_color,
        )
        base, pi_baseline, skill_baseline = self._session.baseline
        draft_base, _, skill_draft = self._draft_snapshot()
        selected_model = self._selected_pi_model()
        pi_dirty = self._pi_model_selection_changed or self._pi_thinking_selection_changed
        skill_dirty = skill_draft != self._skill_preferences
        saved: list[str] = []
        errors: list[str] = []
        if pi_dirty and selected_model is not None:
            try:
                save_project_pi_runtime(
                    selected_model,
                    self._selected_pi_thinking_level() if self._pi_thinking_selection_changed else None,
                )
            except PiSettingsError as exc:
                errors.append(f"Pi Agent: {exc}")
            else:
                self._original_pi_model_key = selected_model.settings_key
                if self._pi_thinking_selection_changed:
                    self._original_pi_thinking_level = self._selected_pi_thinking_level()
                self._pi_model_selection_changed = False
                self._pi_thinking_selection_changed = False
                pi_baseline = self._original_pi_model_key, self._original_pi_thinking_level
                saved.append("Agent model")
        if skill_dirty:
            try:
                self._skill_revision = save_preferences(skill_draft, self._skill_revision)
            except (OSError, ValueError) as exc:
                errors.append(f"Research Skills: {exc}")
            else:
                self._skill_preferences = skill_baseline = skill_draft
                saved.append("Research Skills")
        if draft_base != base or not (pi_dirty or skill_dirty):
            try:
                save_ai_settings(settings)
                self.app.update_font_sizes(
                    font_size_pt=record_font_size,
                    ai_font_size_pt=ai_font_size,
                    table_font_size_pt=table_font_size,
                    record_font_family_name=record_font_family_name,
                )
                self.app.on_ai_settings_saved(settings)
            except Exception:
                errors.append("Some settings may already have been written; drafts are retained.")
            else:
                base = draft_base
                saved.append("Focus settings")
        self._session.baseline = base, pi_baseline, skill_baseline
        if saved:
            callback = getattr(self.app, "on_research_settings_changed", None)
            if callback is not None:
                callback()
        if errors:
            prefix = f"Saved {', '.join(saved)}. " if saved else ""
            self._show_status_toast(prefix + "Save failed: " + " ".join(errors))
        else:
            self._show_status_toast("Saved. Model and reasoning changes apply to new sessions.")
