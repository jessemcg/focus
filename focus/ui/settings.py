from __future__ import annotations

from focus.core import *  # noqa: F401,F403

@dataclass
class SummarizationPromptWidgets:
    profile_dropdown: Gtk.DropDown
    prompt_buffer: Gtk.TextBuffer


@dataclass
class RagPromptWidgets:
    profile_dropdown: Gtk.DropDown
    provider_row: Adw.ComboRow
    provider_values: list[str]
    voyage_model_row: Adw.EntryRow
    voyage_key_row: Adw.EntryRow
    isaacus_model_row: Adw.EntryRow
    isaacus_key_row: Adw.EntryRow
    rag_chunk_row: Adw.SpinRow
    speech_rag_source_row: Adw.EntryRow
    prompt_buffer: Gtk.TextBuffer


@dataclass
class AgentSettingsWidgets:
    pi_agent_command_row: Adw.EntryRow


@dataclass
class ModelProfileEditorWidgets:
    nickname_row: Adw.EntryRow
    abbreviation_row: Adw.EntryRow
    api_url_row: Adw.EntryRow
    model_row: Adw.EntryRow
    api_key_row: Adw.EntryRow
    disable_reasoning_row: Adw.SwitchRow
    priority_service_tier_row: Adw.SwitchRow


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
        self._prompt_editors: dict[
            str,
            SummarizationPromptWidgets | RagPromptWidgets | AgentSettingsWidgets,
        ] = {}
        self._model_profiles: list[ModelProfile] = list(app._ai_settings.model_profiles)
        self._model_profile_editors: dict[str, ModelProfileEditorWidgets] = {}
        self._prompt_row_keys: dict[Gtk.ListBoxRow, str] = {}
        self._prompt_list: Gtk.ListBox | None = None
        self._prompt_stack: Gtk.Stack | None = None
        self._speech_rag_source_dialog: Gtk.FileDialog | None = None

        self.set_title("Settings")
        self.set_default_size(900, 720)
        self.set_resizable(True)
        self._build_ui()
        self._load_settings()

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
            "Search Chip Color",
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

        split = Gtk.Paned(orientation=Gtk.Orientation.HORIZONTAL)
        split.set_hexpand(True)
        split.set_vexpand(True)
        split.set_shrink_start_child(False)
        split.set_shrink_end_child(False)
        split.set_resize_start_child(False)
        split.set_resize_end_child(True)

        prompt_list = Gtk.ListBox()
        prompt_list.set_selection_mode(Gtk.SelectionMode.SINGLE)
        prompt_list.add_css_class("navigation-sidebar")
        prompt_list.connect("row-selected", self._on_prompt_row_selected)
        self._prompt_list = prompt_list

        prompt_list_scroller = Gtk.ScrolledWindow()
        prompt_list_scroller.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        prompt_list_scroller.set_min_content_width(240)
        prompt_list_scroller.set_child(prompt_list)

        prompt_stack = Gtk.Stack()
        prompt_stack.set_hexpand(True)
        prompt_stack.set_vexpand(True)
        prompt_stack.set_transition_type(Gtk.StackTransitionType.SLIDE_LEFT_RIGHT)
        self._prompt_stack = prompt_stack

        prompt_definitions = [
            ("profiles", "Model Profiles", self._build_model_profiles_page),
            ("page", "Single Page Summarization", self._build_summarization_prompt_page),
            ("range", "Page Range Summarization", self._build_summarization_prompt_page),
            ("extract", "Extract Information", self._build_summarization_prompt_page),
            ("rag", "RAG Answer Prompt", self._build_rag_prompt_page),
            ("agent", "Agent", self._build_agent_settings_page),
        ]
        first_row: Gtk.ListBoxRow | None = None
        for key, title, builder in prompt_definitions:
            row = Gtk.ListBoxRow()
            row_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
            row_box.set_margin_top(8)
            row_box.set_margin_bottom(8)
            row_box.set_margin_start(12)
            row_box.set_margin_end(12)
            label = Gtk.Label(label=title, xalign=0)
            row_box.append(label)
            row.set_child(row_box)
            prompt_list.append(row)
            self._prompt_row_keys[row] = key
            if first_row is None:
                first_row = row

            page = builder(key, title)
            prompt_stack.add_named(page, key)

        if first_row is not None:
            prompt_stack.set_visible_child_name(self._prompt_row_keys[first_row])

            def _select_first_prompt_row() -> bool:
                if first_row.get_parent() is prompt_list:
                    prompt_list.select_row(first_row)
                return False

            GLib.idle_add(_select_first_prompt_row)

        split.set_start_child(prompt_list_scroller)
        split.set_end_child(prompt_stack)
        box.append(split)

        scrolled = Gtk.ScrolledWindow()
        scrolled.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        scrolled.set_hexpand(True)
        scrolled.set_vexpand(True)
        scrolled.set_child(box)

        self._toast_overlay = Adw.ToastOverlay()
        self._toast_overlay.set_child(scrolled)
        view.set_content(self._toast_overlay)
        self.set_content(view)

    def _build_password_row(self, title: str) -> Adw.EntryRow:
        password_row_cls = getattr(Adw, "PasswordEntryRow", None)
        if password_row_cls:
            row = password_row_cls(title=title)
            if hasattr(row, "set_show_peek_icon"):
                row.set_show_peek_icon(True)
        else:
            row = Adw.EntryRow(title=title)
            if hasattr(row, "set_input_purpose"):
                row.set_input_purpose(Gtk.InputPurpose.PASSWORD)
            if hasattr(row, "set_visibility"):
                try:
                    row.set_visibility(False)
                except Exception:
                    pass
        if hasattr(row, "set_hexpand"):
            row.set_hexpand(True)
        return row

    def _profile_dropdown_model(self, *, include_legacy: bool = True) -> Gtk.StringList:
        labels = [profile.display_name() for profile in self._model_profiles]
        if include_legacy:
            labels = [UNSET_PROFILE_LABEL, *labels]
        return Gtk.StringList.new(labels)

    def _profile_dropdown_selected_index(
        self,
        settings: AiSettings,
        task_key: str,
        *,
        include_legacy: bool = True,
    ) -> int:
        selected_key = settings.task_profile_defaults.get(task_key)
        if selected_key in MODEL_PROFILE_IDS:
            selected_index = MODEL_PROFILE_IDS.index(selected_key)
            return selected_index + 1 if include_legacy else selected_index
        return 0

    def _profile_key_from_dropdown(
        self,
        dropdown: Gtk.DropDown,
        *,
        include_legacy: bool = True,
    ) -> str | None:
        selected = int(dropdown.get_selected())
        if include_legacy:
            selected -= 1
        if 0 <= selected < len(MODEL_PROFILE_IDS):
            return MODEL_PROFILE_IDS[selected]
        return None

    def _build_profile_dropdown(self, settings: AiSettings, task_key: str) -> Gtk.DropDown:
        dropdown = Gtk.DropDown(model=self._profile_dropdown_model())
        dropdown.set_selected(self._profile_dropdown_selected_index(settings, task_key))
        dropdown.set_hexpand(False)
        return dropdown

    def _build_model_profiles_page(self, _key: str, title: str) -> Gtk.Widget:
        page_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        page_box.set_margin_top(12)
        page_box.set_margin_bottom(12)
        page_box.set_margin_start(12)
        page_box.set_margin_end(12)
        page_box.set_vexpand(True)

        title_label = Gtk.Label(label=title, xalign=0)
        title_label.add_css_class("title-3")
        page_box.append(title_label)

        info_label = Gtk.Label(
            label=(
                "Set up four shared LLM profiles. Prompt pages choose one of these profiles "
                "as their default model."
            ),
            xalign=0,
        )
        info_label.add_css_class("dim-label")
        info_label.set_wrap(True)
        info_label.set_wrap_mode(Pango.WrapMode.WORD_CHAR)
        page_box.append(info_label)

        self._model_profile_editors = {}
        for profile in self._model_profiles:
            group = Adw.PreferencesGroup(title=profile.display_name())
            group.add_css_class("list-stack")
            group.set_hexpand(True)

            nickname_row = Adw.EntryRow(title="Nickname")
            nickname_row.set_text(profile.display_name())
            group.add(nickname_row)

            abbreviation_row = Adw.EntryRow(title="Abbreviation (optional)")
            abbreviation_row.set_text(profile.abbreviation)
            group.add(abbreviation_row)

            api_url_row = Adw.EntryRow(title="API URL")
            api_url_row.set_text(profile.api_url)
            group.add(api_url_row)

            model_row = Adw.EntryRow(title="Model ID")
            model_row.set_text(profile.model_id)
            group.add(model_row)

            api_key_row = self._build_password_row("API Key")
            api_key_row.set_text(profile.api_key)
            group.add(api_key_row)

            disable_reasoning_row = Adw.SwitchRow(title="Disable reasoning")
            disable_reasoning_row.set_active(bool(profile.disable_reasoning))
            group.add(disable_reasoning_row)

            priority_service_tier_row = Adw.SwitchRow(title="Priority")
            priority_service_tier_row.set_active(bool(profile.priority_service_tier))
            group.add(priority_service_tier_row)

            self._model_profile_editors[profile.key] = ModelProfileEditorWidgets(
                nickname_row=nickname_row,
                abbreviation_row=abbreviation_row,
                api_url_row=api_url_row,
                model_row=model_row,
                api_key_row=api_key_row,
                disable_reasoning_row=disable_reasoning_row,
                priority_service_tier_row=priority_service_tier_row,
            )
            page_box.append(group)

        page = Gtk.ScrolledWindow()
        page.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        page.set_hexpand(True)
        page.set_vexpand(True)
        page.set_child(page_box)
        return page

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

    def _build_prompt_editor(self, text: str) -> tuple[Gtk.ScrolledWindow, Gtk.TextBuffer]:
        scroller = Gtk.ScrolledWindow()
        scroller.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.AUTOMATIC)
        scroller.set_hexpand(True)
        scroller.set_vexpand(True)
        scroller.set_has_frame(False)

        buffer = Gtk.TextBuffer()
        buffer.set_text(text)
        prompt_view = Gtk.TextView.new_with_buffer(buffer)
        prompt_view.set_wrap_mode(Gtk.WrapMode.WORD_CHAR)
        prompt_view.set_monospace(True)
        prompt_view.set_vexpand(True)
        prompt_view.set_hexpand(True)
        prompt_view.set_top_margin(12)
        prompt_view.set_bottom_margin(12)
        prompt_view.set_left_margin(12)
        prompt_view.set_right_margin(12)
        scroller.set_child(prompt_view)
        return scroller, buffer

    def _build_summarization_prompt_page(self, key: str, title: str) -> Gtk.Widget:
        page_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        page_box.set_margin_top(12)
        page_box.set_margin_bottom(12)
        page_box.set_margin_start(12)
        page_box.set_margin_end(12)
        page_box.set_vexpand(True)

        title_label = Gtk.Label(label=title, xalign=0)
        title_label.add_css_class("title-3")
        page_box.append(title_label)

        settings = load_ai_settings()
        profile_group = Adw.PreferencesGroup(title="Default Model Profile")
        profile_group.add_css_class("list-stack")
        profile_group.set_hexpand(True)
        page_box.append(profile_group)

        profile_row = Adw.ActionRow(
            title="Profile",
            subtitle="Uses the selected profile's API URL, model, API key, and reasoning setting.",
        )
        profile_row.set_activatable(False)
        task_key = key if key in TASK_PROFILE_KEYS else TASK_PROFILE_PAGE
        profile_dropdown = self._build_profile_dropdown(settings, task_key)
        profile_row.add_suffix(profile_dropdown)
        profile_row.set_activatable_widget(profile_dropdown)
        profile_group.add(profile_row)

        prompt_section = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        prompt_section.set_hexpand(True)
        prompt_section.set_vexpand(True)
        prompt_label = Gtk.Label(label="Prompt", xalign=0)
        prompt_label.add_css_class("dim-label")
        prompt_section.append(prompt_label)
        default_prompt = DEFAULT_EXTRACT_PROMPT if key == "extract" else DEFAULT_SUMMARIZATION_PROMPT
        prompt_scroller, buffer = self._build_prompt_editor(default_prompt)
        prompt_section.append(prompt_scroller)
        page_box.append(prompt_section)

        page = Gtk.ScrolledWindow()
        page.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        page.set_hexpand(True)
        page.set_vexpand(True)
        page.set_child(page_box)

        self._prompt_editors[key] = SummarizationPromptWidgets(
            profile_dropdown=profile_dropdown,
            prompt_buffer=buffer,
        )
        return page

    def _build_rag_prompt_page(self, key: str, title: str) -> Gtk.Widget:
        page_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        page_box.set_margin_top(12)
        page_box.set_margin_bottom(12)
        page_box.set_margin_start(12)
        page_box.set_margin_end(12)
        page_box.set_vexpand(True)

        title_label = Gtk.Label(label=title, xalign=0)
        title_label.add_css_class("title-3")
        page_box.append(title_label)

        settings = load_ai_settings()
        rag_group = Adw.PreferencesGroup(title="Default Model Profile")
        rag_group.add_css_class("list-stack")
        rag_group.set_hexpand(True)
        page_box.append(rag_group)

        rag_profile_row = Adw.ActionRow(
            title="RAG Answer",
            subtitle="Uses the selected profile as the default model for RAG answers.",
        )
        rag_profile_row.set_activatable(False)
        rag_profile_dropdown = self._build_profile_dropdown(settings, TASK_PROFILE_RAG)
        rag_profile_row.add_suffix(rag_profile_dropdown)
        rag_profile_row.set_activatable_widget(rag_profile_dropdown)
        rag_group.add(rag_profile_row)

        provider_group = Adw.PreferencesGroup(title="Embedding Provider")
        provider_group.add_css_class("list-stack")
        provider_group.set_hexpand(True)
        page_box.append(provider_group)

        provider_values = [RAG_PROVIDER_VOYAGE, RAG_PROVIDER_ISAACUS]
        provider_labels = ["VoyageAI", "Isaacus"]
        provider_row = Adw.ComboRow(title="Provider")
        provider_row.set_model(Gtk.StringList.new(provider_labels))
        provider_group.add(provider_row)

        rag_context_group = Adw.PreferencesGroup(title="RAG Context")
        rag_context_group.add_css_class("list-stack")
        rag_context_group.set_hexpand(True)
        page_box.append(rag_context_group)

        rag_chunk_adjustment = Gtk.Adjustment(
            value=DEFAULT_RAG_CHUNK_COUNT,
            lower=1,
            upper=50,
            step_increment=1,
            page_increment=2,
        )
        rag_chunk_row = Adw.SpinRow(
            title="Context Chunks",
            adjustment=rag_chunk_adjustment,
        )
        rag_chunk_row.set_digits(0)
        rag_context_group.add(rag_chunk_row)

        speech_rag_source_row = Adw.EntryRow(title="Speech-to-text question file")
        speech_rag_source_row.set_hexpand(True)
        choose_speech_rag_btn = Gtk.Button(label="Choose")
        choose_speech_rag_btn.add_css_class("flat")
        choose_speech_rag_btn.connect("clicked", self._on_choose_speech_rag_source_file)
        speech_rag_source_row.add_suffix(choose_speech_rag_btn)
        clear_speech_rag_btn = Gtk.Button(label="Clear")
        clear_speech_rag_btn.add_css_class("flat")
        clear_speech_rag_btn.connect("clicked", self._on_clear_speech_rag_source_file)
        speech_rag_source_row.add_suffix(clear_speech_rag_btn)
        rag_context_group.add(speech_rag_source_row)

        voyage_group = Adw.PreferencesGroup(title="Voyage Embeddings")
        voyage_group.add_css_class("list-stack")
        voyage_group.set_hexpand(True)
        page_box.append(voyage_group)

        voyage_model_row = Adw.EntryRow(title="Voyage Embedding Model")
        voyage_model_row.set_hexpand(True)
        voyage_group.add(voyage_model_row)

        voyage_key_row = self._build_password_row("Voyage API Key")
        voyage_group.add(voyage_key_row)

        isaacus_group = Adw.PreferencesGroup(title="Isaacus Embeddings")
        isaacus_group.add_css_class("list-stack")
        isaacus_group.set_hexpand(True)
        page_box.append(isaacus_group)

        isaacus_model_row = Adw.EntryRow(title="Isaacus Embedding Model")
        isaacus_model_row.set_hexpand(True)
        isaacus_group.add(isaacus_model_row)

        isaacus_key_row = self._build_password_row("Isaacus API Key")
        isaacus_group.add(isaacus_key_row)

        prompt_section = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        prompt_section.set_hexpand(True)
        prompt_section.set_vexpand(True)
        prompt_label = Gtk.Label(label="Prompt", xalign=0)
        prompt_label.add_css_class("dim-label")
        prompt_section.append(prompt_label)
        prompt_scroller, buffer = self._build_prompt_editor(DEFAULT_RAG_PROMPT)
        prompt_section.append(prompt_scroller)
        page_box.append(prompt_section)

        page = Gtk.ScrolledWindow()
        page.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        page.set_hexpand(True)
        page.set_vexpand(True)
        page.set_child(page_box)

        self._prompt_editors[key] = RagPromptWidgets(
            profile_dropdown=rag_profile_dropdown,
            provider_row=provider_row,
            provider_values=provider_values,
            voyage_model_row=voyage_model_row,
            voyage_key_row=voyage_key_row,
            isaacus_model_row=isaacus_model_row,
            isaacus_key_row=isaacus_key_row,
            rag_chunk_row=rag_chunk_row,
            speech_rag_source_row=speech_rag_source_row,
            prompt_buffer=buffer,
        )
        return page

    def _build_agent_settings_page(self, key: str, title: str) -> Gtk.Widget:
        page_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        page_box.set_margin_top(12)
        page_box.set_margin_bottom(12)
        page_box.set_margin_start(12)
        page_box.set_margin_end(12)
        page_box.set_vexpand(True)

        title_label = Gtk.Label(label=title, xalign=0)
        title_label.add_css_class("title-3")
        page_box.append(title_label)

        launch_group = Adw.PreferencesGroup(
            title="PI Agent",
            description="PI must be installed to answer Agent questions.",
        )
        launch_group.add_css_class("list-stack")
        launch_group.set_hexpand(True)
        page_box.append(launch_group)

        pi_agent_command_row = Adw.EntryRow(title="PI command")
        pi_agent_command_row.set_hexpand(True)
        launch_group.add(pi_agent_command_row)

        pi_configuration_row = Adw.ActionRow(
            title="PI configuration",
            subtitle=(
                "The project .pi/settings.json pins the provider and model; "
                "authentication remains in your global PI configuration."
            ),
        )
        launch_group.add(pi_configuration_row)

        pi_access_row = Adw.ActionRow(
            title="PI access",
            subtitle=(
                "Focus enables read-oriented PI tools plus bash for the "
                "citation helper; the project skill prohibits case-file writes."
            ),
        )
        warning_icon = Gtk.Image.new_from_icon_name("dialog-warning-symbolic")
        warning_icon.add_css_class("warning")
        pi_access_row.add_prefix(warning_icon)
        launch_group.add(pi_access_row)

        page = Gtk.ScrolledWindow()
        page.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        page.set_hexpand(True)
        page.set_vexpand(True)
        page.set_child(page_box)

        self._prompt_editors[key] = AgentSettingsWidgets(
            pi_agent_command_row=pi_agent_command_row,
        )
        return page

    def _on_prompt_row_selected(self, _listbox: Gtk.ListBox, row: Gtk.ListBoxRow | None) -> None:
        if not row or not self._prompt_stack:
            return
        key = self._prompt_row_keys.get(row)
        if key:
            self._prompt_stack.set_visible_child_name(key)

    def _prompt_text(self, buffer: Gtk.TextBuffer) -> str:
        start, end = buffer.get_bounds()
        return buffer.get_text(start, end, True)

    def _on_choose_speech_rag_source_file(self, _button: Gtk.Button) -> None:
        rag_widgets = self._prompt_editors.get("rag")
        if not isinstance(rag_widgets, RagPromptWidgets):
            return
        dialog = Gtk.FileDialog()
        dialog.set_title("Select Speech-to-Text Question File")
        dialog.set_modal(True)
        raw_path = rag_widgets.speech_rag_source_row.get_text().strip()
        if raw_path:
            current_path = Path(raw_path).expanduser()
            initial_folder = current_path.parent if current_path.parent.exists() else None
            if initial_folder is not None:
                try:
                    dialog.set_initial_folder(Gio.File.new_for_path(str(initial_folder)))
                except (TypeError, AttributeError):
                    pass
        dialog.open(self, None, self._on_speech_rag_source_file_chosen)
        self._speech_rag_source_dialog = dialog

    def _on_speech_rag_source_file_chosen(
        self,
        dialog: Gtk.FileDialog,
        result: Gio.AsyncResult,
    ) -> None:
        try:
            file = dialog.open_finish(result)
        except GLib.Error as exc:
            if not exc.matches(Gio.io_error_quark(), Gio.IOErrorEnum.CANCELLED):
                self._show_status_toast(f"File selection failed: {exc.message}")
        else:
            path_str = file.get_path() if file else None
            if path_str:
                rag_widgets = self._prompt_editors.get("rag")
                if isinstance(rag_widgets, RagPromptWidgets):
                    rag_widgets.speech_rag_source_row.set_text(path_str)
        if self._speech_rag_source_dialog is dialog:
            self._speech_rag_source_dialog = None

    def _on_clear_speech_rag_source_file(self, _button: Gtk.Button) -> None:
        rag_widgets = self._prompt_editors.get("rag")
        if isinstance(rag_widgets, RagPromptWidgets):
            rag_widgets.speech_rag_source_row.set_text("")

    def _load_settings(self) -> None:
        settings = load_ai_settings()
        page_widgets = self._prompt_editors.get("page")
        range_widgets = self._prompt_editors.get("range")
        extract_widgets = self._prompt_editors.get("extract")
        rag_widgets = self._prompt_editors.get("rag")
        agent_widgets = self._prompt_editors.get("agent")

        if isinstance(page_widgets, SummarizationPromptWidgets):
            page_widgets.profile_dropdown.set_model(self._profile_dropdown_model())
            page_widgets.profile_dropdown.set_selected(
                self._profile_dropdown_selected_index(settings, TASK_PROFILE_PAGE)
            )
            page_widgets.prompt_buffer.set_text(settings.page_prompt or DEFAULT_SUMMARIZATION_PROMPT)

        if isinstance(range_widgets, SummarizationPromptWidgets):
            range_widgets.profile_dropdown.set_model(self._profile_dropdown_model())
            range_widgets.profile_dropdown.set_selected(
                self._profile_dropdown_selected_index(settings, TASK_PROFILE_RANGE)
            )
            range_widgets.prompt_buffer.set_text(settings.range_prompt or DEFAULT_SUMMARIZATION_PROMPT)

        if isinstance(extract_widgets, SummarizationPromptWidgets):
            extract_widgets.profile_dropdown.set_model(self._profile_dropdown_model())
            extract_widgets.profile_dropdown.set_selected(
                self._profile_dropdown_selected_index(settings, TASK_PROFILE_EXTRACT)
            )
            extract_widgets.prompt_buffer.set_text(settings.extract_prompt or DEFAULT_EXTRACT_PROMPT)

        if isinstance(rag_widgets, RagPromptWidgets):
            rag_widgets.profile_dropdown.set_model(self._profile_dropdown_model())
            rag_widgets.profile_dropdown.set_selected(
                self._profile_dropdown_selected_index(settings, TASK_PROFILE_RAG)
            )
            provider = _normalize_rag_provider(settings.rag_provider)
            if provider in rag_widgets.provider_values:
                rag_widgets.provider_row.set_selected(rag_widgets.provider_values.index(provider))
            else:
                rag_widgets.provider_row.set_selected(0)
            rag_widgets.voyage_model_row.set_text(settings.voyage_model)
            rag_widgets.voyage_key_row.set_text(settings.voyage_api_key)
            rag_widgets.isaacus_model_row.set_text(settings.isaacus_model)
            rag_widgets.isaacus_key_row.set_text(settings.isaacus_api_key)
            rag_widgets.rag_chunk_row.set_value(float(settings.rag_chunk_count))
            rag_widgets.speech_rag_source_row.set_text(settings.speech_rag_source_file)
            rag_widgets.prompt_buffer.set_text(settings.rag_prompt or DEFAULT_RAG_PROMPT)

        if isinstance(agent_widgets, AgentSettingsWidgets):
            agent_widgets.pi_agent_command_row.set_text(settings.pi_agent_command)

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
        page_widgets = self._prompt_editors.get("page")
        range_widgets = self._prompt_editors.get("range")
        extract_widgets = self._prompt_editors.get("extract")
        rag_widgets = self._prompt_editors.get("rag")
        agent_widgets = self._prompt_editors.get("agent")
        if not isinstance(page_widgets, SummarizationPromptWidgets):
            return
        if not isinstance(range_widgets, SummarizationPromptWidgets):
            return
        if not isinstance(extract_widgets, SummarizationPromptWidgets):
            return
        if not isinstance(rag_widgets, RagPromptWidgets):
            return
        if not isinstance(agent_widgets, AgentSettingsWidgets):
            return

        current_settings = load_ai_settings()
        model_profiles: list[ModelProfile] = []
        for profile_key in MODEL_PROFILE_IDS:
            widgets = self._model_profile_editors.get(profile_key)
            if widgets is None:
                existing = current_settings.profile_by_key(profile_key)
                if existing is not None:
                    model_profiles.append(existing)
                continue
            model_profiles.append(
                ModelProfile(
                    key=profile_key,
                    nickname=(
                        widgets.nickname_row.get_text().strip()
                        or DEFAULT_MODEL_PROFILE_NICKNAMES[profile_key]
                    ),
                    abbreviation=widgets.abbreviation_row.get_text().strip(),
                    api_url=widgets.api_url_row.get_text().strip(),
                    model_id=widgets.model_row.get_text().strip(),
                    api_key=widgets.api_key_row.get_text().strip(),
                    disable_reasoning=bool(widgets.disable_reasoning_row.get_active()),
                    priority_service_tier=bool(widgets.priority_service_tier_row.get_active()),
                )
            )
        task_profile_defaults = {
            TASK_PROFILE_PAGE: self._profile_key_from_dropdown(page_widgets.profile_dropdown),
            TASK_PROFILE_RANGE: self._profile_key_from_dropdown(range_widgets.profile_dropdown),
            TASK_PROFILE_EXTRACT: self._profile_key_from_dropdown(extract_widgets.profile_dropdown),
            TASK_PROFILE_RAG: self._profile_key_from_dropdown(rag_widgets.profile_dropdown),
        }
        provider_index = int(rag_widgets.provider_row.get_selected())
        if 0 <= provider_index < len(rag_widgets.provider_values):
            rag_provider = rag_widgets.provider_values[provider_index]
        else:
            rag_provider = DEFAULT_RAG_PROVIDER
        voyage_model = rag_widgets.voyage_model_row.get_text().strip()
        voyage_key = rag_widgets.voyage_key_row.get_text().strip()
        isaacus_model = rag_widgets.isaacus_model_row.get_text().strip()
        isaacus_key = rag_widgets.isaacus_key_row.get_text().strip()
        rag_chunk_count = _coerce_rag_chunk_count(
            int(round(rag_widgets.rag_chunk_row.get_value())),
            DEFAULT_RAG_CHUNK_COUNT,
        )
        speech_rag_source_file = rag_widgets.speech_rag_source_row.get_text()
        pi_agent_command = agent_widgets.pi_agent_command_row.get_text().strip()

        page_prompt = self._prompt_text(page_widgets.prompt_buffer).strip()
        range_prompt = self._prompt_text(range_widgets.prompt_buffer).strip()
        extract_prompt = self._prompt_text(extract_widgets.prompt_buffer).strip()
        rag_prompt = self._prompt_text(rag_widgets.prompt_buffer).strip()
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
            api_url=current_settings.api_url,
            model_id=current_settings.model_id,
            api_key=current_settings.api_key,
            page_api_url=current_settings.page_api_url,
            page_model_id=current_settings.page_model_id,
            page_api_key=current_settings.page_api_key,
            range_api_url=current_settings.range_api_url,
            range_model_id=current_settings.range_model_id,
            range_api_key=current_settings.range_api_key,
            extract_api_url=current_settings.extract_api_url,
            extract_model_id=current_settings.extract_model_id,
            extract_api_key=current_settings.extract_api_key,
            page_disable_reasoning=current_settings.page_disable_reasoning,
            range_disable_reasoning=current_settings.range_disable_reasoning,
            extract_disable_reasoning=current_settings.extract_disable_reasoning,
            page_prompt=page_prompt or DEFAULT_SUMMARIZATION_PROMPT,
            range_prompt=range_prompt or DEFAULT_SUMMARIZATION_PROMPT,
            extract_prompt=extract_prompt or DEFAULT_EXTRACT_PROMPT,
            rag_provider=rag_provider,
            voyage_api_key=voyage_key,
            voyage_model=voyage_model or DEFAULT_RAG_VOYAGE_MODEL,
            isaacus_api_key=isaacus_key,
            isaacus_model=isaacus_model or DEFAULT_RAG_ISAACUS_MODEL,
            rag_llm_model=current_settings.rag_llm_model,
            rag_deep_llm_model=current_settings.rag_deep_llm_model,
            rag_prompt=rag_prompt or DEFAULT_RAG_PROMPT,
            rag_api_url=current_settings.rag_api_url,
            rag_api_key=current_settings.rag_api_key,
            rag_deep_api_url=current_settings.rag_deep_api_url,
            rag_deep_api_key=current_settings.rag_deep_api_key,
            rag_disable_reasoning=current_settings.rag_disable_reasoning,
            rag_deep_disable_reasoning=current_settings.rag_deep_disable_reasoning,
            rag_chunk_count=rag_chunk_count,
            speech_rag_source_file=speech_rag_source_file,
            pi_agent_command=pi_agent_command or DEFAULT_PI_AGENT_COMMAND,
            highlight_phrases=highlight_phrases,
            grep_highlight_color=grep_highlight_color,
            phrase_highlight_color=phrase_highlight_color,
            summary_emphasis_color=summary_emphasis_color,
            search_chip_color=search_chip_color,
            model_profiles=model_profiles,
            task_profile_defaults=task_profile_defaults,
        )
        save_ai_settings(settings)
        self.app.update_font_sizes(
            font_size_pt=record_font_size,
            ai_font_size_pt=ai_font_size,
            table_font_size_pt=table_font_size,
            record_font_family_name=record_font_family_name,
        )
        self.app.on_ai_settings_saved(settings)
        if settings.is_configured() and settings.is_rag_ready():
            self._show_status_toast("Saved. Summaries and RAG questions are enabled.")
        elif settings.is_configured():
            self._show_status_toast(
                "Saved. Add RAG API URL, embedding provider credentials, and RAG fields "
                "to enable questions."
            )
        else:
            self._show_status_toast("Saved. Add required fields to enable summaries.")
