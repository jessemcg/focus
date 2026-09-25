from __future__ import annotations

import threading

from focus.core import *  # noqa: F401,F403
from focus.pi_runtime import (
    PiModel,
    PiRuntimeError,
    PiSettingsError,
    available_pi_models,
    clamp_pi_thinking_level,
    current_project_pi_model,
    current_project_pi_thinking_level,
    ensure_project_pi_settings,
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
        self._phrase_highlight_color_control: Gtk.Widget | None = None
        self._summary_emphasis_color_control: Gtk.Widget | None = None
        self._search_chip_color_control: Gtk.Widget | None = None
        self._highlight_phrases_buffer: Gtk.TextBuffer | None = None
        self._agent_widgets: AgentSettingsWidgets | None = None
        self._pi_model_options: list[PiModel | None] = []
        self._pi_available_model_keys: set[tuple[str, str]] = set()
        self._pi_thinking_options: list[str] = []
        self._pi_model_generation = 0
        self._pi_model_applying = False
        self._pi_model_selection_changed = False
        self._pi_thinking_selection_changed = False
        self._pi_model_closed = False
        try:
            ensure_project_pi_settings()
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
        self._load_pi_models()

    def _build_ui(self) -> None:
        view = Adw.ToolbarView()
        header = Adw.HeaderBar()
        header.add_css_class("flat")
        header.set_title_widget(Adw.WindowTitle(title="Settings"))
        save_btn = Gtk.Button(label="Save")
        save_btn.add_css_class("suggested-action")
        save_btn.add_css_class("flat")
        save_btn.connect("clicked", self._on_save_clicked)
        header.pack_end(save_btn)
        view.add_top_bar(header)

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
            subtitle="Colors and phrases",
        )
        highlight_row.set_expanded(False)
        appearance_group.add(highlight_row)

        grep_color_row, self._grep_highlight_color_control = self._build_color_row(
            "Grep Highlight Color",
            DEFAULT_MATCH_COLOR,
        )
        highlight_row.add_row(grep_color_row)

        phrase_color_row, self._phrase_highlight_color_control = self._build_color_row(
            "Phrase Highlight Color",
            DEFAULT_HIGHLIGHT_COLOR,
        )
        highlight_row.add_row(phrase_color_row)

        summary_emphasis_row, self._summary_emphasis_color_control = self._build_color_row(
            "Summary Emphasis Color",
            DEFAULT_SUMMARY_EMPHASIS_COLOR,
        )
        highlight_row.add_row(summary_emphasis_row)

        search_chip_row, self._search_chip_color_control = self._build_color_row(
            "Search and Cite Chip Color",
            DEFAULT_SEARCH_CHIP_COLOR,
        )
        highlight_row.add_row(search_chip_row)

        highlight_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        highlight_box.set_margin_top(6)
        highlight_box.set_margin_bottom(6)
        highlight_box.set_margin_start(12)
        highlight_box.set_margin_end(12)
        highlight_label = Gtk.Label(
            label="Highlight phrases (case-sensitive, one per line)",
            xalign=0,
        )
        highlight_label.add_css_class("dim-label")
        highlight_box.append(highlight_label)

        highlight_scroller = Gtk.ScrolledWindow()
        highlight_scroller.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.AUTOMATIC)
        highlight_scroller.set_hexpand(True)
        highlight_scroller.set_vexpand(False)
        highlight_scroller.set_min_content_height(110)
        highlight_buffer = Gtk.TextBuffer()
        highlight_view = Gtk.TextView.new_with_buffer(highlight_buffer)
        highlight_view.set_wrap_mode(Gtk.WrapMode.WORD_CHAR)
        highlight_view.set_top_margin(8)
        highlight_view.set_bottom_margin(8)
        highlight_view.set_left_margin(8)
        highlight_view.set_right_margin(8)
        highlight_scroller.set_child(highlight_view)
        highlight_box.append(highlight_scroller)
        highlight_row.add_row(highlight_box)
        self._highlight_phrases_buffer = highlight_buffer

        agent_row = self._build_agent_settings_page()
        appearance_group.add(agent_row)

        scrolled = Gtk.ScrolledWindow()
        scrolled.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        scrolled.set_hexpand(True)
        scrolled.set_vexpand(True)
        scrolled.set_child(box)

        self._toast_overlay = Adw.ToastOverlay()
        self._toast_overlay.set_child(scrolled)
        view.set_content(self._toast_overlay)
        self.set_content(view)

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
        self.pi_thinking_row.set_model(Gtk.StringList.new(["Medium"]))
        self.pi_thinking_row.set_sensitive(False)
        self.pi_thinking_row.connect(
            "notify::selected",
            self._on_pi_thinking_selected,
        )
        agent_row.add_row(self.pi_thinking_row)

        pi_configuration_row = Adw.ActionRow(
            title="PI configuration",
            subtitle=(
                "The selected provider, model, and reasoning effort are saved in "
                "project .pi/settings.json; credentials remain in your "
                "global PI configuration."
            ),
        )
        agent_row.add_row(pi_configuration_row)

        pi_access_row = Adw.ActionRow(
            title="PI access",
            subtitle=(
                "Focus permits guarded transcript-page reads and its structured "
                "record search and answer tools; shell access is disabled."
            ),
        )
        warning_icon = Gtk.Image.new_from_icon_name("dialog-warning-symbolic")
        warning_icon.add_css_class("warning")
        pi_access_row.add_prefix(warning_icon)
        agent_row.add_row(pi_access_row)

        self._agent_widgets = AgentSettingsWidgets(
            pi_agent_command_row=pi_agent_command_row,
            speech_agent_source_row=speech_agent_source_row,
        )
        return agent_row

    def _on_settings_close_request(self, *_args: object) -> bool:
        self._pi_model_closed = True
        self._pi_model_generation += 1
        return False

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
        requested = preferred or self._original_pi_thinking_level or "medium"
        self._pi_model_applying = True
        try:
            if model is None:
                self._pi_thinking_options = [requested]
                self.pi_thinking_row.set_model(
                    Gtk.StringList.new([_format_pi_thinking_level(requested)])
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
                    Gtk.StringList.new([_format_pi_thinking_level(requested)])
                )
                self.pi_thinking_row.set_selected(0)
                self.pi_thinking_row.set_sensitive(False)
                self.pi_thinking_row.set_subtitle(
                    "The configured model is unavailable; this value is preserved."
                )
                self._pi_thinking_selection_changed = False
                return

            effective = clamp_pi_thinking_level(model, requested)
            levels = list(model.supported_thinking_levels or ("off",))
            self._pi_thinking_options = levels
            self.pi_thinking_row.set_model(
                Gtk.StringList.new(
                    [_format_pi_thinking_level(level) for level in levels]
                )
            )
            self.pi_thinking_row.set_selected(levels.index(effective))
            self.pi_thinking_row.set_sensitive(True)
            self._pi_thinking_selection_changed = (
                effective != self._original_pi_thinking_level
            )
            if effective != requested:
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
        if not thinking_level:
            return
        self._pi_thinking_selection_changed = (
            thinking_level != self._original_pi_thinking_level
        )
        self.pi_thinking_row.set_subtitle(
            "New Agent sessions start with "
            f"{_format_pi_thinking_level(thinking_level)} reasoning."
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
                return

        selected = self._selected_pi_model()
        desired_key = (
            selected.settings_key
            if self._pi_model_selection_changed and selected is not None
            else self._original_pi_model_key
        )
        selected_thinking = self._selected_pi_thinking_level()
        desired_thinking = (
            selected_thinking
            if self._pi_thinking_selection_changed and selected_thinking
            else self._original_pi_thinking_level or "medium"
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
        if error:
            self._pi_available_model_keys = set()
            current = self._original_pi_model_key
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
            self._pi_model_selection_changed = False
            self.pi_model_row.set_sensitive(False)
            self.pi_model_row.set_subtitle(error)
            self._populate_pi_thinking_row(desired_thinking)
            self.pi_thinking_row.set_subtitle(error)
            return False

        available_keys = {model.settings_key for model in models}
        self._pi_available_model_keys = available_keys
        options: list[PiModel | None] = []
        labels: list[str] = []
        current = self._original_pi_model_key
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
                "Authorize a provider in PI, then refresh this list."
            )
        else:
            self._update_pi_model_subtitle()
        self._populate_pi_thinking_row(desired_thinking)
        return False

    def _prompt_text(self, buffer: Gtk.TextBuffer) -> str:
        start, end = buffer.get_bounds()
        return buffer.get_text(start, end, True)

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
        if self._highlight_phrases_buffer is not None:
            self._highlight_phrases_buffer.set_text(
                _format_highlight_phrases(settings.highlight_phrases)
            )
        self._set_color_control_value(
            self._grep_highlight_color_control,
            settings.grep_highlight_color,
            DEFAULT_MATCH_COLOR,
        )
        self._set_color_control_value(
            self._phrase_highlight_color_control,
            settings.phrase_highlight_color,
            DEFAULT_HIGHLIGHT_COLOR,
        )
        self._set_color_control_value(
            self._summary_emphasis_color_control,
            settings.summary_emphasis_color,
            DEFAULT_SUMMARY_EMPHASIS_COLOR,
        )
        self._set_color_control_value(
            self._search_chip_color_control,
            settings.search_chip_color,
            DEFAULT_SEARCH_CHIP_COLOR,
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

        highlight_phrases = (
            _normalize_highlight_phrases(self._prompt_text(self._highlight_phrases_buffer))
            if self._highlight_phrases_buffer is not None
            else []
        )
        grep_highlight_color = self._read_color_control_value(
            self._grep_highlight_color_control,
            DEFAULT_MATCH_COLOR,
        )
        phrase_highlight_color = self._read_color_control_value(
            self._phrase_highlight_color_control,
            DEFAULT_HIGHLIGHT_COLOR,
        )
        summary_emphasis_color = self._read_color_control_value(
            self._summary_emphasis_color_control,
            DEFAULT_SUMMARY_EMPHASIS_COLOR,
        )
        search_chip_color = self._read_color_control_value(
            self._search_chip_color_control,
            DEFAULT_SEARCH_CHIP_COLOR,
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
            highlight_phrases=highlight_phrases,
            grep_highlight_color=grep_highlight_color,
            phrase_highlight_color=phrase_highlight_color,
            summary_emphasis_color=summary_emphasis_color,
            search_chip_color=search_chip_color,
        )
        selected_pi_model = self._selected_pi_model()
        selected_pi_thinking = self._selected_pi_thinking_level()
        pi_runtime_saved = False
        if (
            self._pi_model_selection_changed
            or self._pi_thinking_selection_changed
        ) and selected_pi_model is not None and selected_pi_thinking:
            try:
                save_project_pi_runtime(
                    selected_pi_model,
                    selected_pi_thinking,
                )
                pi_runtime_saved = True
            except PiSettingsError as exc:
                self._show_status_toast(f"Unable to save PI Agent settings: {exc}")
                return
        save_ai_settings(settings)
        if pi_runtime_saved and selected_pi_model is not None:
            self._original_pi_model_key = selected_pi_model.settings_key
            self._original_pi_thinking_level = selected_pi_thinking
            self._pi_model_selection_changed = False
            self._pi_thinking_selection_changed = False
        self.app.update_font_sizes(
            font_size_pt=record_font_size,
            ai_font_size_pt=ai_font_size,
            table_font_size_pt=table_font_size,
            record_font_family_name=record_font_family_name,
        )
        self.app.on_ai_settings_saved(settings)
        if pi_runtime_saved:
            self._show_status_toast(
                "Saved. The PI model and reasoning effort apply to new Agent sessions."
            )
        else:
            self._show_status_toast("Saved. Agent questions are enabled.")
