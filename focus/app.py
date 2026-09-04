from __future__ import annotations

from pathlib import Path
import sys

from .core import *  # noqa: F401,F403
from .summary_editions import (
    SummaryEdition,
    SummaryEditionError,
    find_page_for_source_line,
    load_summary_edition,
    render_page_text,
    search_pages,
    with_paragraph_spacing,
)
from .agent_answer import (
    create_focus_run_id,
    focus_answer_artifact_path,
    focus_answer_runtime_dir,
    focus_answer_status_message,
    read_focus_answer_artifact,
    remove_focus_answer_artifact,
)
from .agent_trace import (
    TraceSnapshotError,
    find_latest_pi_session_log_for_cwd,
    focus_preserved_session_path,
    focus_session_preserve_dir,
    reasoning_trace_path,
    snapshot_pi_session_jsonl,
    trace_clipboard_text,
)
from .ui.commands import FocusCommandsWindow
from .ui.settings import AiSettingsWindow


CASE_TOOL_DESCRIPTIONS = {
    AI_VIEW_AGENT_QA: "Ask record-grounded questions across the original record.",
    AI_VIEW_SUMMARIZE: "Summarize a page or citation range with the selected model profile.",
    AI_VIEW_EXTRACT: "Extract structured information from the current page or a page range.",
}
SUMMARY_SOURCE_DESCRIPTIONS = {
    SUMMARY_SOURCE_HEARING: "Browse prepared hearing summaries; verify material points in the record.",
    SUMMARY_SOURCE_REPORTS: "Browse prepared report summaries; verify material points in the record.",
    SUMMARY_SOURCE_MINUTES: "Browse prepared minute-order summaries; verify material points in the record.",
}


class Focus(Adw.Application):
    def __init__(self, *, input_override: Path | None = None) -> None:
        super().__init__(
            application_id=APPLICATION_ID,
            flags=Gio.ApplicationFlags.FLAGS_NONE,
        )
        try:
            style_manager = Adw.StyleManager.get_default()
            style_manager.set_color_scheme(Adw.ColorScheme.DEFAULT)
            style_manager.connect("notify::color-scheme", self._on_color_scheme_changed)
            style_manager.connect("notify::dark", self._on_color_scheme_changed)
        except Exception:
            pass
        self.connect("activate", self.on_activate)
        prune_deprecated_summary_bookmarking_config()

        if input_override is not None:
            self.input_dir = input_override
        else:
            self.input_dir = load_input_dir_from_config()
        self._record_layout = _resolve_record_layout(self.input_dir)
        self._case_name = _read_case_name(self._record_layout.root)
        self._font_size_pt, self._ai_font_size_pt, self._table_font_size_pt = load_font_preferences()
        self._record_font_family_name = load_record_font_family_name()
        self._record_font_family_css = _record_font_css_for_name(self._record_font_family_name)

        self.pages: list[int] = []
        self.page_to_path: dict[int, Path] = {}
        self._transcript_page_index = TranscriptPageIndex({}, {}, {})
        self._hearing_boundaries: tuple[RecordBoundary, ...] = ()
        self._minute_boundaries: tuple[RecordBoundary, ...] = ()
        self._minute_order_return_page: int | None = None
        self._minute_order_return_boundary: RecordBoundary | None = None
        self.current_index: int = 0

        self.win: Adw.ApplicationWindow | None = None
        self._transcript_breakdown_window: Adw.ApplicationWindow | None = None
        self._transcript_breakdown_buffer: Gtk.TextBuffer | None = None
        self._shortcuts_window: Gtk.ShortcutsWindow | None = None
        self._commands_window: FocusCommandsWindow | None = None
        self._input_dir_dialog: Gtk.FileDialog | None = None
        self.textview: Gtk.TextView | None = None
        self.scroller: Gtk.ScrolledWindow | None = None
        self._text_mode_box: Gtk.Box | None = None
        self._text_scroll_overlay: Gtk.Overlay | None = None
        self._right_scroll_zone: Gtk.Button | None = None
        self._right_scroll_zone_scroll_controller: Gtk.EventControllerScroll | None = None
        self._right_scroll_active = False
        self._image_preview_rail: Gtk.Box | None = None
        self._image_preview_button: Gtk.Button | None = None
        self._image_preview_picture: Gtk.Picture | None = None
        self._grep_entry: Gtk.SearchEntry | None = None
        self._grep_entry_sync_guard = False
        self._title_widget: Adw.WindowTitle | None = None
        self._split_view: Adw.NavigationSplitView | None = None
        self._toc_sidebar_revealer: Gtk.Revealer | None = None
        self._toc_sidebar_overlay: Gtk.Overlay | None = None
        self._toc_sidebar_scroller: Gtk.ScrolledWindow | None = None
        self._toc_list_view: Gtk.ListBox | None = None
        self._toc_sidebar_root_store: Gio.ListStore | None = None
        self._toc_sidebar_tree_model: Gtk.TreeListModel | None = None
        self._toc_sidebar_button: Gtk.ToggleButton | None = None
        self._toc_sidebar_action: Gio.SimpleAction | None = None
        self._toc_sidebar_icon: Gtk.Image | None = None
        self._split_content_page: Adw.NavigationPage | None = None
        self._split_sidebar_page: Adw.NavigationPage | None = None
        self._toc_placeholder: Gtk.Widget | None = None
        self._toc_sidebar_has_items = False
        self._toc_sidebar_visible = True
        self._sidebar_button_guard = False
        self._current_text_color = DEFAULT_TEXT_COLOR

        self._color_provider = Gtk.CssProvider()
        self._css_provider_registered = False

        self._page_back_one_button: Gtk.Button | None = None
        self._page_forward_one_button: Gtk.Button | None = None
        self._record_boundary_date_label: Gtk.Label | None = None
        self._page_number_entry: Gtk.Entry | None = None
        self._page_jump_popover: Gtk.Popover | None = None
        self._page_total_label: Gtk.Label | None = None
        self._show_transcript_breakdown_action: Gio.SimpleAction | None = None
        self._minute_order_button: Gtk.Button | None = None
        self._current_page_citation_button: Gtk.Button | None = None
        self._page_citation_range_button: Gtk.Button | None = None
        self._page_citation_range_start: TranscriptPageLabel | None = None
        self._grep_prev_hit_button: Gtk.Button | None = None
        self._grep_next_hit_button: Gtk.Button | None = None
        self._grep_hit_label: Gtk.Label | None = None
        self._grep_highlighted_button: Gtk.Button | None = None

        self._grep_phrase_raw: str | None = None
        self._grep_regex: re.Pattern[str] | None = None
        self._grep_active = False
        self._grep_hits: dict[int, list[tuple[int, int]]] = {}
        self._matching_pages: list[int] = []
        self._matching_lookup: dict[int, int] = {}
        self._grep_match_order: list[tuple[int, int]] = []
        self._grep_current_match_index = -1
        self._grep_search_thread: threading.Thread | None = None
        self._grep_search_cancel_event: threading.Event | None = None
        self._grep_search_generation = 0

        self._page_cache: dict[int, str] = {}
        self._page_search_cache: dict[int, str] = {}
        self._page_search_map_cache: dict[int, list[int]] = {}
        self._link_tags: list[Gtk.TextTag] = []
        self._link_tag_lookup: dict[Gtk.TextTag, tuple[str, str]] = {}
        self._ai_outputs: dict[str, AiOutputView] = {
            AI_VIEW_SUMMARIZE: AiOutputView(),
            AI_VIEW_EXTRACT: AiOutputView(),
            AI_VIEW_AGENT_QA: AiOutputView(),
        }
        self._ai_active_view = AI_VIEW_AGENT_QA
        self._textview_click_gesture: Gtk.GestureClick | None = None
        self._textview_focus_controller: Gtk.EventControllerFocus | None = None
        self._textview_motion_controller: Gtk.EventControllerMotion | None = None
        self._summary_link_tags: list[Gtk.TextTag] = []
        self._summary_link_tag_lookup: dict[Gtk.TextTag, tuple[str, str]] = {}
        self._summary_click_gesture: Gtk.GestureClick | None = None
        self._summary_focus_controller: Gtk.EventControllerFocus | None = None
        self._summary_motion_controller: Gtk.EventControllerMotion | None = None
        self._summary_search_entry: Gtk.SearchEntry | None = None
        self._summary_search_query = ""
        self._summary_search_matches: list[tuple[int, ...]] = []
        self._summary_search_index = -1
        self._summary_search_tag: Gtk.TextTag | None = None
        self._summary_search_current_tag: Gtk.TextTag | None = None
        self._summary_view: Gtk.TextView | None = None
        self._summary_buffer: Gtk.TextBuffer | None = None
        self._summary_scroller: Gtk.ScrolledWindow | None = None
        self._summary_loaded_path: Path | None = None
        self._summary_raw = ""
        self._auto_loading_summary = False
        self._summary_scroll_handler_id: int | None = None
        self._summary_scroll_restore_guard = False
        self._summary_pending_restore_fraction: float | None = None
        self._summary_scroll_restore_source_id: int | None = None
        self._summary_scroll_restore_geometry: tuple[float, float, float] | None = None
        self._summary_scroll_restore_stable_passes = 0
        self._summary_scroll_restore_attempts = 0
        self._summary_active_source: str | None = None
        self._summary_progress_label: Gtk.Label | None = None
        self._summary_edition: SummaryEdition | None = None
        self._summary_edition_page = 1
        self._summary_page_entry: Gtk.Entry | None = None
        self._summary_page_total_label: Gtk.Label | None = None
        self._summary_prev_page_button: Gtk.Button | None = None
        self._summary_next_page_button: Gtk.Button | None = None
        self._summary_open_pdf_button: Gtk.Button | None = None
        self._summary_source_buttons: dict[str, Gtk.ToggleButton] = {}
        self._more_case_tools_button: Gtk.MenuButton | None = None
        self._summary_bookmark_action_button: Gtk.Button | None = None
        self._summary_return_bookmark_action_button: Gtk.Button | None = None
        self._edge_flash_source_id: int | None = None
        self._content_overlay: Gtk.Overlay | None = None
        self._content_stack: Gtk.Stack | None = None
        self._main_root: Gtk.Box | None = None
        self._image_scroller: Gtk.ScrolledWindow | None = None
        self._image_picture: Gtk.Picture | None = None
        self._image_fixed: Gtk.Fixed | None = None
        self._image_pixbuf: GdkPixbuf.Pixbuf | None = None
        self._image_scaled_size: tuple[int, int] | None = None
        self._image_tick_id: int | None = None
        self._image_viewport_size: tuple[int, int] | None = None
        self._show_image = False
        self._image_print_window: Adw.ApplicationWindow | None = None
        self._image_print_entry: Gtk.Entry | None = None
        self._image_print_pages: list[int] = []
        self._show_image_action: Gio.SimpleAction | None = None
        self._show_image_button: Gtk.ToggleButton | None = None
        self._show_image_icon: Gtk.Image | None = None
        self._show_image_button_guard = False
        self._image_icon_name_on = IMAGE_ICON_ON_CHOICES[0]
        self._image_icon_name_off = self._image_icon_name_on
        self._toc_categories: list[TocCategory] = []
        self._toc_load_generation = 0
        self._ai_panel_revealer: Gtk.Revealer | None = None
        self._ai_panel_root: Gtk.Widget | None = None
        self._ai_panel_header: Gtk.Widget | None = None
        self._ai_view_stack: Adw.ViewStack | None = None
        self._ai_view_buttons: dict[str, Gtk.ToggleButton] = {}
        self._ai_view_toggle_guard = False
        self._ai_controls_stack: Gtk.Stack | None = None
        self._ai_output_scrollers: list[Gtk.ScrolledWindow] = []
        self._ai_panel_resize_tick_id: int | None = None
        self._ai_panel_layout_idle_id: int | None = None
        self._ai_panel_post_render_tick_id: int | None = None
        self._ai_panel_post_render_frames = 0
        self._last_ai_panel_host_height = -1
        self._ai_status_label: Gtk.Label | None = None
        self._ai_spinner: Gtk.Spinner | None = None
        self._ai_range_start_entry: Gtk.Entry | None = None
        self._ai_range_end_entry: Gtk.Entry | None = None
        self._ai_range_status_label: Gtk.Label | None = None
        self._sum_range_choice_popover: Gtk.Popover | None = None
        self._ai_range_autofilled = True
        self._ai_range_update_guard = False
        self._extract_range_entry: Gtk.Entry | None = None
        self._ai_panel_toggle: Gtk.ToggleButton | None = None
        self._ai_panel_toggle_guard = False
        self._ai_stream_thread: threading.Thread | None = None
        self._ai_cancel_event: threading.Event | None = None
        self._ai_settings_window: AiSettingsWindow | None = None
        self._ai_settings: AiSettings = load_ai_settings()
        self._ai_in_flight = False
        self._ai_request_generation = 0
        self._agent_question_entry: Gtk.Entry | None = None
        self._agent_submit_button: Gtk.Button | None = None
        self._agent_output_header: Gtk.Widget | None = None
        self._agent_subview_host: Gtk.Box | None = None
        self._agent_subview_name = AGENT_SUBVIEW_SESSION
        self._agent_answer_scroller: Gtk.ScrolledWindow | None = None
        self._agent_session_widget: Gtk.Widget | None = None
        self._agent_answer_button: Gtk.ToggleButton | None = None
        self._agent_session_button: Gtk.ToggleButton | None = None
        self._agent_copy_trace_button: Gtk.Button | None = None
        self._agent_subview_toggle_guard = False
        self._agent_answer_poll_id: int | None = None
        self._agent_workspace_path: Path | None = None
        self._agent_session_log_path: Path | None = None
        self._agent_session_preserve_path: Path | None = None
        self._agent_run_id = ""
        self._agent_answer_artifact_path: Path | None = None
        self._agent_answer_revision = 0
        self._agent_answer_diagnostics: dict[str, Any] = {}
        self._agent_answer_status = ""
        self._agent_last_answer_text = ""
        self._agent_terminal: Any | None = None
        self._agent_terminal_pid: int | None = None
        self._agent_terminal_active = False
        self._agent_terminal_closing = False
        self._agent_terminal_ignore_next_exit = False
        self._view_state = FocusViewState()

    @property
    def text_dir(self) -> Path:
        return self._record_layout.text_dir

    @property
    def images_dir(self) -> Path:
        return self._record_layout.images_dir

    @property
    def toc_path(self) -> Path:
        return self._record_layout.toc_path

    @property
    def transcript_page_number_series_path(self) -> Path:
        return self._record_layout.transcript_page_number_series_path

    def _choose_icon(self, *names: str) -> str:
        if not names:
            return ""
        display = self.win.get_display() if self.win else Gdk.Display.get_default()
        theme = Gtk.IconTheme.get_for_display(display) if display else None
        if theme:
            for name in names:
                try:
                    if theme.has_icon(name):
                        return name
                except TypeError:
                    continue
        return names[0]

    def _build_header_icon(self, *icon_names: str) -> Gtk.Image:
        icon = Gtk.Image.new_from_icon_name(self._choose_icon(*icon_names))
        icon.add_css_class("focus-toggle-icon")
        icon.set_valign(Gtk.Align.CENTER)
        return icon

    def _build_labeled_icon(self, label: str, *icon_names: str) -> Gtk.Widget:
        content = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        content.set_valign(Gtk.Align.CENTER)
        if icon_names:
            icon = self._build_header_icon(*icon_names)
            icon.set_pixel_size(16)
            content.append(icon)
        content.append(Gtk.Label(label=label))
        return content

    @staticmethod
    def _set_accessible_label(widget: Gtk.Widget, label: str) -> None:
        try:
            widget.update_property(
                [Gtk.AccessibleProperty.LABEL],
                [label],
            )
        except (AttributeError, TypeError):
            pass

    def _scan_pages(self) -> None:
        self.page_to_path.clear()
        self.pages.clear()
        self._page_cache.clear()
        self._page_search_cache.clear()
        self._page_search_map_cache.clear()
        self._transcript_page_index = load_transcript_page_index(
            self._record_layout.transcript_page_numbers_path
        )
        self._hearing_boundaries = load_record_boundaries(
            self._record_layout.hearing_boundaries_path
        )
        self._minute_boundaries = load_record_boundaries(
            self._record_layout.minutes_boundaries_path
        )
        self._minute_order_return_page = None
        self._minute_order_return_boundary = None
        text_dir = self.text_dir
        if not text_dir.exists():
            return
        for p in text_dir.iterdir():
            if not p.is_file():
                continue
            m = PAGE_RE.match(p.name)
            if m:
                num = int(m.group("num"))
                self.page_to_path[num] = p
        self.pages = sorted(self.page_to_path.keys())
        self._ai_range_autofilled = True
        self._maybe_prefill_sum_range_for_current_page()

    def _current_toc_path(self) -> Path:
        return self.toc_path

    def _load_toc_from_disk_async(self) -> None:
        toc_path = self._current_toc_path()
        self._toc_load_generation += 1
        generation = self._toc_load_generation
        target_dir = self.input_dir

        def worker() -> None:
            text, error = read_toc_text(toc_path)
            GLib.idle_add(self._on_toc_text_loaded, generation, text, error, target_dir)

        threading.Thread(target=worker, daemon=True).start()

    def _on_toc_text_loaded(
        self,
        generation: int,
        text: str,
        error: str | None,
        target_dir: Path,
    ) -> bool:
        if generation != self._toc_load_generation:
            return False
        if target_dir != self.input_dir:
            return False
        if error:
            self._transient_toast(error)
        self._update_toc_from_text(text)
        return False

    def _update_toc_from_text(self, text: str) -> None:
        self._toc_categories = parse_toc_text(text)
        self._rebuild_toc_sidebar()

    def on_toc_text_updated(self, text: str) -> None:
        self._toc_load_generation += 1
        self._update_toc_from_text(text)

    def _nearest_index_for(self, page_num: int) -> int:
        if not self.pages:
            return 0
        pos = bisect.bisect_left(self.pages, page_num)
        if pos == 0:
            return 0
        if pos == len(self.pages):
            return len(self.pages) - 1
        before = self.pages[pos - 1]
        after = self.pages[pos]
        if page_num - before <= after - page_num:
            return pos - 1
        return pos

    def on_activate(self, app: Gio.Application) -> None:  # noqa: ARG002
        self._scan_pages()
        self._ensure_window()
        self._load_toc_from_disk_async()
        if self.pages:
            self.current_index = 0
            self._load_current()
            self._persist_active_view_state()
        else:
            self._set_window_title("No pages found")
            self._set_text("No .txt pages found in:\n" + str(self.text_dir))
        if self.win:
            self.win.present()

    def _ensure_window(self) -> None:
        if self.win:
            return

        self.win = Adw.ApplicationWindow(application=self)
        self.win.add_css_class("focus-window")
        self.win.set_default_size(900, 700)
        self.win.connect("close-request", self._on_main_window_close_request)
        win_display = self.win.get_display()
        if win_display:
            Gtk.StyleContext.add_provider_for_display(
                win_display,
                _chrome_provider,
                Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION,
            )

        toolbar = Adw.ToolbarView()
        self.win.set_content(toolbar)

        header = Adw.HeaderBar()
        header.add_css_class("flat")
        header.add_css_class("focus-header")

        left_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        left_box.set_valign(Gtk.Align.CENTER)

        self._toc_sidebar_button = Gtk.ToggleButton()
        self._toc_sidebar_icon = self._build_header_icon("sidebar-show-symbolic")
        self._toc_sidebar_button.set_child(self._toc_sidebar_icon)
        self._toc_sidebar_button.add_css_class("flat")
        self._toc_sidebar_button.set_tooltip_text("Toggle TOC sidebar (Ctrl+Shift+Z)")
        self._toc_sidebar_button.connect("toggled", self._on_sidebar_toggle_button)
        left_box.append(self._toc_sidebar_button)

        self._ai_panel_toggle = Gtk.ToggleButton()
        self._ai_panel_toggle.add_css_class("flat")
        self._ai_panel_toggle.add_css_class("no-bold")
        self._ai_panel_toggle.add_css_class("focus-view-toggle")
        self._ai_panel_toggle.add_css_class("focus-case-tools-toggle")
        self._ai_panel_toggle.set_valign(Gtk.Align.CENTER)
        self._ai_panel_toggle.set_child(
            self._build_labeled_icon("Case Tools", *CASE_TOOLS_ICON_CHOICES)
        )
        self._ai_panel_toggle.set_tooltip_text("Show case tools (Ctrl+Shift+A)")
        self._set_accessible_label(self._ai_panel_toggle, "Case Tools")
        self._ai_panel_toggle.connect("toggled", self._on_ai_panel_toggled)
        self._set_ai_panel_visible(self._current_view_state().ai_panel_visible)

        header.pack_start(left_box)

        self._title_widget = Adw.WindowTitle(title="Focus")
        header.set_title_widget(self._title_widget)

        # Hamburger menu on the right
        menu_model = Gio.Menu()
        document_menu = Gio.Menu()
        document_menu.append(
            "Transcript Page Breakdown",
            "app.show_transcript_breakdown",
        )
        document_menu.append("Print Images", "app.print_images")
        document_menu.append("Input Directory", "app.choose_input")
        menu_model.append_section(None, document_menu)

        application_menu = Gio.Menu()
        application_menu.append("D-Bus Commands", "app.show_dbus_commands")
        application_menu.append("Settings", "app.open_ai_settings")
        application_menu.append("Keyboard Shortcuts", "app.show_shortcuts")
        menu_model.append_section(None, application_menu)

        menu_button = Gtk.MenuButton(icon_name="open-menu-symbolic")
        menu_button.add_css_class("flat")
        menu_button.set_valign(Gtk.Align.CENTER)
        menu_button.set_popover(Gtk.PopoverMenu.new_from_model(menu_model))

        trailing_header_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        trailing_header_box.set_valign(Gtk.Align.CENTER)
        trailing_header_box.append(self._ai_panel_toggle)
        trailing_header_box.append(menu_button)
        header.pack_end(trailing_header_box)

        # Place headerbar in main window
        toolbar.add_top_bar(header)

        self.textview = Gtk.TextView(editable=False, monospace=False, wrap_mode=Gtk.WrapMode.WORD)
        self.textview.set_hexpand(True)
        self.textview.set_vexpand(True)
        self.textview.set_name("page-text")
        self.textview.set_top_margin(12)
        self.textview.set_bottom_margin(12)
        self.textview.set_left_margin(16)
        self.textview.set_right_margin(16)
        self.textview.set_cursor_visible(False)
        self.textview.get_buffer().connect(
            "notify::has-selection",
            self._on_search_selection_changed,
        )
        self._apply_text_color(DEFAULT_TEXT_COLOR)
        self._install_textview_link_controllers()

        self.scroller = Gtk.ScrolledWindow()
        self.scroller.add_css_class("focus-scroller")
        self.scroller.add_css_class("focus-page-rounded")
        self.scroller.set_hexpand(True)
        self.scroller.set_vexpand(True)
        self.scroller.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.AUTOMATIC)
        self.scroller.set_placement(Gtk.CornerType.TOP_LEFT)
        self.scroller.set_propagate_natural_height(False)
        self.scroller.set_min_content_height(0)
        self.scroller.set_size_request(-1, 0)
        self.scroller.set_child(self.textview)
        self._text_scroll_overlay = Gtk.Overlay()
        self._text_scroll_overlay.set_hexpand(True)
        self._text_scroll_overlay.set_vexpand(True)
        self._text_scroll_overlay.set_child(self.scroller)

        self._right_scroll_zone = Gtk.Button()
        self._right_scroll_zone.add_css_class("flat")
        self._right_scroll_zone.add_css_class("focus-right-scroll-zone")
        self._right_scroll_zone.set_halign(Gtk.Align.FILL)
        self._right_scroll_zone.set_valign(Gtk.Align.FILL)
        self._right_scroll_zone.set_hexpand(True)
        self._right_scroll_zone.set_vexpand(True)
        self._right_scroll_zone.set_margin_start(0)
        self._right_scroll_zone.set_margin_top(RIGHT_SCROLL_ZONE_EDGE_MARGIN)
        self._right_scroll_zone.set_margin_bottom(RIGHT_SCROLL_ZONE_EDGE_MARGIN)
        self._right_scroll_zone.set_margin_end(0)
        self._right_scroll_zone.set_can_target(True)
        self._right_scroll_zone.set_focus_on_click(False)

        right_scroll_hint = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        right_scroll_hint.add_css_class("focus-right-scroll-hint")
        right_scroll_hint.set_halign(Gtk.Align.CENTER)
        right_scroll_hint.set_valign(Gtk.Align.END)
        right_scroll_hint.set_margin_bottom(12)

        right_scroll_icon = Gtk.Image.new_from_icon_name(
            self._choose_icon(
                "input-mouse-symbolic",
                "input-touchpad-symbolic",
                "view-more-symbolic",
            )
        )
        right_scroll_icon.add_css_class("focus-right-scroll-icon")
        right_scroll_icon.set_valign(Gtk.Align.CENTER)
        right_scroll_hint.append(right_scroll_icon)

        right_scroll_label = Gtk.Label(label="Use Mouse Wheel")
        right_scroll_label.add_css_class("focus-right-scroll-label")
        right_scroll_label.set_valign(Gtk.Align.CENTER)
        right_scroll_hint.append(right_scroll_label)
        self._right_scroll_zone.set_child(right_scroll_hint)
        self._right_scroll_zone.connect("clicked", self._on_right_scroll_zone_clicked)

        self._right_scroll_zone_scroll_controller = Gtk.EventControllerScroll.new(
            Gtk.EventControllerScrollFlags.VERTICAL
        )
        self._right_scroll_zone_scroll_controller.set_propagation_phase(Gtk.PropagationPhase.CAPTURE)
        self._right_scroll_zone_scroll_controller.connect("scroll", self._on_right_scroll_zone_scroll)
        self._right_scroll_zone.add_controller(self._right_scroll_zone_scroll_controller)

        self._image_preview_picture = Gtk.Picture()
        self._image_preview_picture.add_css_class("focus-image-preview")
        self._image_preview_picture.set_hexpand(False)
        self._image_preview_picture.set_vexpand(False)
        self._image_preview_picture.set_halign(Gtk.Align.CENTER)
        self._image_preview_picture.set_valign(Gtk.Align.CENTER)
        self._image_preview_picture.set_content_fit(Gtk.ContentFit.CONTAIN)
        self._image_preview_picture.set_can_shrink(True)
        self._image_preview_picture.set_overflow(Gtk.Overflow.HIDDEN)

        self._image_preview_button = Gtk.Button()
        self._image_preview_button.add_css_class("flat")
        self._image_preview_button.add_css_class("focus-image-preview-button")
        self._image_preview_button.set_halign(Gtk.Align.CENTER)
        self._image_preview_button.set_valign(Gtk.Align.START)
        self._image_preview_button.set_focus_on_click(False)
        self._image_preview_button.set_size_request(IMAGE_PREVIEW_RAIL_WIDTH, -1)
        self._image_preview_button.set_child(self._image_preview_picture)
        self._image_preview_button.set_visible(False)
        self._image_preview_button.connect("clicked", self._on_image_preview_clicked)

        self._image_preview_rail = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        self._image_preview_rail.add_css_class("focus-image-preview-rail")
        self._image_preview_rail.set_hexpand(False)
        self._image_preview_rail.set_vexpand(True)
        self._image_preview_rail.set_halign(Gtk.Align.END)
        self._image_preview_rail.set_valign(Gtk.Align.FILL)
        self._image_preview_rail.set_size_request(IMAGE_PREVIEW_RAIL_WIDTH, -1)
        self._image_preview_rail.append(self._image_preview_button)
        self._image_preview_rail.append(self._right_scroll_zone)

        self._text_mode_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        self._text_mode_box.add_css_class("focus-text-mode")
        self._text_mode_box.set_hexpand(True)
        self._text_mode_box.set_vexpand(True)
        self._text_mode_box.append(self._text_scroll_overlay)
        self._text_mode_box.append(self._image_preview_rail)
        GLib.idle_add(self._refresh_right_scroll_zone_geometry)

        self._image_picture = Gtk.Picture()
        self._image_picture.set_hexpand(False)
        self._image_picture.set_vexpand(False)
        self._image_picture.set_halign(Gtk.Align.START)
        self._image_picture.set_valign(Gtk.Align.START)
        self._image_picture.set_content_fit(Gtk.ContentFit.CONTAIN)
        self._image_picture.set_can_shrink(True)

        self._image_fixed = Gtk.Fixed()
        self._image_fixed.set_hexpand(False)
        self._image_fixed.set_vexpand(False)
        self._image_fixed.set_halign(Gtk.Align.START)
        self._image_fixed.set_valign(Gtk.Align.START)
        self._image_fixed.put(self._image_picture, 0, 0)

        self._image_scroller = Gtk.ScrolledWindow()
        self._image_scroller.add_css_class("focus-scroller")
        self._image_scroller.add_css_class("focus-image-scroller")
        self._image_scroller.add_css_class("focus-page-rounded")
        self._image_scroller.set_hexpand(True)
        self._image_scroller.set_vexpand(True)
        self._image_scroller.set_halign(Gtk.Align.FILL)
        self._image_scroller.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.AUTOMATIC)
        self._image_scroller.set_propagate_natural_height(False)
        self._image_scroller.set_propagate_natural_width(False)
        self._image_scroller.set_min_content_height(0)
        self._image_scroller.set_size_request(-1, 0)
        self._image_scroller.set_child(self._image_fixed)

        content_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        content_box.set_hexpand(True)
        content_box.set_vexpand(True)

        self._image_icon_name_on = self._choose_icon(*IMAGE_ICON_ON_CHOICES)
        self._image_icon_name_off = self._image_icon_name_on

        self._content_stack = Gtk.Stack()
        self._content_stack.set_hexpand(True)
        self._content_stack.set_vexpand(True)
        self._content_stack.set_transition_type(Gtk.StackTransitionType.CROSSFADE)
        self._content_stack.set_transition_duration(120)
        self._content_stack.set_hhomogeneous(False)
        self._content_stack.set_vhomogeneous(False)
        self._content_stack.add_named(self._text_mode_box, "text")
        self._content_stack.add_named(self._image_scroller, "image")
        self._content_stack.set_visible_child_name("text")

        self._content_overlay = Gtk.Overlay()
        self._content_overlay.set_hexpand(True)
        self._content_overlay.set_vexpand(True)
        self._content_overlay.set_child(self._content_stack)

        self._ai_panel_revealer = Gtk.Revealer()
        self._ai_panel_revealer.set_transition_type(Gtk.RevealerTransitionType.SLIDE_DOWN)
        self._ai_panel_revealer.set_reveal_child(False)

        ai_panel_root = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        ai_panel_root.set_hexpand(True)
        ai_panel_root.set_vexpand(False)
        ai_panel_root.set_margin_top(12)
        ai_panel_root.set_margin_bottom(8)
        ai_panel_root.set_margin_start(12)
        ai_panel_root.set_margin_end(12)
        ai_panel_root.add_css_class("ai-output-frame")
        self._ai_panel_root = ai_panel_root

        ai_header = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=5)
        ai_header.set_hexpand(True)
        self._ai_panel_header = ai_header

        self._ai_view_stack = Adw.ViewStack()
        try:
            self._ai_view_stack.set_transition_type(Adw.ViewStackTransitionType.CROSSFADE)
        except AttributeError:
            # Older libadwaita versions may not expose transition helpers; fall back to defaults.
            try:
                self._ai_view_stack.set_property("transition-type", Adw.ViewStackTransitionType.CROSSFADE)
            except Exception:
                pass
        self._ai_view_stack.set_hhomogeneous(False)
        self._ai_view_stack.set_vhomogeneous(False)
        self._ai_view_stack.set_vexpand(True)
        self._ai_view_stack.connect("notify::visible-child-name", self._on_ai_view_changed)

        ai_mode_strip = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=2)
        ai_mode_strip.add_css_class("focus-pill-group")
        ai_mode_strip.add_css_class("focus-case-tools-nav")
        ai_mode_strip.set_halign(Gtk.Align.START)
        ai_mode_strip.set_valign(Gtk.Align.CENTER)

        agent_mode_button = self._build_ai_mode_button(
            "Agent Q&A",
            AI_VIEW_AGENT_QA,
            "Ask citation-grounded questions with the embedded PI Agent",
            ("dialog-question-symbolic", "system-search-symbolic"),
        )
        ai_mode_strip.append(agent_mode_button)

        hearings_button = self._build_summary_mode_button(
            "Hearings",
            SUMMARY_SOURCE_HEARING,
            "Open hearing summaries",
            ("x-office-calendar-symbolic", "document-open-symbolic"),
        )
        ai_mode_strip.append(hearings_button)

        reports_button = self._build_summary_mode_button(
            "Reports",
            SUMMARY_SOURCE_REPORTS,
            "Open report summaries",
            ("text-x-generic-symbolic", "document-open-symbolic"),
        )
        ai_mode_strip.append(reports_button)

        more_separator = Gtk.Separator(orientation=Gtk.Orientation.VERTICAL)
        more_separator.add_css_class("focus-case-tools-separator")
        ai_mode_strip.append(more_separator)

        more_case_tools_menu = Gio.Menu()
        ai_tools_menu = Gio.Menu()
        ai_tools_menu.append("Summarize Pages", "app.show_summarize")
        ai_tools_menu.append("Extract Information", "app.show_extract")
        more_case_tools_menu.append_section("AI Tools", ai_tools_menu)
        summary_tools_menu = Gio.Menu()
        summary_tools_menu.append("Minute Orders", "app.show_minutes_summary")
        more_case_tools_menu.append_section("Summaries", summary_tools_menu)

        self._more_case_tools_button = Gtk.MenuButton()
        self._more_case_tools_button.set_child(
            self._build_labeled_icon(
                "More",
                "view-more-symbolic",
                "open-menu-symbolic",
            )
        )
        self._more_case_tools_button.add_css_class("flat")
        self._more_case_tools_button.add_css_class("no-bold")
        self._more_case_tools_button.add_css_class("focus-pill-segment")
        self._more_case_tools_button.set_valign(Gtk.Align.CENTER)
        self._more_case_tools_button.set_tooltip_text("More case tools")
        self._set_accessible_label(self._more_case_tools_button, "More case tools")
        self._more_case_tools_button.set_menu_model(more_case_tools_menu)
        ai_mode_strip.append(self._more_case_tools_button)
        ai_header.append(ai_mode_strip)

        status_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        status_row.add_css_class("focus-case-tools-status-row")
        status_row.set_hexpand(True)
        self._ai_spinner = Gtk.Spinner(spinning=False)
        self._ai_spinner.set_size_request(16, 16)
        self._ai_spinner.set_valign(Gtk.Align.CENTER)
        self._ai_spinner.set_visible(False)
        status_row.append(self._ai_spinner)
        self._ai_status_label = Gtk.Label(label="", xalign=0)
        self._ai_status_label.add_css_class("focus-case-tools-status")
        self._ai_status_label.set_hexpand(True)
        self._ai_status_label.set_single_line_mode(True)
        self._ai_status_label.set_ellipsize(Pango.EllipsizeMode.END)
        self._ai_status_label.set_accessible_role(Gtk.AccessibleRole.STATUS)
        status_row.append(self._ai_status_label)
        ai_header.append(status_row)

        self._ai_controls_stack = Gtk.Stack()
        self._ai_controls_stack.set_hexpand(True)
        self._ai_controls_stack.set_hhomogeneous(False)
        self._ai_controls_stack.set_vhomogeneous(False)
        self._ai_controls_stack.set_transition_type(Gtk.StackTransitionType.CROSSFADE)
        ai_header.append(self._ai_controls_stack)

        ai_panel_root.append(ai_header)

        summarize_view = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        summarize_view.set_hexpand(True)
        summarize_view.set_vexpand(True)
        summarize_controls = self._build_wrapping_controls_box()

        from_label = Gtk.Label(label="From")
        from_label.add_css_class("dim-label")
        from_label.set_valign(Gtk.Align.CENTER)
        summarize_controls.insert(from_label, -1)

        self._ai_range_start_entry = Gtk.Entry()
        self._ai_range_start_entry.set_width_chars(8)
        self._ai_range_start_entry.set_max_width_chars(12)
        self._ai_range_start_entry.set_max_length(16)
        self._ai_range_start_entry.set_input_purpose(Gtk.InputPurpose.FREE_FORM)
        self._ai_range_start_entry.set_alignment(0.5)
        self._ai_range_start_entry.set_valign(Gtk.Align.CENTER)
        self._ai_range_start_entry.set_placeholder_text("RT 1")
        self._ai_range_start_entry.connect("changed", self._on_sum_range_field_changed)
        self._ai_range_start_entry.connect("activate", self._on_summarize_range_activate)
        summarize_controls.insert(self._ai_range_start_entry, -1)

        to_label = Gtk.Label(label="To")
        to_label.add_css_class("dim-label")
        to_label.set_valign(Gtk.Align.CENTER)
        summarize_controls.insert(to_label, -1)

        self._ai_range_end_entry = Gtk.Entry()
        self._ai_range_end_entry.set_width_chars(8)
        self._ai_range_end_entry.set_max_width_chars(12)
        self._ai_range_end_entry.set_max_length(16)
        self._ai_range_end_entry.set_input_purpose(Gtk.InputPurpose.FREE_FORM)
        self._ai_range_end_entry.set_alignment(0.5)
        self._ai_range_end_entry.set_valign(Gtk.Align.CENTER)
        self._ai_range_end_entry.set_placeholder_text("RT 1")
        self._ai_range_end_entry.connect("changed", self._on_sum_range_field_changed)
        self._ai_range_end_entry.connect("activate", self._on_summarize_range_activate)
        summarize_controls.insert(self._ai_range_end_entry, -1)

        summarize_submit_button = Gtk.Button(label="Submit")
        summarize_submit_button.add_css_class("flat")
        summarize_submit_button.add_css_class("no-bold")
        summarize_submit_button.set_valign(Gtk.Align.CENTER)
        summarize_submit_button.connect("clicked", self._on_summarize_range_button_clicked)
        summarize_controls.insert(summarize_submit_button, -1)

        self._ai_range_status_label = Gtk.Label(label="")
        self._ai_range_status_label.add_css_class("dim-label")
        self._ai_range_status_label.set_valign(Gtk.Align.CENTER)
        self._ai_range_status_label.set_xalign(0.0)
        self._ai_range_status_label.set_width_chars(12)
        self._ai_range_status_label.set_max_width_chars(32)
        self._ai_range_status_label.set_ellipsize(Pango.EllipsizeMode.END)
        summarize_controls.insert(self._ai_range_status_label, -1)

        self._maybe_prefill_sum_range_for_current_page()

        extract_view = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        extract_view.set_hexpand(True)
        extract_view.set_vexpand(True)
        extract_controls = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        extract_controls.set_hexpand(True)
        extract_controls.set_valign(Gtk.Align.CENTER)

        extract_btn = Gtk.Button(label="Current Page")
        extract_btn.add_css_class("flat")
        extract_btn.add_css_class("no-bold")
        extract_btn.set_valign(Gtk.Align.CENTER)
        extract_btn.set_hexpand(False)
        extract_btn.set_halign(Gtk.Align.START)
        extract_btn.connect("clicked", self._on_extract_page_clicked)
        extract_controls.append(extract_btn)

        self._extract_range_entry = Gtk.Entry()
        self._extract_range_entry.set_placeholder_text("Page Range")
        self._extract_range_entry.set_max_length(9)
        self._extract_range_entry.set_hexpand(True)
        self._extract_range_entry.connect("activate", self._on_extract_range_activate)
        extract_controls.append(self._extract_range_entry)

        extract_range_btn = Gtk.Button(label="Submit")
        extract_range_btn.add_css_class("flat")
        extract_range_btn.add_css_class("no-bold")
        extract_range_btn.set_valign(Gtk.Align.CENTER)
        extract_range_btn.set_hexpand(False)
        extract_range_btn.set_halign(Gtk.Align.START)
        extract_range_btn.connect("clicked", self._on_extract_range_button_clicked)
        extract_controls.append(extract_range_btn)

        agent_view = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        agent_view.set_hexpand(True)
        agent_view.set_vexpand(True)
        agent_header_controls = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        agent_header_controls.add_css_class("focus-agent-composer")
        agent_header_controls.set_hexpand(True)
        agent_header_controls.set_valign(Gtk.Align.CENTER)

        self._agent_question_entry = Gtk.Entry()
        self._agent_question_entry.set_hexpand(True)
        self._agent_question_entry.set_width_chars(24)
        self._agent_question_entry.set_placeholder_text("Ask a question about this record")
        self._agent_question_entry.connect("activate", self._on_agent_question_activate)
        self._agent_question_entry.connect("changed", self._on_agent_question_changed)
        agent_header_controls.append(self._agent_question_entry)

        self._agent_submit_button = Gtk.Button(label="Ask")
        self._agent_submit_button.add_css_class("flat")
        self._agent_submit_button.add_css_class("focus-agent-submit-button")
        self._agent_submit_button.set_valign(Gtk.Align.CENTER)
        self._agent_submit_button.set_sensitive(False)
        self._agent_submit_button.set_tooltip_text("Ask the embedded Agent about the record")
        self._agent_submit_button.connect("clicked", self._on_agent_question_submit_clicked)
        agent_header_controls.append(self._agent_submit_button)

        agent_output_header = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=4)
        agent_output_header.add_css_class("focus-agent-output-header")
        agent_output_header.set_hexpand(True)
        agent_output_header.set_visible(False)

        agent_subview_strip = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=4)
        agent_subview_strip.add_css_class("focus-pill-group")
        agent_subview_strip.set_hexpand(True)
        agent_subview_strip.set_valign(Gtk.Align.CENTER)

        self._agent_answer_button = self._build_agent_subview_button(
            "Answer",
            AGENT_SUBVIEW_ANSWER,
            "Show the latest linked Agent final answer",
        )
        agent_subview_strip.append(self._agent_answer_button)

        self._agent_session_button = self._build_agent_subview_button(
            "Session",
            AGENT_SUBVIEW_SESSION,
            "Show the embedded Agent terminal session",
        )
        agent_subview_strip.append(self._agent_session_button)
        agent_output_header.append(agent_subview_strip)

        self._agent_copy_trace_button = Gtk.Button(label="Copy Trace")
        self._agent_copy_trace_button.add_css_class("flat")
        self._agent_copy_trace_button.add_css_class("no-bold")
        self._agent_copy_trace_button.set_valign(Gtk.Align.CENTER)
        self._agent_copy_trace_button.set_tooltip_text(
            "Refresh the latest full Agent session trace and copy its path "
            "for pasting into a new PI session"
        )
        self._agent_copy_trace_button.set_sensitive(False)
        self._agent_copy_trace_button.connect(
            "clicked", self._on_agent_copy_trace_clicked
        )
        agent_subview_strip.append(self._agent_copy_trace_button)
        self._agent_output_header = agent_output_header
        agent_view.append(agent_output_header)

        self._agent_subview_host = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        self._agent_subview_host.set_hexpand(True)
        self._agent_subview_host.set_vexpand(True)

        agent_answer_scroller = self._build_ai_output_view(AI_VIEW_AGENT_QA)
        self._agent_answer_scroller = agent_answer_scroller
        self._agent_subview_host.append(agent_answer_scroller)

        if Vte is not None:
            agent_terminal_frame = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
            agent_terminal_frame.set_hexpand(True)
            agent_terminal_frame.set_vexpand(True)
            agent_terminal_frame.add_css_class("focus-agent-terminal-frame")
            agent_terminal_frame.set_overflow(Gtk.Overflow.HIDDEN)

            agent_terminal = Vte.Terminal()
            agent_terminal.set_hexpand(True)
            agent_terminal.set_vexpand(True)
            agent_terminal.add_css_class("focus-agent-terminal")
            _apply_focus_terminal_theme(agent_terminal)
            terminal_key_controller = Gtk.EventControllerKey()
            terminal_key_controller.set_propagation_phase(Gtk.PropagationPhase.CAPTURE)
            terminal_key_controller.connect("key-pressed", self._on_agent_terminal_key_pressed)
            agent_terminal.add_controller(terminal_key_controller)
            agent_terminal.connect("child-exited", self._on_agent_terminal_child_exited)
            agent_terminal.connect(
                "selection-changed",
                self._on_search_selection_changed,
            )
            agent_terminal_frame.append(agent_terminal)
            self._agent_session_widget = agent_terminal_frame
            self._agent_subview_host.append(agent_terminal_frame)
            self._agent_terminal = agent_terminal
        else:
            agent_missing = Gtk.Label(
                label=(
                    "Embedded terminal support requires GTK4 VTE "
                    "(gir1.2-vte-3.91 and libvte-2.91-gtk4-0)."
                ),
                xalign=0,
            )
            agent_missing.set_wrap(True)
            agent_missing.set_wrap_mode(Pango.WrapMode.WORD_CHAR)
            agent_missing.add_css_class("dim-label")
            self._agent_session_widget = agent_missing
            self._agent_subview_host.append(agent_missing)

        agent_view.append(self._agent_subview_host)
        self._set_agent_subview(AGENT_SUBVIEW_SESSION)

        file_view = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        file_view.set_hexpand(True)
        file_view.set_vexpand(True)
        summary_row = self._build_wrapping_controls_box()

        self._summary_search_entry = Gtk.SearchEntry()
        self._summary_search_entry.set_placeholder_text("Search this summary")
        self._summary_search_entry.set_width_chars(18)
        self._summary_search_entry.set_max_width_chars(32)
        self._summary_search_entry.set_hexpand(True)
        self._summary_search_entry.set_valign(Gtk.Align.CENTER)
        self._summary_search_entry.connect("search-changed", self._on_summary_search_changed)
        self._summary_search_entry.connect("activate", self._on_summary_search_activate)
        summary_row.insert(self._summary_search_entry, -1)

        self._summary_progress_label = Gtk.Label(label="0%")
        self._summary_progress_label.add_css_class("dim-label")
        self._summary_progress_label.set_valign(Gtk.Align.CENTER)
        self._summary_progress_label.set_xalign(1.0)
        self._summary_progress_label.set_width_chars(6)
        self._summary_progress_label.set_single_line_mode(True)
        self._summary_progress_label.set_ellipsize(Pango.EllipsizeMode.END)
        summary_row.insert(self._summary_progress_label, -1)

        self._summary_prev_page_button = Gtk.Button(icon_name="go-previous-symbolic")
        self._summary_prev_page_button.add_css_class("flat")
        self._summary_prev_page_button.add_css_class("no-bold")
        self._summary_prev_page_button.set_valign(Gtk.Align.CENTER)
        self._summary_prev_page_button.set_tooltip_text("Previous summary page")
        self._summary_prev_page_button.connect(
            "clicked", self._on_summary_prev_page_clicked
        )
        self._summary_prev_page_button.set_visible(False)
        summary_row.insert(self._summary_prev_page_button, -1)

        self._summary_page_entry = Gtk.Entry()
        self._summary_page_entry.set_width_chars(3)
        self._summary_page_entry.set_max_width_chars(4)
        self._summary_page_entry.set_alignment(1.0)
        self._summary_page_entry.set_valign(Gtk.Align.CENTER)
        self._summary_page_entry.set_tooltip_text("Jump to a summary page number")
        self._summary_page_entry.connect(
            "activate", self._on_summary_page_entry_activate
        )
        self._summary_page_entry.set_visible(False)
        summary_row.insert(self._summary_page_entry, -1)

        self._summary_page_total_label = Gtk.Label(label="of 1")
        self._summary_page_total_label.add_css_class("dim-label")
        self._summary_page_total_label.set_valign(Gtk.Align.CENTER)
        self._summary_page_total_label.set_visible(False)
        summary_row.insert(self._summary_page_total_label, -1)

        self._summary_next_page_button = Gtk.Button(icon_name="go-next-symbolic")
        self._summary_next_page_button.add_css_class("flat")
        self._summary_next_page_button.add_css_class("no-bold")
        self._summary_next_page_button.set_valign(Gtk.Align.CENTER)
        self._summary_next_page_button.set_tooltip_text("Next summary page")
        self._summary_next_page_button.connect(
            "clicked", self._on_summary_next_page_clicked
        )
        self._summary_next_page_button.set_visible(False)
        summary_row.insert(self._summary_next_page_button, -1)

        self._summary_open_pdf_button = Gtk.Button(label="Open PDF")
        self._summary_open_pdf_button.add_css_class("flat")
        self._summary_open_pdf_button.add_css_class("no-bold")
        self._summary_open_pdf_button.set_valign(Gtk.Align.CENTER)
        self._summary_open_pdf_button.set_tooltip_text(
            "Open the page-matched summary PDF for printing"
        )
        self._summary_open_pdf_button.connect(
            "clicked", self._on_summary_open_pdf_clicked
        )
        self._summary_open_pdf_button.set_visible(False)
        summary_row.insert(self._summary_open_pdf_button, -1)

        self._summary_bookmark_action_button = Gtk.Button(label="Set Bookmark")
        self._summary_bookmark_action_button.add_css_class("flat")
        self._summary_bookmark_action_button.add_css_class("no-bold")
        self._summary_bookmark_action_button.set_valign(Gtk.Align.CENTER)
        self._summary_bookmark_action_button.set_tooltip_text("Bookmark the top visible summary line")
        self._summary_bookmark_action_button.connect("clicked", self._on_summary_bookmark_clicked)
        summary_row.insert(self._summary_bookmark_action_button, -1)

        self._summary_return_bookmark_action_button = Gtk.Button(label="Return")
        self._summary_return_bookmark_action_button.add_css_class("flat")
        self._summary_return_bookmark_action_button.add_css_class("no-bold")
        self._summary_return_bookmark_action_button.set_valign(Gtk.Align.CENTER)
        self._summary_return_bookmark_action_button.set_tooltip_text("Jump to the saved summary bookmark")
        self._summary_return_bookmark_action_button.connect(
            "clicked",
            self._on_summary_return_bookmark_clicked,
        )
        summary_row.insert(self._summary_return_bookmark_action_button, -1)

        self._refresh_summary_actions_state()

        if self._ai_controls_stack:
            self._ai_controls_stack.add_named(summarize_controls, AI_VIEW_SUMMARIZE)
            self._ai_controls_stack.add_named(extract_controls, AI_VIEW_EXTRACT)
            self._ai_controls_stack.add_named(agent_header_controls, AI_VIEW_AGENT_QA)
            self._ai_controls_stack.add_named(summary_row, AI_VIEW_FILE)
            self._ai_controls_stack.set_visible_child_name(AI_VIEW_AGENT_QA)

        self._summary_view = Gtk.TextView(editable=False, monospace=False, wrap_mode=Gtk.WrapMode.WORD_CHAR)
        self._summary_view.add_css_class("ai-output-view")
        self._summary_view.set_hexpand(True)
        self._summary_view.set_vexpand(True)
        self._summary_view.set_top_margin(6)
        self._summary_view.set_bottom_margin(6)
        self._summary_view.set_left_margin(6)
        self._summary_view.set_right_margin(6)
        self._summary_view.set_cursor_visible(False)
        self._summary_view.connect("map", self._on_summary_view_mapped)
        self._summary_buffer = self._summary_view.get_buffer()
        self._summary_buffer.connect(
            "notify::has-selection",
            self._on_search_selection_changed,
        )
        self._install_summary_link_controllers()

        self._summary_scroller = Gtk.ScrolledWindow()
        self._summary_scroller.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.AUTOMATIC)
        self._summary_scroller.set_hexpand(True)
        self._summary_scroller.set_vexpand(True)
        self._summary_scroller.set_propagate_natural_height(True)
        self._summary_scroller.set_min_content_height(EMBEDDED_AI_OUTPUT_MIN_HEIGHT)
        self._summary_scroller.set_max_content_height(AI_OUTPUT_MAX_HEIGHT)
        self._summary_scroller.set_child(self._summary_view)
        self._connect_summary_scroll_watch()
        self._ai_output_scrollers.append(self._summary_scroller)

        file_view.append(self._summary_scroller)

        summarize_scroller = self._build_ai_output_view(AI_VIEW_SUMMARIZE)
        extract_scroller = self._build_ai_output_view(AI_VIEW_EXTRACT)

        summarize_view.append(summarize_scroller)
        extract_view.append(extract_scroller)

        self._ai_view_stack.add_titled(summarize_view, AI_VIEW_SUMMARIZE, "Summarize")
        self._ai_view_stack.add_titled(extract_view, AI_VIEW_EXTRACT, "Extract")
        self._ai_view_stack.add_titled(agent_view, AI_VIEW_AGENT_QA, "Agent Q&A")
        self._ai_view_stack.add_titled(file_view, AI_VIEW_FILE, "Show File")
        self._ai_view_stack.set_visible_child_name(AI_VIEW_AGENT_QA)
        self._sync_ai_view_toggles(AI_VIEW_AGENT_QA)
        self._update_ai_status("", spinning=False)

        self._auto_load_summary_file()

        ai_panel_root.append(self._ai_view_stack)
        self._attach_ai_panel_to_embedded_host()
        main_root = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        main_root.set_hexpand(True)
        main_root.set_vexpand(True)
        self._main_root = main_root
        main_root.append(self._ai_panel_revealer)

        document_shell = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        document_shell.set_hexpand(True)
        document_shell.set_vexpand(True)
        document_shell.set_margin_start(12)
        document_shell.set_margin_end(12)
        document_shell.set_margin_top(0)

        text_controls = Gtk.CenterBox()
        text_controls.set_hexpand(True)
        text_controls.set_valign(Gtk.Align.CENTER)
        text_controls.set_halign(Gtk.Align.FILL)

        page_controls = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=4)
        page_controls.set_halign(Gtk.Align.START)
        page_controls.set_valign(Gtk.Align.CENTER)

        self._page_number_entry = Gtk.Entry()
        self._page_number_entry.add_css_class("focus-page-number-entry")
        self._page_number_entry.set_width_chars(6)
        self._page_number_entry.set_max_width_chars(8)
        self._page_number_entry.set_input_purpose(Gtk.InputPurpose.FREE_FORM)
        self._page_number_entry.set_alignment(1.0)
        self._page_number_entry.set_valign(Gtk.Align.CENTER)
        self._page_number_entry.set_tooltip_text(
            "Type a record page, citation page, or file page and press Enter (Ctrl+E)"
        )
        self._page_number_entry.connect("activate", self._on_page_number_activate)
        page_controls.append(self._page_number_entry)

        self._page_total_label = Gtk.Label(label="/ --")
        self._page_total_label.add_css_class("dim-label")
        self._page_total_label.set_xalign(0.0)
        self._page_total_label.set_valign(Gtk.Align.CENTER)
        page_controls.append(self._page_total_label)

        self._record_boundary_date_label = Gtk.Label(label="")
        self._record_boundary_date_label.add_css_class("dim-label")
        self._record_boundary_date_label.set_xalign(0.0)
        self._record_boundary_date_label.set_valign(Gtk.Align.CENTER)
        self._record_boundary_date_label.set_margin_start(4)
        self._record_boundary_date_label.set_tooltip_text("Boundary date")
        self._record_boundary_date_label.set_visible(False)
        page_controls.append(self._record_boundary_date_label)

        self._minute_order_button = Gtk.Button()
        self._minute_order_button.add_css_class("flat")
        self._minute_order_button.set_valign(Gtk.Align.CENTER)
        self._minute_order_button.set_child(
            self._build_header_icon("text-x-generic-symbolic", "document-open-symbolic")
        )
        self._minute_order_button.set_tooltip_text("Open the minute order for this RT page")
        self._minute_order_button.set_sensitive(False)
        self._minute_order_button.set_visible(False)
        self._minute_order_button.connect("clicked", self._on_minute_order_clicked)
        page_controls.append(self._minute_order_button)
        text_controls.set_start_widget(page_controls)

        grep_controls = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=4)
        grep_controls.set_halign(Gtk.Align.CENTER)
        grep_controls.set_valign(Gtk.Align.CENTER)

        self._grep_entry = Gtk.SearchEntry()
        self._grep_entry.set_width_chars(20)
        self._grep_entry.set_max_width_chars(30)
        self._grep_entry.set_hexpand(True)
        self._grep_entry.set_placeholder_text("Search record")
        self._grep_entry.connect("activate", self._on_grep_entry_activate)
        self._grep_entry.connect("search-changed", self._on_grep_search_changed)
        self._grep_entry.connect("stop-search", self._on_grep_stop_search)
        grep_controls.append(self._grep_entry)

        self._grep_highlighted_button = Gtk.Button()
        self._grep_highlighted_button.add_css_class("flat")
        self._grep_highlighted_button.add_css_class("focus-subdued")
        self._grep_highlighted_button.set_valign(Gtk.Align.CENTER)
        self._grep_highlighted_button.set_tooltip_text("Search highlighted text")
        self._grep_highlighted_button.set_child(
            Gtk.Image.new_from_icon_name(
                self._choose_icon("edit-find-symbolic", "system-search-symbolic", "edit-find")
            )
        )
        self._grep_highlighted_button.set_visible(False)
        self._grep_highlighted_button.connect(
            "clicked",
            self._on_grep_search_highlighted_clicked,
        )
        grep_controls.append(self._grep_highlighted_button)

        self._grep_hit_label = Gtk.Label(label="")
        self._grep_hit_label.add_css_class("focus-search-chip")
        self._grep_hit_label.set_valign(Gtk.Align.CENTER)
        self._grep_hit_label.set_xalign(0.0)
        self._grep_hit_label.set_visible(False)
        grep_controls.append(self._grep_hit_label)

        self._grep_prev_hit_button = Gtk.Button()
        self._grep_prev_hit_button.add_css_class("flat")
        self._grep_prev_hit_button.set_valign(Gtk.Align.CENTER)
        self._grep_prev_hit_button.set_tooltip_text("Previous grep hit (Ctrl+Shift+G)")
        self._grep_prev_hit_button.set_child(
            Gtk.Image.new_from_icon_name(self._choose_icon("go-up-symbolic", "go-up"))
        )
        self._grep_prev_hit_button.set_visible(False)
        self._grep_prev_hit_button.connect("clicked", self._on_grep_prev_hit_clicked)
        grep_controls.append(self._grep_prev_hit_button)

        self._grep_next_hit_button = Gtk.Button()
        self._grep_next_hit_button.add_css_class("flat")
        self._grep_next_hit_button.set_valign(Gtk.Align.CENTER)
        self._grep_next_hit_button.set_tooltip_text("Next grep hit (Ctrl+G)")
        self._grep_next_hit_button.set_child(
            Gtk.Image.new_from_icon_name(self._choose_icon("go-down-symbolic", "go-down"))
        )
        self._grep_next_hit_button.set_visible(False)
        self._grep_next_hit_button.connect("clicked", self._on_grep_next_hit_clicked)
        grep_controls.append(self._grep_next_hit_button)
        text_controls.set_center_widget(grep_controls)

        end_controls = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        end_controls.set_halign(Gtk.Align.END)
        end_controls.set_valign(Gtk.Align.CENTER)

        self._current_page_citation_button = Gtk.Button(label="Cite")
        self._current_page_citation_button.add_css_class("flat")
        self._current_page_citation_button.add_css_class("no-bold")
        self._current_page_citation_button.add_css_class("focus-subdued")
        self._current_page_citation_button.set_valign(Gtk.Align.CENTER)
        self._current_page_citation_button.set_tooltip_text(
            "Insert current page citation in Prose (Ctrl+Alt+Shift+C)"
        )
        self._current_page_citation_button.set_sensitive(False)
        self._current_page_citation_button.connect(
            "clicked",
            self._on_current_page_citation_clicked,
        )
        end_controls.append(self._current_page_citation_button)

        self._page_citation_range_button = Gtk.Button(label="Range")
        self._page_citation_range_button.add_css_class("flat")
        self._page_citation_range_button.add_css_class("no-bold")
        self._page_citation_range_button.add_css_class("focus-subdued")
        self._page_citation_range_button.set_valign(Gtk.Align.CENTER)
        self._page_citation_range_button.set_tooltip_text(
            "Set citation range start (Ctrl+Alt+C)"
        )
        self._page_citation_range_button.set_sensitive(False)
        self._page_citation_range_button.connect(
            "clicked",
            self._on_page_citation_range_clicked,
        )
        end_controls.append(self._page_citation_range_button)

        self._show_image_icon = Gtk.Image.new_from_icon_name(self._image_icon_name_off)
        self._show_image_icon.add_css_class("focus-toggle-icon")
        self._show_image_button = Gtk.ToggleButton()
        self._show_image_button.set_child(self._show_image_icon)
        self._show_image_button.add_css_class("flat")
        self._show_image_button.set_valign(Gtk.Align.CENTER)
        self._show_image_button.set_tooltip_text("Enable image view (Ctrl+I)")
        self._show_image_button.connect("toggled", self._on_show_image_button_toggled)
        end_controls.append(self._show_image_button)
        text_controls.set_end_widget(end_controls)
        self._refresh_search_highlighted_button()

        document_shell.append(text_controls)
        self._update_show_image_toggle_button()
        self._update_page_nav_buttons()

        content_box.append(self._content_overlay)

        self._split_view = Adw.NavigationSplitView()
        self._split_view.set_collapsed(False)
        self._split_view.add_css_class("focus-split")
        self._split_view.set_hexpand(True)
        self._split_view.set_vexpand(True)
        self._split_view.set_sidebar_width_fraction(0.05)
        self._split_view.set_min_sidebar_width(180)
        self._split_view.set_max_sidebar_width(320)
        self._split_content_page = Adw.NavigationPage.new(content_box, "Document")
        self._split_view.set_content(self._split_content_page)
        self._split_view.set_collapsed(True)
        sidebar_root = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        sidebar_root.set_hexpand(True)
        sidebar_root.set_vexpand(True)
        sidebar_root.add_css_class("focus-sidebar")

        sidebar_container = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        sidebar_container.set_margin_top(0)
        sidebar_container.set_margin_bottom(8)
        sidebar_container.set_margin_start(0)
        sidebar_container.set_margin_end(0)
        sidebar_container.set_valign(Gtk.Align.FILL)
        sidebar_container.set_vexpand(True)

        self._toc_sidebar_root_store = Gio.ListStore(item_type=FocusSidebarItem)
        self._toc_sidebar_tree_model = Gtk.TreeListModel.new(
            self._toc_sidebar_root_store,
            False,
            False,
            self._create_sidebar_children_model,
        )

        self._toc_list_view = Gtk.ListBox()
        self._toc_list_view.set_selection_mode(Gtk.SelectionMode.NONE)
        self._toc_list_view.add_css_class("focus-sidebar-listview")
        self._toc_list_view.set_activate_on_single_click(True)
        self._toc_list_view.connect("row-activated", self._on_sidebar_row_activated)
        if self._toc_sidebar_tree_model is not None:
            self._toc_list_view.bind_model(self._toc_sidebar_tree_model, self._create_sidebar_row_for_item)

        self._toc_placeholder = Gtk.Label(label="No TOC loaded", xalign=0)
        self._toc_placeholder.add_css_class("dim-label")
        self._toc_placeholder.set_hexpand(True)
        self._toc_placeholder.set_vexpand(True)
        self._toc_placeholder.set_margin_top(24)
        self._toc_placeholder.set_margin_start(4)
        self._toc_placeholder.set_margin_end(4)
        self._toc_placeholder.set_halign(Gtk.Align.START)
        self._toc_placeholder.set_valign(Gtk.Align.START)

        self._toc_sidebar_overlay = Gtk.Overlay()
        self._toc_sidebar_overlay.set_child(self._toc_list_view)
        self._toc_sidebar_overlay.add_overlay(self._toc_placeholder)
        self._toc_sidebar_overlay.set_hexpand(True)
        self._toc_sidebar_overlay.set_vexpand(True)
        self._toc_sidebar_overlay.set_valign(Gtk.Align.START)

        self._toc_sidebar_scroller = Gtk.ScrolledWindow()
        self._toc_sidebar_scroller.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        self._toc_sidebar_scroller.set_hexpand(True)
        self._toc_sidebar_scroller.set_vexpand(True)
        self._toc_sidebar_scroller.set_propagate_natural_height(False)
        self._toc_sidebar_scroller.set_child(self._toc_sidebar_overlay)

        sidebar_container.append(self._toc_sidebar_scroller)

        self._toc_sidebar_revealer = Gtk.Revealer()
        self._toc_sidebar_revealer.set_transition_type(Gtk.RevealerTransitionType.SLIDE_RIGHT)
        self._toc_sidebar_revealer.set_reveal_child(self._toc_sidebar_visible)
        sidebar_root.append(sidebar_container)
        self._toc_sidebar_revealer.set_child(sidebar_root)
        self._split_sidebar_page = Adw.NavigationPage.new(self._toc_sidebar_revealer, "Contents")
        if self._split_view:
            self._split_view.set_sidebar(self._split_sidebar_page)

        document_shell.append(self._split_view)
        main_root.append(document_shell)
        toolbar.set_content(main_root)
        self._ensure_ai_panel_resize_tracking()
        self._reset_embedded_ai_panel_sizing()
        self._rebuild_toc_sidebar()

        self._install_navigation_controllers()
        self._install_actions()

    def _get_ai_host_window(self) -> Adw.ApplicationWindow | None:
        return self.win

    def _detach_widget_from_parent(self, widget: Gtk.Widget | None) -> None:
        if widget is None:
            return
        parent = widget.get_parent()
        if parent is None:
            return
        if isinstance(parent, Gtk.Box):
            parent.remove(widget)
            return
        if isinstance(parent, Gtk.Revealer):
            parent.set_child(None)
            return
        if isinstance(parent, Gtk.ScrolledWindow):
            parent.set_child(None)
            return
        if isinstance(parent, Adw.ToolbarView):
            parent.set_content(None)
            return

    def _attach_ai_panel_to_embedded_host(self) -> None:
        if not self._ai_panel_revealer or not self._ai_panel_root:
            return
        self._detach_widget_from_parent(self._ai_panel_root)
        self._ai_panel_revealer.set_child(self._ai_panel_root)
        visible = self._current_view_state().ai_panel_visible
        self._ai_panel_revealer.set_reveal_child(visible)
        if visible:
            self._update_embedded_ai_panel_height(force=True)
        else:
            self._reset_embedded_ai_panel_sizing()

    def _reset_ai_output_scroller_sizing(self) -> None:
        for scroller in self._ai_output_scrollers:
            scroller.set_visible(True)
            scroller.set_size_request(-1, -1)
            scroller.set_propagate_natural_height(True)
            scroller.set_min_content_height(EMBEDDED_AI_OUTPUT_MIN_HEIGHT)
            scroller.set_max_content_height(AI_OUTPUT_MAX_HEIGHT)
        if self._summary_scroller:
            self._summary_scroller.set_visible(True)
            self._summary_scroller.set_size_request(-1, -1)
            self._summary_scroller.set_propagate_natural_height(True)
            self._summary_scroller.set_min_content_height(EMBEDDED_AI_OUTPUT_MIN_HEIGHT)
            self._summary_scroller.set_max_content_height(AI_OUTPUT_MAX_HEIGHT)

    def _reset_embedded_ai_panel_sizing(self) -> None:
        if self._ai_panel_revealer:
            self._ai_panel_revealer.set_size_request(-1, -1)
        if self._ai_panel_root:
            self._ai_panel_root.set_size_request(-1, -1)
        if self._ai_view_stack:
            self._ai_view_stack.set_size_request(-1, -1)
        self._reset_ai_output_scroller_sizing()
        self._last_ai_panel_host_height = -1

    @staticmethod
    def _widget_natural_height(widget: Gtk.Widget | None) -> int:
        if widget is None:
            return 0
        allocated_width = max(0, int(widget.get_width()))
        for_size = allocated_width if allocated_width > 0 else -1
        try:
            _minimum, natural, _min_baseline, _nat_baseline = widget.measure(
                Gtk.Orientation.VERTICAL,
                for_size,
            )
            return max(0, int(natural))
        except Exception:
            return max(0, int(widget.get_height()))

    def _active_ai_output_scroller(self) -> tuple[Gtk.ScrolledWindow | None, bool]:
        active_view = (
            self._ai_view_stack.get_visible_child_name()
            if self._ai_view_stack
            else self._ai_active_view
        )
        if active_view == AI_VIEW_FILE:
            return self._summary_scroller, bool(self._summary_raw.strip())
        if active_view == AI_VIEW_AGENT_QA:
            if self._agent_subview_name != AGENT_SUBVIEW_ANSWER:
                return None, False
        output_state = self._ai_outputs.get(active_view or "")
        if output_state is None:
            return None, False
        if active_view == AI_VIEW_AGENT_QA:
            return output_state.scroller, bool(output_state.raw.strip())
        return output_state.scroller, bool(output_state.raw.strip())

    def _active_ai_body_has_content(self) -> bool:
        active_view = (
            self._ai_view_stack.get_visible_child_name()
            if self._ai_view_stack
            else self._ai_active_view
        )
        if active_view == AI_VIEW_AGENT_QA and self._agent_subview_name == AGENT_SUBVIEW_SESSION:
            return self._agent_session_has_content()
        _active_scroller, has_output = self._active_ai_output_scroller()
        return has_output

    def _embedded_ai_output_min_height(self, max_height: int) -> int:
        if max_height <= 0:
            return 0
        return min(AI_OUTPUT_MIN_HEIGHT, max_height)

    @staticmethod
    def _embedded_ai_panel_max_height(host_height: int) -> int:
        if host_height <= 0:
            return 0
        preferred_height = max(
            EMBEDDED_AI_PANEL_MIN_HEIGHT,
            host_height // EMBEDDED_AI_PANEL_HEIGHT_DIVISOR,
        )
        return min(host_height, preferred_height)

    @staticmethod
    def _set_scroller_content_height_bounds(
        scroller: Gtk.ScrolledWindow,
        min_height: int,
        max_height: int,
    ) -> None:
        scroller.set_min_content_height(-1)
        scroller.set_max_content_height(max_height)
        scroller.set_min_content_height(min_height)

    def _sync_embedded_ai_output_scrollers(self, max_height: int) -> None:
        active_scroller, has_output = self._active_ai_output_scroller()
        for scroller in self._ai_output_scrollers:
            is_active = scroller is active_scroller
            show_output = bool(is_active and has_output)
            scroller.set_visible(show_output)
            scroller.set_propagate_natural_height(True)
            scroller.set_size_request(-1, -1)
            if show_output:
                min_height = self._embedded_ai_output_min_height(max_height)
                self._set_scroller_content_height_bounds(
                    scroller,
                    min_height,
                    max(min_height, max_height),
                )
            else:
                self._set_scroller_content_height_bounds(
                    scroller,
                    AI_OUTPUT_COLLAPSED_HEIGHT,
                    AI_OUTPUT_COLLAPSED_HEIGHT,
                )
        if self._summary_scroller:
            is_active = self._summary_scroller is active_scroller
            show_output = bool(is_active and has_output)
            self._summary_scroller.set_visible(show_output)
            self._summary_scroller.set_propagate_natural_height(True)
            self._summary_scroller.set_size_request(-1, -1)
            if show_output:
                min_height = self._embedded_ai_output_min_height(max_height)
                self._set_scroller_content_height_bounds(
                    self._summary_scroller,
                    min_height,
                    max(min_height, max_height),
                )
            else:
                self._set_scroller_content_height_bounds(
                    self._summary_scroller,
                    AI_OUTPUT_COLLAPSED_HEIGHT,
                    AI_OUTPUT_COLLAPSED_HEIGHT,
                )

    def _queue_embedded_ai_panel_height_update(
        self,
        *,
        after_render: bool = False,
    ) -> None:
        if not self._ai_panel_revealer or not self._ai_panel_revealer.get_reveal_child():
            return
        if after_render:
            self._ensure_ai_panel_post_render_resize()
        if self._ai_panel_layout_idle_id is not None:
            return
        self._ai_panel_layout_idle_id = GLib.idle_add(self._update_embedded_ai_panel_height_idle)

    def _ensure_ai_panel_post_render_resize(self) -> None:
        if not self.win:
            return
        self._ai_panel_post_render_frames = max(
            self._ai_panel_post_render_frames,
            2,
        )
        if self._ai_panel_post_render_tick_id is None:
            self._ai_panel_post_render_tick_id = self.win.add_tick_callback(
                self._on_ai_panel_post_render_tick
            )

    def _on_ai_panel_post_render_tick(
        self,
        widget: Gtk.Widget,
        _frame_clock: Gdk.FrameClock,
    ) -> bool:
        if self.win is None or widget is not self.win:
            self._ai_panel_post_render_tick_id = None
            self._ai_panel_post_render_frames = 0
            return False
        if self._ai_panel_post_render_frames > 1:
            active_scroller, _has_output = self._active_ai_output_scroller()
            if active_scroller:
                child = active_scroller.get_child()
                if child:
                    child.queue_resize()
                active_scroller.queue_resize()
        else:
            self._update_embedded_ai_panel_height(force=True)
        self._ai_panel_post_render_frames -= 1
        if self._ai_panel_post_render_frames <= 0:
            self._ai_panel_post_render_tick_id = None
            self._ai_panel_post_render_frames = 0
            return False
        return True

    def _update_embedded_ai_panel_height_idle(self) -> bool:
        self._ai_panel_layout_idle_id = None
        self._update_embedded_ai_panel_height(force=True)
        return False

    def _embedded_ai_panel_chrome_height(self) -> int:
        if not self._ai_panel_root or not self._ai_view_stack:
            return 0
        body_was_visible = self._ai_view_stack.get_visible()
        self._ai_view_stack.set_visible(False)
        try:
            return self._widget_natural_height(self._ai_panel_root)
        finally:
            self._ai_view_stack.set_visible(body_was_visible)

    def _active_ai_body_fixed_height(self, active_scroller: Gtk.ScrolledWindow) -> int:
        if not self._ai_view_stack:
            return 0
        active_child = self._ai_view_stack.get_visible_child()
        if not active_child or not active_scroller.get_visible():
            return 0
        active_scroller.set_visible(False)
        try:
            fixed_height = self._widget_natural_height(active_child)
        finally:
            active_scroller.set_visible(True)
        if fixed_height <= 0:
            return 0
        parent = active_scroller.get_parent()
        if isinstance(parent, Gtk.Box):
            fixed_height += max(0, parent.get_spacing())
        return fixed_height

    def _update_embedded_ai_panel_height(self, *, force: bool = False) -> None:
        if not self.win or not self._ai_panel_root or not self._ai_view_stack:
            return
        if not self._ai_panel_revealer or not self._ai_panel_revealer.get_reveal_child():
            self._reset_embedded_ai_panel_sizing()
            return
        host_height = max(0, self.win.get_height())
        if host_height <= 0:
            return
        if not force and host_height == self._last_ai_panel_host_height:
            return
        self._last_ai_panel_host_height = host_height
        if self._ai_panel_revealer:
            self._ai_panel_revealer.set_size_request(-1, -1)
        self._ai_panel_root.set_size_request(-1, -1)
        self._ai_view_stack.set_size_request(-1, -1)
        body_visible = self._active_ai_body_has_content()
        if not body_visible:
            self._sync_embedded_ai_output_scrollers(0)
            self._ai_view_stack.set_visible(False)
            self._ai_panel_root.queue_resize()
            self._ai_view_stack.queue_resize()
            return

        self._ai_view_stack.set_visible(True)
        max_panel_height = self._embedded_ai_panel_max_height(host_height)
        chrome_height = self._embedded_ai_panel_chrome_height()
        body_spacing = (
            self._ai_panel_root.get_spacing()
            if isinstance(self._ai_panel_root, Gtk.Box)
            else 0
        )
        max_body_height = max(0, max_panel_height - chrome_height - body_spacing)
        self._sync_embedded_ai_output_scrollers(max_body_height)
        active_scroller, has_output = self._active_ai_output_scroller()
        if active_scroller and has_output:
            fixed_body_height = self._active_ai_body_fixed_height(active_scroller)
            max_output_height = max(0, max_body_height - fixed_body_height)
            self._sync_embedded_ai_output_scrollers(max_output_height)
        self._ai_panel_root.queue_resize()
        self._ai_view_stack.queue_resize()

    def _on_ai_panel_resize_tick(
        self,
        widget: Gtk.Widget,
        _frame_clock: Gdk.FrameClock,
    ) -> bool:
        if self.win is None or widget is not self.win:
            self._ai_panel_resize_tick_id = None
            return False
        current_height = max(0, self.win.get_height())
        if current_height > 0 and current_height != self._last_ai_panel_host_height:
            self._update_embedded_ai_panel_height(force=True)
        return True

    def _ensure_ai_panel_resize_tracking(self) -> None:
        if not self.win or self._ai_panel_resize_tick_id is not None:
            return
        self._ai_panel_resize_tick_id = self.win.add_tick_callback(self._on_ai_panel_resize_tick)

    def _stop_ai_panel_resize_tracking(self) -> None:
        if self.win and self._ai_panel_resize_tick_id is not None:
            self.win.remove_tick_callback(self._ai_panel_resize_tick_id)
        self._ai_panel_resize_tick_id = None
        if self.win and self._ai_panel_post_render_tick_id is not None:
            self.win.remove_tick_callback(self._ai_panel_post_render_tick_id)
        self._ai_panel_post_render_tick_id = None
        self._ai_panel_post_render_frames = 0
        if self._ai_panel_layout_idle_id is not None:
            GLib.source_remove(self._ai_panel_layout_idle_id)
            self._ai_panel_layout_idle_id = None

    def _update_ai_panel_toggle(self, visible: bool) -> None:
        if not self._ai_panel_toggle:
            return
        tooltip = (
            "Hide case tools (Ctrl+Shift+A)"
            if visible
            else "Show case tools (Ctrl+Shift+A)"
        )
        self._ai_panel_toggle_guard = True
        try:
            self._ai_panel_toggle.set_active(visible)
            self._ai_panel_toggle.set_tooltip_text(tooltip)
        finally:
            self._ai_panel_toggle_guard = False

    def _current_view_state(self) -> FocusViewState:
        return self._view_state

    def _reset_view_states(self) -> None:
        self._stop_grep_search_if_running()
        self._cancel_all_ai_streams()
        self._stop_agent_answer_polling()
        self._cleanup_agent_answer_artifact()
        self._cancel_pending_summary_scroll_restore()
        self._page_citation_range_start = None
        self._sync_citation_buttons()
        self._set_grep_entry_text("")
        self._view_state = FocusViewState()
        self._current_view_state().sidebar_visible = self._toc_sidebar_visible
        self._current_view_state().ai_panel_visible = bool(
            (self._ai_panel_toggle and self._ai_panel_toggle.get_active())
            or (self._ai_panel_revealer and self._ai_panel_revealer.get_child_revealed())
        )
        self._ai_active_view = AI_VIEW_AGENT_QA
        self._ai_request_generation = 0
        self._ai_in_flight = False
        self._ai_cancel_event = None
        self._ai_stream_thread = None
        for ai_state in self._ai_outputs.values():
            ai_state.raw = ""
            self._apply_ai_output_links("", ai_state)
        self._agent_workspace_path = None
        self._reset_agent_trace_state()
        self._agent_answer_status = ""
        self._agent_last_answer_text = ""
        self._sync_show_image_action()

    def _cancel_all_ai_streams(self) -> None:
        state = self._current_view_state()
        if state.ai_cancel_event:
            state.ai_cancel_event.set()
        if state.ai_stream_thread and state.ai_stream_thread.is_alive():
            try:
                state.ai_stream_thread.join(timeout=0.2)
            except Exception:
                pass
        state.ai_in_flight = False
        state.ai_cancel_event = None
        state.ai_stream_thread = None
        self._ai_in_flight = False
        self._ai_cancel_event = None
        self._ai_stream_thread = None

    def _persist_active_view_state(self) -> None:
        state = self._current_view_state()
        if (
            self._ai_active_view == AI_VIEW_FILE
            and self._summary_scroller
            and self._summary_loaded_path
        ):
            self._capture_summary_scroll_position()
        state.current_index = self.current_index
        state.show_image = self._show_image
        state.sidebar_visible = self._toc_sidebar_visible
        state.ai_panel_visible = bool(
            (self._ai_panel_toggle and self._ai_panel_toggle.get_active())
            or (self._ai_panel_revealer and self._ai_panel_revealer.get_child_revealed())
        )
        state.grep_phrase_raw = self._grep_phrase_raw
        state.grep_regex = self._grep_regex
        state.grep_active = self._grep_active
        state.grep_hits = {k: list(v) for k, v in self._grep_hits.items()}
        state.matching_pages = list(self._matching_pages)
        state.matching_lookup = dict(self._matching_lookup)
        state.grep_match_order = list(self._grep_match_order)
        state.grep_current_match_index = self._grep_current_match_index
        state.ai_active_view = self._ai_active_view
        state.ai_output_raw = {name: view.raw or "" for name, view in self._ai_outputs.items()}
        state.ai_status_text = ""
        state.ai_spinning = bool(self._ai_spinner and self._ai_spinner.get_spinning())
        state.ai_request_generation = self._ai_request_generation
        state.ai_in_flight = self._ai_in_flight
        state.ai_cancel_event = self._ai_cancel_event
        state.ai_stream_thread = self._ai_stream_thread
        state.sidebar_expanded = self._get_sidebar_expanded_keys()
        if self._ai_range_start_entry:
            state.ai_range_start_text = self._ai_range_start_entry.get_text()
        if self._ai_range_end_entry:
            state.ai_range_end_text = self._ai_range_end_entry.get_text()
        state.ai_range_autofilled = self._ai_range_autofilled
        if self._extract_range_entry:
            state.extract_range_text = self._extract_range_entry.get_text()
        if self._agent_question_entry:
            state.agent_question_text = self._agent_question_entry.get_text()
        state.summary_loaded_path = self._summary_loaded_path
        state.summary_active_source = self._summary_active_source
        state.summary_current_page = (
            self._summary_edition_page if self._summary_is_paged() else None
        )

    def _set_window_title(self, window_suffix: str | None = None) -> None:
        case_name = self._case_name
        title_text = "Focus"
        if case_name:
            title_text = f"{title_text} - {case_name}"
        if self.win:
            win_title = title_text
            if window_suffix:
                win_title = f"{win_title} - {window_suffix}"
            self.win.set_title(win_title)
        if self._title_widget:
            self._title_widget.set_title(title_text)
            self._title_widget.set_subtitle("")

    def _set_text(self, text: str, highlights: list[tuple[int, int]] | None = None) -> None:
        if not self.textview:
            return
        buf = self.textview.get_buffer()
        rendered_text, markdown_spans, orig_to_clean = _render_markdown_text(text)
        buf.set_text(rendered_text)
        self._apply_markdown_spans(buf, markdown_spans)
        self._apply_page_marker_style(buf, rendered_text)
        self._apply_page_links(buf, rendered_text)
        if highlights:
            highlights = self._map_markdown_spans(highlights, orig_to_clean)
            tag = self._ensure_highlight_tag()
            if tag is not None:
                char_count = buf.get_char_count()
                for start, end in highlights:
                    if end <= start:
                        continue
                    start = max(0, min(start, char_count))
                    end = max(0, min(end, char_count))
                    if end <= start:
                        continue
                    for line_start, line_end in split_span_at_line_breaks(rendered_text, start, end):
                        start_iter = buf.get_iter_at_offset(line_start)
                        end_iter = buf.get_iter_at_offset(line_end)
                        buf.apply_tag(tag, start_iter, end_iter)
        self._apply_keyword_highlights(buf, rendered_text)
        self._apply_rounded_grid_table_no_wrap(buf, rendered_text)
        if self.scroller:
            vadj = self.scroller.get_vadjustment()
            if vadj:
                GLib.idle_add(vadj.set_value, vadj.get_lower())
            hadj = self.scroller.get_hadjustment()
            if hadj:
                GLib.idle_add(hadj.set_value, hadj.get_lower())

    def _scroll_textview_to_offset(self, offset: int) -> None:
        if not self.textview:
            return
        buffer = self.textview.get_buffer()
        char_count = buffer.get_char_count()
        if char_count <= 0:
            return
        clamped = max(0, min(int(offset), char_count - 1))
        iter_ = buffer.get_iter_at_offset(clamped)
        self.textview.scroll_to_iter(iter_, 0.0, True, 0.0, 0.5)
        if self.scroller:
            hadj = self.scroller.get_hadjustment()
            if hadj:
                hadj.set_value(hadj.get_lower())

    def _current_grep_highlights(self) -> list[tuple[int, int]]:
        if not self.pages or not self._grep_hits:
            return []
        if self.current_index < 0 or self.current_index >= len(self.pages):
            return []
        page = self.pages[self.current_index]
        hits = self._grep_hits.get(page, [])
        if not hits:
            return []
        return [(start, end) for start, end in hits if end > start]

    def _scroll_to_current_grep_match(self) -> None:
        highlights = self._current_grep_highlights()
        if not highlights:
            return
        local_index = 0
        if self._grep_active and 0 <= self._grep_current_match_index < len(self._grep_match_order):
            page, hit_index = self._grep_match_order[self._grep_current_match_index]
            current_page = self._current_page_number()
            if page == current_page:
                local_index = hit_index
        elif 0 <= self._grep_current_match_index < len(highlights):
            local_index = self._grep_current_match_index
        local_index = max(0, min(local_index, len(highlights) - 1))
        start, _end = highlights[local_index]
        GLib.idle_add(self._scroll_textview_to_offset, start)

    def _apply_page_marker_style(self, buf: Gtk.TextBuffer, text: str) -> None:
        self._append_page_marker_style(buf, text, 0)

    def _apply_rounded_grid_table_no_wrap(self, buf: Gtk.TextBuffer, text: str) -> None:
        self._append_rounded_grid_table_style(buf, text, 0)

    def _apply_table_font_size_to_current_buffer(self) -> None:
        buffers: list[Gtk.TextBuffer] = []
        if self.textview:
            buffers.append(self.textview.get_buffer())
        if self._transcript_breakdown_buffer:
            buffers.append(self._transcript_breakdown_buffer)
        for buf in buffers:
            table = buf.get_tag_table()
            if table is None:
                continue
            tag = table.lookup("rounded-grid-nowrap")
            if tag is None:
                continue
            tag.set_property("size-points", float(self._table_font_size_pt))

    def _append_rounded_grid_table_style(
        self,
        buf: Gtk.TextBuffer,
        text: str,
        start_offset: int,
    ) -> None:
        table = buf.get_tag_table()
        if table is None:
            return
        tag = table.lookup("rounded-grid-nowrap")
        if tag is None:
            tag = buf.create_tag(
                "rounded-grid-nowrap",
                wrap_mode=Gtk.WrapMode.NONE,
                family="monospace",
            )
        tag.set_property("size-points", float(self._table_font_size_pt))
        for start, end in _iter_rounded_grid_table_blocks(text):
            if end <= start:
                continue
            start_iter = buf.get_iter_at_offset(start_offset + start)
            end_iter = buf.get_iter_at_offset(start_offset + end)
            buf.apply_tag(tag, start_iter, end_iter)

    def _append_page_marker_style(
        self,
        buf: Gtk.TextBuffer,
        text: str,
        start_offset: int,
    ) -> None:
        if not text:
            return
        table = buf.get_tag_table()
        if table is None:
            return
        tag = table.lookup("multi-page-marker")
        if tag is None:
            tag = buf.create_tag("multi-page-marker")
        tag.set_property("foreground", PAGE_MARKER_FG_COLOR)
        tag.set_property("paragraph-background", PAGE_MARKER_BG_COLOR)
        tag.set_property("justification", Gtk.Justification.LEFT)
        tag.set_property("left-margin", 14)
        tag.set_property("pixels-above-lines", 6)
        tag.set_property("pixels-below-lines", 5)
        tag.set_property("weight", Pango.Weight.NORMAL)
        tag.set_property("scale", 0.92)
        for match in PAGE_MARKER_LINE_RE.finditer(text):
            start_iter = buf.get_iter_at_offset(start_offset + match.start())
            end_iter = buf.get_iter_at_offset(start_offset + match.end("label"))
            buf.apply_tag(tag, start_iter, end_iter)

    def _apply_markdown_spans(
        self,
        buf: Gtk.TextBuffer,
        spans: list[tuple[int, int, str]],
        base_offset: int = 0,
    ) -> None:
        if not spans:
            return
        table = buf.get_tag_table()
        if table is None:
            return

        def ensure_tag(name: str, **props: object) -> Gtk.TextTag:
            tag = table.lookup(name)
            if tag is None:
                tag = buf.create_tag(name, **props)
            return tag

        bold_tag = ensure_tag("md-bold", weight=Pango.Weight.BOLD)
        italic_tag = ensure_tag("md-italic", style=Pango.Style.ITALIC)
        inline_code_tag = ensure_tag(
            "md-inline-code",
            family="monospace",
            scale=0.95,
        )
        code_block_tag = ensure_tag(
            "md-code-block",
            family="monospace",
            left_margin=AI_BLOCKQUOTE_LEFT_MARGIN,
            right_margin=AI_BLOCKQUOTE_RIGHT_MARGIN,
            pixels_above_lines=AI_BLOCKQUOTE_SPACING_PX,
            pixels_below_lines=AI_BLOCKQUOTE_SPACING_PX,
        )
        strikethrough_tag = ensure_tag("md-strikethrough", strikethrough=True)
        blockquote_tag = ensure_tag(
            "md-blockquote",
            style=Pango.Style.ITALIC,
            left_margin=AI_BLOCKQUOTE_LEFT_MARGIN,
            right_margin=AI_BLOCKQUOTE_RIGHT_MARGIN,
            indent=AI_BLOCKQUOTE_INDENT,
            pixels_above_lines=AI_BLOCKQUOTE_SPACING_PX,
            pixels_below_lines=AI_BLOCKQUOTE_SPACING_PX,
        )
        heading_tags: dict[str, Gtk.TextTag] = {}
        for level, scale in MARKDOWN_HEADING_SCALES.items():
            heading_tags[f"heading{level}"] = ensure_tag(
                f"md-h{level}",
                weight=Pango.Weight.BOLD,
                scale=scale,
            )

        for start, end, kind in spans:
            if end <= start:
                continue
            start_iter = buf.get_iter_at_offset(start + base_offset)
            end_iter = buf.get_iter_at_offset(end + base_offset)
            if kind == "bold":
                buf.apply_tag(bold_tag, start_iter, end_iter)
            elif kind == "italic":
                buf.apply_tag(italic_tag, start_iter, end_iter)
            elif kind == "inline_code":
                buf.apply_tag(inline_code_tag, start_iter, end_iter)
            elif kind == "code_block":
                buf.apply_tag(code_block_tag, start_iter, end_iter)
            elif kind == "strikethrough":
                buf.apply_tag(strikethrough_tag, start_iter, end_iter)
            elif kind == "blockquote":
                buf.apply_tag(blockquote_tag, start_iter, end_iter)
            elif kind.startswith("heading"):
                tag = heading_tags.get(kind)
                if tag is not None:
                    buf.apply_tag(tag, start_iter, end_iter)

    def _map_markdown_offset(self, offset: int, mapping: list[int]) -> int:
        if offset <= 0:
            return 0
        if offset >= len(mapping):
            return mapping[-1] if mapping else 0
        return mapping[offset]

    def _map_markdown_spans(
        self,
        spans: list[tuple[int, int]],
        mapping: list[int],
    ) -> list[tuple[int, int]]:
        mapped: list[tuple[int, int]] = []
        for start, end in spans:
            if end <= start:
                continue
            mapped_start = self._map_markdown_offset(start, mapping)
            mapped_end = self._map_markdown_offset(end, mapping)
            if mapped_end <= mapped_start:
                continue
            mapped.append((mapped_start, mapped_end))
        return mapped

    def _rebuild_toc_sidebar(self) -> None:
        if self._toc_sidebar_root_store is None:
            return
        self._toc_sidebar_root_store.remove_all()
        if not self._toc_categories:
            self._update_sidebar_placeholder(False)
            self._sync_sidebar_active_page()
            return
        for category in self._toc_categories:
            item = FocusSidebarItem.from_category(category)
            self._toc_sidebar_root_store.append(item)
        self._update_sidebar_placeholder(True)
        self._apply_sidebar_expansion_state(self._current_view_state())
        self._sync_sidebar_active_page()

    def _create_sidebar_children_model(self, item: GObject.Object) -> Gio.ListModel | None:
        if isinstance(item, FocusSidebarItem):
            return item.get_children_model()
        return None

    def _create_sidebar_row_for_item(self, obj: GObject.Object, _user_data: object | None = None) -> Gtk.Widget:
        row_widget = Gtk.ListBoxRow()
        row_widget.set_activatable(True)
        row_widget.add_css_class("focus-sidebar-listbox-row")
        row_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=2)
        row_box.add_css_class("focus-sidebar-row")
        row_box.set_hexpand(True)
        row_box.set_valign(Gtk.Align.CENTER)

        active_marker = Gtk.Box()
        active_marker.add_css_class("focus-sidebar-active-marker")
        active_marker.set_size_request(2, -1)
        active_marker.set_valign(Gtk.Align.FILL)
        row_box.append(active_marker)

        arrow_icon = Gtk.Image.new_from_icon_name("pan-end-symbolic")
        arrow_button = Gtk.ToggleButton()
        arrow_button.add_css_class("focus-sidebar-expand-button")
        arrow_button.set_child(arrow_icon)
        arrow_button.set_focus_on_click(False)
        arrow_button.set_valign(Gtk.Align.CENTER)
        arrow_button._focus_list_item = row_widget  # type: ignore[attr-defined]
        arrow_button.connect("toggled", self._on_sidebar_expand_button_toggled)
        row_box.append(arrow_button)

        title_label = Gtk.Label()
        title_label.add_css_class("focus-sidebar-title")
        title_label.set_xalign(0.0)
        title_label.set_hexpand(True)
        title_label.set_single_line_mode(False)
        title_label.set_wrap(True)
        title_label.set_wrap_mode(Pango.WrapMode.WORD_CHAR)
        title_label.set_lines(2)
        title_label.set_ellipsize(Pango.EllipsizeMode.END)
        title_label.set_valign(Gtk.Align.CENTER)
        row_box.append(title_label)

        row_widget.set_child(row_box)
        row_widget._focus_row = row_box  # type: ignore[attr-defined]
        row_widget._focus_title_label = title_label  # type: ignore[attr-defined]
        row_widget._focus_active_marker = active_marker  # type: ignore[attr-defined]
        row_widget._focus_arrow_button = arrow_button  # type: ignore[attr-defined]
        row_widget._focus_arrow_icon = arrow_icon  # type: ignore[attr-defined]
        row_widget._focus_arrow_guard = False  # type: ignore[attr-defined]
        row_widget._focus_tree_row = None  # type: ignore[attr-defined]
        row_widget._focus_tree_handler = None  # type: ignore[attr-defined]
        row_widget.connect("destroy", self._on_sidebar_row_destroy)
        if isinstance(obj, Gtk.TreeListRow):
            self._bind_sidebar_row(row_widget, obj)
        return row_widget

    def _bind_sidebar_row(self, list_row: Gtk.ListBoxRow, tree_row: Gtk.TreeListRow) -> None:
        row_box = getattr(list_row, "_focus_row", None)
        title_label = getattr(list_row, "_focus_title_label", None)
        arrow_button = getattr(list_row, "_focus_arrow_button", None)
        arrow_icon = getattr(list_row, "_focus_arrow_icon", None)
        if (
            not isinstance(row_box, Gtk.Widget)
            or not isinstance(title_label, Gtk.Label)
            or arrow_button is None
            or arrow_icon is None
        ):
            return
        previous_row = getattr(list_row, "_focus_tree_row", None)
        previous_handler = getattr(list_row, "_focus_tree_handler", None)
        if isinstance(previous_row, Gtk.TreeListRow) and isinstance(previous_handler, int):
            try:
                previous_row.disconnect(previous_handler)
            except (TypeError, RuntimeError):
                pass
        list_row._focus_tree_row = tree_row  # type: ignore[attr-defined]
        handler_id = tree_row.connect("notify::expanded", self._on_sidebar_tree_row_expanded, list_row)
        list_row._focus_tree_handler = handler_id  # type: ignore[attr-defined]
        depth = max(tree_row.get_depth(), 0)
        row_box.set_margin_start(depth * SIDEBAR_TREE_INDENT)
        item = tree_row.get_item()
        if not isinstance(item, FocusSidebarItem):
            title_label.set_text("")
            arrow_button.set_visible(False)
            return
        row_box.remove_css_class("focus-sidebar-category")
        row_box.remove_css_class("focus-sidebar-bookmark")
        row_box.remove_css_class("focus-sidebar-category-expanded")
        row_box.remove_css_class("focus-sidebar-category-active")
        row_box.remove_css_class("focus-sidebar-bookmark-active")
        row_box.remove_css_class("focus-sidebar-top-level")
        if item.kind == "category":
            row_box.add_css_class("focus-sidebar-category")
        else:
            row_box.add_css_class("focus-sidebar-bookmark")
        if depth == 0:
            row_box.add_css_class("focus-sidebar-top-level")
        title_label.set_text(item.title)
        self._update_sidebar_row_expand_widgets(list_row, tree_row)
        self._update_sidebar_row_active_state(list_row)

    def _on_sidebar_row_destroy(self, list_row: Gtk.ListBoxRow) -> None:
        tree_row = getattr(list_row, "_focus_tree_row", None)
        handler_id = getattr(list_row, "_focus_tree_handler", None)
        if isinstance(tree_row, Gtk.TreeListRow) and isinstance(handler_id, int):
            try:
                tree_row.disconnect(handler_id)
            except (TypeError, RuntimeError):
                pass
        list_row._focus_tree_row = None  # type: ignore[attr-defined]
        list_row._focus_tree_handler = None  # type: ignore[attr-defined]

    def _on_sidebar_row_activated(self, _list_box: Gtk.ListBox, row: Gtk.ListBoxRow) -> None:
        tree_row = getattr(row, "_focus_tree_row", None)
        if not isinstance(tree_row, Gtk.TreeListRow):
            return
        item = tree_row.get_item()
        if not isinstance(item, FocusSidebarItem):
            return
        if item.kind == "category":
            tree_row.set_expanded(not tree_row.get_expanded())
            return
        self._show_page_from_link(f"{item.page:04d}")

    def _sidebar_item_contains_page(self, item: FocusSidebarItem, page: int) -> bool:
        if item.page == page:
            return True
        children = item.get_children_model()
        if children is None:
            return False
        for index in range(children.get_n_items()):
            child = children.get_item(index)
            if isinstance(child, FocusSidebarItem) and child.page == page:
                return True
        return False

    def _update_sidebar_row_active_state(self, list_row: Gtk.ListBoxRow) -> bool:
        row_box = getattr(list_row, "_focus_row", None)
        tree_row = getattr(list_row, "_focus_tree_row", None)
        if not isinstance(row_box, Gtk.Widget) or not isinstance(tree_row, Gtk.TreeListRow):
            return False
        row_box.remove_css_class("focus-sidebar-bookmark-active")
        row_box.remove_css_class("focus-sidebar-category-active")
        if not self.pages or not (0 <= self.current_index < len(self.pages)):
            return False
        current_page = self.pages[self.current_index]
        item = tree_row.get_item()
        if (
            isinstance(item, FocusSidebarItem)
            and item.kind == "bookmark"
            and item.page == current_page
        ):
            row_box.add_css_class("focus-sidebar-bookmark-active")
            return True
        if (
            isinstance(item, FocusSidebarItem)
            and item.kind == "category"
            and self._sidebar_item_contains_page(item, current_page)
        ):
            row_box.add_css_class("focus-sidebar-category-active")
        return False

    def _sync_sidebar_active_page(self, *, scroll: bool = False) -> None:
        if not self._toc_list_view:
            return
        active_bookmark_row: Gtk.ListBoxRow | None = None
        child = self._toc_list_view.get_first_child()
        while child:
            if isinstance(child, Gtk.ListBoxRow):
                if self._update_sidebar_row_active_state(child):
                    active_bookmark_row = child
            child = child.get_next_sibling()
        if scroll and active_bookmark_row is not None:
            GLib.idle_add(self._scroll_sidebar_row_into_view, active_bookmark_row)

    def _scroll_sidebar_row_into_view(self, row: Gtk.ListBoxRow) -> bool:
        if not self._toc_sidebar_scroller or row.get_parent() is None:
            return False
        vadj = self._toc_sidebar_scroller.get_vadjustment()
        allocation = row.get_allocation()
        row_top = float(allocation.y)
        row_bottom = row_top + float(allocation.height)
        visible_top = vadj.get_value()
        visible_bottom = visible_top + vadj.get_page_size()
        margin = float(SIDEBAR_ACTIVE_SCROLL_MARGIN)

        if row_top < visible_top + margin:
            target = row_top - margin
        elif row_bottom > visible_bottom - margin:
            target = row_bottom + margin - vadj.get_page_size()
        else:
            return False

        lower = vadj.get_lower()
        upper = max(lower, vadj.get_upper() - vadj.get_page_size())
        vadj.set_value(max(lower, min(target, upper)))
        return False

    def _update_sidebar_placeholder(self, has_items: bool) -> None:
        self._toc_sidebar_has_items = has_items
        if self._toc_list_view is not None:
            self._toc_list_view.set_sensitive(has_items)
        if self._toc_placeholder is not None:
            self._toc_placeholder.set_visible(not has_items)

    def _update_sidebar_row_expand_widgets(self, list_row: Gtk.ListBoxRow, tree_row: Gtk.TreeListRow) -> None:
        arrow_button = getattr(list_row, "_focus_arrow_button", None)
        arrow_icon = getattr(list_row, "_focus_arrow_icon", None)
        row = getattr(list_row, "_focus_row", None)
        if arrow_button is None or arrow_icon is None:
            return
        if tree_row.is_expandable():
            arrow_button.set_visible(True)
            arrow_button.set_can_target(True)
            arrow_button.set_opacity(1.0)
            list_row._focus_arrow_guard = True  # type: ignore[attr-defined]
            try:
                arrow_button.set_active(tree_row.get_expanded())
            finally:
                list_row._focus_arrow_guard = False  # type: ignore[attr-defined]
            expanded = tree_row.get_expanded()
            icon_name = "pan-down-symbolic" if expanded else "pan-end-symbolic"
            arrow_icon.set_from_icon_name(icon_name)
            if isinstance(row, Gtk.Widget):
                if expanded:
                    row.add_css_class("focus-sidebar-category-expanded")
                else:
                    row.remove_css_class("focus-sidebar-category-expanded")
        else:
            arrow_button.set_visible(False)
            arrow_button.set_can_target(False)
            if isinstance(row, Gtk.Widget):
                row.remove_css_class("focus-sidebar-category-expanded")

    def _on_sidebar_expand_button_toggled(self, button: Gtk.ToggleButton) -> None:
        list_row = getattr(button, "_focus_list_item", None)
        if list_row is None or getattr(list_row, "_focus_arrow_guard", False):
            return
        tree_row = getattr(list_row, "_focus_tree_row", None)
        arrow_icon = getattr(list_row, "_focus_arrow_icon", None)
        if not isinstance(tree_row, Gtk.TreeListRow):
            return
        tree_row.set_expanded(button.get_active())
        if arrow_icon:
            icon_name = "pan-down-symbolic" if button.get_active() else "pan-end-symbolic"
            arrow_icon.set_from_icon_name(icon_name)

    def _on_sidebar_tree_row_expanded(
        self,
        tree_row: Gtk.TreeListRow,
        _pspec: GObject.ParamSpec,
        list_row: Gtk.ListBoxRow,
    ) -> None:
        self._update_sidebar_row_expand_widgets(list_row, tree_row)
        self._current_view_state().sidebar_expanded = self._get_sidebar_expanded_keys()

    def _sidebar_item_key(self, item: FocusSidebarItem) -> str:
        page = "" if item.page is None else str(item.page)
        return f"{item.title}::{page}"

    def _get_sidebar_expanded_keys(self) -> list[str]:
        if not self._toc_list_view:
            return []
        keys: list[str] = []
        seen: set[str] = set()
        child = self._toc_list_view.get_first_child()
        while child:
            if isinstance(child, Gtk.ListBoxRow):
                tree_row = getattr(child, "_focus_tree_row", None)
                if isinstance(tree_row, Gtk.TreeListRow):
                    item = tree_row.get_item()
                    if (
                        isinstance(item, FocusSidebarItem)
                        and item.kind == "category"
                        and tree_row.get_expanded()
                    ):
                        key = self._sidebar_item_key(item)
                        if key not in seen:
                            seen.add(key)
                            keys.append(key)
            child = child.get_next_sibling()
        return keys

    def _apply_sidebar_expansion_state(self, state: FocusViewState) -> None:
        if not self._toc_list_view:
            return
        desired = set(state.sidebar_expanded)
        rows: list[tuple[Gtk.TreeListRow, FocusSidebarItem]] = []
        child = self._toc_list_view.get_first_child()
        while child:
            if isinstance(child, Gtk.ListBoxRow):
                tree_row = getattr(child, "_focus_tree_row", None)
                if isinstance(tree_row, Gtk.TreeListRow):
                    item = tree_row.get_item()
                    if isinstance(item, FocusSidebarItem) and item.kind == "category":
                        rows.append((tree_row, item))
            child = child.get_next_sibling()
        for tree_row, item in rows:
            should_expand = self._sidebar_item_key(item) in desired
            if tree_row.get_expanded() != should_expand:
                tree_row.set_expanded(should_expand)

    def _set_sidebar_visible(self, visible: bool) -> None:
        self._toc_sidebar_visible = visible
        self._current_view_state().sidebar_visible = visible
        if self._split_view:
            self._split_view.set_collapsed(not visible)
            current_sidebar = (
                self._split_view.get_sidebar() if hasattr(self._split_view, "get_sidebar") else None
            )
            if visible:
                if self._split_sidebar_page and current_sidebar is None:
                    self._split_view.set_sidebar(self._split_sidebar_page)
            else:
                if current_sidebar is not None:
                    self._split_view.set_sidebar(None)
        if self._toc_sidebar_revealer:
            self._toc_sidebar_revealer.set_reveal_child(visible)
        self._sync_sidebar_controls()

    def _sync_sidebar_controls(self) -> None:
        if self._toc_sidebar_button and self._toc_sidebar_button.get_active() != self._toc_sidebar_visible:
            self._sidebar_button_guard = True
            self._toc_sidebar_button.set_active(self._toc_sidebar_visible)
            self._sidebar_button_guard = False
        if self._toc_sidebar_icon:
            self._toc_sidebar_icon.set_from_icon_name("sidebar-show-symbolic")
        if self._toc_sidebar_button:
            tooltip = (
                "Hide TOC sidebar (Ctrl+Shift+Z)"
                if self._toc_sidebar_visible
                else "Show TOC sidebar (Ctrl+Shift+Z)"
            )
            self._toc_sidebar_button.set_tooltip_text(tooltip)
        if self._toc_sidebar_action:
            state = self._toc_sidebar_action.get_state()
            current = state.get_boolean() if state is not None else None
            if current != self._toc_sidebar_visible:
                self._toc_sidebar_action.set_state(GLib.Variant.new_boolean(self._toc_sidebar_visible))

    def _on_sidebar_toggle_button(self, button: Gtk.ToggleButton) -> None:
        if self._sidebar_button_guard:
            return
        self._set_sidebar_visible(button.get_active())

    def _on_stateful_toggle_activate(
        self,
        action: Gio.SimpleAction,
        _param: GLib.Variant | None,
    ) -> None:
        state = action.get_state()
        if state is None or not state.is_of_type(GLib.VariantType.new("b")):
            return
        action.change_state(GLib.Variant.new_boolean(not state.get_boolean()))

    def _on_toggle_toc_sidebar(
        self,
        action: Gio.SimpleAction,
        value: GLib.Variant,
    ) -> None:
        visible = value.get_boolean()
        action.set_state(value)
        self._set_sidebar_visible(visible)

    def _on_toggle_show_image(
        self,
        action: Gio.SimpleAction,
        value: GLib.Variant,
    ) -> None:
        desired = value.get_boolean()
        self._set_show_image(desired)
        action.set_state(GLib.Variant.new_boolean(self._show_image))

    def _on_show_image_button_toggled(self, button: Gtk.ToggleButton) -> None:
        if self._show_image_button_guard:
            return
        desired = button.get_active()
        self._set_show_image(desired)
        self._update_show_image_toggle_button()

    def _apply_text_color(self, color_value: str) -> None:
        self._current_text_color = color_value
        search_chip_color = (
            self._ai_settings.search_chip_color
            if self._ai_settings
            else DEFAULT_SEARCH_CHIP_COLOR
        )
        css = (
            "#page-text { "
            f"color: {PAGE_TEXT_FG_COLOR}; font-size: {self._font_size_pt}pt; "
            f"font-family: {self._record_font_family_css}; "
            "}"
            "textview.ai-output-view { "
            f"color: {color_value}; font-size: {self._ai_font_size_pt}pt; line-height: {AI_OUTPUT_LINE_HEIGHT}; "
            "}"
            "label.focus-search-chip { "
            f"background-color: {search_chip_color}; "
            "}"
            "button.focus-citation-range-active, "
            "button.focus-citation-range-active:hover, "
            "button.focus-citation-range-active:active, "
            "button.focus-minute-order-return-active, "
            "button.focus-minute-order-return-active:hover, "
            "button.focus-minute-order-return-active:active { "
            f"background-color: {search_chip_color}; "
            "color: #1f2937; "
            "}"
            "button.focus-citation-range-active label { "
            "color: #1f2937; "
            "}"
        ).encode()
        try:
            self._color_provider.load_from_data(css)
        except GLib.Error:
            return
        self._ensure_color_provider()

    def _ensure_color_provider(self) -> None:
        if self._css_provider_registered:
            return
        display = Gdk.Display.get_default()
        if not display:
            return
        Gtk.StyleContext.add_provider_for_display(
            display,
            self._color_provider,
            Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION,
        )
        self._css_provider_registered = True

    def _clear_page_links(self, table: Gtk.TextTagTable | None) -> None:
        if table is None:
            return
        for existing_tag in self._link_tags:
            try:
                table.remove(existing_tag)
            except TypeError:
                pass
        self._link_tags.clear()
        self._link_tag_lookup.clear()

    def _ensure_highlight_tag(self) -> Gtk.TextTag | None:
        if not self.textview:
            return None
        buf = self.textview.get_buffer()
        table = buf.get_tag_table()
        color = (
            self._ai_settings.grep_highlight_color
            if self._ai_settings
            else DEFAULT_MATCH_COLOR
        )
        tag = table.lookup("match-highlight") if table is not None else None
        if tag is None:
            tag = buf.create_tag("match-highlight", background=color)
        else:
            tag.set_property("background", color)
        return tag

    def _ensure_keyword_highlight_tag(self) -> Gtk.TextTag | None:
        if not self.textview:
            return None
        buf = self.textview.get_buffer()
        table = buf.get_tag_table()
        color = (
            self._ai_settings.phrase_highlight_color
            if self._ai_settings
            else DEFAULT_HIGHLIGHT_COLOR
        )
        tag = table.lookup("keyword-highlight") if table is not None else None
        if tag is None:
            tag = buf.create_tag("keyword-highlight", background=color)
        else:
            tag.set_property("background", color)
        return tag

    def _apply_keyword_highlights(self, buf: Gtk.TextBuffer, text: str) -> None:
        phrases = self._ai_settings.highlight_phrases if self._ai_settings else []
        if not phrases:
            return
        tag = self._ensure_keyword_highlight_tag()
        if tag is None:
            return
        char_count = buf.get_char_count()
        for phrase in phrases:
            if not phrase:
                continue
            start = 0
            phrase_len = len(phrase)
            while start < len(text):
                idx = text.find(phrase, start)
                if idx == -1:
                    break
                end = idx + phrase_len
                if end <= idx:
                    start = idx + 1
                    continue
                if idx < char_count:
                    end = min(end, char_count)
                    start_iter = buf.get_iter_at_offset(idx)
                    end_iter = buf.get_iter_at_offset(end)
                    buf.apply_tag(tag, start_iter, end_iter)
                start = end

    def _append_page_links(self, buf: Gtk.TextBuffer, text: str, start_offset: int) -> None:
        table = buf.get_tag_table()
        if table is None:
            return
        link_spans: list[tuple[int, int, str]] = []
        for match in PAGE_HEADER_LINE_RE.finditer(text):
            page_str = match.group("num")
            if not page_str:
                continue
            link_spans.append((match.start("num"), match.end("num"), page_str))
        for match in PAGE_MARKER_LINE_RE.finditer(text):
            page_str = match.group("num")
            if not page_str:
                continue
            link_spans.append((match.start("label"), match.end("label"), page_str))
        for start, end, page_str in sorted(link_spans):
            start_iter = buf.get_iter_at_offset(start_offset + start)
            end_iter = buf.get_iter_at_offset(start_offset + end)
            page_tag = buf.create_tag(
                None,
                foreground=PAGE_LINK_COLOR,
                underline=Pango.Underline.SINGLE,
            )
            self._link_tag_lookup[page_tag] = ("page", page_str)
            buf.apply_tag(page_tag, start_iter, end_iter)
            self._link_tags.append(page_tag)

    def _apply_page_links(self, buf: Gtk.TextBuffer, text: str) -> None:
        table = buf.get_tag_table()
        if table is None:
            return
        self._clear_page_links(table)
        self._append_page_links(buf, text, 0)

    def _get_ai_output_state(self, view_name: str) -> AiOutputView:
        state = self._ai_outputs.get(view_name)
        if state is None:
            state = AiOutputView()
            self._ai_outputs[view_name] = state
        return state

    def _build_ai_mode_button(
        self,
        label: str,
        view_name: str,
        tooltip: str,
        icon_names: tuple[str, ...] = (),
    ) -> Gtk.ToggleButton:
        button = Gtk.ToggleButton()
        button.set_child(self._build_labeled_icon(label, *icon_names))
        button.add_css_class("flat")
        button.add_css_class("no-bold")
        button.add_css_class("focus-pill-segment")
        button.set_valign(Gtk.Align.CENTER)
        button.set_tooltip_text(tooltip)
        self._set_accessible_label(button, label)
        button.connect("toggled", self._on_ai_mode_button_toggled, view_name)
        self._ai_view_buttons[view_name] = button
        return button

    def _build_summary_mode_button(
        self,
        label: str,
        source: str,
        tooltip: str,
        icon_names: tuple[str, ...] = (),
    ) -> Gtk.ToggleButton:
        button = Gtk.ToggleButton()
        button.set_child(self._build_labeled_icon(label, *icon_names))
        button.add_css_class("flat")
        button.add_css_class("no-bold")
        button.add_css_class("focus-pill-segment")
        button.set_valign(Gtk.Align.CENTER)
        button.set_tooltip_text(tooltip)
        self._set_accessible_label(button, label)
        button.connect("toggled", self._on_summary_mode_button_toggled, source)
        self._summary_source_buttons[source] = button
        return button

    def _build_agent_subview_button(
        self,
        label: str,
        subview_name: str,
        tooltip: str,
    ) -> Gtk.ToggleButton:
        button = Gtk.ToggleButton(label=label)
        button.add_css_class("flat")
        button.add_css_class("no-bold")
        button.add_css_class("focus-pill-segment")
        button.set_valign(Gtk.Align.CENTER)
        button.set_tooltip_text(tooltip)
        button.connect("toggled", self._on_agent_subview_button_toggled, subview_name)
        return button

    def _agent_session_has_content(self) -> bool:
        return bool(self._agent_terminal_active or Vte is None)

    def _agent_trace_source(self) -> Path | None:
        """Return the current run's session JSONL: live first, then preserved."""
        workspace = self._agent_workspace_path
        if workspace is not None:
            live = find_latest_pi_session_log_for_cwd(
                workspace / "pi-sessions",
                workspace,
            )
            if live is not None and live.is_file():
                return live
        preserved = self._agent_session_preserve_path
        if preserved is not None and preserved.is_file():
            return preserved
        return None

    def _reset_agent_trace_state(self) -> None:
        """Drop the previous run's trace references before a new Agent launch."""
        previous = self._agent_session_preserve_path
        if previous is not None:
            try:
                previous.unlink(missing_ok=True)
            except OSError:
                pass
        self._agent_session_log_path = None
        self._agent_session_preserve_path = None

    def _resync_agent_trace_after_exit(self) -> bool:
        """One-shot post-exit resync; the wrapper preserves the trace on exit."""
        if not self._agent_terminal_active:
            self._sync_agent_output_header_state()
        return False

    def _agent_answer_has_content(self) -> bool:
        state = self._ai_outputs.get(AI_VIEW_AGENT_QA)
        return bool(
            self._agent_last_answer_text.strip()
            or (state is not None and state.raw.strip())
        )

    def _sync_agent_output_header_state(self) -> None:
        has_answer = self._agent_answer_has_content()
        has_session = self._agent_session_has_content()
        has_trace = self._agent_trace_source() is not None
        if self._agent_output_header:
            self._agent_output_header.set_visible(has_answer or has_session or has_trace)
        if self._agent_answer_button:
            self._agent_answer_button.set_sensitive(has_answer)
        if self._agent_session_button:
            self._agent_session_button.set_sensitive(has_session)
        if self._agent_copy_trace_button:
            self._agent_copy_trace_button.set_sensitive(has_trace)

    def _sync_agent_session_widget_visibility(self) -> None:
        if self._agent_session_widget:
            show_session = (
                self._agent_subview_name == AGENT_SUBVIEW_SESSION
                and self._agent_session_has_content()
            )
            self._agent_session_widget.set_visible(show_session)
            if show_session and self._agent_terminal_active:
                self._agent_session_widget.set_size_request(-1, 260)
            else:
                self._agent_session_widget.set_size_request(-1, -1)
        self._sync_agent_output_header_state()

    def _set_agent_subview(self, subview_name: str) -> None:
        target = (
            subview_name
            if subview_name in {AGENT_SUBVIEW_ANSWER, AGENT_SUBVIEW_SESSION}
            else AGENT_SUBVIEW_SESSION
        )
        self._agent_subview_name = target
        if self._agent_answer_scroller:
            self._agent_answer_scroller.set_visible(target == AGENT_SUBVIEW_ANSWER)
            if target == AGENT_SUBVIEW_ANSWER:
                self._agent_answer_scroller.set_min_content_height(
                    EMBEDDED_AI_OUTPUT_MIN_HEIGHT
                )
                self._agent_answer_scroller.set_max_content_height(AI_OUTPUT_MAX_HEIGHT)
        self._sync_agent_session_widget_visibility()
        self._agent_subview_toggle_guard = True
        try:
            for name, button in (
                (AGENT_SUBVIEW_ANSWER, self._agent_answer_button),
                (AGENT_SUBVIEW_SESSION, self._agent_session_button),
            ):
                if not button:
                    continue
                active = name == target
                button.set_active(active)
                if active:
                    button.add_css_class("focus-ai-view-active")
                else:
                    button.remove_css_class("focus-ai-view-active")
        finally:
            self._agent_subview_toggle_guard = False
        if self._ai_panel_revealer and self._ai_panel_revealer.get_reveal_child():
            self._update_embedded_ai_panel_height(force=True)
        self._refresh_search_highlighted_button()

    def _on_agent_subview_button_toggled(
        self,
        button: Gtk.ToggleButton,
        subview_name: str,
    ) -> None:
        if self._agent_subview_toggle_guard:
            return
        if not button.get_active():
            if self._agent_subview_name == subview_name:
                self._set_agent_subview(subview_name)
            return
        self._set_agent_subview(subview_name)

    def _build_wrapping_controls_box(self) -> Gtk.FlowBox:
        box = Gtk.FlowBox()
        box.set_selection_mode(Gtk.SelectionMode.NONE)
        box.set_valign(Gtk.Align.CENTER)
        box.set_halign(Gtk.Align.FILL)
        box.set_hexpand(True)
        box.set_min_children_per_line(1)
        box.set_max_children_per_line(32)
        box.set_row_spacing(6)
        box.set_column_spacing(6)
        return box

    def _sum_page_display_label(self, page: int) -> str:
        label = self._transcript_page_index.by_file_page.get(page)
        if label:
            return label.citation_label
        return str(page)

    def _set_sum_range_fields(self, start_page: int, end_page: int, *, autofilled: bool) -> None:
        if not self._ai_range_start_entry or not self._ai_range_end_entry:
            return
        self._ai_range_update_guard = True
        try:
            self._ai_range_start_entry.set_text(self._sum_page_display_label(start_page))
            self._ai_range_end_entry.set_text(self._sum_page_display_label(end_page))
        finally:
            self._ai_range_update_guard = False
        self._ai_range_autofilled = autofilled
        state = self._current_view_state()
        state.ai_range_start_text = self._ai_range_start_entry.get_text()
        state.ai_range_end_text = self._ai_range_end_entry.get_text()
        state.ai_range_autofilled = autofilled

    def _sum_range_fields_empty(self) -> bool:
        start_text = self._ai_range_start_entry.get_text().strip() if self._ai_range_start_entry else ""
        end_text = self._ai_range_end_entry.get_text().strip() if self._ai_range_end_entry else ""
        return not start_text and not end_text

    def _current_page_number(self) -> int | None:
        if not self.pages or self.current_index < 0 or self.current_index >= len(self.pages):
            return None
        return self.pages[self.current_index]

    def _current_transcript_page_label(self) -> TranscriptPageLabel | None:
        current_page = self._current_page_number()
        if current_page is None:
            return None
        return self._transcript_page_index.by_file_page.get(current_page)

    def _current_minute_order_boundary(self) -> RecordBoundary | None:
        current_page = self._current_page_number()
        if current_page is None:
            return None
        boundary = find_minute_order_boundary_for_transcript_page(
            current_page,
            self._transcript_page_index,
            self._hearing_boundaries,
            self._minute_boundaries,
        )
        if boundary is None or boundary.start_page not in self.page_to_path:
            return None
        return boundary

    def _viewing_return_minute_order(self) -> bool:
        current_page = self._current_page_number()
        return should_show_minute_order_return(
            current_page,
            self._minute_order_return_page,
            self._minute_order_return_boundary,
        )

    def _sync_minute_order_return_state(self) -> None:
        if self._minute_order_return_page is None:
            return
        if self._viewing_return_minute_order():
            return
        self._minute_order_return_page = None
        self._minute_order_return_boundary = None

    def _refresh_minute_order_button(self) -> None:
        if not self._minute_order_button:
            return
        self._sync_minute_order_return_state()
        if self._viewing_return_minute_order():
            self._minute_order_button.set_visible(True)
            self._minute_order_button.set_child(
                self._build_header_icon("go-previous-symbolic", "edit-undo-symbolic")
            )
            self._minute_order_button.set_tooltip_text(
                "Return to the RT page you came from (Ctrl+Shift+M)"
            )
            self._minute_order_button.set_sensitive(True)
            self._minute_order_button.add_css_class("focus-minute-order-return-active")
            return

        target = self._current_minute_order_boundary()
        self._minute_order_button.set_visible(target is not None)
        self._minute_order_button.remove_css_class("focus-minute-order-return-active")
        self._minute_order_button.set_child(
            self._build_header_icon("text-x-generic-symbolic", "document-open-symbolic")
        )
        self._minute_order_button.set_tooltip_text(
            "Open the minute order for this RT page (Ctrl+Shift+M)"
        )
        self._minute_order_button.set_sensitive(target is not None)

    def _refresh_record_boundary_date_label(self) -> None:
        if not self._record_boundary_date_label:
            return
        date_text = record_boundary_date_for_page(
            self._current_page_number(),
            self._hearing_boundaries,
            self._minute_boundaries,
        )
        self._record_boundary_date_label.set_text(date_text)
        self._record_boundary_date_label.set_visible(bool(date_text))
        self._record_boundary_date_label.set_tooltip_text(
            f"Boundary date: {date_text}" if date_text else "Boundary date"
        )

    def _current_page_entry_text(self) -> str:
        current_page = self._current_page_number()
        entry_text, _detail_text = format_page_nav_labels(
            current_page,
            len(self.pages),
            self._transcript_page_index,
        )
        return entry_text

    def _maybe_prefill_sum_range_for_current_page(self) -> None:
        if not self._ai_range_start_entry or not self._ai_range_end_entry:
            return
        if not self.pages:
            self._refresh_sum_range_state()
            return
        if not self._ai_range_autofilled and not self._sum_range_fields_empty():
            self._refresh_sum_range_state()
            return
        current_page = self._current_page_number()
        if current_page is None:
            self._refresh_sum_range_state()
            return
        self._set_sum_range_fields(current_page, current_page, autofilled=True)
        self._refresh_sum_range_state(status="Current page")

    def _sum_range_validation(self) -> SumRangeValidation:
        start_text = self._ai_range_start_entry.get_text() if self._ai_range_start_entry else ""
        end_text = self._ai_range_end_entry.get_text() if self._ai_range_end_entry else ""
        return validate_sum_page_fields(
            start_text,
            end_text,
            self.pages,
            self._transcript_page_index,
            self._current_page_number(),
        )

    def _refresh_sum_range_state(self, *, status: str | None = None) -> None:
        validation = self._sum_range_validation()
        if self._ai_range_status_label:
            if status and validation.valid:
                text = f"{status} - {len(validation.targets)} pages"
            else:
                text = validation.message
            self._ai_range_status_label.set_text(text)

    def _on_sum_range_field_changed(self, _entry: Gtk.Entry) -> None:
        if not self._ai_range_update_guard:
            self._ai_range_autofilled = False
            self._current_view_state().ai_range_autofilled = False
        self._refresh_sum_range_state()

    def _build_ai_output_view(self, view_name: str) -> Gtk.ScrolledWindow:
        state = self._get_ai_output_state(view_name)
        text_view = Gtk.TextView(
            editable=False,
            monospace=False,
            wrap_mode=Gtk.WrapMode.WORD_CHAR,
        )
        text_view.add_css_class("ai-output-view")
        text_view.set_hexpand(True)
        text_view.set_vexpand(True)
        text_view.set_top_margin(6)
        text_view.set_bottom_margin(6)
        text_view.set_left_margin(6)
        text_view.set_right_margin(6)
        text_view.set_cursor_visible(False)
        text_view.connect("map", self._on_ai_output_view_mapped, view_name)
        state.view = text_view
        state.buffer = text_view.get_buffer()
        state.buffer.connect(
            "notify::has-selection",
            self._on_search_selection_changed,
        )
        self._install_ai_output_link_controllers(state)

        scroller = Gtk.ScrolledWindow()
        scroller.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.AUTOMATIC)
        scroller.set_hexpand(True)
        scroller.set_vexpand(True)
        scroller.set_propagate_natural_height(True)
        scroller.set_min_content_height(EMBEDDED_AI_OUTPUT_MIN_HEIGHT)
        scroller.set_max_content_height(AI_OUTPUT_MAX_HEIGHT)
        scroller.set_child(text_view)
        state.scroller = scroller
        self._ai_output_scrollers.append(scroller)
        return scroller

    @staticmethod
    def _json_safe_value(value: Any) -> Any:
        if value is None or isinstance(value, (str, int, float, bool)):
            return value
        if isinstance(value, Path):
            return str(value)
        if isinstance(value, dict):
            safe: dict[str, Any] = {}
            for key, item in value.items():
                safe[str(key)] = Focus._json_safe_value(item)
            return safe
        if isinstance(value, (list, tuple, set)):
            return [Focus._json_safe_value(item) for item in value]
        return str(value)

    @staticmethod
    def _rgba_luminance(color: Gdk.RGBA) -> float:
        return (
            (0.2126 * color.red)
            + (0.7152 * color.green)
            + (0.0722 * color.blue)
        )

    def _resolve_ai_quote_color(self, view: Gtk.TextView | None) -> Gdk.RGBA:
        dark = Adw.StyleManager.get_default().get_dark()
        fallback = Gdk.RGBA()
        fallback.parse("#f2f4f8" if dark else "#30343b")
        base = fallback
        if view:
            if hasattr(view, "get_color"):
                candidate = view.get_color()
            else:
                context = view.get_style_context()
                try:
                    candidate = context.get_color()
                except TypeError:
                    candidate = context.get_color(Gtk.StateFlags.NORMAL)
            luminance = self._rgba_luminance(candidate)
            if (dark and luminance >= 0.5) or (not dark and luminance < 0.5):
                base = candidate
        quote = Gdk.RGBA()
        quote.red = base.red
        quote.green = base.green
        quote.blue = base.blue
        quote.alpha = DEFAULT_QUOTED_PHRASE_ALPHA
        return quote

    @staticmethod
    def _adjust_summary_emphasis_for_theme(
        accent: Gdk.RGBA,
        *,
        dark: bool,
    ) -> Gdk.RGBA:
        luminance = Focus._rgba_luminance(accent)
        if not dark and luminance > 0.58:
            scale = 0.58 / luminance
            accent.red *= scale
            accent.green *= scale
            accent.blue *= scale
        elif dark and luminance < 0.52:
            blend = min(1.0, (0.52 - luminance) / max(0.001, 1.0 - luminance))
            accent.red += (1.0 - accent.red) * blend
            accent.green += (1.0 - accent.green) * blend
            accent.blue += (1.0 - accent.blue) * blend
        return accent

    def _resolve_summary_emphasis_color(self) -> Gdk.RGBA:
        accent = Gdk.RGBA()
        configured = (
            self._ai_settings.summary_emphasis_color
            if self._ai_settings
            else DEFAULT_SUMMARY_EMPHASIS_COLOR
        )
        if not accent.parse(configured):
            accent.parse(DEFAULT_SUMMARY_EMPHASIS_COLOR)
        return self._adjust_summary_emphasis_for_theme(
            accent,
            dark=Adw.StyleManager.get_default().get_dark(),
        )

    def _apply_summary_emphasis(
        self,
        text: str,
        source: str | None,
        buffer: Gtk.TextBuffer | None,
        page_offset_map: list[int],
        markdown_offset_map: list[int],
    ) -> None:
        if not buffer:
            return
        spans = _extract_summary_emphasis_spans(text, source)
        if not spans:
            return
        table = buffer.get_tag_table()
        if table is None:
            return
        tag = table.lookup("summary-entry-emphasis")
        accent_color = self._resolve_summary_emphasis_color()
        if tag is None:
            tag = buffer.create_tag(
                "summary-entry-emphasis",
                foreground_rgba=accent_color,
                weight=Pango.Weight.BOLD,
                scale=1.08,
            )
        else:
            tag.set_property("foreground-rgba", accent_color)
            tag.set_property("weight", Pango.Weight.BOLD)
            tag.set_property("scale", 1.08)

        for start, end in spans:
            if end <= start:
                continue
            start = self._map_markdown_offset(start, page_offset_map)
            end = self._map_markdown_offset(end, page_offset_map)
            if end <= start:
                continue
            start = self._map_markdown_offset(start, markdown_offset_map)
            end = self._map_markdown_offset(end, markdown_offset_map)
            if end <= start:
                continue
            start_iter = buffer.get_iter_at_offset(start)
            end_iter = buffer.get_iter_at_offset(end)
            buffer.apply_tag(tag, start_iter, end_iter)

    def _apply_link_spans(
        self,
        text: str,
        buffer: Gtk.TextBuffer | None,
        link_tags: list[Gtk.TextTag],
        link_lookup: dict[Gtk.TextTag, tuple[str, str]],
        scroller: Gtk.ScrolledWindow | None,
    ) -> None:
        if not buffer:
            return
        table = buffer.get_tag_table()
        if table is None:
            return
        for tag in link_tags:
            try:
                table.remove(tag)
            except TypeError:
                pass
        link_tags.clear()
        link_lookup.clear()

        rendered_text, phrase_spans = self._extract_ai_link_spans(text)
        summary_match_text = rendered_text
        rendered_text, page_spans, phrase_to_page_map = self._extract_markdown_page_link_spans(
            rendered_text
        )
        mapped_phrase_spans: list[tuple[int, int, str]] = []
        for start, end, phrase in phrase_spans:
            mapped_start = self._map_markdown_offset(start, phrase_to_page_map)
            mapped_end = self._map_markdown_offset(end, phrase_to_page_map)
            if mapped_end <= mapped_start:
                continue
            mapped_phrase_spans.append((mapped_start, mapped_end, phrase))

        rendered_text, markdown_spans, orig_to_clean = _render_markdown_text(rendered_text)
        buffer.set_text(rendered_text)
        self._apply_markdown_spans(buffer, markdown_spans)
        if buffer is self._summary_buffer:
            summary_source = self._summary_active_source
            if summary_source is None and self._summary_loaded_path is not None:
                summary_source = self._infer_summary_source(self._summary_loaded_path)
            self._apply_summary_emphasis(
                summary_match_text,
                summary_source,
                buffer,
                phrase_to_page_map,
                orig_to_clean,
            )

        quote_color = self._resolve_ai_quote_color(
            self._summary_view if buffer is self._summary_buffer else None
        )
        if buffer is not self._summary_buffer:
            for state in self._ai_outputs.values():
                if state.buffer is buffer:
                    quote_color = self._resolve_ai_quote_color(state.view)
                    break
        for start, end, phrase in mapped_phrase_spans:
            if end <= start:
                continue
            start = self._map_markdown_offset(start, orig_to_clean)
            end = self._map_markdown_offset(end, orig_to_clean)
            if end <= start:
                continue
            start_iter = buffer.get_iter_at_offset(start)
            end_iter = buffer.get_iter_at_offset(end)
            tag = buffer.create_tag(
                None,
                foreground_rgba=quote_color,
                underline=Pango.Underline.NONE,
                weight=Pango.Weight.MEDIUM,
            )
            link_lookup[tag] = ("phrase", phrase)
            buffer.apply_tag(tag, start_iter, end_iter)
            link_tags.append(tag)

        for start, end, page_str in page_spans:
            if end <= start:
                continue
            start = self._map_markdown_offset(start, orig_to_clean)
            end = self._map_markdown_offset(end, orig_to_clean)
            if end <= start:
                continue
            start_iter = buffer.get_iter_at_offset(start)
            end_iter = buffer.get_iter_at_offset(end)
            page_link_color = Gdk.RGBA()
            brighten = 0.18
            page_link_color.red = min(1.0, quote_color.red + brighten)
            page_link_color.green = min(1.0, quote_color.green + brighten)
            page_link_color.blue = min(1.0, quote_color.blue + brighten)
            page_link_color.alpha = 1.0
            tag = buffer.create_tag(
                None,
                foreground_rgba=page_link_color,
                underline=Pango.Underline.NONE,
            )
            link_lookup[tag] = ("page", page_str)
            buffer.apply_tag(tag, start_iter, end_iter)
            link_tags.append(tag)
        if scroller:
            scroller.queue_resize()

    def _apply_ai_output_links(self, text: str, state: AiOutputView) -> None:
        self._apply_link_spans(text, state.buffer, state.link_tags, state.link_lookup, state.scroller)

    def _apply_summary_links(self, text: str) -> None:
        self._apply_link_spans(
            text,
            self._summary_buffer,
            self._summary_link_tags,
            self._summary_link_tag_lookup,
            self._summary_scroller,
        )

    def _refresh_ai_quote_colors(self) -> None:
        if self._summary_view and self._summary_raw:
            self._apply_summary_links(self._summary_raw)
        for state in self._ai_outputs.values():
            if state.raw:
                self._apply_ai_output_links(state.raw, state)

    def _on_color_scheme_changed(self, *_args: object) -> None:
        GLib.idle_add(self._refresh_ai_quote_colors_idle)

    def _refresh_ai_quote_colors_idle(self) -> bool:
        self._refresh_ai_quote_colors()
        return False

    def _on_ai_output_view_mapped(self, _view: Gtk.TextView, view_name: str) -> None:
        state = self._ai_outputs.get(view_name)
        if not state or not state.raw:
            return
        self._apply_ai_output_links(state.raw, state)

    def _on_summary_view_mapped(self, _view: Gtk.TextView) -> None:
        if not self._summary_raw:
            return
        self._apply_summary_links(self._summary_raw)
        if self._summary_loaded_path:
            self._restore_summary_position(self._summary_loaded_path)

    def _extract_ai_link_spans(self, text: str) -> tuple[str, list[tuple[int, int, str]]]:
        spans: list[tuple[int, int, str]] = []
        parts: list[str] = []
        cursor = 0
        offset = 0
        for match in AI_LINK_SPAN_RE.finditer(text):
            start, end = match.span()
            before = text[cursor:start]
            parts.append(before)
            offset += len(before)
            phrase = (match.group(1) or match.group(2) or "").strip()
            if phrase:
                link_phrase, trailing = split_link_phrase(phrase)
                if link_phrase:
                    parts.append(link_phrase)
                    spans.append((offset, offset + len(link_phrase), link_phrase))
                    offset += len(link_phrase)
                if trailing:
                    parts.append(trailing)
                    offset += len(trailing)
            cursor = end
        parts.append(text[cursor:])
        return "".join(parts), spans

    def _extract_markdown_page_link_spans(
        self,
        text: str,
    ) -> tuple[str, list[tuple[int, int, str]], list[int]]:
        spans: list[tuple[int, int, str]] = []
        parts: list[str] = []
        orig_to_clean = [0] * (len(text) + 1)
        cursor = 0
        clean_offset = 0

        for match in MARKDOWN_PAGE_LINK_RE.finditer(text):
            start, end = match.span()
            if start > cursor:
                before = text[cursor:start]
                parts.append(before)
                for idx in range(cursor, start):
                    orig_to_clean[idx] = clean_offset + (idx - cursor)
                clean_offset += len(before)

            label = (match.group("label") or "").strip()
            page_str = (match.group("page") or "").strip()
            page_value = page_str.zfill(4) if page_str else ""
            link_label = label or f"page {page_value}" if page_value else label

            span_start = clean_offset
            if link_label:
                parts.append(link_label)
                clean_offset += len(link_label)
                spans.append((span_start, clean_offset, page_value))

            for idx in range(start, end):
                orig_to_clean[idx] = span_start
            orig_to_clean[end] = clean_offset
            cursor = end

        if cursor < len(text):
            tail = text[cursor:]
            parts.append(tail)
            for idx in range(cursor, len(text)):
                orig_to_clean[idx] = clean_offset + (idx - cursor)
            clean_offset += len(tail)

        orig_to_clean[len(text)] = clean_offset
        return "".join(parts), spans, orig_to_clean

    def _install_textview_link_controllers(self) -> None:
        if not self.textview:
            return
        if not self._textview_motion_controller:
            motion = Gtk.EventControllerMotion()
            motion.connect("motion", self._on_textview_motion)
            motion.connect("enter", self._on_textview_motion)
            motion.connect("leave", self._on_textview_leave)
            self.textview.add_controller(motion)
            self._textview_motion_controller = motion
        if not self._textview_click_gesture:
            click = Gtk.GestureClick.new()
            click.set_button(Gdk.BUTTON_PRIMARY)
            click.connect("released", self._on_textview_click)
            self.textview.add_controller(click)
            self._textview_click_gesture = click
        if not self._textview_focus_controller:
            focus_controller = Gtk.EventControllerFocus()
            focus_controller.connect("enter", self._on_textview_focus_enter)
            focus_controller.connect("leave", self._on_textview_focus_leave)
            self.textview.add_controller(focus_controller)
            self._textview_focus_controller = focus_controller

    def _on_textview_focus_enter(self, _controller: Gtk.EventControllerFocus) -> None:
        if self.textview:
            self.textview.set_cursor_visible(False)

    def _on_textview_focus_leave(self, _controller: Gtk.EventControllerFocus) -> None:
        if self.textview:
            self.textview.set_cursor_visible(False)

    def _on_textview_motion(
        self,
        _controller: Gtk.EventControllerMotion,
        x: float,
        y: float,
    ) -> None:
        if not self.textview:
            return
        link = self._link_at_coords(self.textview, x, y)
        if link:
            self.textview.set_cursor_from_name("pointer")
        else:
            self.textview.set_cursor_from_name(None)

    def _sync_right_scroll_zone_geometry(
        self, width: int, height: int
    ) -> tuple[float, float, float, float]:
        right = max(0.0, float(width))
        left = 0.0
        top = 0.0
        bottom = max(0.0, float(height))

        if self._right_scroll_zone:
            zone_width = IMAGE_PREVIEW_RAIL_WIDTH
            if right > 0:
                zone_width = min(zone_width, max(1, int(round(right))))
            self._right_scroll_zone.set_size_request(zone_width, -1)
            self._right_scroll_zone.set_margin_start(0)
            self._right_scroll_zone.set_margin_top(RIGHT_SCROLL_ZONE_EDGE_MARGIN)
            self._right_scroll_zone.set_margin_bottom(RIGHT_SCROLL_ZONE_EDGE_MARGIN)
            self._right_scroll_zone.set_margin_end(0)
        return left, right, top, bottom

    def _refresh_right_scroll_zone_geometry(self) -> bool:
        if self._image_preview_rail:
            self._sync_right_scroll_zone_geometry(
                self._image_preview_rail.get_width(),
                self._image_preview_rail.get_height(),
            )
            return False
        if not self.textview:
            return False
        self._sync_right_scroll_zone_geometry(self.textview.get_width(), self.textview.get_height())
        return False

    def _on_textview_leave(self, _controller: Gtk.EventControllerMotion) -> None:
        if self.textview:
            self.textview.set_cursor_from_name(None)
        self._set_right_scroll_active(False)

    def _on_textview_click(
        self,
        gesture: Gtk.GestureClick,
        _n_press: int,
        x: float,
        y: float,
    ) -> None:
        button = gesture.get_current_button()
        if button and button != Gdk.BUTTON_PRIMARY:
            return
        if not self.textview:
            return
        self.textview.grab_focus()
        self.textview.set_cursor_visible(False)
        link = self._link_at_coords(self.textview, x, y)
        if link is None:
            return
        kind, value = link
        if kind == "page":
            self._show_page_from_link(value)

    def _install_ai_output_link_controllers(self, state: AiOutputView) -> None:
        view = state.view
        if not view:
            return
        if not state.motion_controller:
            motion = Gtk.EventControllerMotion()
            motion.connect("motion", self._on_ai_output_motion, view, state.link_lookup)
            motion.connect("enter", self._on_ai_output_motion, view, state.link_lookup)
            motion.connect("leave", self._on_ai_output_leave, view)
            view.add_controller(motion)
            state.motion_controller = motion
        if not state.click_gesture:
            click = Gtk.GestureClick.new()
            click.set_button(Gdk.BUTTON_PRIMARY)
            click.connect("released", self._on_ai_output_click, view, state.link_lookup)
            view.add_controller(click)
            state.click_gesture = click
        if not state.focus_controller:
            focus_controller = Gtk.EventControllerFocus()
            focus_controller.connect("enter", self._ai_output_focus_enter, view)
            focus_controller.connect("leave", self._ai_output_focus_leave, view)
            view.add_controller(focus_controller)
            state.focus_controller = focus_controller

    def _ai_output_focus_enter(self, _controller: Gtk.EventControllerFocus, view: Gtk.TextView) -> None:
        view.set_cursor_visible(False)

    def _ai_output_focus_leave(self, _controller: Gtk.EventControllerFocus, view: Gtk.TextView) -> None:
        view.set_cursor_visible(False)

    def _ai_link_at_coords(
        self,
        textview: Gtk.TextView,
        x: float,
        y: float,
        lookup: dict[Gtk.TextTag, tuple[str, str]],
    ) -> tuple[str, str] | None:
        bx, by = textview.window_to_buffer_coords(Gtk.TextWindowType.WIDGET, int(x), int(y))
        iter_result = textview.get_iter_at_location(int(bx), int(by))
        if isinstance(iter_result, tuple):
            success, iter_ = iter_result
            if not success:
                return None
        else:
            iter_ = iter_result
        if iter_ is None:
            return None
        for tag in iter_.get_tags():
            link = lookup.get(tag)
            if link is not None:
                return link
        return None

    def _on_ai_output_motion(
        self,
        _controller: Gtk.EventControllerMotion,
        x: float,
        y: float,
        view: Gtk.TextView,
        lookup: dict[Gtk.TextTag, tuple[str, str]],
    ) -> None:
        link = self._ai_link_at_coords(view, x, y, lookup)
        if link:
            view.set_cursor_from_name("pointer")
        else:
            view.set_cursor_from_name(None)

    def _on_ai_output_leave(self, _controller: Gtk.EventControllerMotion, view: Gtk.TextView) -> None:
        view.set_cursor_from_name(None)

    def _on_ai_output_click(
        self,
        gesture: Gtk.GestureClick,
        _n_press: int,
        x: float,
        y: float,
        view: Gtk.TextView,
        lookup: dict[Gtk.TextTag, tuple[str, str]],
    ) -> None:
        button = gesture.get_current_button()
        if button and button != Gdk.BUTTON_PRIMARY:
            return
        view.grab_focus()
        view.set_cursor_visible(False)
        link = self._ai_link_at_coords(view, x, y, lookup)
        if not link:
            return
        self._activate_link(link)

    def _install_summary_link_controllers(self) -> None:
        if not self._summary_view:
            return
        if not self._summary_motion_controller:
            motion = Gtk.EventControllerMotion()
            motion.connect("motion", self._on_summary_motion)
            motion.connect("enter", self._on_summary_motion)
            motion.connect("leave", self._on_summary_leave)
            self._summary_view.add_controller(motion)
            self._summary_motion_controller = motion
        if not self._summary_click_gesture:
            click = Gtk.GestureClick.new()
            click.set_button(Gdk.BUTTON_PRIMARY)
            click.connect("released", self._on_summary_click)
            self._summary_view.add_controller(click)
            self._summary_click_gesture = click
        if not self._summary_focus_controller:
            focus_controller = Gtk.EventControllerFocus()
            focus_controller.connect("enter", self._summary_focus_enter)
            focus_controller.connect("leave", self._summary_focus_leave)
            self._summary_view.add_controller(focus_controller)
            self._summary_focus_controller = focus_controller

    def _summary_focus_enter(self, _controller: Gtk.EventControllerFocus) -> None:
        if self._summary_view:
            self._summary_view.set_cursor_visible(False)

    def _summary_focus_leave(self, _controller: Gtk.EventControllerFocus) -> None:
        if self._summary_view:
            self._summary_view.set_cursor_visible(False)

    def _on_summary_search_changed(self, entry: Gtk.SearchEntry) -> None:
        query = entry.get_text().strip()
        if query == self._summary_search_query:
            return
        self._summary_search_query = query
        self._refresh_summary_search(reset_active=True)

    def _on_summary_search_activate(self, entry: Gtk.SearchEntry) -> None:
        query = entry.get_text().strip()
        if query != self._summary_search_query:
            self._summary_search_query = query
            self._refresh_summary_search(reset_active=True)
        if not self._summary_search_matches:
            if query:
                self._transient_toast("No matches found in the file.")
            return
        if self._summary_search_index < 0:
            self._summary_search_index = 0
        else:
            self._summary_search_index = (self._summary_search_index + 1) % len(self._summary_search_matches)
        self._apply_summary_search_highlights()
        self._scroll_to_summary_match(self._summary_search_index)

    def _refresh_summary_search(self, *, reset_active: bool = False) -> None:
        if reset_active:
            self._summary_search_index = -1
        self._update_summary_search_matches()

    def _ensure_summary_search_tags(self) -> None:
        if not self._summary_buffer:
            return
        table = self._summary_buffer.get_tag_table()
        if table is None:
            return
        if self._summary_search_tag is None:
            tag = table.lookup("summary-search-match")
            if tag is None:
                tag = self._summary_buffer.create_tag(
                    "summary-search-match",
                    background="#f7dcc3",
                    foreground="#3f2b1a",
                )
            self._summary_search_tag = tag
        if self._summary_search_current_tag is None:
            tag = table.lookup("summary-search-current")
            if tag is None:
                tag = self._summary_buffer.create_tag(
                    "summary-search-current",
                    background="#f4b26b",
                    foreground="#2b1600",
                )
            self._summary_search_current_tag = tag
        if self._summary_search_current_tag is not None:
            self._summary_search_current_tag.set_property("background", "#f4b26b")

    def _clear_summary_search_tags(self) -> None:
        if not self._summary_buffer:
            return
        start = self._summary_buffer.get_start_iter()
        end = self._summary_buffer.get_end_iter()
        if self._summary_search_tag:
            self._summary_buffer.remove_tag(self._summary_search_tag, start, end)
        if self._summary_search_current_tag:
            self._summary_buffer.remove_tag(self._summary_search_current_tag, start, end)

    def _summary_page_search_text(self, text: str) -> str:
        """Render summary text exactly as the summary buffer displays it."""
        rendered, _phrase_spans = self._extract_ai_link_spans(text)
        rendered, _page_spans, _phrase_map = self._extract_markdown_page_link_spans(
            rendered
        )
        rendered, _markdown_spans, _orig_to_clean = _render_markdown_text(rendered)
        return rendered

    def _update_summary_search_matches(self) -> None:
        if not self._summary_buffer:
            return
        self._summary_search_matches = []
        self._clear_summary_search_tags()
        query = self._summary_search_query
        if not query:
            return
        if self._summary_is_paged():
            # Search every paper page in document order; paper page boundaries
            # are search boundaries. Match against exactly the text the
            # buffer displays so offsets align with rendered highlights.
            assert self._summary_edition is not None
            self._summary_search_matches = search_pages(
                self._summary_edition,
                query,
                render=lambda _edition, page_number: (
                    self._summary_page_search_text(
                        with_paragraph_spacing(
                            render_page_text(self._summary_edition, page_number)
                        )
                    )
                ),
            )
        else:
            start = self._summary_buffer.get_start_iter()
            end = self._summary_buffer.get_end_iter()
            flags = Gtk.TextSearchFlags.CASE_INSENSITIVE
            while True:
                result = start.forward_search(query, flags, end)
                if result is None:
                    break
                match_start, match_end = result
                self._summary_search_matches.append(
                    (match_start.get_offset(), match_end.get_offset())
                )
                start = match_end
        self._apply_summary_search_highlights()

    def _apply_summary_search_highlights(self) -> None:
        if not self._summary_buffer:
            return
        self._ensure_summary_search_tags()
        if not self._summary_search_tag or not self._summary_search_current_tag:
            return
        start = self._summary_buffer.get_start_iter()
        end = self._summary_buffer.get_end_iter()
        self._summary_buffer.remove_tag(self._summary_search_tag, start, end)
        self._summary_buffer.remove_tag(self._summary_search_current_tag, start, end)
        active_match = None
        if 0 <= self._summary_search_index < len(self._summary_search_matches):
            active_match = self._summary_search_matches[self._summary_search_index]
        paged = self._summary_is_paged()
        current_page = self._summary_edition_page
        for match in self._summary_search_matches:
            if paged:
                match_page, start_offset, end_offset = match
                if match_page != current_page:
                    continue
            else:
                start_offset, end_offset = match
            start_iter = self._summary_buffer.get_iter_at_offset(start_offset)
            end_iter = self._summary_buffer.get_iter_at_offset(end_offset)
            self._summary_buffer.apply_tag(self._summary_search_tag, start_iter, end_iter)
            if active_match == match:
                self._summary_buffer.apply_tag(
                    self._summary_search_current_tag, start_iter, end_iter
                )

    def _scroll_to_summary_match(self, index: int) -> None:
        if not self._summary_view or not self._summary_buffer:
            return
        if index < 0 or index >= len(self._summary_search_matches):
            return
        match = self._summary_search_matches[index]
        if self._summary_is_paged():
            match_page, start_offset, _end_offset = match
            if match_page != self._summary_edition_page:
                self._display_summary_page(match_page, scroll_top=False)
        else:
            start_offset = match[0]
        start_iter = self._summary_buffer.get_iter_at_offset(start_offset)
        self._summary_view.scroll_to_iter(start_iter, 0.15, True, 0.1, 0.1)

    def _connect_summary_scroll_watch(self) -> None:
        if not self._summary_scroller:
            return
        vadj = self._summary_scroller.get_vadjustment()
        if not vadj:
            return
        if self._summary_scroll_handler_id is not None:
            try:
                vadj.disconnect(self._summary_scroll_handler_id)
            except (TypeError, RuntimeError):
                pass
        self._summary_scroll_handler_id = vadj.connect("value-changed", self._on_summary_scroll)
        self._update_summary_progress_label(vadj)

    def _summary_scroll_fraction(self, adjustment: Gtk.Adjustment) -> float:
        lower = adjustment.get_lower()
        upper = adjustment.get_upper()
        page_size = adjustment.get_page_size()
        total = upper - lower - page_size
        if total <= 0:
            return 0.0
        value = adjustment.get_value()
        return (value - lower) / total

    def _update_summary_progress_label(self, adjustment: Gtk.Adjustment | None = None) -> None:
        if not self._summary_progress_label:
            return
        if self._summary_is_paged():
            # Paged mode shows flat page controls instead of a percentage.
            self._summary_progress_label.set_visible(False)
            return
        if not self._summary_buffer or self._summary_buffer.get_char_count() <= 0:
            self._summary_progress_label.set_text("0%")
            return
        if adjustment is None and self._summary_scroller:
            adjustment = self._summary_scroller.get_vadjustment()
        fraction = 0.0
        if adjustment:
            fraction = self._summary_scroll_fraction(adjustment)
            fraction = min(1.0, max(0.0, fraction))
        percent = int(round(fraction * 100))
        self._summary_progress_label.set_text(f"{percent}%")

    def _on_summary_scroll(self, adjustment: Gtk.Adjustment) -> None:
        fraction = self._summary_scroll_fraction(adjustment)
        fraction = min(1.0, max(0.0, fraction))
        if (
            self._ai_active_view == AI_VIEW_FILE
            and not self._summary_scroll_restore_guard
            and self._summary_pending_restore_fraction is None
            and not self._summary_is_paged()
        ):
            self._current_view_state().summary_scroll_fraction = fraction
        self._update_summary_progress_label(adjustment)

    def _capture_summary_scroll_position(self) -> None:
        if not self._summary_scroller or not self._summary_loaded_path:
            return
        state = self._current_view_state()
        if self._summary_is_paged():
            state.summary_current_page = self._summary_edition_page
            return
        if self._summary_pending_restore_fraction is not None:
            state.summary_scroll_fraction = self._summary_pending_restore_fraction
            return
        vadj = self._summary_scroller.get_vadjustment()
        if not vadj:
            return
        fraction = self._summary_scroll_fraction(vadj)
        state.summary_scroll_fraction = min(1.0, max(0.0, fraction))

    def _cancel_pending_summary_scroll_restore(self) -> None:
        if self._summary_scroll_restore_source_id is not None:
            GLib.source_remove(self._summary_scroll_restore_source_id)
        self._summary_scroll_restore_source_id = None
        self._summary_pending_restore_fraction = None
        self._summary_scroll_restore_geometry = None
        self._summary_scroll_restore_stable_passes = 0
        self._summary_scroll_restore_attempts = 0

    def _prepare_summary_scroll_restore(self, fraction: float) -> None:
        self._cancel_pending_summary_scroll_restore()
        self._summary_pending_restore_fraction = min(1.0, max(0.0, fraction))

    def _schedule_pending_summary_scroll_restore(self, fraction: float) -> None:
        self._prepare_summary_scroll_restore(fraction)
        self._summary_scroll_restore_source_id = GLib.timeout_add(
            SUMMARY_SCROLL_RESTORE_INTERVAL_MS,
            self._apply_pending_summary_scroll_restore,
        )

    def _apply_pending_summary_scroll_restore(self) -> bool:
        fraction = self._summary_pending_restore_fraction
        if fraction is None or not self._summary_scroller:
            self._cancel_pending_summary_scroll_restore()
            return False
        vadj = self._summary_scroller.get_vadjustment()
        if not vadj:
            self._cancel_pending_summary_scroll_restore()
            return False

        lower = vadj.get_lower()
        upper = vadj.get_upper()
        page_size = vadj.get_page_size()
        geometry = (lower, upper, page_size)
        # ViewStack mapping and panel sizing can update the adjustment over
        # several frames. Keep restoring until its geometry settles.
        if geometry == self._summary_scroll_restore_geometry:
            self._summary_scroll_restore_stable_passes += 1
        else:
            self._summary_scroll_restore_geometry = geometry
            self._summary_scroll_restore_stable_passes = 1
        self._summary_scroll_restore_attempts += 1

        total = upper - lower - page_size
        if total > 0:
            target = lower + fraction * total
            self._summary_scroll_restore_guard = True
            try:
                vadj.set_value(target)
            finally:
                self._summary_scroll_restore_guard = False
            self._update_summary_progress_label(vadj)

        restore_complete = (
            total > 0
            and self._summary_scroll_restore_stable_passes
            >= SUMMARY_SCROLL_RESTORE_STABLE_PASSES
        )
        attempts_exhausted = (
            self._summary_scroll_restore_attempts
            >= SUMMARY_SCROLL_RESTORE_MAX_ATTEMPTS
        )
        if not restore_complete and not attempts_exhausted:
            return True

        self._current_view_state().summary_scroll_fraction = fraction
        self._summary_scroll_restore_source_id = None
        self._summary_pending_restore_fraction = None
        self._summary_scroll_restore_geometry = None
        self._summary_scroll_restore_stable_passes = 0
        self._summary_scroll_restore_attempts = 0
        return False

    def _restore_summary_scroll_position(self, path: Path | None) -> None:
        if not path or not self._summary_scroller:
            return
        state = self._current_view_state()
        if not state.summary_loaded_path or state.summary_loaded_path != path:
            return
        fraction = state.summary_scroll_fraction
        if fraction is None:
            return
        self._restore_summary_scroll_fraction(fraction)

    def _restore_summary_position(self, path: Path | None) -> None:
        if not path:
            return
        state = self._current_view_state()
        if self._summary_is_paged():
            if state.summary_loaded_path == path and state.summary_current_page:
                self._display_summary_page(state.summary_current_page)
            return
        if state.summary_loaded_path == path and state.summary_scroll_fraction is not None:
            self._restore_summary_scroll_fraction(state.summary_scroll_fraction)
            return
        self._restore_summary_bookmark_or_top(path)

    def _summary_bookmarks_path_for(self, summary_path: Path) -> Path:
        return summary_path.parent / SUMMARY_BOOKMARKS_FILENAME

    def _read_summary_bookmarks(self, bookmarks_path: Path) -> dict[str, Any]:
        try:
            raw = bookmarks_path.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            return {}
        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            return {}
        if isinstance(data, dict):
            return data
        return {}

    def _extract_summary_bookmark_entry(self, summary_path: Path) -> dict[str, Any] | None:
        bookmarks_path = self._summary_bookmarks_path_for(summary_path)
        data = self._read_summary_bookmarks(bookmarks_path)
        bookmarks = data.get("bookmarks")
        if not isinstance(bookmarks, dict):
            return None
        entry = bookmarks.get(summary_path.name)
        if not isinstance(entry, dict):
            return None
        return entry

    def _extract_summary_bookmark_line(self, summary_path: Path) -> int | None:
        entry = self._extract_summary_bookmark_entry(summary_path)
        if entry is None:
            return None
        try:
            line_num = int(entry.get("line"))
        except (TypeError, ValueError):
            return None
        if line_num < 1:
            return None
        return line_num

    def _summary_bookmark_page(self, summary_path: Path) -> int | None:
        """Resolve the saved bookmark to a paper page for paged summaries.

        Version-3 bookmarks name their paper page, the summary source hash,
        and the edition PDF hash. The exact page is honored only when both
        hashes still match; a matching source with a different PDF hash means
        the edition was repaginated, so the saved source line maps through
        the current sidecar instead and the user is notified. Legacy
        version-2 page bookmarks validate the source hash and then use their
        stored line fallback rather than trusting an obsolete page number.
        Version-1 line bookmarks map to the first sidecar page whose
        source-line range contains the line; they are not rewritten until the
        user next sets a bookmark. Any source mismatch or unusable line/page
        falls back safely to page 1.
        """
        if not self._summary_is_paged() or self._summary_edition is None:
            return None
        entry = self._extract_summary_bookmark_entry(summary_path)
        if entry is None:
            return None
        version = entry.get("version")
        if version in (2, 3):
            source_sha = entry.get("source_sha256")
            if source_sha != self._summary_edition.source_sha256:
                self._ai_transient_toast(
                    "The summary changed since this bookmark was saved; starting at page 1."
                )
                return 1
            if version == 3:
                pdf_sha = entry.get("pdf_sha256")
                if not isinstance(pdf_sha, str) or not pdf_sha:
                    return 1
                if pdf_sha != self._summary_edition.pdf_sha256:
                    return self._repaginated_bookmark_page(entry)
                try:
                    page = int(entry.get("page"))
                except (TypeError, ValueError):
                    return 1
                if page < 1 or page > self._summary_edition.page_count:
                    return 1
                return page
            # Legacy version-2: the named page may be obsolete after the v2
            # repagination, so map the stored line fallback instead.
            line_num = self._extract_summary_bookmark_line(summary_path)
            if line_num is None:
                return 1
            return find_page_for_source_line(self._summary_edition, line_num)
        line_num = self._extract_summary_bookmark_line(summary_path)
        if line_num is None:
            return None
        return find_page_for_source_line(self._summary_edition, line_num)

    def _repaginated_bookmark_page(self, entry: dict[str, Any]) -> int:
        """Map a repaginated bookmark's saved source line to the new layout."""
        self._ai_transient_toast(
            "Summary pagination changed since this bookmark was saved; "
            "returning to the saved line in the new layout."
        )
        try:
            line_num = int(entry.get("line"))
        except (TypeError, ValueError):
            return 1
        if line_num < 1:
            return 1
        assert self._summary_edition is not None
        return find_page_for_source_line(self._summary_edition, line_num)

    def _scroll_summary_to_line(self, line_num: int) -> None:
        if not self._summary_view or not self._summary_buffer:
            return
        clamped = max(1, line_num)

        def _apply(remaining: int) -> bool:
            if not self._summary_view or not self._summary_buffer:
                return False
            line_count = self._summary_buffer.get_line_count()
            if line_count <= 0:
                if remaining <= 0:
                    return False
                GLib.timeout_add(50, _apply, remaining - 1)
                return False
            target_line = min(clamped, line_count) - 1
            iter_result = self._summary_buffer.get_iter_at_line(target_line)
            if isinstance(iter_result, tuple):
                if len(iter_result) == 2:
                    success, iter_ = iter_result
                    if not success:
                        iter_ = self._summary_buffer.get_start_iter()
                else:
                    iter_ = iter_result[-1]
            else:
                iter_ = iter_result
            self._summary_view.scroll_to_iter(iter_, 0.08, True, 0.0, 0.0)
            self._update_summary_progress_label()
            return False

        GLib.idle_add(_apply, 8)

    def _restore_summary_bookmark_or_top(self, summary_path: Path) -> None:
        line_num = self._extract_summary_bookmark_line(summary_path)
        if line_num is None:
            self._scroll_summary_to_line(1)
            return
        self._scroll_summary_to_line(line_num)

    def _top_visible_summary_line_number(self) -> int | None:
        if not self._summary_view or not self._summary_buffer:
            return None
        if self._summary_buffer.get_char_count() <= 0:
            return None
        try:
            visible_rect = self._summary_view.get_visible_rect()
            line_result = self._summary_view.get_line_at_y(visible_rect.y)
        except (AttributeError, TypeError, ValueError):
            return 1
        if isinstance(line_result, tuple):
            if not line_result:
                return 1
            iter_ = line_result[0]
        else:
            iter_ = line_result
        if iter_ is None:
            return 1
        return iter_.get_line() + 1

    def _summary_has_saved_bookmark(self) -> bool:
        if not self._summary_loaded_path:
            return False
        return self._extract_summary_bookmark_line(self._summary_loaded_path) is not None

    def _refresh_summary_actions_state(self) -> None:
        has_summary = bool(self._summary_loaded_path)
        has_bookmark = self._summary_has_saved_bookmark()
        has_printable_text = bool(self._summary_raw.strip())
        if self._summary_bookmark_action_button:
            self._summary_bookmark_action_button.set_sensitive(has_summary and has_printable_text)
        if self._summary_return_bookmark_action_button:
            self._summary_return_bookmark_action_button.set_sensitive(has_summary and has_bookmark)
        self._update_summary_page_controls()

    def _on_summary_bookmark_clicked(self, _button: Gtk.Button) -> None:
        if not self._summary_loaded_path:
            self._ai_transient_toast("No summary file is loaded.")
            return
        bookmarks_path = self._summary_bookmarks_path_for(self._summary_loaded_path)
        data = self._read_summary_bookmarks(bookmarks_path)
        bookmarks = data.get("bookmarks")
        if not isinstance(bookmarks, dict):
            bookmarks = {}
        if self._summary_is_paged():
            assert self._summary_edition is not None
            page = self._summary_edition_page
            entry: dict[str, Any] = {
                "page": page,
                "line": self._summary_edition.pages[page - 1].source_first_line,
                "source_sha256": self._summary_edition.source_sha256,
                "pdf_sha256": self._summary_edition.pdf_sha256,
                "layout_id": self._summary_edition.layout_id,
                "version": 3,
                "updated_at": datetime.now(timezone.utc).isoformat(),
            }
            label = f"page {page}"
        else:
            line_num = self._top_visible_summary_line_number()
            if line_num is None:
                self._ai_transient_toast("No summary text is available to bookmark.")
                return
            entry = {
                "line": line_num,
                "updated_at": datetime.now(timezone.utc).isoformat(),
            }
            label = f"line {line_num}"
        bookmarks[self._summary_loaded_path.name] = entry
        data["version"] = 3 if self._summary_is_paged() else 1
        data["bookmarks"] = bookmarks
        try:
            bookmarks_path.parent.mkdir(parents=True, exist_ok=True)
            bookmarks_path.write_text(json.dumps(data, indent=2, sort_keys=True), encoding="utf-8")
        except OSError as exc:  # noqa: BLE001
            self._ai_transient_toast(f"Could not save summary bookmark: {exc}")
            return
        self._refresh_summary_actions_state()
        self._ai_transient_toast(
            f"Bookmarked {self._summary_loaded_path.name} at {label}."
        )

    def _on_summary_return_bookmark_clicked(self, _button: Gtk.Button) -> None:
        if not self._summary_loaded_path:
            self._ai_transient_toast("No summary file is loaded.")
            return
        if self._summary_is_paged():
            page = self._summary_bookmark_page(self._summary_loaded_path)
            if page is None:
                self._ai_transient_toast("No saved bookmark for this summary.")
                return
            self._display_summary_page(page)
            self._ai_transient_toast(
                f"Returned to bookmark in {self._summary_loaded_path.name} at page {page}."
            )
            return
        line_num = self._extract_summary_bookmark_line(self._summary_loaded_path)
        if line_num is None:
            self._ai_transient_toast("No saved bookmark for this summary.")
            return
        self._scroll_summary_to_line(line_num)
        self._ai_transient_toast(
            f"Returned to bookmark in {self._summary_loaded_path.name} at line {line_num}."
        )

    def _restore_summary_scroll_fraction(self, fraction: float) -> None:
        if not self._summary_scroller:
            return
        self._schedule_pending_summary_scroll_restore(fraction)

    def _summary_link_at_coords(
        self,
        textview: Gtk.TextView,
        x: float,
        y: float,
    ) -> tuple[str, str] | None:
        bx, by = textview.window_to_buffer_coords(Gtk.TextWindowType.WIDGET, int(x), int(y))
        iter_result = textview.get_iter_at_location(int(bx), int(by))
        if isinstance(iter_result, tuple):
            success, iter_ = iter_result
            if not success:
                return None
        else:
            iter_ = iter_result
        if iter_ is None:
            return None
        for tag in iter_.get_tags():
            link = self._summary_link_tag_lookup.get(tag)
            if link is not None:
                return link
        return None

    def _on_summary_motion(
        self,
        _controller: Gtk.EventControllerMotion,
        x: float,
        y: float,
    ) -> None:
        if not self._summary_view:
            return
        link = self._summary_link_at_coords(self._summary_view, x, y)
        if link:
            self._summary_view.set_cursor_from_name("pointer")
        else:
            self._summary_view.set_cursor_from_name(None)

    def _on_summary_leave(self, _controller: Gtk.EventControllerMotion) -> None:
        if self._summary_view:
            self._summary_view.set_cursor_from_name(None)

    def _on_summary_click(
        self,
        gesture: Gtk.GestureClick,
        _n_press: int,
        x: float,
        y: float,
    ) -> None:
        button = gesture.get_current_button()
        if button and button != Gdk.BUTTON_PRIMARY:
            return
        if not self._summary_view:
            return
        self._summary_view.grab_focus()
        self._summary_view.set_cursor_visible(False)
        link = self._summary_link_at_coords(self._summary_view, x, y)
        if not link:
            return
        self._activate_link(link)

    def _activate_link(self, link: tuple[str, str]) -> None:
        kind, value = link
        if kind == "page":
            self._show_page_from_link(value)
            return
        cleaned, _trailing = split_link_phrase(value)
        if not cleaned:
            return
        self._set_grep_entry_text(cleaned)
        self._apply_grep(cleaned)

    def _show_page_from_link(self, page_str: str) -> None:
        try:
            page_num = int(page_str)
        except ValueError:
            return
        if not self.pages:
            return
        idx = bisect.bisect_left(self.pages, page_num)
        if idx >= len(self.pages) or self.pages[idx] != page_num:
            self._transient_toast(f"Page {page_num:04d} not available")
            return
        self.current_index = idx
        if self._grep_active or self._grep_search_thread:
            self._clear_grep_state()
        self._load_current()

    def _image_path_for_page(self, page: int) -> Path:
        return self.images_dir / f"{page:04d}.png"

    def _load_image_for_page(self, page: int, *, silent: bool = False) -> bool:
        if not (self._image_picture and self._image_scroller):
            return False
        text_path = self.page_to_path.get(page)
        if not text_path:
            if not silent:
                self._transient_toast(f"Text for page {page:04d} not available")
            return False
        image_path = self._image_path_for_page(page)
        if not image_path.exists():
            if not silent:
                self._transient_toast(f"Image {image_path.name} not found")
            return False

        try:
            pixbuf = GdkPixbuf.Pixbuf.new_from_file(str(image_path))
        except GLib.Error:
            if not silent:
                self._transient_toast(f"Image {image_path.name} could not be loaded")
            return False

        self._image_pixbuf = pixbuf
        self._image_scaled_size = None
        self._image_viewport_size = None
        self._start_image_scale_tick()
        self._update_image_scaled()
        self._image_picture.set_alternative_text(f"Page {page:04d} image")

        vadj = self._image_scroller.get_vadjustment()
        if vadj:
            GLib.idle_add(vadj.set_value, vadj.get_lower())
        hadj = self._image_scroller.get_hadjustment()
        if hadj:
            GLib.idle_add(hadj.set_value, hadj.get_lower())
        return True

    def _load_image_preview_for_page(self, page: int) -> None:
        if not (self._image_preview_picture and self._image_preview_button):
            return
        image_path = self._image_path_for_page(page)
        if not image_path.exists():
            self._clear_image_preview()
            return
        try:
            pixbuf = GdkPixbuf.Pixbuf.new_from_file(str(image_path))
        except GLib.Error:
            self._clear_image_preview()
            return

        width = max(1, pixbuf.get_width())
        height = max(1, pixbuf.get_height())
        scale = IMAGE_PREVIEW_THUMB_WIDTH / width
        target_width = IMAGE_PREVIEW_THUMB_WIDTH
        target_height = max(1, int(height * scale))
        scaled = pixbuf.scale_simple(
            target_width,
            target_height,
            GdkPixbuf.InterpType.BILINEAR,
        )
        if not scaled:
            self._clear_image_preview()
            return

        texture = Gdk.Texture.new_for_pixbuf(scaled)
        self._image_preview_picture.set_paintable(texture)
        self._image_preview_picture.set_size_request(target_width, target_height)
        self._image_preview_picture.set_alternative_text(f"Page {page:04d} image preview")
        self._image_preview_button.set_tooltip_text(f"Open page {page:04d} image")
        self._image_preview_button.set_sensitive(True)
        self._image_preview_button.set_visible(True)

    def _clear_image_preview(self) -> None:
        if self._image_preview_picture:
            self._image_preview_picture.set_paintable(None)
            self._image_preview_picture.set_alternative_text("")
            self._image_preview_picture.set_size_request(-1, -1)
        if self._image_preview_button:
            self._image_preview_button.set_sensitive(False)
            self._image_preview_button.set_visible(False)

    def _on_image_preview_clicked(self, _button: Gtk.Button) -> None:
        self._set_show_image(True)

    def _clear_image_view(self) -> None:
        if self._image_picture:
            self._image_picture.set_paintable(None)
            self._image_picture.set_alternative_text("")
            self._image_picture.set_size_request(-1, -1)
        if self._image_fixed:
            self._image_fixed.set_size_request(-1, -1)
        self._image_pixbuf = None
        self._image_scaled_size = None
        self._stop_image_scale_tick()
        self._image_viewport_size = None

    def _start_image_scale_tick(self) -> None:
        if not self._image_scroller or self._image_tick_id is not None:
            return
        self._image_tick_id = self._image_scroller.add_tick_callback(self._on_image_tick)

    def _stop_image_scale_tick(self) -> None:
        if not self._image_scroller or self._image_tick_id is None:
            return
        self._image_scroller.remove_tick_callback(self._image_tick_id)
        self._image_tick_id = None

    def _on_image_tick(
        self,
        _widget: Gtk.Widget,
        _frame_clock: Gdk.FrameClock,
    ) -> bool:
        if not self._image_pixbuf or not self._image_scroller:
            return False
        width = self._image_scroller.get_width()
        height = self._image_scroller.get_height()
        if width > 0 and height > 0 and (width, height) != self._image_viewport_size:
            self._image_viewport_size = (width, height)
            self._update_image_scaled()
        return True

    def _update_image_scaled(self) -> None:
        if not (self._image_picture and self._image_scroller and self._image_pixbuf):
            return
        viewport_width = self._image_scroller.get_width()
        viewport_height = self._image_scroller.get_height()
        if viewport_width <= 0 or viewport_height <= 0:
            return
        width = self._image_pixbuf.get_width()
        height = self._image_pixbuf.get_height()
        scale = min(1.0, viewport_width / width, viewport_height / height)
        target_width = max(1, int(width * scale))
        target_height = max(1, int(height * scale))
        if self._image_scaled_size == (target_width, target_height):
            return
        scaled = self._image_pixbuf.scale_simple(
            target_width,
            target_height,
            GdkPixbuf.InterpType.BILINEAR,
        )
        if not scaled:
            return
        texture = Gdk.Texture.new_for_pixbuf(scaled)
        self._image_picture.set_paintable(texture)
        self._image_picture.set_size_request(target_width, target_height)
        if self._image_fixed:
            self._image_fixed.set_size_request(target_width, target_height)
        self._image_scaled_size = (target_width, target_height)

    def _show_image_update_visible(self) -> None:
        if not self._content_stack:
            return
        target = "image" if self._show_image else "text"
        current = self._content_stack.get_visible_child_name()
        if current != target:
            self._content_stack.set_visible_child_name(target)

    def _sync_show_image_action(self) -> None:
        if not self._show_image_action:
            self._update_show_image_toggle_button()
            return
        state = self._show_image_action.get_state()
        current = state.get_boolean() if state is not None else None
        if current != self._show_image:
            self._show_image_action.set_state(GLib.Variant.new_boolean(self._show_image))
        self._update_show_image_toggle_button()

    def _update_show_image_toggle_button(self) -> None:
        if not self._show_image_button or not self._show_image_icon:
            return
        self._show_image_button_guard = True
        try:
            self._show_image_button.set_active(self._show_image)
        finally:
            self._show_image_button_guard = False
        icon_name = self._image_icon_name_on if self._show_image else self._image_icon_name_off
        self._show_image_icon.set_from_icon_name(icon_name)
        tooltip = "Disable image view (Ctrl+I)" if self._show_image else "Enable image view (Ctrl+I)"
        self._show_image_button.set_tooltip_text(tooltip)

    def _set_summary_active_source(self, source: str | None) -> None:
        self._summary_active_source = source
        self._sync_ai_view_toggles(self._ai_active_view)
        if self._ai_active_view == AI_VIEW_FILE:
            self._refresh_case_tools_status()

    def _infer_summary_source(self, path: Path) -> str:
        name = path.name.casefold()
        if name in HEARING_SUMMARY_CANDIDATES or "hearing" in name:
            return SUMMARY_SOURCE_HEARING
        if name in REPORTS_SUMMARY_CANDIDATES or "report" in name:
            return SUMMARY_SOURCE_REPORTS
        manifest_path = _find_manifest_near_path(self.input_dir)
        if manifest_path:
            manifest = _read_manifest_file(manifest_path)
            files = manifest.get("files") if isinstance(manifest.get("files"), dict) else {}
            summary_path = _path_from_manifest(
                files.get(MINUTES_SUMMARY_MANIFEST_KEY),
                manifest_path.parent,
            )
            if summary_path and summary_path.resolve() == path.resolve():
                return SUMMARY_SOURCE_MINUTES
        return SUMMARY_SOURCE_HEARING

    def _set_font_preferences(
        self,
        *,
        font_size_pt: int | None = None,
        ai_font_size_pt: int | None = None,
        table_font_size_pt: int | None = None,
        record_font_family_name: str | None = None,
    ) -> None:
        base = self._font_size_pt
        ai = self._ai_font_size_pt
        table = self._table_font_size_pt
        record_font_family = self._record_font_family_name
        if font_size_pt is not None:
            base = _coerce_font_size(font_size_pt, DEFAULT_FONT_SIZE_PT)
        if ai_font_size_pt is not None:
            ai = _coerce_font_size(ai_font_size_pt, max(base, DEFAULT_AI_FONT_SIZE_PT))
        if table_font_size_pt is not None:
            table = _coerce_font_size(table_font_size_pt, base)
        if record_font_family_name is not None:
            record_font_family = _normalize_record_font_family_name(record_font_family_name)
        self._font_size_pt = base
        self._ai_font_size_pt = ai
        self._table_font_size_pt = table
        self._record_font_family_name = record_font_family
        self._record_font_family_css = _record_font_css_for_name(record_font_family)
        save_font_preferences(
            base,
            ai,
            table,
            record_font_family_name=record_font_family,
        )
        self._apply_text_color(self._current_text_color)
        self._apply_table_font_size_to_current_buffer()

    def get_font_preferences(self) -> tuple[int, int, int]:
        return self._font_size_pt, self._ai_font_size_pt, self._table_font_size_pt

    def get_record_font_family_name(self) -> str:
        return self._record_font_family_name

    def update_font_sizes(
        self,
        *,
        font_size_pt: int | None = None,
        ai_font_size_pt: int | None = None,
        table_font_size_pt: int | None = None,
        record_font_family_name: str | None = None,
    ) -> None:
        self._set_font_preferences(
            font_size_pt=font_size_pt,
            ai_font_size_pt=ai_font_size_pt,
            table_font_size_pt=table_font_size_pt,
            record_font_family_name=record_font_family_name,
        )

    def update_ai_font_size(self, ai_font_size_pt: int) -> None:
        self.update_font_sizes(ai_font_size_pt=ai_font_size_pt)

    def _summary_has_text(self) -> bool:
        return bool(self._summary_buffer and self._summary_buffer.get_char_count() > 0)

    def _show_summary_view(self, *, switch_view: bool = True) -> None:
        if switch_view:
            self._set_ai_view(AI_VIEW_FILE)
        if self._summary_scroller:
            self._summary_scroller.queue_resize()
        if self._summary_view:
            self._summary_view.set_cursor_visible(False)
        if self._summary_loaded_path:
            self._restore_summary_position(self._summary_loaded_path)
        self._update_summary_progress_label()

    def _set_show_image(self, enabled: bool, *, silent: bool = False) -> bool:
        if enabled:
            if not self.pages:
                if not silent:
                    self._transient_toast("No page available to display an image.")
                self._sync_show_image_action()
                self._refresh_search_highlighted_button()
                return False
            page = self.pages[self.current_index]
            if not self._load_image_for_page(page, silent=silent):
                self._clear_image_view()
                self._show_image = False
                self._show_image_update_visible()
                self._sync_show_image_action()
                self._refresh_search_highlighted_button()
                return False
            self._show_image = True
            self._show_image_update_visible()
            self._sync_show_image_action()
            self._refresh_search_highlighted_button()
            return True

        # Always force the stack back to the text view when disabling image mode,
        # even if the flag was already false (e.g., after returning from a different view).
        self._show_image = False
        self._show_image_update_visible()
        self._clear_image_view()
        self._sync_show_image_action()
        self._refresh_search_highlighted_button()
        return True

    def _link_at_coords(self, textview: Gtk.TextView, x: float, y: float) -> tuple[str, str] | None:
        bx, by = textview.window_to_buffer_coords(Gtk.TextWindowType.WIDGET, int(x), int(y))
        iter_result = textview.get_iter_at_location(int(bx), int(by))
        if isinstance(iter_result, tuple):
            success, iter_ = iter_result
            if not success:
                return None
        else:
            iter_ = iter_result
        if iter_ is None:
            return None
        for tag in iter_.get_tags():
            link = self._link_tag_lookup.get(tag)
            if link is not None:
                return link
        return None

    def _update_page_nav_buttons(self) -> None:
        enabled = bool(self.pages)
        if self._page_back_one_button:
            self._page_back_one_button.set_sensitive(enabled)
        if self._page_forward_one_button:
            self._page_forward_one_button.set_sensitive(enabled)
        if self._page_number_entry:
            self._page_number_entry.set_sensitive(bool(self.pages))
        self._refresh_minute_order_button()
        self._refresh_record_boundary_date_label()
        if self._page_total_label and self._page_number_entry:
            if self.pages and 0 <= self.current_index < len(self.pages):
                current_page = self.pages[self.current_index]
                entry_text, detail_text = format_page_nav_labels(
                    current_page,
                    len(self.pages),
                    self._transcript_page_index,
                )
                if not self._page_number_entry.has_focus():
                    self._page_number_entry.set_text(entry_text)
                self._page_total_label.set_text(detail_text)
            else:
                if not self._page_number_entry.has_focus():
                    self._page_number_entry.set_text("")
                self._page_total_label.set_text("--/--")

    def _update_grep_hit_navigation(self) -> None:
        total_hits = len(self._grep_match_order) if self._grep_active else 0
        current_index = min(max(self._grep_current_match_index, 0), total_hits - 1)
        if self._grep_hit_label:
            status_text = format_grep_status_text(
                self._grep_match_order,
                self._grep_current_match_index,
            )
            self._grep_hit_label.set_text(status_text)
            self._grep_hit_label.set_visible(bool(status_text))
        show_hit_navigation = total_hits > 0
        prev_enabled = total_hits > 0 and current_index > 0
        next_enabled = total_hits > 0 and current_index < total_hits - 1
        if self._grep_prev_hit_button:
            self._grep_prev_hit_button.set_visible(show_hit_navigation)
            self._grep_prev_hit_button.set_sensitive(prev_enabled)
        if self._grep_next_hit_button:
            self._grep_next_hit_button.set_visible(show_hit_navigation)
            self._grep_next_hit_button.set_sensitive(next_enabled)
        self._sync_citation_buttons()

    def _update_header(self) -> None:
        self._update_page_nav_buttons()
        self._update_grep_hit_navigation()
        if not self.pages:
            self._set_window_title("No pages found")
            return
        page = self.pages[self.current_index]
        self._set_window_title(f"Page {page:04d}")

    def _read_page_text(self, page: int) -> tuple[str, str, list[int]]:
        if (
            page in self._page_cache
            and page in self._page_search_cache
            and page in self._page_search_map_cache
        ):
            return (
                self._page_cache[page],
                self._page_search_cache[page],
                self._page_search_map_cache[page],
            )
        path = self.page_to_path.get(page)
        if not path:
            return "", "", []
        content = self._read_text_file(path)
        normalized, norm_to_orig = normalize_text_for_search_with_map(content)

        self._page_cache[page] = content
        self._page_search_cache[page] = normalized
        self._page_search_map_cache[page] = norm_to_orig
        return content, normalized, norm_to_orig

    def _read_text_file(self, path: Path) -> str:
        try:
            with io.open(path, "r", encoding="utf-8", errors="replace") as handle:
                content = handle.read()
        except Exception as exc:  # noqa: BLE001
            content = f"Error reading {path.name}: {exc}"
        return content.replace("\r\n", "\n").replace("\r", "\n")

    def _transcript_breakdown_available(self) -> bool:
        return self.transcript_page_number_series_path.is_file()

    def _refresh_transcript_breakdown_action(self) -> None:
        if not self._show_transcript_breakdown_action:
            return
        self._show_transcript_breakdown_action.set_enabled(
            self._transcript_breakdown_available()
        )

    def _ensure_transcript_breakdown_window(self) -> Adw.ApplicationWindow:
        if self._transcript_breakdown_window:
            return self._transcript_breakdown_window

        window = Adw.ApplicationWindow(application=self, title="Transcript Page Breakdown")
        window.set_default_size(760, 560)
        window.set_resizable(True)
        if self.win:
            window.set_transient_for(self.win)

        view = Adw.ToolbarView()
        header = Adw.HeaderBar()
        header.add_css_class("flat")
        header.set_title_widget(Adw.WindowTitle(title="Transcript Page Breakdown"))
        view.add_top_bar(header)

        text_view = Gtk.TextView()
        text_view.set_editable(False)
        text_view.set_cursor_visible(False)
        text_view.set_wrap_mode(Gtk.WrapMode.WORD_CHAR)
        text_view.set_top_margin(16)
        text_view.set_bottom_margin(16)
        text_view.set_left_margin(18)
        text_view.set_right_margin(18)
        self._transcript_breakdown_buffer = text_view.get_buffer()

        scroller = Gtk.ScrolledWindow()
        scroller.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.AUTOMATIC)
        scroller.set_hexpand(True)
        scroller.set_vexpand(True)
        scroller.set_child(text_view)
        view.set_content(scroller)

        window.set_content(view)
        window.connect("close-request", self._on_transcript_breakdown_closed)
        self._transcript_breakdown_window = window
        return window

    def _on_transcript_breakdown_closed(self, _window: Gtk.Window) -> bool:
        self._transcript_breakdown_window = None
        self._transcript_breakdown_buffer = None
        return False

    def _close_transcript_breakdown_window(self) -> None:
        window = self._transcript_breakdown_window
        self._transcript_breakdown_window = None
        self._transcript_breakdown_buffer = None
        if window:
            window.close()

    def _show_transcript_breakdown(self) -> None:
        path = self.transcript_page_number_series_path
        if not path.is_file():
            self._refresh_transcript_breakdown_action()
            self._transient_toast("Transcript page breakdown not available.")
            return
        content = self._read_text_file(path)
        rendered_text, markdown_spans = render_transcript_breakdown_markdown(content)
        window = self._ensure_transcript_breakdown_window()
        if self._transcript_breakdown_buffer:
            self._transcript_breakdown_buffer.set_text(rendered_text)
            self._apply_markdown_spans(self._transcript_breakdown_buffer, markdown_spans)
            self._append_rounded_grid_table_style(
                self._transcript_breakdown_buffer,
                rendered_text,
                0,
            )
        window.present()

    def _on_show_transcript_breakdown_action(
        self,
        _action: Gio.SimpleAction,
        _param: GLib.Variant | None,
    ) -> None:
        self._show_transcript_breakdown()

    def _render_page_display(
        self,
        _page: int,
        content: str,
        highlights: list[tuple[int, int]] | None,
    ) -> tuple[str, list[tuple[int, int]] | None]:
        adjusted = [(start, end) for start, end in highlights or [] if end > start]
        return content, adjusted if adjusted else None

    def _load_current(self) -> None:
        if not self.pages:
            self._clear_image_preview()
            self._set_show_image(False, silent=True)
            return
        page = self.pages[self.current_index]
        self._sync_minute_order_return_state()
        path = self.page_to_path.get(page)
        if not path or not path.exists():
            display_text, highlight_spans = self._render_page_display(
                page, f"Missing file for page {page:04d}", None
            )
            self._set_text(display_text, highlight_spans)
            self._clear_image_preview()
            self._set_show_image(False, silent=True)
            self._update_header()
            self._sync_sidebar_active_page(scroll=True)
            return
        content, _, _ = self._read_page_text(page)
        highlights = self._grep_hits.get(page)
        display_text, highlight_spans = self._render_page_display(page, content, highlights)
        self._set_text(display_text, highlight_spans)
        self._load_image_preview_for_page(page)
        if self._show_image:
            if not self._load_image_for_page(page):
                self._set_show_image(False, silent=True)
            else:
                self._show_image_update_visible()
        else:
            self._show_image_update_visible()
        self._update_header()
        self._sync_sidebar_active_page(scroll=True)
        if self._ai_active_view == AI_VIEW_SUMMARIZE:
            self._maybe_prefill_sum_range_for_current_page()
        if self._grep_hits.get(page):
            self._scroll_to_current_grep_match()

    def _clear_grep_state(self) -> None:
        self._stop_grep_search_if_running()
        self._grep_regex = None
        self._grep_active = False
        self._grep_hits.clear()
        self._matching_pages.clear()
        self._matching_lookup.clear()
        self._grep_match_order = []
        self._grep_current_match_index = -1

    def _stop_grep_search_if_running(self) -> None:
        if self._grep_search_cancel_event:
            self._grep_search_cancel_event.set()
        if self._grep_search_thread and self._grep_search_thread.is_alive():
            try:
                self._grep_search_thread.join(timeout=0.1)
            except Exception:
                pass
        self._grep_search_thread = None
        self._grep_search_cancel_event = None

    def _apply_grep(self, phrase: str) -> None:
        self._stop_grep_search_if_running()
        phrase = phrase.strip()
        if phrase:
            self._set_show_image(False, silent=True)
        if not phrase:
            self._grep_phrase_raw = None
            self._clear_grep_state()
            self._load_current()
            return

        self._grep_phrase_raw = phrase
        self._grep_hits.clear()
        self._matching_pages.clear()
        self._matching_lookup.clear()
        self._grep_match_order = []
        self._grep_current_match_index = -1
        self._grep_active = False
        self._update_header()
        try:
            self._grep_regex = re.compile(
                build_pattern(preprocess_phrase(self._grep_phrase_raw), MAX_BREAKS),
                re.IGNORECASE | re.DOTALL,
            )
        except re.error as exc:
            self._transient_toast(f"Invalid grep pattern: {exc}")
            return
        self._grep_search_generation += 1
        generation = self._grep_search_generation
        cancel_event = threading.Event()
        pages = list(self.pages)
        page_to_path = dict(self.page_to_path)
        assert self._grep_regex is not None
        worker = threading.Thread(
            target=self._grep_search_worker,
            args=(self._grep_regex, generation, cancel_event, pages, page_to_path),
            daemon=True,
        )
        self._grep_search_cancel_event = cancel_event
        self._grep_search_thread = worker
        worker.start()

    def _grep_search_worker(
        self,
        regex: re.Pattern[str],
        generation: int,
        cancel_event: threading.Event,
        pages: list[int],
        page_to_path: dict[int, Path],
    ) -> None:
        local_hits: dict[int, list[tuple[int, int]]] = {}
        for page in pages:
            if cancel_event.is_set():
                return
            path = page_to_path.get(page)
            if not path:
                continue
            content = self._read_text_file(path)

            # Search normalized text first without building an offset map. This
            # inexpensive pass rejects nonmatching pages while preserving every
            # Unicode, punctuation, spacing, and line-break rule used by the
            # authoritative Python regex.
            normalized = normalize_text_for_search(content)
            if not normalized or regex.search(normalized) is None:
                continue

            # Build the more expensive normalized-to-original map only for a
            # page that actually matched, then locate and map every hit.
            normalized, norm_to_orig = normalize_text_for_search_with_map(content)
            matches = list(regex.finditer(normalized))
            mapped_hits: list[tuple[int, int]] = []
            for match in matches:
                mapped = self._map_normalized_span_to_original(
                    norm_to_orig,
                    match.start(),
                    match.end(),
                    len(content),
                )
                if mapped:
                    mapped_hits.append(mapped)
            if mapped_hits:
                local_hits[page] = mapped_hits

        matching_pages = sorted(local_hits.keys())

        GLib.idle_add(
            self._on_grep_search_finished,
            generation,
            local_hits,
            matching_pages,
        )

    def _map_normalized_span_to_original(
        self,
        norm_to_orig: list[int],
        start: int,
        end: int,
        original_len: int,
    ) -> tuple[int, int] | None:
        if not norm_to_orig or end <= start or end <= 0:
            return None
        max_index = len(norm_to_orig) - 1
        if max_index < 0:
            return None
        if start < 0:
            start = 0
        if start > max_index:
            return None
        if end > len(norm_to_orig):
            end = len(norm_to_orig)
        if end <= start:
            return None
        start_orig = norm_to_orig[start]
        end_orig = norm_to_orig[end - 1] + 1
        if end_orig <= start_orig or start_orig >= original_len:
            return None
        if end_orig > original_len:
            end_orig = original_len
        return start_orig, end_orig

    def _on_grep_search_finished(
        self,
        generation: int,
        grep_hits: dict[int, list[tuple[int, int]]],
        matching_pages: list[int],
    ) -> bool:
        if generation != self._grep_search_generation:
            return False

        self._grep_search_thread = None
        self._grep_search_cancel_event = None
        self._grep_hits = {page: list(hits) for page, hits in grep_hits.items()}
        self._matching_pages = list(matching_pages)
        self._matching_lookup = {page: idx for idx, page in enumerate(self._matching_pages)}
        self._grep_match_order = build_grep_match_order(self._grep_hits, self._matching_pages)

        if not self._grep_match_order:
            self._grep_active = False
            self._grep_current_match_index = -1
            self._transient_toast("No pages matched the grep phrase")
            self._load_current()
            return False

        self._grep_active = True
        first_page, _first_hit = self._grep_match_order[0]
        if first_page in self.pages:
            self.current_index = self.pages.index(first_page)
        self._grep_current_match_index = 0
        self._load_current()
        return False

    def _on_grep_prev_hit_clicked(self, _button: Gtk.Button) -> None:
        self._navigate_grep_match(-1)

    def _on_grep_next_hit_clicked(self, _button: Gtk.Button) -> None:
        self._navigate_grep_match(1)

    def _on_current_page_citation_clicked(self, _button: Gtk.Button) -> None:
        self._insert_current_page_citation_in_prose_or_clipboard()

    def _on_page_citation_range_clicked(self, _button: Gtk.Button) -> None:
        self._insert_page_citation_range_in_prose_or_clipboard()

    def _current_page_citation_for_clipboard(self) -> str:
        current_page = self._current_page_number()
        if current_page is None:
            return ""
        return format_current_page_citation_for_clipboard(
            current_page,
            self._transcript_page_index,
        )

    def _copy_text_to_clipboard(self, text: str) -> bool:
        display = Gdk.Display.get_default()
        if not display:
            self._transient_toast("Clipboard is not available.")
            return False
        display.get_clipboard().set(text)
        return True

    def _sync_citation_buttons(self) -> None:
        enabled = bool(self.pages)
        if self._current_page_citation_button:
            self._current_page_citation_button.set_sensitive(enabled)
        if not self._page_citation_range_button:
            return
        self._page_citation_range_button.set_sensitive(enabled)
        start = self._page_citation_range_start
        if start:
            self._page_citation_range_button.add_css_class(
                "focus-citation-range-active"
            )
            self._page_citation_range_button.set_tooltip_text(
                f"Range starts at {start.citation_label}. "
                "Click again to insert. (Ctrl+Alt+C)"
            )
        else:
            self._page_citation_range_button.remove_css_class(
                "focus-citation-range-active"
            )
            self._page_citation_range_button.set_tooltip_text(
                "Set citation range start (Ctrl+Alt+C)"
            )

    def _prose_record_citations_action_available(self) -> bool:
        try:
            connection = Gio.bus_get_sync(Gio.BusType.SESSION, None)
        except Exception:
            return False
        for object_path in PROSE_ACTION_OBJECT_PATHS:
            try:
                connection.call_sync(
                    PROSE_APPLICATION_ID,
                    object_path,
                    "org.gtk.Actions",
                    "Describe",
                    GLib.Variant("(s)", (PROSE_INSERT_RECORD_CITATIONS_ACTION,)),
                    GLib.VariantType.new("((bgav))"),
                    Gio.DBusCallFlags.NONE,
                    1000,
                    None,
                )
                return True
            except Exception:
                continue
        return False

    def _send_text_to_prose_record_citations_action(self, text: str) -> bool:
        if not self._prose_record_citations_action_available():
            return False
        try:
            connection = Gio.bus_get_sync(Gio.BusType.SESSION, None)
        except Exception:
            return False
        for object_path in PROSE_ACTION_OBJECT_PATHS:
            try:
                connection.call_sync(
                    PROSE_APPLICATION_ID,
                    object_path,
                    "org.gtk.Actions",
                    "Activate",
                    GLib.Variant(
                        "(sava{sv})",
                        (
                            PROSE_INSERT_RECORD_CITATIONS_ACTION,
                            [GLib.Variant("s", text)],
                            {},
                        ),
                    ),
                    None,
                    Gio.DBusCallFlags.NONE,
                    1000,
                    None,
                )
                return True
            except Exception:
                continue
        return False

    def _insert_current_page_citation_in_prose_or_clipboard(self) -> bool:
        if self._current_page_number() is None:
            self._transient_toast("No current page citation to send.")
            return False
        citation = self._current_page_citation_for_clipboard()
        if not citation:
            self._transient_toast("No transcript citation available for current page.")
            return False
        if self._send_text_to_prose_record_citations_action(citation):
            return True
        if not self._copy_text_to_clipboard(citation):
            return False
        return True

    def _insert_page_citation_range_in_prose_or_clipboard(self) -> bool:
        current_label = self._current_transcript_page_label()
        if current_label is None:
            self._transient_toast("No transcript citation available for current page.")
            return False
        start_label = self._page_citation_range_start
        if start_label is None:
            self._page_citation_range_start = current_label
            self._sync_citation_buttons()
            return True

        result = format_page_citation_range_for_clipboard(start_label, current_label)
        if not result.valid:
            self._transient_toast(result.message)
            return False
        self._page_citation_range_start = None
        self._sync_citation_buttons()
        if self._send_text_to_prose_record_citations_action(result.citation):
            return True
        if not self._copy_text_to_clipboard(result.citation):
            return False
        return True

    def _on_append_selection_citation_to_file_action(
        self,
        _action: Gio.SimpleAction,
        param: GLib.Variant | None,
    ) -> None:
        if param is None:
            return
        file_path = param.get_string()
        if not file_path:
            return
        selection = self._get_main_text_selection()
        if not selection:
            return
        if (
            not self.pages
            or self.current_index < 0
            or self.current_index >= len(self.pages)
        ):
            return

        path = Path(file_path)
        try:
            captured_text = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            return

        updated_text = append_page_citation_to_selected_text(
            captured_text,
            selection,
            self.pages[self.current_index],
            self._transcript_page_index,
        )
        if updated_text == captured_text:
            return
        try:
            path.write_text(updated_text, encoding="utf-8")
        except OSError:
            return

    def _navigate_grep_match(self, direction: int, *, wrap: bool = False) -> bool:
        if direction == 0 or not self._grep_active or not self._grep_match_order:
            return False
        count = len(self._grep_match_order)
        current = next_grep_match_index(
            self._grep_current_match_index,
            count,
            direction,
            wrap=wrap,
        )
        if current is None:
            self._edge_flash()
            return True
        self._grep_current_match_index = current
        target_page, _hit_index = self._grep_match_order[current]
        if target_page in self.pages and (
            not self.pages
            or self.current_index < 0
            or self.current_index >= len(self.pages)
            or self.pages[self.current_index] != target_page
        ):
            self.current_index = self.pages.index(target_page)
            self._load_current()
            return True
        self._update_grep_hit_navigation()
        self._scroll_to_current_grep_match()
        return True

    def _install_navigation_controllers(self) -> None:
        if not self.win:
            return
        def attach_scroll_controller(widget: Gtk.Widget | None) -> bool:
            if widget is None:
                return False
            controller = Gtk.EventControllerScroll.new(Gtk.EventControllerScrollFlags.VERTICAL)
            controller.set_propagation_phase(Gtk.PropagationPhase.CAPTURE)
            controller.connect("scroll", self._on_scroll)
            widget.add_controller(controller)
            return True

        attached = attach_scroll_controller(self.scroller)
        if not attached:
            attach_scroll_controller(self.win)
        if self._image_scroller:
            image_scroll_controller = Gtk.EventControllerScroll.new(Gtk.EventControllerScrollFlags.VERTICAL)
            image_scroll_controller.set_propagation_phase(Gtk.PropagationPhase.CAPTURE)
            image_scroll_controller.connect("scroll", self._on_image_scroll)
            self._image_scroller.add_controller(image_scroll_controller)

        key_ctrl = Gtk.EventControllerKey.new()
        key_ctrl.set_propagation_phase(Gtk.PropagationPhase.CAPTURE)
        key_ctrl.connect("key-pressed", self._on_key)
        self.win.add_controller(key_ctrl)

    def _install_actions(self) -> None:
        choose_input = Gio.SimpleAction.new("choose_input", None)
        choose_input.connect("activate", self._on_choose_input_dir)
        self.add_action(choose_input)

        open_ai_settings = Gio.SimpleAction.new("open_ai_settings", None)
        open_ai_settings.connect("activate", self._on_open_ai_settings)
        self.add_action(open_ai_settings)

        for action_name, view_name in {
            "show_summarize": AI_VIEW_SUMMARIZE,
            "show_extract": AI_VIEW_EXTRACT,
        }.items():
            action = Gio.SimpleAction.new(action_name, None)
            action.connect(
                "activate",
                lambda _a, _p, view_name=view_name: self._open_case_tool_view(view_name),
            )
            self.add_action(action)

        for action_name, source in {
            "show_minutes_summary": SUMMARY_SOURCE_MINUTES,
            "show_hearings_summary": SUMMARY_SOURCE_HEARING,
            "show_reports_summary": SUMMARY_SOURCE_REPORTS,
        }.items():
            action = Gio.SimpleAction.new(action_name, None)
            action.connect(
                "activate",
                lambda _a, _p, source=source: self._open_case_tool_summary(source),
            )
            self.add_action(action)

        self._refresh_summary_actions_state()

        show_shortcuts = Gio.SimpleAction.new("show_shortcuts", None)
        show_shortcuts.connect("activate", self._on_show_shortcuts)
        self.add_action(show_shortcuts)

        show_dbus_commands = Gio.SimpleAction.new("show_dbus_commands", None)
        show_dbus_commands.connect("activate", self._on_show_dbus_commands)
        self.add_action(show_dbus_commands)

        show_transcript_breakdown = Gio.SimpleAction.new(
            "show_transcript_breakdown",
            None,
        )
        show_transcript_breakdown.connect(
            "activate",
            self._on_show_transcript_breakdown_action,
        )
        self.add_action(show_transcript_breakdown)
        self._show_transcript_breakdown_action = show_transcript_breakdown
        self._refresh_transcript_breakdown_action()

        print_images = Gio.SimpleAction.new("print_images", None)
        print_images.connect("activate", self._on_print_images_action)
        self.add_action(print_images)

        print_current_image = Gio.SimpleAction.new("print_current_image", None)
        print_current_image.connect("activate", self._on_print_current_image_action)
        self.add_action(print_current_image)

        toggle_sidebar = Gio.SimpleAction.new_stateful(
            "toggle_toc_sidebar",
            None,
            GLib.Variant.new_boolean(self._toc_sidebar_visible),
        )
        toggle_sidebar.connect("activate", self._on_stateful_toggle_activate)
        toggle_sidebar.connect("change-state", self._on_toggle_toc_sidebar)
        self.add_action(toggle_sidebar)
        self._toc_sidebar_action = toggle_sidebar

        show_image_action = Gio.SimpleAction.new_stateful(
            "toggle_show_image",
            None,
            GLib.Variant.new_boolean(self._show_image),
        )
        show_image_action.connect("activate", self._on_stateful_toggle_activate)
        show_image_action.connect("change-state", self._on_toggle_show_image)
        self.add_action(show_image_action)
        self._show_image_action = show_image_action

        focus_agent_question = Gio.SimpleAction.new("focus_agent_question", None)
        focus_agent_question.connect(
            "activate",
            lambda _a, _p: self._focus_agent_question_entry(),
        )
        self.add_action(focus_agent_question)

        submit_speech_agent_question = Gio.SimpleAction.new("submit_speech_agent_question", None)
        submit_speech_agent_question.connect(
            "activate",
            lambda _a, _p: self._submit_speech_agent_question(),
        )
        self.add_action(submit_speech_agent_question)

        focus_page_number = Gio.SimpleAction.new("focus_page_number", None)
        focus_page_number.connect("activate", lambda _a, _p: self._focus_page_number_entry())
        self.add_action(focus_page_number)

        toggle_ai_panel = Gio.SimpleAction.new("toggle_ai_panel", None)
        toggle_ai_panel.connect(
            "activate",
            lambda _a, _p: self._toggle_embedded_ai_panel_from_shortcut(),
        )
        self.add_action(toggle_ai_panel)

        toggle_minute_order = Gio.SimpleAction.new("toggle_minute_order", None)
        toggle_minute_order.connect(
            "activate",
            lambda _a, _p: self._toggle_minute_order_view(),
        )
        self.add_action(toggle_minute_order)

        focus_grep = Gio.SimpleAction.new("focus_grep", None)
        focus_grep.connect("activate", lambda _a, _p: self._focus_grep_entry())
        self.add_action(focus_grep)

        grep_next_hit = Gio.SimpleAction.new("grep_next_hit", None)
        grep_next_hit.connect("activate", lambda _a, _p: self._navigate_grep_match(1, wrap=True))
        self.add_action(grep_next_hit)

        grep_prev_hit = Gio.SimpleAction.new("grep_prev_hit", None)
        grep_prev_hit.connect("activate", lambda _a, _p: self._navigate_grep_match(-1, wrap=True))
        self.add_action(grep_prev_hit)

        insert_current_page_citation = Gio.SimpleAction.new(
            "insert_current_page_citation",
            None,
        )
        insert_current_page_citation.connect(
            "activate",
            lambda _a, _p: self._insert_current_page_citation_in_prose_or_clipboard(),
        )
        self.add_action(insert_current_page_citation)

        insert_page_citation_range = Gio.SimpleAction.new(
            "insert_page_citation_range",
            None,
        )
        insert_page_citation_range.connect(
            "activate",
            lambda _a, _p: self._insert_page_citation_range_in_prose_or_clipboard(),
        )
        self.add_action(insert_page_citation_range)

        append_selection_citation = Gio.SimpleAction.new(
            "append_selection_citation_to_file",
            GLib.VariantType.new("s"),
        )
        append_selection_citation.connect(
            "activate",
            self._on_append_selection_citation_to_file_action,
        )
        self.add_action(append_selection_citation)

        for name, cb in {
            "next": self._go_next,
            "prev": self._go_prev,
            "first": self._go_first,
            "last": self._go_last,
        }.items():
            act = Gio.SimpleAction.new(name, None)
            act.connect("activate", lambda a, p, cb=cb: cb())  # noqa: ARG005
            self.add_action(act)

        self.set_accels_for_action("app.prev", ["Up"])
        self.set_accels_for_action("app.next", ["Down"])
        self.set_accels_for_action("app.first", ["Home"])
        self.set_accels_for_action("app.last", ["End"])
        self.set_accels_for_action("app.toggle_toc_sidebar", ["<Primary><Shift>z"])
        self.set_accels_for_action("app.toggle_show_image", ["<Primary>i"])
        self.set_accels_for_action("app.focus_grep", ["<Primary>f"])
        self.set_accels_for_action("app.grep_next_hit", ["<Primary>g"])
        self.set_accels_for_action("app.grep_prev_hit", ["<Primary><Shift>g"])
        self.set_accels_for_action(
            "app.insert_current_page_citation",
            ["<Primary><Alt><Shift>c"],
        )
        self.set_accels_for_action(
            "app.insert_page_citation_range",
            ["<Primary><Alt>c"],
        )
        self.set_accels_for_action("app.focus_agent_question", ["<Primary>q"])
        self.set_accels_for_action("app.focus_page_number", ["<Primary>e"])
        self.set_accels_for_action("app.print_current_image", ["<Primary>p"])
        self.set_accels_for_action("app.toggle_ai_panel", ["<Primary><Shift>a"])
        self.set_accels_for_action("app.toggle_minute_order", ["<Primary><Shift>m"])
        self.set_accels_for_action("app.show_shortcuts", ["F1"])
        self._set_sidebar_visible(self._toc_sidebar_visible)

    def _build_shortcuts_window(self) -> Gtk.ShortcutsWindow:
        if self._shortcuts_window:
            return self._shortcuts_window

        window = Gtk.ShortcutsWindow(
            transient_for=self.win,
            modal=False,
            hide_on_close=True,
            title=f"{APPLICATION_NAME} Keyboard Shortcuts",
        )
        window.set_default_size(760, 540)

        navigation_section = Gtk.ShortcutsSection(title="Keyboard Shortcuts")
        navigation_group = Gtk.ShortcutsGroup(title="Transcript")
        navigation_group.append(Gtk.ShortcutsShortcut(title="Previous page", accelerator="Up"))
        navigation_group.append(Gtk.ShortcutsShortcut(title="Next page", accelerator="Down"))
        navigation_group.append(Gtk.ShortcutsShortcut(title="First page", accelerator="Home"))
        navigation_group.append(Gtk.ShortcutsShortcut(title="Last page", accelerator="End"))
        navigation_group.append(
            Gtk.ShortcutsShortcut(title="Focus page number field", accelerator="<Primary>E")
        )
        navigation_group.append(
            Gtk.ShortcutsShortcut(title="Toggle TOC sidebar", accelerator="<Primary><Shift>Z")
        )
        navigation_group.append(
            Gtk.ShortcutsShortcut(title="Toggle image view", accelerator="<Primary>I")
        )
        navigation_group.append(
            Gtk.ShortcutsShortcut(
                title="Open or return from minute order",
                accelerator="<Primary><Shift>M",
            )
        )
        navigation_group.append(
            Gtk.ShortcutsShortcut(title="Print current page image", accelerator="<Primary>P")
        )
        navigation_section.append(navigation_group)

        search_group = Gtk.ShortcutsGroup(title="Grep")
        search_group.append(
            Gtk.ShortcutsShortcut(title="Focus grep search field", accelerator="<Primary>F")
        )
        search_group.append(
            Gtk.ShortcutsShortcut(title="Next grep result", accelerator="<Primary>G")
        )
        search_group.append(
            Gtk.ShortcutsShortcut(title="Previous grep result", accelerator="<Primary><Shift>G")
        )
        search_group.append(
            Gtk.ShortcutsShortcut(
                title="Insert current page citation",
                accelerator="<Primary><Alt><Shift>C",
            )
        )
        search_group.append(
            Gtk.ShortcutsShortcut(
                title="Set or insert citation range",
                accelerator="<Primary><Alt>C",
            )
        )
        navigation_section.append(search_group)

        tools_group = Gtk.ShortcutsGroup(title="AI Panel")
        tools_group.append(
            Gtk.ShortcutsShortcut(
                title="Toggle case tools and focus question box",
                accelerator="<Primary><Shift>A",
            )
        )
        tools_group.append(
            Gtk.ShortcutsShortcut(title="Focus Agent question box", accelerator="<Primary>Q")
        )
        navigation_section.append(tools_group)

        help_group = Gtk.ShortcutsGroup(title="Reference")
        help_group.append(Gtk.ShortcutsShortcut(title="Show keyboard shortcuts", accelerator="F1"))
        navigation_section.append(help_group)
        window.add_section(navigation_section)

        self._shortcuts_window = window
        return window

    def _on_show_shortcuts(self, _action: Gio.SimpleAction, _param: GLib.Variant | None) -> None:
        window = self._build_shortcuts_window()
        if self.win:
            window.set_transient_for(self.win)
        window.present()

    def _on_show_dbus_commands(
        self,
        _action: Gio.SimpleAction,
        _param: GLib.Variant | None,
    ) -> None:
        if not self._commands_window:
            self._commands_window = FocusCommandsWindow(self)
            self._commands_window.connect("close-request", self._on_dbus_commands_closed)
        self._commands_window.present()

    def _on_dbus_commands_closed(self, _window: Gtk.Window) -> bool:
        self._commands_window = None
        return False

    def _on_print_images_action(
        self, _action: Gio.SimpleAction, _param: GLib.Variant | None
    ) -> None:
        if not self.pages:
            self._transient_toast("No pages available to print.")
            return
        window = self._ensure_image_print_window()
        if self._image_print_entry:
            if 0 <= self.current_index < len(self.pages):
                self._image_print_entry.set_text(f"{self.pages[self.current_index]:04d}")
            self._image_print_entry.grab_focus()
            self._image_print_entry.select_region(0, -1)
        window.present()

    def _on_print_current_image_action(
        self, _action: Gio.SimpleAction, _param: GLib.Variant | None
    ) -> None:
        self._print_current_image_page()

    def _ensure_image_print_window(self) -> Adw.ApplicationWindow:
        if self._image_print_window:
            return self._image_print_window

        window = Adw.ApplicationWindow(application=self, transient_for=self.win)
        window.set_title("Print Images")
        window.set_default_size(380, 170)
        window.set_resizable(False)
        window.connect("close-request", self._on_image_print_window_close_request)

        toolbar = Adw.ToolbarView()
        header = Adw.HeaderBar()
        header.add_css_class("flat")
        toolbar.add_top_bar(header)

        root = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        root.set_margin_top(18)
        root.set_margin_bottom(18)
        root.set_margin_start(18)
        root.set_margin_end(18)

        label = Gtk.Label(label="Pages to print")
        label.set_halign(Gtk.Align.START)
        root.append(label)

        entry = Gtk.Entry()
        entry.set_placeholder_text("12, 18-22, 30")
        entry.set_activates_default(True)
        entry.connect("activate", self._on_image_print_entry_activate)
        root.append(entry)

        button_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        button_box.set_halign(Gtk.Align.END)

        cancel_button = Gtk.Button(label="Cancel")
        cancel_button.add_css_class("flat")
        cancel_button.connect("clicked", self._on_image_print_cancel_clicked)
        button_box.append(cancel_button)

        print_button = Gtk.Button(label="Print")
        print_button.add_css_class("flat")
        print_button.add_css_class("suggested-action")
        print_button.connect("clicked", self._on_image_print_clicked)
        button_box.append(print_button)
        root.append(button_box)

        toolbar.set_content(root)
        window.set_content(toolbar)
        window.set_default_widget(print_button)

        self._image_print_window = window
        self._image_print_entry = entry
        return window

    def _on_image_print_window_close_request(self, window: Adw.ApplicationWindow) -> bool:
        window.set_visible(False)
        return True

    def _on_image_print_cancel_clicked(self, _button: Gtk.Button) -> None:
        if self._image_print_window:
            self._image_print_window.set_visible(False)

    def _on_image_print_entry_activate(self, _entry: Gtk.Entry) -> None:
        self._start_image_print()

    def _on_image_print_clicked(self, _button: Gtk.Button) -> None:
        self._start_image_print()

    def _parse_image_page_selection(self, raw: str) -> list[int] | None:
        return parse_image_page_selection(raw)

    def _collect_printable_image_pages(
        self, requested_pages: list[int]
    ) -> tuple[list[int], int, int]:
        available_pages = set(self.pages)
        printable_pages: list[int] = []
        missing_pages = 0
        missing_images = 0
        for page in requested_pages:
            if page not in available_pages:
                missing_pages += 1
                continue
            image_path = self._image_path_for_page(page)
            if not image_path.exists():
                missing_images += 1
                continue
            printable_pages.append(page)
        return printable_pages, missing_pages, missing_images

    def _start_image_print(self) -> None:
        if not self._image_print_entry:
            return
        requested_pages = self._parse_image_page_selection(self._image_print_entry.get_text())
        if requested_pages is None:
            self._transient_toast(
                "Enter pages like 12, 18-22, 30.",
                window=self._image_print_window,
            )
            return

        printable_pages, missing_pages, missing_images = self._collect_printable_image_pages(
            requested_pages
        )
        if not printable_pages:
            self._transient_toast(
                "No printable images found for that selection.",
                window=self._image_print_window,
            )
            return
        skipped_parts: list[str] = []
        if missing_pages:
            skipped_parts.append(f"{missing_pages} unavailable page(s)")
        if missing_images:
            skipped_parts.append(f"{missing_images} missing image(s)")
        skipped_message = "Skipped " + " and ".join(skipped_parts) + "." if skipped_parts else ""
        self._run_image_print_operation(
            printable_pages,
            Gtk.PrintOperationAction.PRINT_DIALOG,
            skipped_message=skipped_message,
        )

    def _print_current_image_page(self) -> None:
        if not self.pages:
            self._transient_toast("No pages available to print.")
            return
        if self.current_index < 0 or self.current_index >= len(self.pages):
            self._transient_toast("No current page available to print.")
            return
        page = self.pages[self.current_index]
        printable_pages, _missing_pages, missing_images = self._collect_printable_image_pages([page])
        if not printable_pages:
            if missing_images:
                self._transient_toast(f"No image found for page {page:04d}.")
            else:
                self._transient_toast("No printable image found for the current page.")
            return
        self._run_image_print_operation(printable_pages, Gtk.PrintOperationAction.PRINT)

    def _run_image_print_operation(
        self,
        printable_pages: list[int],
        action: Gtk.PrintOperationAction,
        *,
        skipped_message: str = "",
    ) -> None:
        self._image_print_pages = printable_pages
        operation = Gtk.PrintOperation()
        operation.set_use_full_page(True)
        operation.set_job_name(self._build_image_print_job_name(printable_pages))
        operation.connect("begin-print", self._on_image_print_begin_print)
        operation.connect("draw-page", self._on_image_print_draw_page)
        if self._image_print_window:
            self._image_print_window.set_visible(False)
        if skipped_message:
            self._transient_toast(skipped_message)
        try:
            operation.run(action, self.win)
        except GLib.Error as exc:
            self._transient_toast(f"Print failed: {exc.message}")

    def _build_image_print_job_name(self, pages: list[int]) -> str:
        if not pages:
            return "Focus image pages"
        if len(pages) == 1:
            return f"Focus image page {pages[0]:04d}"
        contiguous = pages == list(range(min(pages), max(pages) + 1))
        if contiguous:
            return f"Focus image pages {pages[0]:04d}-{pages[-1]:04d}"
        if len(pages) <= 4:
            page_label = ", ".join(f"{page:04d}" for page in pages)
        else:
            page_label = f"{pages[0]:04d}-{pages[-1]:04d}"
        return f"Focus image pages {page_label}"

    def _on_image_print_begin_print(
        self, operation: Gtk.PrintOperation, _context: Gtk.PrintContext
    ) -> None:
        operation.set_n_pages(len(self._image_print_pages))

    def _on_image_print_draw_page(
        self, _operation: Gtk.PrintOperation, context: Gtk.PrintContext, page_num: int
    ) -> None:
        if page_num < 0 or page_num >= len(self._image_print_pages):
            return
        page = self._image_print_pages[page_num]
        image_path = self._image_path_for_page(page)
        try:
            pixbuf = GdkPixbuf.Pixbuf.new_from_file(str(image_path))
        except GLib.Error:
            return

        dpi_x = context.get_dpi_x()
        dpi_y = context.get_dpi_y()
        margin_left = DEFAULT_PRINT_MARGIN_IN * dpi_x
        margin_right = DEFAULT_PRINT_MARGIN_IN * dpi_x
        margin_top = DEFAULT_PRINT_MARGIN_IN * dpi_y
        margin_bottom = DEFAULT_PRINT_MARGIN_IN * dpi_y
        content_width = max(1.0, context.get_width() - margin_left - margin_right)
        content_height = max(1.0, context.get_height() - margin_top - margin_bottom)

        image_width = max(1, pixbuf.get_width())
        image_height = max(1, pixbuf.get_height())
        scale = min(content_width / image_width, content_height / image_height)
        scaled_width = image_width * scale
        scaled_height = image_height * scale
        x = margin_left + (content_width - scaled_width) / 2
        y = margin_top + (content_height - scaled_height) / 2

        cr = context.get_cairo_context()
        cr.save()
        cr.translate(x, y)
        cr.scale(scale, scale)
        Gdk.cairo_set_source_pixbuf(cr, pixbuf, 0, 0)
        cr.paint()
        cr.restore()

    def _on_choose_input_dir(self, _action: Gio.SimpleAction, _param: GLib.Variant | None) -> None:
        if not self.win:
            return
        dialog = Gtk.FileDialog()
        dialog.set_title("Select Input Directory")
        dialog.set_modal(True)
        if self.input_dir.exists():
            try:
                dialog.set_initial_folder(Gio.File.new_for_path(str(self.input_dir)))
            except (TypeError, AttributeError):
                pass
        dialog.select_folder(self.win, None, self._on_input_dir_dialog_response)
        self._input_dir_dialog = dialog

    def _on_input_dir_dialog_response(self, dialog: Gtk.FileDialog, result: Gio.AsyncResult) -> None:
        try:
            file = dialog.select_folder_finish(result)
        except GLib.Error as exc:
            if not exc.matches(Gio.io_error_quark(), Gio.IOErrorEnum.CANCELLED):
                self._transient_toast(f"Directory selection failed: {exc.message}")
        else:
            path_str = file.get_path() if file else None
            if path_str:
                self._apply_input_dir(Path(path_str))
        if self._input_dir_dialog is dialog:
            self._input_dir_dialog = None

    def _on_open_ai_settings(self, _action: Gio.SimpleAction, _param: GLib.Variant | None) -> None:
        try:
            window = self._ensure_ai_settings_window()
        except Exception as exc:  # noqa: BLE001
            self._transient_toast(f"Settings unavailable: {exc}")
            return
        if window:
            window.present()

    def _ensure_ai_settings_window(self) -> "AiSettingsWindow" | None:
        if self._ai_settings_window:
            return self._ai_settings_window
        window = AiSettingsWindow(self)
        window.connect("close-request", self._on_ai_settings_window_close_request)
        self._ai_settings_window = window
        return window

    def _on_ai_settings_window_close_request(self, window: "AiSettingsWindow") -> bool:
        if self._ai_settings_window is window:
            self._ai_settings_window = None
        return False

    def _on_main_window_close_request(self, _window: Adw.ApplicationWindow) -> bool:
        self._stop_grep_search_if_running()
        self._stop_agent_terminal()
        self._stop_agent_answer_polling()
        self._cleanup_agent_answer_artifact()
        self._stop_ai_panel_resize_tracking()
        self._cancel_pending_summary_scroll_restore()
        if self._image_print_window:
            self._image_print_window.destroy()
            self._image_print_window = None
        if self._transcript_breakdown_window:
            self._transcript_breakdown_window.destroy()
            self._transcript_breakdown_window = None
            self._transcript_breakdown_buffer = None
        return False

    def on_ai_settings_saved(self, settings: AiSettings) -> None:
        self._ai_settings = settings
        if not self._ai_settings.page_prompt.strip():
            self._ai_settings.page_prompt = DEFAULT_SUMMARIZATION_PROMPT
        if not self._ai_settings.range_prompt.strip():
            self._ai_settings.range_prompt = DEFAULT_SUMMARIZATION_PROMPT
        self._refresh_ai_quote_colors()
        self._apply_text_color(self._current_text_color)
        if self.textview:
            self._load_current()
        self._transient_toast("AI settings updated.")

    def _apply_input_dir(self, path: Path) -> None:
        self._stop_grep_search_if_running()
        target = path.expanduser()
        resolved = target.resolve(strict=False)
        if not resolved.exists() or not resolved.is_dir():
            self._transient_toast(f"Directory not found: {resolved}")
            return
        normalized = _normalize_input_dir(resolved)
        if not normalized.exists() or not normalized.is_dir():
            self._transient_toast(f"Directory not found: {normalized}")
            return
        self._set_show_image(False, silent=True)
        self._close_transcript_breakdown_window()
        self._reset_view_states()
        self.input_dir = normalized
        self._record_layout = _resolve_record_layout(self.input_dir)
        self._case_name = _read_case_name(self._record_layout.root)
        save_input_dir_to_config(normalized)
        if not self.text_dir.exists():
            self._transient_toast(f"Text pages directory not found: {self.text_dir}")
        self._grep_phrase_raw = None
        self._grep_regex = None
        self._grep_active = False
        self._grep_hits.clear()
        self._matching_pages.clear()
        self._matching_lookup.clear()
        self._grep_match_order = []
        self._grep_current_match_index = -1
        self._scan_pages()
        self._refresh_transcript_breakdown_action()
        self._load_toc_from_disk_async()
        if self.pages:
            self.current_index = 0
            self._load_current()
            self._persist_active_view_state()
        else:
            self._update_header()
            self._set_window_title("No pages found")
            self._set_text("No .txt pages found in:\n" + str(self.text_dir))

    def _on_scroll(self, ctrl: Gtk.EventControllerScroll, dx: float, dy: float) -> bool:
        state = ctrl.get_current_event_state()
        if state & Gdk.ModifierType.CONTROL_MASK:
            if dy > 0:
                self._go_next()
            elif dy < 0:
                self._go_prev()
            return True
        return False

    def _on_image_scroll(self, _ctrl: Gtk.EventControllerScroll, _dx: float, dy: float) -> bool:
        if dy > 0:
            self._go_next()
            return True
        if dy < 0:
            self._go_prev()
            return True
        return False

    def _on_key(self, _ctrl: Gtk.EventControllerKey, keyval: int, keycode: int, state: int) -> bool:  # noqa: ARG002
        key = Gdk.keyval_name(keyval)
        if key in ("g", "G") and (state & Gdk.ModifierType.CONTROL_MASK):
            direction = -1 if (state & Gdk.ModifierType.SHIFT_MASK) else 1
            if self._navigate_grep_match(direction, wrap=True):
                return True
        if key == "Up":
            self._go_prev(); return True
        if key == "Down":
            self._go_next(); return True
        if key == "Home":
            self._go_first(); return True
        if key == "End":
            self._go_last(); return True
        if key in ("e", "E") and (state & Gdk.ModifierType.CONTROL_MASK):
            self._focus_page_number_entry(); return True
        if key == "f" and (state & Gdk.ModifierType.CONTROL_MASK):
            self._focus_grep_entry(); return True
        if key in ("p", "P") and (state & Gdk.ModifierType.CONTROL_MASK):
            self._print_current_image_page(); return True
        if (
            key in ("A", "a")
            and (state & Gdk.ModifierType.CONTROL_MASK)
            and (state & Gdk.ModifierType.SHIFT_MASK)
        ):
            self._toggle_embedded_ai_panel_from_shortcut()
            return True
        return False

    def _on_page_back_one_clicked(self, _button: Gtk.Button) -> None:
        self._go_prev()

    def _on_page_forward_one_clicked(self, _button: Gtk.Button) -> None:
        self._go_next()

    def _on_minute_order_clicked(self, _button: Gtk.Button) -> None:
        self._toggle_minute_order_view()

    def _toggle_minute_order_view(self) -> None:
        if not self.pages:
            return
        if self._viewing_return_minute_order() and self._minute_order_return_page is not None:
            return_page = self._minute_order_return_page
            self._minute_order_return_page = None
            self._minute_order_return_boundary = None
            self._show_page_from_link(str(return_page))
            self._set_show_image(False, silent=True)
            return

        current_page = self._current_page_number()
        target = self._current_minute_order_boundary()
        if current_page is None or target is None:
            self._transient_toast("No matching minute order for this page.")
            return
        self._minute_order_return_page = current_page
        self._minute_order_return_boundary = target
        self._show_page_from_link(str(target.start_page))
        self._set_show_image(True)

    def _on_page_number_activate(self, entry: Gtk.Entry) -> None:
        if not self.pages:
            return
        target = entry.get_text().strip()
        if not target:
            self._update_page_nav_buttons()
            return
        query = parse_transcript_page_jump_query(target)
        if query is None:
            self._transient_toast("Enter a page, citation page, or file page.")
            self._update_page_nav_buttons()
            return
        self._show_page_from_query(query)
        self._update_page_nav_buttons()

    def _show_page_from_query(self, query: TranscriptPageJumpQuery) -> None:
        if query.kind == "file":
            self._show_page_from_link(str(query.page_number))
            return
        if query.kind == "citation":
            matches = self._transcript_page_index.by_citation_key.get(
                _citation_key(query.citation_prefix, query.page_number),
                (),
            )
            if not matches:
                self._transient_toast(
                    f"{query.citation_prefix} {query.page_number} not available"
                )
                return
            self._show_or_choose_transcript_page(matches)
            return

        matches = self._transcript_page_index.by_transcript_number.get(query.page_number, ())
        if matches:
            self._show_or_choose_transcript_page(matches)
            return
        self._show_page_from_link(str(query.page_number))

    def _show_or_choose_transcript_page(
        self,
        matches: Sequence[TranscriptPageLabel],
    ) -> None:
        if not matches:
            return
        if len(matches) == 1:
            self._show_transcript_page_label(matches[0])
            return
        self._show_transcript_page_chooser(matches)

    def _show_transcript_page_label(self, label: TranscriptPageLabel) -> None:
        self._show_page_from_link(str(label.file_page))

    def _show_transcript_page_chooser(
        self,
        matches: Sequence[TranscriptPageLabel],
    ) -> None:
        if not self._page_number_entry:
            return
        if self._page_jump_popover:
            self._page_jump_popover.popdown()
            self._page_jump_popover = None

        popover = Gtk.Popover()
        popover.set_parent(self._page_number_entry)
        popover.set_autohide(True)
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        box.set_margin_top(6)
        box.set_margin_bottom(6)
        box.set_margin_start(6)
        box.set_margin_end(6)

        heading = Gtk.Label(label="Choose citation page")
        heading.add_css_class("dim-label")
        heading.set_xalign(0.0)
        heading.set_margin_bottom(2)
        box.append(heading)

        for label in matches:
            button_label = format_transcript_page_choice_label(label)
            button = Gtk.Button(label=button_label)
            button.add_css_class("flat")
            button.add_css_class("no-bold")
            button.set_halign(Gtk.Align.FILL)
            if label.series_description:
                button.set_tooltip_text(label.series_description)
            button.connect("clicked", self._on_transcript_page_choice_clicked, label, popover)
            box.append(button)

        popover.set_child(box)
        self._page_jump_popover = popover
        popover.popup()

    def _on_transcript_page_choice_clicked(
        self,
        _button: Gtk.Button,
        label: TranscriptPageLabel,
        popover: Gtk.Popover,
    ) -> None:
        popover.popdown()
        if self._page_jump_popover is popover:
            self._page_jump_popover = None
        self._show_transcript_page_label(label)
        self._update_page_nav_buttons()

    def _set_right_scroll_active(self, active: bool) -> None:
        if self._right_scroll_active == active:
            return
        self._right_scroll_active = active
        if not self._right_scroll_zone:
            return
        if active:
            self._right_scroll_zone.add_css_class("hover")
        else:
            self._right_scroll_zone.remove_css_class("hover")

    def _on_right_scroll_zone_clicked(self, _button: Gtk.Button) -> None:
        self._go_next()

    def _on_right_scroll_zone_scroll(
        self, _ctrl: Gtk.EventControllerScroll, _dx: float, dy: float
    ) -> bool:
        if dy > 0:
            self._go_next()
            return True
        if dy < 0:
            self._go_prev()
            return True
        return False

    def _focus_grep_entry(self) -> None:
        if self._grep_entry:
            self._grep_entry.grab_focus()
            self._grep_entry.select_region(0, -1)

    def _focus_page_number_entry(self) -> None:
        if not self._page_number_entry or not self.pages:
            return
        if 0 <= self.current_index < len(self.pages):
            self._page_number_entry.set_text(self._current_page_entry_text())
        self._page_number_entry.grab_focus()
        self._page_number_entry.select_region(0, -1)

    def _set_grep_entry_text(self, text: str) -> None:
        if not self._grep_entry:
            return
        self._grep_entry_sync_guard = True
        try:
            self._grep_entry.set_text(text)
        finally:
            self._grep_entry_sync_guard = False

    def _clear_grep_for_search_entry(self) -> None:
        self._grep_phrase_raw = None
        self._clear_grep_state()
        self._load_current()

    def _on_grep_entry_activate(self, entry: Gtk.SearchEntry) -> None:
        phrase = entry.get_text()
        self._apply_grep(phrase)

    def _on_grep_search_changed(self, entry: Gtk.SearchEntry) -> None:
        if self._grep_entry_sync_guard:
            return
        applied_phrase = (self._grep_phrase_raw or "").strip()
        if entry.get_text().strip() == applied_phrase:
            return
        if not applied_phrase and not self._grep_active and not self._grep_search_thread:
            return
        self._clear_grep_for_search_entry()

    def _on_grep_stop_search(self, _entry: Gtk.SearchEntry) -> None:
        self._set_grep_entry_text("")
        self._clear_grep_for_search_entry()
        if self.textview:
            self.textview.grab_focus()

    def _on_search_selection_changed(self, *_args: object) -> None:
        self._refresh_search_highlighted_button()

    def _visible_search_selection(self) -> str:
        if not self._show_image:
            selection = self._get_main_text_selection()
            if selection:
                return selection
        if (
            self._ai_panel_revealer
            and self._ai_panel_revealer.get_reveal_child()
        ):
            return self._get_ai_panel_selection()
        return ""

    def _refresh_search_highlighted_button(self) -> None:
        if not self._grep_highlighted_button:
            return
        self._grep_highlighted_button.set_visible(
            bool(self._visible_search_selection())
        )

    def _on_grep_search_highlighted_clicked(self, _button: Gtk.Button) -> None:
        phrase = self._visible_search_selection()
        if not phrase:
            self._transient_toast("Highlight text in the transcript or case tools to search.")
            return
        self._set_grep_entry_text(phrase)
        self._apply_grep(phrase)

    def _get_main_text_selection(self) -> str:
        if not self.textview:
            return ""
        return self._get_buffer_selection(self.textview.get_buffer())

    def _get_ai_panel_selection(self) -> str:
        if self._ai_active_view == AI_VIEW_AGENT_QA:
            return self._get_agent_panel_selection()
        buffer = None
        if self._ai_active_view == AI_VIEW_FILE:
            buffer = self._summary_buffer
        else:
            state = self._ai_outputs.get(self._ai_active_view)
            if state:
                buffer = state.buffer
        return self._get_buffer_selection(buffer)

    def _get_agent_panel_selection(self) -> str:
        if (
            self._agent_subview_name == AGENT_SUBVIEW_SESSION
            and Vte is not None
            and self._agent_terminal is not None
        ):
            try:
                selected = self._agent_terminal.get_text_selected(Vte.Format.TEXT)
            except Exception:
                selected = None
            return (selected or "").strip()
        state = self._ai_outputs.get(AI_VIEW_AGENT_QA)
        return self._get_buffer_selection(state.buffer if state else None)

    def _get_buffer_selection(self, buffer: Gtk.TextBuffer | None) -> str:
        if not buffer:
            return ""
        selection = buffer.get_selection_bounds()
        if not selection:
            return ""
        if len(selection) == 3:
            has_selection, start_iter, end_iter = selection
            if not has_selection:
                return ""
        else:
            start_iter, end_iter = selection
        text = buffer.get_text(start_iter, end_iter, True)
        return text.strip()

    def _go_by(self, delta: int) -> None:
        if not self.pages:
            return
        if self._grep_active or self._grep_search_thread:
            self._clear_grep_state()
        new_index = self.current_index + delta
        new_index = max(0, min(len(self.pages) - 1, new_index))
        if new_index != self.current_index:
            self.current_index = new_index
            self._load_current()
        else:
            self._edge_flash()

    def _go_prev(self) -> None:
        self._go_by(-1)

    def _go_next(self) -> None:
        self._go_by(1)

    def _go_prev_ten(self) -> None:
        self._go_by(-10)

    def _go_next_ten(self) -> None:
        self._go_by(10)

    def _go_first(self) -> None:
        if not self.pages:
            return
        if self._grep_active or self._grep_search_thread:
            self._clear_grep_state()
        self.current_index = 0
        self._load_current()

    def _go_last(self) -> None:
        if not self.pages:
            return
        if self._grep_active or self._grep_search_thread:
            self._clear_grep_state()
        self.current_index = len(self.pages) - 1
        self._load_current()

    def _toggle_embedded_ai_panel_from_shortcut(self) -> None:
        if self._ai_panel_toggle:
            current_visible = self._ai_panel_toggle.get_active()
        elif self._ai_panel_revealer:
            current_visible = self._ai_panel_revealer.get_child_revealed()
        else:
            current_visible = False
        new_visible = not bool(current_visible)
        self._set_ai_panel_visible(new_visible)
        if new_visible:
            self._focus_agent_question_entry()

    def _on_ai_panel_toggled(self, button: Gtk.ToggleButton) -> None:
        if self._ai_panel_toggle_guard:
            return
        self._set_ai_panel_visible(button.get_active())

    def _set_ai_panel_visible(self, visible: bool) -> None:
        was_visible = bool(
            self._ai_panel_revealer
            and self._ai_panel_revealer.get_reveal_child()
        )
        if not visible and was_visible and self._ai_active_view == AI_VIEW_FILE:
            self._capture_summary_scroll_position()
            fraction = self._current_view_state().summary_scroll_fraction
            if fraction is not None:
                self._prepare_summary_scroll_restore(fraction)
        elif visible and not was_visible and self._ai_active_view == AI_VIEW_FILE:
            fraction = self._current_view_state().summary_scroll_fraction
            if fraction is not None:
                self._prepare_summary_scroll_restore(fraction)
        if self._ai_panel_revealer:
            self._ai_panel_revealer.set_reveal_child(visible)
            if visible:
                self._update_embedded_ai_panel_height(force=True)
            else:
                self._reset_embedded_ai_panel_sizing()
        if visible and self._ai_active_view == AI_VIEW_FILE:
            self._restore_summary_scroll_position(self._summary_loaded_path)
        self._current_view_state().ai_panel_visible = visible
        self._update_ai_panel_toggle(visible)
        self._refresh_search_highlighted_button()

    def _ensure_ai_panel_visible(self) -> None:
        self._set_ai_panel_visible(True)

    def _open_case_tool_view(self, view_name: str) -> None:
        self._ensure_ai_panel_visible()
        self._set_ai_view(view_name)

    def _open_case_tool_summary(self, source: str) -> None:
        self._ensure_ai_panel_visible()
        if source == SUMMARY_SOURCE_MINUTES:
            self._on_minutes_summary_clicked(None)
        elif source == SUMMARY_SOURCE_HEARING:
            self._on_hearing_summary_clicked(None)
        elif source == SUMMARY_SOURCE_REPORTS:
            self._on_reports_summary_clicked(None)

    def _case_tool_description(self, view_name: str | None = None) -> str:
        target = view_name or self._ai_active_view
        if target == AI_VIEW_FILE:
            return SUMMARY_SOURCE_DESCRIPTIONS.get(
                self._summary_active_source,
                "Browse prepared case summaries; verify material points in the record.",
            )
        return CASE_TOOL_DESCRIPTIONS.get(
            target,
            "Choose a record tool.",
        )

    def _refresh_case_tools_status(self, *, preserve_busy: bool = True) -> None:
        if (
            preserve_busy
            and self._ai_spinner is not None
            and self._ai_spinner.get_spinning()
        ):
            return
        self._update_ai_status("", spinning=False)

    def _set_ai_view(self, view_name: str) -> None:
        target = view_name
        if target not in self._ai_outputs and target != AI_VIEW_FILE:
            target = AI_VIEW_SUMMARIZE
        previous = self._ai_active_view
        if previous == AI_VIEW_FILE and target != AI_VIEW_FILE:
            # Capture before the outgoing summary scroller is collapsed.
            self._capture_summary_scroll_position()
            self._cancel_pending_summary_scroll_restore()
        elif previous != AI_VIEW_FILE and target == AI_VIEW_FILE:
            state = self._current_view_state()
            if (
                state.summary_loaded_path == self._summary_loaded_path
                and state.summary_scroll_fraction is not None
            ):
                self._prepare_summary_scroll_restore(state.summary_scroll_fraction)
        self._ai_active_view = target
        self._current_view_state().ai_active_view = target
        if target == AI_VIEW_FILE and not self._auto_loading_summary:
            self._ensure_summary_for_active_view()
        if self._ai_view_stack and self._ai_view_stack.get_visible_child_name() != target:
            self._ai_view_stack.set_visible_child_name(target)
        if (
            self._ai_controls_stack
            and self._ai_controls_stack.get_child_by_name(target) is not None
            and self._ai_controls_stack.get_visible_child_name() != target
        ):
            self._ai_controls_stack.set_visible_child_name(target)
        self._sync_ai_view_toggles(target)
        self._refresh_case_tools_status()
        if self._ai_panel_revealer and self._ai_panel_revealer.get_reveal_child():
            self._update_embedded_ai_panel_height(force=True)
        if target == AI_VIEW_FILE:
            self._restore_summary_scroll_position(self._summary_loaded_path)
            self._update_summary_progress_label()
        elif target == AI_VIEW_SUMMARIZE:
            self._maybe_prefill_sum_range_for_current_page()
        self._refresh_search_highlighted_button()

    def _ensure_summary_for_active_view(self) -> None:
        state = self._current_view_state()
        if (
            state.summary_loaded_path
            and self._summary_loaded_path
            and state.summary_loaded_path == self._summary_loaded_path
            and self._summary_has_text()
        ):
            self._set_summary_active_source(state.summary_active_source)
            return
        if state.summary_loaded_path and state.summary_loaded_path.exists():
            self._load_summary_from_path(
                state.summary_loaded_path,
                allow_auto=True,
                source=state.summary_active_source,
                show_toast=False,
            )
            return
        self._auto_load_summary_file()

    def _sync_ai_view_toggles(self, target: str) -> None:
        if (
            not self._ai_view_buttons
            and not self._summary_source_buttons
            and not self._more_case_tools_button
        ):
            return
        self._ai_view_toggle_guard = True
        try:
            for view_name, button in self._ai_view_buttons.items():
                active = view_name == target
                button.set_active(active)
                if active:
                    button.add_css_class("focus-ai-view-active")
                else:
                    button.remove_css_class("focus-ai-view-active")
            for source, button in self._summary_source_buttons.items():
                active = target == AI_VIEW_FILE and source == self._summary_active_source
                button.set_active(active)
                if active:
                    button.add_css_class("focus-ai-view-active")
                else:
                    button.remove_css_class("focus-ai-view-active")
            if self._more_case_tools_button:
                exposed_summary_active = (
                    target == AI_VIEW_FILE
                    and self._summary_active_source in self._summary_source_buttons
                )
                more_active = target in {AI_VIEW_SUMMARIZE, AI_VIEW_EXTRACT} or (
                    target == AI_VIEW_FILE and not exposed_summary_active
                )
                if more_active:
                    self._more_case_tools_button.add_css_class("focus-ai-view-active")
                else:
                    self._more_case_tools_button.remove_css_class("focus-ai-view-active")
        finally:
            self._ai_view_toggle_guard = False

    def _on_ai_view_changed(self, stack: Adw.ViewStack, _pspec: GObject.ParamSpec) -> None:
        name = stack.get_visible_child_name() or AI_VIEW_AGENT_QA
        self._set_ai_view(name)

    def _on_ai_mode_button_toggled(
        self,
        button: Gtk.ToggleButton,
        view_name: str,
    ) -> None:
        if self._ai_view_toggle_guard:
            return
        if not button.get_active():
            if self._ai_active_view == view_name:
                self._sync_ai_view_toggles(view_name)
            return
        self._set_ai_view(view_name)

    def _on_summary_mode_button_toggled(
        self,
        button: Gtk.ToggleButton,
        source: str,
    ) -> None:
        if self._ai_view_toggle_guard:
            return
        if not button.get_active():
            if (
                self._ai_active_view == AI_VIEW_FILE
                and self._summary_active_source == source
            ):
                self._sync_ai_view_toggles(AI_VIEW_FILE)
            return
        self._open_case_tool_summary(source)
        self._sync_ai_view_toggles(self._ai_active_view)

    def _on_summarize_range_activate(self, _entry: Gtk.Entry) -> None:
        self._summarize_page_range()

    def _on_summarize_range_button_clicked(self, _button: Gtk.Button) -> None:
        self._summarize_page_range()

    def _show_sum_range_choice_popover(
        self,
        choices: Sequence[SumRangeChoice],
    ) -> None:
        entry = self._ai_range_start_entry
        if entry is None or not choices:
            return
        if self._sum_range_choice_popover:
            self._sum_range_choice_popover.popdown()
            self._sum_range_choice_popover = None

        popover = Gtk.Popover()
        popover.set_parent(entry)
        popover.set_autohide(True)
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        box.set_margin_top(6)
        box.set_margin_bottom(6)
        box.set_margin_start(6)
        box.set_margin_end(6)

        heading = Gtk.Label(label="Choose citation range")
        heading.add_css_class("dim-label")
        heading.set_xalign(0.0)
        heading.set_margin_bottom(2)
        box.append(heading)

        for choice in choices:
            button = Gtk.Button(label=choice.label)
            button.add_css_class("flat")
            button.add_css_class("no-bold")
            button.set_halign(Gtk.Align.FILL)
            description = choice.start.series_description or choice.end.series_description
            if description:
                button.set_tooltip_text(description)
            button.connect("clicked", self._on_sum_range_choice_clicked, choice, popover)
            box.append(button)

        popover.set_child(box)
        self._sum_range_choice_popover = popover
        popover.popup()

    def _on_sum_range_choice_clicked(
        self,
        _button: Gtk.Button,
        choice: SumRangeChoice,
        popover: Gtk.Popover,
    ) -> None:
        popover.popdown()
        if self._sum_range_choice_popover is popover:
            self._sum_range_choice_popover = None
        if not self._ai_range_start_entry or not self._ai_range_end_entry:
            return
        self._ai_range_update_guard = True
        try:
            self._ai_range_start_entry.set_text(choice.start.citation_label)
            self._ai_range_end_entry.set_text(choice.end.citation_label)
        finally:
            self._ai_range_update_guard = False
        state = self._current_view_state()
        if self._ai_range_start_entry:
            state.ai_range_start_text = self._ai_range_start_entry.get_text()
        if self._ai_range_end_entry:
            state.ai_range_end_text = self._ai_range_end_entry.get_text()
        self._ai_range_autofilled = False
        state.ai_range_autofilled = False
        self._refresh_sum_range_state()
        self._summarize_page_range()

    def _summarize_page_range(self) -> None:
        if not self.pages:
            self._ai_transient_toast("No pages available to summarize.")
            return
        if not self._ai_range_start_entry or not self._ai_range_end_entry:
            return
        validation = self._sum_range_validation()
        self._refresh_sum_range_state()
        if validation.ambiguous_range_choices:
            self._show_sum_range_choice_popover(validation.ambiguous_range_choices)
            return
        if validation.ambiguous_field and validation.ambiguous_matches:
            choices = tuple(
                SumRangeChoice(label, label)
                for label in validation.ambiguous_matches
            )
            self._show_sum_range_choice_popover(choices)
            return
        if not validation.valid or validation.start_page is None or validation.end_page is None:
            self._ai_transient_toast(validation.message)
            return
        start_page = validation.start_page
        end_page = validation.end_page
        targets = validation.targets
        self._set_ai_view(AI_VIEW_SUMMARIZE)
        parts: list[str] = []
        for page in targets:
            content, _, _ = self._read_page_text(page)
            page_label = format_toc_page_subtitle(page, self._transcript_page_index)
            parts.append(f"{page_label}\n\n{content}\n\n")
        combined = "".join(parts)
        label = f"{validation.start_label}-{validation.end_label}"
        self._start_ai_stream(
            label=label,
            content=combined,
            prompt_kind="range",
        )
        self._ai_range_autofilled = True
        self._current_view_state().ai_range_autofilled = True

    def _parse_page_range(self, raw: str) -> tuple[int, int] | None:
        if not raw:
            return None
        match = re.fullmatch(r"\s*(\d{1,4})(?:\s*-\s*(\d{1,4}))?\s*", raw)
        if not match:
            return None
        start = int(match.group(1))
        end = int(match.group(2) or start)
        if start > end:
            start, end = end, start
        return start, end

    def _on_extract_page_clicked(self, _button: Gtk.Button) -> None:
        if not self.pages:
            self._ai_transient_toast("No page loaded to extract from.")
            return
        self._set_ai_view(AI_VIEW_EXTRACT)
        page = self.pages[self.current_index]
        content, _, _ = self._read_page_text(page)
        payload = f"Page {page:04d}\n\n{content}"
        self._start_ai_stream(
            label=f"page {page:04d}",
            content=payload,
            prompt_kind="extract",
        )

    def _on_extract_range_activate(self, _entry: Gtk.Entry) -> None:
        self._extract_page_range()

    def _on_extract_range_button_clicked(self, _button: Gtk.Button) -> None:
        self._extract_page_range()

    def _extract_page_range(self) -> None:
        if not self.pages:
            self._ai_transient_toast("No pages available to extract from.")
            return
        if not self._extract_range_entry:
            return
        raw = self._extract_range_entry.get_text().strip()
        page_range = self._parse_page_range(raw)
        if page_range is None:
            self._ai_transient_toast("Enter a page range like 10-25.")
            return
        start_page, end_page = page_range
        targets = [p for p in self.pages if start_page <= p <= end_page]
        if not targets:
            self._ai_transient_toast("No matching pages found in that range.")
            return
        self._set_ai_view(AI_VIEW_EXTRACT)
        parts: list[str] = []
        for page in targets:
            content, _, _ = self._read_page_text(page)
            parts.append(f"Page {page:04d}\n\n{content}\n\n")
        combined = "".join(parts)
        label = f"pages {start_page:04d}-{end_page:04d}"
        self._start_ai_stream(
            label=label,
            content=combined,
            prompt_kind="extract",
        )
        self._extract_range_entry.set_text("")

    def _on_agent_question_activate(self, _entry: Gtk.Entry) -> None:
        self._launch_agent_question()

    def _on_agent_question_changed(self, _entry: Gtk.Entry) -> None:
        if self._agent_question_entry:
            self._current_view_state().agent_question_text = (
                self._agent_question_entry.get_text()
            )
        self._refresh_agent_submit_state()

    def _on_agent_question_submit_clicked(self, _button: Gtk.Button) -> None:
        self._launch_agent_question()

    def _refresh_agent_submit_state(self) -> None:
        if not self._agent_submit_button:
            return
        has_question = bool(
            self._agent_question_entry
            and self._agent_question_entry.get_text().strip()
        )
        self._agent_submit_button.set_sensitive(has_question)

    def _focus_agent_question_entry(self) -> None:
        self._ensure_ai_panel_visible()
        self._set_ai_view(AI_VIEW_AGENT_QA)
        if self._agent_question_entry:
            self._agent_question_entry.grab_focus()
            self._agent_question_entry.select_region(0, -1)

    def _agent_terminal_unavailable(self) -> None:
        self._ensure_ai_panel_visible()
        self._set_ai_view(AI_VIEW_AGENT_QA)
        self._ai_transient_toast(
            "Install gir1.2-vte-3.91 and libvte-2.91-gtk4-0 to use the embedded Agent terminal."
        )

    def _agent_python_path(self) -> str:
        venv_python = PROJECT_DIR / ".venv" / "bin" / "python"
        if venv_python.is_file():
            return str(venv_python)
        return sys.executable or "python3"

    def _create_agent_workspace(self) -> Path:
        cache_root = Path(
            os.environ.get("XDG_CACHE_HOME", Path.home() / ".cache")
        ).expanduser()
        parent = cache_root / "focus-agent-workspaces"
        parent.mkdir(parents=True, exist_ok=True)
        return Path(tempfile.mkdtemp(prefix="workspace.", dir=parent))

    def _clear_agent_answer(self) -> None:
        self._agent_last_answer_text = ""
        self._agent_answer_status = ""
        state = self._ai_outputs.get(AI_VIEW_AGENT_QA)
        if state:
            state.raw = ""
            self._apply_ai_output_links("", state)
        self._current_view_state().ai_output_raw[AI_VIEW_AGENT_QA] = ""
        self._sync_agent_output_header_state()
        self._queue_embedded_ai_panel_height_update()

    def _stop_agent_answer_polling(self) -> None:
        if self._agent_answer_poll_id is not None:
            GLib.source_remove(self._agent_answer_poll_id)
            self._agent_answer_poll_id = None

    def _cleanup_agent_answer_artifact(self) -> None:
        remove_focus_answer_artifact(self._agent_answer_artifact_path)
        self._agent_answer_artifact_path = None
        self._agent_run_id = ""
        self._agent_answer_revision = 0

    def _start_agent_answer_polling(self) -> None:
        self._stop_agent_answer_polling()
        if self._agent_answer_artifact_path is None or not self._agent_run_id:
            return
        self._agent_answer_poll_id = GLib.timeout_add(250, self._poll_agent_answer)
        self._poll_agent_answer()

    def _poll_agent_answer(self) -> bool:
        artifact_path = self._agent_answer_artifact_path
        run_id = self._agent_run_id
        if artifact_path is None or not run_id:
            self._agent_answer_poll_id = None
            return False
        workspace = self._agent_workspace_path
        if workspace is not None and self._agent_session_log_path is None:
            discovered = find_latest_pi_session_log_for_cwd(
                workspace / "pi-sessions",
                workspace,
            )
            if discovered is not None:
                self._agent_session_log_path = discovered
                self._sync_agent_output_header_state()
        result = read_focus_answer_artifact(
            artifact_path,
            run_id=run_id,
            last_revision=self._agent_answer_revision,
        )
        artifact = result.artifact
        if artifact is not None:
            self._agent_answer_revision = artifact.revision
            self._agent_answer_diagnostics = dict(artifact.diagnostics)
            answer = artifact.markdown
            if answer:
                self._agent_last_answer_text = answer
                state = self._get_ai_output_state(AI_VIEW_AGENT_QA)
                state.raw = answer
                self._current_view_state().ai_output_raw[AI_VIEW_AGENT_QA] = answer
                self._apply_ai_output_links(answer, state)
                self._set_agent_subview(AGENT_SUBVIEW_ANSWER)
                self._agent_answer_status = focus_answer_status_message(artifact)
                self._update_ai_status(
                    self._agent_answer_status,
                    spinning=False,
                )
                self._queue_embedded_ai_panel_height_update(after_render=True)
            else:
                self._agent_answer_status = (
                    "Provider/session failure: no usable answer text."
                )
                self._update_ai_status(self._agent_answer_status, spinning=False)
        elif result.error not in {"", "missing", "stale_revision"}:
            self._update_ai_status(
                f"Agent answer protocol failure ({result.error}).",
                spinning=False,
            )
        keep_polling = self._agent_terminal_active
        if not keep_polling:
            self._agent_answer_poll_id = None
        return keep_polling

    def _on_agent_copy_trace_clicked(self, _button: Gtk.Button) -> None:
        source = self._agent_trace_source()
        if source is None:
            self._ai_transient_toast(
                "Copy Trace: no session trace available for the current Agent run."
            )
            self._sync_agent_output_header_state()
            return
        try:
            destination = reasoning_trace_path()
        except ValueError as error:
            self._ai_transient_toast(f"Copy Trace: {error}")
            return
        try:
            snapshot_pi_session_jsonl(source, destination)
        except (TraceSnapshotError, OSError) as error:
            self._ai_transient_toast(
                f"Copy Trace failed; previous trace preserved: {error}"
            )
            return
        display = Gdk.Display.get_default()
        if display is None:
            self._ai_transient_toast(
                f"Agent trace saved to {destination}, but the clipboard was unavailable."
            )
            return
        display.get_clipboard().set(trace_clipboard_text(destination))
        self._ai_transient_toast(
            f"Copied Agent trace path. Trace: {destination}"
        )

    @staticmethod
    def _compose_agent_prompt(question: str) -> str:
        return (
            f"/skill:{FOCUS_PI_SKILL_NAME} <question>\n"
            f"{question.strip()}\n"
            "</question>"
        )

    def _write_agent_prompt_file(self, prompt: str) -> Path:
        handle = tempfile.NamedTemporaryFile(
            "w",
            encoding="utf-8",
            prefix="focus-agent-",
            suffix=".txt",
            delete=False,
        )
        with handle:
            handle.write(prompt)
        return Path(handle.name)

    def _launch_agent_question(self) -> None:
        if Vte is None or self._agent_terminal is None:
            self._agent_terminal_unavailable()
            return
        if not self._agent_question_entry:
            return
        question = self._agent_question_entry.get_text().strip()
        if not question:
            self._ai_transient_toast("Enter a question to launch the Agent.")
            return
        self._stop_agent_terminal()
        self._stop_agent_answer_polling()
        self._clear_agent_answer()
        self._reset_agent_trace_state()
        self._set_agent_subview(AGENT_SUBVIEW_SESSION)
        self._ai_settings = load_ai_settings()
        self._current_view_state().agent_question_text = question
        prompt_path = self._write_agent_prompt_file(
            self._compose_agent_prompt(question)
        )
        self._start_agent_terminal(prompt_path)

    def _start_agent_terminal(self, prompt_path: Path) -> None:
        terminal = self._agent_terminal
        if Vte is None or terminal is None:
            self._agent_terminal_unavailable()
            return
        self._ai_settings = load_ai_settings()
        settings = self._ai_settings
        command = settings.pi_agent_command.strip() or DEFAULT_PI_AGENT_COMMAND
        try:
            command_argv = resolve_pi_agent_argv(
                command,
                path_env=os.environ.get("PATH"),
            )
        except ValueError as exc:
            self._ai_transient_toast(f"Invalid PI command: {exc}")
            return
        if not command_argv:
            self._ai_transient_toast("PI command is empty.")
            return
        incompatible_flag = incompatible_pi_agent_flag(command_argv)
        if incompatible_flag:
            self._ai_transient_toast(
                f"PI option {incompatible_flag} is incompatible with the embedded session."
            )
            return
        executable = command_argv[0]
        if os.path.sep in executable:
            executable_path = Path(executable).expanduser()
            if not executable_path.is_file() or not os.access(executable_path, os.X_OK):
                self._ai_transient_toast(
                    "PI executable not found. Install PI or set the PI command in Settings."
                )
                return
            command_argv[0] = str(executable_path)
        elif shutil.which(executable) is None:
            self._ai_transient_toast(
                "PI executable not found. Install PI or set the PI command in Settings."
            )
            return
        wrapper = PROJECT_DIR / "scripts" / "focus-agent-vte.sh"
        if not wrapper.is_file():
            self._ai_transient_toast(f"Agent wrapper not found: {wrapper}")
            return
        helper = FOCUS_RECORD_AGENT_HELPER
        if not helper.is_file():
            self._ai_transient_toast(f"Record Agent helper not found: {helper}")
            return
        pi_settings = FOCUS_PI_PROJECT_DIR / "settings.json"
        if (
            not pi_settings.is_file()
            or not FOCUS_PI_SYSTEM_PROMPT_FILE.is_file()
            or not FOCUS_PI_SKILL_FILE.is_file()
            or not FOCUS_PI_EXTENSION_FILE.is_file()
            or not FOCUS_AGENT_ANSWER_PROTOCOL_FILE.is_file()
        ):
            self._ai_transient_toast(
                "Focus PI settings, prompt, skill, extension, or answer protocol is missing."
            )
            return

        try:
            workspace = self._create_agent_workspace()
        except OSError as exc:
            self._ai_transient_toast(f"Unable to create Agent workspace: {exc}")
            return
        self._agent_workspace_path = workspace
        self._cleanup_agent_answer_artifact()
        try:
            runtime_dir = focus_answer_runtime_dir()
            run_id = create_focus_run_id()
            answer_artifact = focus_answer_artifact_path(run_id, runtime_dir)
        except (OSError, ValueError) as exc:
            self._ai_transient_toast(f"Unable to create Agent answer transport: {exc}")
            return
        remove_focus_answer_artifact(answer_artifact)
        self._agent_run_id = run_id
        self._agent_answer_artifact_path = answer_artifact
        self._agent_answer_revision = 0
        self._agent_answer_diagnostics = {}
        try:
            session_preserve_dir = focus_session_preserve_dir()
            session_preserve_path = focus_preserved_session_path(
                run_id,
                session_preserve_dir,
            )
        except (OSError, ValueError) as exc:
            self._ai_transient_toast(
                f"Unable to create Agent session trace storage: {exc}"
            )
            return
        self._agent_session_preserve_path = session_preserve_path

        env = os.environ.copy()
        env.update(
            {
                "FOCUS_AGENT_PROMPT_FILE": str(prompt_path),
                "FOCUS_AGENT_CASE_ROOT": str(self._record_layout.root),
                "FOCUS_AGENT_WORKSPACE": str(workspace),
                "FOCUS_AGENT_RUN_ID": run_id,
                "FOCUS_AGENT_ANSWER_ARTIFACT": str(answer_artifact),
                "FOCUS_AGENT_RUNTIME_DIR": str(runtime_dir),
                "FOCUS_AGENT_SESSION_PRESERVE_DIR": str(session_preserve_dir),
                "FOCUS_AGENT_ANSWER_PROTOCOL": str(FOCUS_AGENT_ANSWER_PROTOCOL_FILE),
                "FOCUS_RECORD_AGENT_HELPER": str(helper),
                "FOCUS_RECORD_AGENT_PYTHON": self._agent_python_path(),
                "FOCUS_PI_PROJECT_DIR": str(FOCUS_PI_PROJECT_DIR),
                "FOCUS_AGENT_COMMAND_ARGC": str(len(command_argv)),
            }
        )
        for index, arg in enumerate(command_argv):
            env[f"FOCUS_AGENT_COMMAND_ARG_{index}"] = arg
        if os.path.sep in command_argv[0]:
            executable_dir = str(Path(command_argv[0]).parent)
            env["PATH"] = executable_dir + os.pathsep + env.get("PATH", "")
        argv = ["bash", str(wrapper)]
        cwd = str(self._record_layout.root)
        try:
            terminal.reset(True, True)
            _apply_focus_terminal_theme(terminal)
            terminal.spawn_async(
                Vte.PtyFlags.DEFAULT,
                cwd,
                argv,
                [f"{key}={value}" for key, value in env.items()],
                GLib.SpawnFlags.DEFAULT,
                None,
                None,
                -1,
                None,
                self._on_agent_terminal_spawned,
                None,
            )
        except Exception as exc:  # noqa: BLE001
            self._ai_transient_toast(f"Unable to start embedded Agent: {exc}")
            return

        self._agent_terminal_active = True
        self._agent_terminal_closing = False
        self._ensure_ai_panel_visible()
        self._set_ai_view(AI_VIEW_AGENT_QA)
        self._set_agent_subview(AGENT_SUBVIEW_SESSION)
        self._start_agent_answer_polling()
        self._update_ai_status(
            "Agent is researching the record…",
            spinning=True,
        )
        terminal.grab_focus()

    def _on_agent_terminal_spawned(
        self,
        _terminal: Any,
        pid: int,
        error: GLib.Error | None,
        _user_data: object,
    ) -> None:
        if error is not None:
            self._agent_terminal_active = False
            self._agent_terminal_pid = None
            if self._agent_answer_poll_id is not None:
                GLib.source_remove(self._agent_answer_poll_id)
                self._agent_answer_poll_id = None
            self._poll_agent_answer()
            self._sync_agent_session_widget_visibility()
            self._queue_embedded_ai_panel_height_update()
            self._update_ai_status("Unable to start the Agent.", spinning=False)
            self._ai_transient_toast(f"Unable to start embedded Agent: {error.message}")
            return
        self._agent_terminal_pid = int(pid)

    def _on_agent_terminal_child_exited(self, _terminal: Any, _status: int) -> None:
        if self._agent_terminal_ignore_next_exit:
            self._agent_terminal_ignore_next_exit = False
            if self._agent_terminal_active:
                return
        closing = self._agent_terminal_closing
        self._agent_terminal_active = False
        self._agent_terminal_pid = None
        self._agent_terminal_closing = False
        if self._agent_answer_poll_id is not None:
            GLib.source_remove(self._agent_answer_poll_id)
            self._agent_answer_poll_id = None
        self._poll_agent_answer()
        self._sync_agent_session_widget_visibility()
        self._queue_embedded_ai_panel_height_update()
        # The wrapper preserves the session JSONL in its exit trap; re-check the
        # trace source once more shortly after exit so Copy Trace stays exposed
        # even if preservation completed after the synchronous header resync.
        GLib.timeout_add(750, self._resync_agent_trace_after_exit)
        if self._agent_answer_has_content():
            message = self._agent_answer_status or "Final answer ready."
        elif closing:
            message = "Agent session closed."
        else:
            message = "Agent session ended without a final answer."
        self._update_ai_status(message, spinning=False)

    def _on_agent_terminal_style_changed(self, *_args: object) -> None:
        if self._agent_terminal is not None:
            _apply_focus_terminal_theme(self._agent_terminal)

    def _on_agent_terminal_key_pressed(
        self,
        _controller: Gtk.EventControllerKey,
        keyval: int,
        _keycode: int,
        state: Gdk.ModifierType,
    ) -> bool:
        terminal = self._agent_terminal
        if Vte is None or terminal is None:
            return False
        required_modifiers = Gdk.ModifierType.CONTROL_MASK | Gdk.ModifierType.SHIFT_MASK
        if state & required_modifiers != required_modifiers:
            return False
        if keyval in (Gdk.KEY_C, Gdk.KEY_c):
            terminal.copy_clipboard_format(Vte.Format.TEXT)
            return True
        if keyval in (Gdk.KEY_V, Gdk.KEY_v):
            terminal.paste_clipboard()
            return True
        return False

    def _stop_agent_terminal(self) -> None:
        if self._agent_terminal_active and self._agent_terminal_pid is not None:
            self._agent_terminal_closing = True
            self._agent_terminal_ignore_next_exit = True
            try:
                os.kill(self._agent_terminal_pid, signal.SIGTERM)
            except OSError:
                pass
        self._agent_terminal_active = False
        self._agent_terminal_pid = None
        self._stop_agent_answer_polling()
        self._cleanup_agent_answer_artifact()
        self._sync_agent_session_widget_visibility()
        self._update_ai_status("", spinning=False)
        self._queue_embedded_ai_panel_height_update()

    def _submit_speech_agent_question(self) -> None:
        settings = load_ai_settings()
        raw_path = settings.speech_agent_source_file.strip()
        if not raw_path:
            self._ai_transient_toast("Set the speech-to-text question file in Settings.")
            self._ensure_ai_panel_visible()
            return
        source_path = Path(raw_path).expanduser().resolve(strict=False)
        if not source_path.exists() or not source_path.is_file():
            self._ai_transient_toast(f"Speech question file not found: {source_path}")
            self._ensure_ai_panel_visible()
            return
        try:
            raw_question = source_path.read_text(encoding="utf-8", errors="ignore")
        except OSError as exc:
            self._ai_transient_toast(f"Could not read speech question file: {exc}")
            self._ensure_ai_panel_visible()
            return
        question = _normalize_speech_agent_question_text(raw_question)
        if not question:
            self._ai_transient_toast("Speech question file is empty.")
            self._ensure_ai_panel_visible()
            return
        self._ensure_ai_panel_visible()
        self._set_ai_view(AI_VIEW_AGENT_QA)
        self._current_view_state().agent_question_text = question
        if self._agent_question_entry:
            self._agent_question_entry.set_text(question)
        self._launch_agent_question()

    def _find_summary_in_dir(
        self,
        label: str,
        candidates: tuple[str, ...],
        keywords: tuple[str, ...],
        *,
        show_toast: bool = True,
    ) -> Path | None:
        summaries_dir = self.input_dir / SUMMARY_DIR_NAME
        if not summaries_dir.exists():
            self._ai_transient_toast(f"Summaries folder not found: {summaries_dir}")
            return None
        matches: list[Path] = []
        try:
            for name in candidates:
                path = summaries_dir / name
                if path.is_file():
                    matches.append(path)
            for item in summaries_dir.iterdir():
                if not item.is_file():
                    continue
                if item.suffix.lower() not in SUMMARY_TEXT_EXTENSIONS:
                    continue
                lowered = item.name.casefold()
                if any(keyword in lowered for keyword in keywords):
                    matches.append(item)
        except OSError as exc:  # noqa: BLE001
            if show_toast:
                self._ai_transient_toast(f"Could not read summaries folder: {exc}")
            return None
        if matches:
            return sorted(set(matches), key=_summary_file_priority)[0]
        if show_toast:
            self._ai_transient_toast(f"{label} summary not found in {summaries_dir}")
        return None

    def _load_summary_from_manifest(
        self,
        label: str,
        manifest_path: Path,
        file_keys: str | tuple[str, ...],
        source: str,
    ) -> None:
        self._ensure_ai_panel_visible()
        self._set_ai_view(AI_VIEW_FILE)
        manifest = _read_manifest_file(manifest_path)
        if not manifest:
            self._ai_transient_toast(f"{label} summary manifest not found: {manifest_path}")
            return
        files = manifest.get("files") if isinstance(manifest.get("files"), dict) else {}
        keys = (file_keys,) if isinstance(file_keys, str) else file_keys
        summary_path: Path | None = None
        for file_key in keys:
            summary_path = _path_from_manifest(files.get(file_key), manifest_path.parent)
            if summary_path and summary_path.exists():
                break
        if not summary_path:
            self._ai_transient_toast(f"{label} summary not listed in manifest: {manifest_path}")
            return
        if not summary_path.exists():
            self._ai_transient_toast(f"{label} summary file not found: {summary_path}")
            return
        self._load_summary_from_path(summary_path, source=source)

    def _find_summary_in_manifest(
        self,
        manifest_path: Path | None,
        file_keys: tuple[str, ...],
    ) -> Path | None:
        if not manifest_path:
            return None
        manifest = _read_manifest_file(manifest_path)
        files = (
            manifest.get("files")
            if isinstance(manifest, dict) and isinstance(manifest.get("files"), dict)
            else {}
        )
        for file_key in file_keys:
            summary_path = _path_from_manifest(files.get(file_key), manifest_path.parent)
            if summary_path and summary_path.exists():
                return summary_path
        return None

    def _find_preferred_summary_path(
        self,
        label: str,
        manifest_path: Path | None,
        file_keys: tuple[str, ...],
        candidates: tuple[str, ...],
        keywords: tuple[str, ...],
        *,
        show_toast: bool = True,
    ) -> Path | None:
        matches: list[Path] = []
        manifest_summary = self._find_summary_in_manifest(manifest_path, file_keys)
        if manifest_summary:
            matches.append(manifest_summary)
        directory_summary = self._find_summary_in_dir(
            label,
            candidates,
            keywords,
            show_toast=show_toast and manifest_summary is None,
        )
        if directory_summary:
            matches.append(directory_summary)
        if not matches:
            return None
        return sorted(set(matches), key=_summary_file_priority)[0]

    def _on_minutes_summary_clicked(self, _button: Gtk.Button) -> None:
        manifest_path = _find_manifest_near_path(self.input_dir)
        if not manifest_path:
            self._ai_transient_toast(
                f"Minutes summary manifest not found near input dir: {self.input_dir}"
            )
            return
        self._load_summary_from_manifest(
            "Minutes",
            manifest_path,
            MINUTES_SUMMARY_MANIFEST_KEY,
            SUMMARY_SOURCE_MINUTES,
        )

    def _on_hearing_summary_clicked(self, _button: Gtk.Button) -> None:
        manifest_path = _find_manifest_near_path(self.input_dir)
        summary_path = self._find_preferred_summary_path(
            "Hearing",
            manifest_path,
            HEARING_SUMMARY_MANIFEST_KEYS,
            HEARING_SUMMARY_CANDIDATES,
            ("hearing",),
        )
        if summary_path:
            self._load_summary_from_path(summary_path, source=SUMMARY_SOURCE_HEARING)

    def _on_reports_summary_clicked(self, _button: Gtk.Button) -> None:
        manifest_path = _find_manifest_near_path(self.input_dir)
        summary_path = self._find_preferred_summary_path(
            "Reports",
            manifest_path,
            REPORTS_SUMMARY_MANIFEST_KEYS,
            REPORTS_SUMMARY_CANDIDATES,
            ("report", "reports"),
        )
        if summary_path:
            self._load_summary_from_path(summary_path, source=SUMMARY_SOURCE_REPORTS)

    def _auto_load_summary_file(self) -> None:
        if self._auto_loading_summary:
            return
        self._auto_loading_summary = True
        try:
            if self._summary_has_text():
                return
            manifest_path = _find_manifest_near_path(self.input_dir)
            if manifest_path:
                manifest = _read_manifest_file(manifest_path)
                files = manifest.get("files") if isinstance(manifest.get("files"), dict) else {}
                summary_path = _path_from_manifest(files.get(MINUTES_SUMMARY_MANIFEST_KEY), manifest_path.parent)
                if summary_path and summary_path.exists():
                    self._load_summary_from_path(
                        summary_path,
                        allow_auto=True,
                        source=SUMMARY_SOURCE_MINUTES,
                        show_toast=False,
                    )
                    return
            hearing = self._find_preferred_summary_path(
                "Hearing",
                manifest_path,
                HEARING_SUMMARY_MANIFEST_KEYS,
                HEARING_SUMMARY_CANDIDATES,
                ("hearing",),
                show_toast=False,
            )
            if hearing:
                self._load_summary_from_path(
                    hearing,
                    allow_auto=True,
                    source=SUMMARY_SOURCE_HEARING,
                    show_toast=False,
                )
                return
            reports = self._find_preferred_summary_path(
                "Reports",
                manifest_path,
                REPORTS_SUMMARY_MANIFEST_KEYS,
                REPORTS_SUMMARY_CANDIDATES,
                ("report", "reports"),
                show_toast=False,
            )
            if reports:
                self._load_summary_from_path(
                    reports,
                    allow_auto=True,
                    source=SUMMARY_SOURCE_REPORTS,
                    show_toast=False,
                )
        finally:
            self._auto_loading_summary = False

    def _set_summary_text(self, text: str, *, switch_view: bool = True) -> None:
        self._summary_raw = text or ""
        if self._summary_buffer:
            self._apply_summary_links(text or "")
        self._refresh_summary_search(reset_active=True)
        self._refresh_summary_actions_state()
        self._show_summary_view(switch_view=switch_view)
        self._queue_embedded_ai_panel_height_update()

    def _load_summary_edition_for(
        self, path: Path, source: str | None
    ) -> SummaryEdition | None:
        """Load a validated page-matched edition, or None for legacy mode."""
        if source is None:
            source = self._infer_summary_source(path)
        manifest_path = _find_manifest_near_path(self.input_dir)
        manifest_files: dict[str, Any] | None = None
        manifest_dir = self.input_dir
        if manifest_path:
            manifest_dir = manifest_path.parent
            manifest = _read_manifest_file(manifest_path)
            files = manifest.get("files")
            if isinstance(files, dict):
                manifest_files = files
        try:
            return load_summary_edition(
                focus_source=source,
                summary_path=path,
                bundle_root=self.input_dir,
                manifest_files=manifest_files,
                manifest_dir=manifest_dir,
            )
        except SummaryEditionError:
            return None
        except OSError:
            return None

    def _summary_is_paged(self) -> bool:
        return self._summary_edition is not None

    def _display_summary_page(
        self,
        page_number: int,
        *,
        switch_view: bool = False,
        scroll_top: bool = True,
    ) -> None:
        edition = self._summary_edition
        if edition is None or not edition.page_count:
            return
        page = min(max(1, page_number), edition.page_count)
        self._summary_edition_page = page
        state = self._current_view_state()
        state.summary_current_page = page
        state.summary_edition_sha256 = edition.pdf_sha256
        page_text = with_paragraph_spacing(render_page_text(edition, page))
        self._summary_raw = page_text
        if self._summary_buffer:
            self._apply_summary_links(page_text)
        self._refresh_summary_actions_state()
        self._update_summary_page_controls()
        self._apply_summary_search_highlights()
        if scroll_top and self._summary_view and self._summary_buffer:
            start_iter = self._summary_buffer.get_start_iter()
            self._summary_view.scroll_to_iter(start_iter, 0.0, True, 0.0, 0.0)
        if switch_view:
            self._show_summary_view(switch_view=True)

    def _update_summary_page_controls(self) -> None:
        paged = self._summary_is_paged()
        if self._summary_progress_label:
            self._summary_progress_label.set_visible(not paged)
        for widget in (
            self._summary_prev_page_button,
            self._summary_page_entry,
            self._summary_page_total_label,
            self._summary_next_page_button,
            self._summary_open_pdf_button,
        ):
            if widget:
                widget.set_visible(paged)
        if not paged or self._summary_edition is None:
            return
        total = self._summary_edition.page_count
        if self._summary_page_entry:
            self._summary_page_entry.set_text(str(self._summary_edition_page))
        if self._summary_page_total_label:
            self._summary_page_total_label.set_text(f"of {total}")
        if self._summary_prev_page_button:
            self._summary_prev_page_button.set_sensitive(self._summary_edition_page > 1)
        if self._summary_next_page_button:
            self._summary_next_page_button.set_sensitive(
                self._summary_edition_page < total
            )

    def _on_summary_prev_page_clicked(self, _button: Gtk.Button | None) -> None:
        if not self._summary_is_paged():
            return
        self._display_summary_page(self._summary_edition_page - 1)

    def _on_summary_next_page_clicked(self, _button: Gtk.Button | None) -> None:
        if not self._summary_is_paged():
            return
        self._display_summary_page(self._summary_edition_page + 1)

    def _on_summary_page_entry_activate(self, entry: Gtk.Entry) -> None:
        if not self._summary_is_paged():
            return
        raw = entry.get_text().strip()
        try:
            requested = int(raw)
        except ValueError:
            self._ai_transient_toast("Enter a summary page number.")
            self._update_summary_page_controls()
            return
        assert self._summary_edition is not None
        if requested < 1 or requested > self._summary_edition.page_count:
            self._ai_transient_toast(
                f"Page {requested} is outside this summary (1–{self._summary_edition.page_count})."
            )
            self._update_summary_page_controls()
            return
        self._display_summary_page(requested)

    def _on_summary_open_pdf_clicked(self, _button: Gtk.Button | None) -> None:
        self._open_page_matched_pdf()

    def _open_page_matched_pdf(self) -> bool:
        """Revalidate and open the canonical summary PDF; True when opened."""
        if not self._summary_loaded_path:
            self._ai_transient_toast("No summary file is loaded.")
            return False
        edition = self._load_summary_edition_for(
            self._summary_loaded_path, self._summary_active_source
        )
        if edition is None:
            self._ai_transient_toast(
                "The page-matched PDF is unavailable; the summary changed or the edition is missing."
            )
            return False
        pdf_path = edition.pdf_path
        try:
            launched = Gio.AppInfo.launch_default_for_uri(
                pdf_path.resolve().as_uri(), None
            )
        except Exception as exc:  # noqa: BLE001
            self._ai_transient_toast(
                f"No PDF viewer is available. Open the summary PDF at: {pdf_path.resolve()} ({exc})"
            )
            return False
        if not launched:
            self._ai_transient_toast(
                f"No PDF viewer is available. Open the summary PDF at: {pdf_path.resolve()}"
            )
            return False
        self._ai_transient_toast(f"Opened page-matched PDF: {pdf_path.name}")
        return True

    def _load_summary_from_path(
        self,
        path: Path,
        *,
        allow_auto: bool = False,
        source: str | None = None,
        show_toast: bool = True,
    ) -> None:
        if self._auto_loading_summary and not allow_auto:
            # Prevent re-entry if an auto load is already in progress.
            return
        target = path.expanduser()
        resolved = target.resolve(strict=False)
        if not resolved.exists() or not resolved.is_file():
            self._ai_transient_toast(f"File not found: {resolved}")
            return
        try:
            text = resolved.read_text(encoding="utf-8", errors="ignore")
        except OSError as exc:  # noqa: BLE001
            self._ai_transient_toast(f"Could not read {resolved.name}: {exc}")
            return
        self._stop_ai_stream_if_running()
        state = self._current_view_state()
        same_summary = state.summary_loaded_path == resolved
        if same_summary:
            if self._ai_active_view == AI_VIEW_FILE:
                self._capture_summary_scroll_position()
            if (
                state.summary_scroll_fraction is not None
                and not self._summary_is_paged()
            ):
                self._prepare_summary_scroll_restore(state.summary_scroll_fraction)
        else:
            self._cancel_pending_summary_scroll_restore()
            state.summary_scroll_fraction = None
        self._summary_loaded_path = resolved
        if source is None:
            source = self._infer_summary_source(resolved)
        self._set_summary_active_source(source)
        state.summary_loaded_path = resolved
        state.summary_active_source = source
        self._summary_edition = self._load_summary_edition_for(resolved, source)
        if self._summary_is_paged():
            assert self._summary_edition is not None
            if (
                same_summary
                and state.summary_current_page
                and state.summary_edition_sha256 == self._summary_edition.pdf_sha256
            ):
                initial_page = state.summary_current_page
            else:
                initial_page = self._summary_bookmark_page(resolved) or 1
            self._display_summary_page(initial_page, switch_view=not allow_auto)
            # Recompute page-aware matches for the newly loaded edition;
            # the search entry text persists across summaries.
            self._refresh_summary_search(reset_active=True)
        else:
            state.summary_current_page = None
            state.summary_edition_sha256 = None
            self._set_summary_text(text, switch_view=not allow_auto)
        self._restore_summary_position(resolved)
        self._update_ai_status("", spinning=False)
        if show_toast:
            self._ai_transient_toast(f"Loaded {resolved.name}")
        if not allow_auto:
            self._ensure_ai_panel_visible()

    def _llm_credentials_error(self, credentials: LlmCredentials, label: str) -> str | None:
        if credentials.is_configured():
            return None
        if credentials.profile is not None:
            return f'Configure the "{credentials.profile.display_name()}" model profile in Settings.'
        return f"Configure {label} API URL, model, API key, and prompt in Settings."

    def _start_ai_stream(
        self,
        *,
        label: str,
        content: str,
        prompt_kind: str,
    ) -> None:
        state = self._current_view_state()
        self._ai_settings = load_ai_settings()
        settings = self._ai_settings
        if prompt_kind == "extract":
            target_view = AI_VIEW_EXTRACT
            action_label = "Extracting"
            credentials = settings.extract_llm_credentials()
            error = self._llm_credentials_error(credentials, "extract")
            if error or not (settings.extract_prompt or DEFAULT_EXTRACT_PROMPT).strip():
                self._ai_transient_toast(error or "Configure the extract prompt in Settings.")
                self._ensure_ai_panel_visible()
                return
        elif prompt_kind == "range":
            target_view = AI_VIEW_SUMMARIZE
            action_label = "Summarizing"
            credentials = settings.range_llm_credentials()
            error = self._llm_credentials_error(credentials, "range summary")
            if error or not (settings.range_prompt or DEFAULT_SUMMARIZATION_PROMPT).strip():
                self._ai_transient_toast(error or "Configure the range summarization prompt in Settings.")
                self._ensure_ai_panel_visible()
                return
        else:
            self._ai_transient_toast("Unsupported AI request.")
            return
        if not content.strip():
            self._ai_transient_toast(f"Nothing to {action_label.lower()} for the requested selection.")
            return
        if prompt_kind == "extract":
            prompt = compose_extract_information_prompt(settings.extract_prompt or DEFAULT_EXTRACT_PROMPT)
        else:
            prompt = settings.range_prompt or DEFAULT_SUMMARIZATION_PROMPT
        api_url = credentials.api_url
        model_id = credentials.model_id
        api_key = credentials.api_key
        disable_reasoning = credentials.disable_reasoning
        priority_service_tier = credentials.priority_service_tier

        self._stop_ai_stream_if_running()
        state.ai_cancel_event = threading.Event()
        state.ai_in_flight = True
        state.ai_request_generation += 1
        generation = state.ai_request_generation
        self._ai_request_generation = generation
        state.ai_active_view = target_view
        self._ai_cancel_event = state.ai_cancel_event
        self._ai_in_flight = True
        self._ensure_ai_panel_visible()
        self._set_ai_view(target_view)
        self._reset_ai_output("", target=target_view)
        self._update_ai_status(f"{action_label} {label}…", spinning=True)

        payload_text = content
        worker_settings = settings
        cancel_event = state.ai_cancel_event

        def worker() -> None:
            self._stream_chat_worker(
                worker_settings,
                payload_text,
                label,
                cancel_event,
                generation,
                prompt,
                target_view,
                model_id=model_id,
                api_url=api_url,
                api_key=api_key,
                disable_reasoning=disable_reasoning,
                priority_service_tier=priority_service_tier,
            )

        state.ai_stream_thread = threading.Thread(target=worker, daemon=True)
        state.ai_stream_thread.start()
        self._ai_stream_thread = state.ai_stream_thread

    def _update_ai_status(self, text: str, spinning: bool) -> None:
        state = self._current_view_state()
        state.ai_status_text = text
        state.ai_spinning = spinning
        display_text = text.strip() or self._case_tool_description()
        if self._ai_status_label:
            self._ai_status_label.set_text(display_text)
            self._ai_status_label.set_tooltip_text(display_text)
        if self._ai_spinner:
            self._ai_spinner.set_spinning(spinning)
            self._ai_spinner.set_visible(spinning)

    def _set_ai_output_text(
        self,
        text: str | None = None,
        *,
        target: str,
        switch_view: bool = False,
    ) -> None:
        focus_state = self._current_view_state()
        focus_state.ai_output_raw[target] = text or ""
        state = self._get_ai_output_state(target)
        if switch_view:
            self._set_ai_view(target)
        state.raw = text or ""
        self._apply_ai_output_links(state.raw, state)
        self._queue_embedded_ai_panel_height_update()

    def _set_ai_output_text_idle(
        self,
        text: str | None,
        target: str,
        switch_view: bool = False,
    ) -> bool:
        self._set_ai_output_text(text, target=target, switch_view=switch_view)
        return False

    def _reset_ai_output(self, text: str | None = None, *, target: str) -> None:
        self._set_ai_output_text(text, target=target, switch_view=True)

    def _append_ai_output(self, text: str, generation: int, target: str) -> bool:
        focus_state = self._current_view_state()
        if generation != focus_state.ai_request_generation:
            return False
        if not text:
            return False
        current_raw = focus_state.ai_output_raw.get(target, "") or ""
        new_raw = current_raw + text
        focus_state.ai_output_raw[target] = new_raw
        state = self._get_ai_output_state(target)
        state.raw = new_raw
        self._apply_ai_output_links(state.raw, state)
        self._queue_embedded_ai_panel_height_update()
        self._update_ai_status("Streaming…", spinning=True)
        return False

    def _scroll_ai_output_to_bottom(self, target: str) -> None:
        state = self._get_ai_output_state(target)
        scroller = state.scroller
        if scroller is None:
            return
        vadj = scroller.get_vadjustment()
        if vadj is None:
            return
        lower = vadj.get_lower()
        upper = vadj.get_upper()
        page_size = vadj.get_page_size()
        vadj.set_value(max(lower, upper - page_size))

    def _stop_ai_stream_if_running(self) -> None:
        state = self._current_view_state()
        if state.ai_cancel_event:
            state.ai_cancel_event.set()
        if state.ai_stream_thread and state.ai_stream_thread.is_alive():
            try:
                state.ai_stream_thread.join(timeout=0.2)
            except Exception:
                pass
        state.ai_stream_thread = None
        state.ai_cancel_event = None
        state.ai_in_flight = False
        self._ai_stream_thread = None
        self._ai_cancel_event = None
        self._ai_in_flight = False

    def _stream_chat_worker(
        self,
        settings: AiSettings,
        content: str,
        label: str,
        cancel_event: threading.Event | None,
        generation: int,
        prompt: str,
        target_view: str,
        *,
        model_id: str,
        api_url: str,
        api_key: str | None = None,
        disable_reasoning: bool = False,
        priority_service_tier: bool = False,
        include_reasoning: bool = False,
    ) -> None:
        headers = {
            "Content-Type": "application/json",
            "Accept": "text/event-stream",
            "Authorization": f"Bearer {api_key or settings.api_key}",
            "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) Focus/1.0",
        }
        body = {
            "model": model_id,
            "stream": True,
            "messages": [
                {"role": "system", "content": prompt or DEFAULT_SUMMARIZATION_PROMPT},
                {"role": "user", "content": content},
            ],
        }
        _apply_disable_reasoning_to_body(
            body,
            model_id=model_id,
            disable_reasoning=disable_reasoning,
        )
        _apply_priority_service_tier_to_body(
            body,
            api_url=api_url,
            priority_service_tier=priority_service_tier,
        )
        attempted_without_thinking = False
        attempted_without_reasoning_effort = False

        while True:
            data = json.dumps(body).encode("utf-8")
            req = urllib.request.Request(api_url, data=data, headers=headers, method="POST")
            try:
                with urllib.request.urlopen(req) as resp:
                    for chunk in self._iter_sse_chunks(
                        resp,
                        cancel_event,
                        include_reasoning=include_reasoning,
                    ):
                        if cancel_event and cancel_event.is_set():
                            GLib.idle_add(self._on_ai_stream_cancelled, generation, target_view)
                            return
                        GLib.idle_add(self._append_ai_output, chunk, generation, target_view)
                if cancel_event and cancel_event.is_set():
                    GLib.idle_add(self._on_ai_stream_cancelled, generation, target_view)
                else:
                    GLib.idle_add(self._on_ai_stream_finished, label, generation, target_view)
                return
            except urllib.error.HTTPError as exc:
                try:
                    error_body = exc.read().decode("utf-8", errors="ignore")
                except Exception:  # noqa: BLE001
                    error_body = ""
                message = (error_body.strip() or exc.reason or "request failed").lower()
                if (
                    not attempted_without_thinking
                    and "thinking" in body
                    and "thinking" in message
                    and any(marker in message for marker in ("unsupported", "unknown", "invalid"))
                ):
                    attempted_without_thinking = True
                    body.pop("thinking", None)
                    continue
                if (
                    not attempted_without_reasoning_effort
                    and "reasoning_effort" in body
                    and "reasoning_effort" in message
                    and any(marker in message for marker in ("unsupported", "unknown", "invalid"))
                ):
                    attempted_without_reasoning_effort = True
                    body.pop("reasoning_effort", None)
                    continue
                detail = error_body.strip() or exc.reason or "request failed"
                GLib.idle_add(
                    self._on_ai_stream_error,
                    f"HTTP error {exc.code}: {detail}",
                    generation,
                    target_view,
                )
                return
            except Exception as exc:  # noqa: BLE001
                GLib.idle_add(self._on_ai_stream_error, str(exc), generation, target_view)
                return

    def _iter_sse_chunks(
        self,
        resp: urllib.response.addinfourl,  # type: ignore[type-arg]
        cancel_event: threading.Event | None,
        *,
        include_reasoning: bool = False,
    ) -> Iterable[str]:
        in_reasoning_trace = False
        while True:
            if cancel_event and cancel_event.is_set():
                break
            raw = resp.readline()
            if not raw:
                break
            line = raw.decode("utf-8", errors="ignore").strip()
            if not line or not line.startswith("data:"):
                continue
            data = line[5:].lstrip()
            if data == "[DONE]":
                break
            if not data:
                continue
            try:
                payload = json.loads(data)
            except json.JSONDecodeError:
                continue
            answer_text, reasoning_text = self._extract_stream_text_parts(payload)
            if include_reasoning and reasoning_text:
                if not in_reasoning_trace:
                    in_reasoning_trace = True
                    yield "\n[Reasoning Trace]\n"
                yield reasoning_text
            if answer_text:
                if include_reasoning and in_reasoning_trace:
                    in_reasoning_trace = False
                    yield "\n[Answer]\n"
                yield answer_text

    def _extract_stream_text_parts(self, payload: Any) -> tuple[str, str]:
        answer_text = ""
        reasoning_text = ""
        choices = payload.get("choices") if isinstance(payload, dict) else None
        if isinstance(choices, list) and choices:
            first = choices[0] or {}
            delta = first.get("delta") or first.get("message") or first
            if isinstance(delta, dict):
                answer_text = self._coerce_stream_text(
                    delta.get("content") if "content" in delta else delta.get("text")
                )
                reasoning_text = self._coerce_stream_text(
                    delta.get("reasoning_content")
                    if "reasoning_content" in delta
                    else delta.get("reasoning")
                    if "reasoning" in delta
                    else delta.get("thinking")
                )
        if isinstance(payload, dict):
            fallback = payload.get("data") or payload.get("text")
            if isinstance(fallback, str):
                answer_text = answer_text or fallback
        return answer_text, reasoning_text

    def _coerce_stream_text(self, value: Any) -> str:
        if isinstance(value, str):
            return value
        if not isinstance(value, list):
            return ""
        merged: list[str] = []
        for item in value:
            if isinstance(item, dict):
                candidate = item.get("text")
                if isinstance(candidate, str):
                    merged.append(candidate)
            elif isinstance(item, str):
                merged.append(item)
        return "".join(merged)

    def _on_ai_stream_finished(self, label: str, generation: int, _target_view: str) -> bool:
        state = self._current_view_state()
        if generation != state.ai_request_generation:
            return False
        state.ai_in_flight = False
        state.ai_cancel_event = None
        state.ai_stream_thread = None
        self._ai_in_flight = False
        self._ai_cancel_event = None
        self._ai_stream_thread = None
        self._update_ai_status(f"Finished AI response for {label}.", spinning=False)
        return False

    def _on_ai_stream_error(self, message: str, generation: int, _target_view: str) -> bool:
        state = self._current_view_state()
        if generation != state.ai_request_generation:
            return False
        state.ai_in_flight = False
        state.ai_cancel_event = None
        state.ai_stream_thread = None
        self._ai_in_flight = False
        self._ai_cancel_event = None
        self._ai_stream_thread = None
        self._update_ai_status("AI request failed.", spinning=False)
        self._ai_transient_toast(message or "AI request failed.")
        return False

    def _on_ai_stream_cancelled(self, generation: int, _target_view: str) -> bool:
        state = self._current_view_state()
        if generation != state.ai_request_generation:
            return False
        state.ai_in_flight = False
        state.ai_cancel_event = None
        state.ai_stream_thread = None
        self._ai_in_flight = False
        self._ai_cancel_event = None
        self._ai_stream_thread = None
        self._update_ai_status("Cancelled.", spinning=False)
        return False

    def _edge_flash(self) -> None:
        if not self.win:
            return
        win = self.win
        if self._edge_flash_source_id is not None:
            GLib.source_remove(self._edge_flash_source_id)
            self._edge_flash_source_id = None
        win.remove_css_class("accent")
        win.add_css_class("accent")
        self._edge_flash_source_id = GLib.timeout_add(120, self._edge_flash_reset)

    def _edge_flash_reset(self) -> bool:
        self._edge_flash_source_id = None
        if self.win:
            self.win.remove_css_class("accent")
        return False

    def _transient_toast(
        self,
        text: str,
        *,
        window: Adw.ApplicationWindow | None = None,
    ) -> None:
        target_window = window or self.win
        if target_window is None:
            return
        toast = Adw.Toast.new(text)
        overlay = self._ensure_toast_overlay(target_window)
        overlay.add_toast(toast)

    def _ai_transient_toast(self, text: str) -> None:
        self._transient_toast(text, window=self._get_ai_host_window())

    def _ensure_toast_overlay(self, window: Adw.ApplicationWindow) -> Adw.ToastOverlay:
        content = window.get_content()
        if isinstance(content, Adw.ToastOverlay):
            return content
        overlay = Adw.ToastOverlay()
        if content is not None:
            window.set_content(None)
            overlay.set_child(content)
        window.set_content(overlay)
        return overlay



def _prepare_cli_input_dir(raw_path: str) -> Path:
    target = Path(raw_path).expanduser().resolve(strict=False)
    if not target.exists() or not target.is_dir():
        _cli_error(f"Input directory not found: {target}")
    normalized = _normalize_input_dir(target)
    if not normalized.exists() or not normalized.is_dir():
        _cli_error(f"Input directory not found: {normalized}")
    layout = _resolve_record_layout(normalized)
    text_dir = layout.text_dir
    if not text_dir.exists() or not text_dir.is_dir():
        _cli_error(f"Text pages directory not found: {text_dir}")
    return normalized


def _cli_error(message: str) -> None:
    print(message, file=sys.stderr)
    raise SystemExit(2)



def run(input_dir: Path | None = None) -> int:
    input_override: Path | None = None
    if input_dir is not None:
        input_override = _prepare_cli_input_dir(str(input_dir))
    app = Focus(input_override=input_override)
    return int(app.run(None))


def main(argv: list[str] | None = None) -> int:
    args = sys.argv[1:] if argv is None else argv
    input_dir: Path | None = None
    if args:
        first = args[0]
        if first in {"-h", "--help"}:
            print("Usage: focus [DIRECTORY]")
            print("Provide DIRECTORY to override the configured record root.")
            return 0
        if len(args) > 1:
            print("Only one directory argument is supported.", file=sys.stderr)
            return 2
        input_dir = Path(first)
    return run(input_dir=input_dir)


if __name__ == "__main__":
    raise SystemExit(main())
