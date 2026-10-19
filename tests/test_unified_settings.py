"""Native settings with fabricated preferences and model adapters."""
import unittest
from unittest.mock import Mock, patch
from focus.ui import settings as ui
from focus.ui.settings_navigation import descendants


class UnifiedSettingsTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not ui.Gtk.init_check():
            raise unittest.SkipTest("GTK display unavailable")
        ui.Adw.init()
        cls.app = ui.Adw.Application(application_id="org.synthetic.Focus.SettingsTests")
        cls.app.register(None)

    def window(self):
        app = self.app
        app.get_font_preferences = lambda: (12, 12, 12)
        app.get_record_font_family_name = lambda: ui.RECORD_FONT_FAMILY_OPTIONS[0][0]
        app.update_font_sizes = Mock()
        app.on_ai_settings_saved = Mock()
        with patch.object(ui, "ensure_project_pi_settings"), \
             patch.object(ui, "current_project_pi_model", return_value=("synthetic", "saved")), \
             patch.object(ui, "current_project_pi_thinking_level", return_value="medium"), \
             patch.object(ui, "load_ai_settings", return_value=ui.AiSettings(speech_agent_source_file="/synthetic/speech", highlight_phrases=[], grep_highlight_color=ui.DEFAULT_MATCH_COLOR, phrase_highlight_color=ui.DEFAULT_HIGHLIGHT_COLOR, search_chip_color=ui.DEFAULT_SEARCH_CHIP_COLOR)), \
             patch.object(ui.AiSettingsWindow, "_load_pi_models"):
            w = ui.AiSettingsWindow(app)
        w.present()
        self.addCleanup(w.destroy)
        return w

    def test_later_font_write_failure_retains_accepted_baseline(self):
        w = self.window()
        baseline = w._session.baseline
        w._ai_font_size_row.set_value(19)
        w._highlight_phrases_buffer.set_text("Retained phrase")
        self.app.update_font_sizes.side_effect = OSError("synthetic font write failure")
        with patch.object(ui, "save_ai_settings") as save, \
             patch.object(w, "_show_status_toast") as status:
            w._navigation.save_buttons["home"].emit("clicked")
        save.assert_called_once()
        self.assertEqual(save.call_args.args[0].highlight_phrases, ["Retained phrase"])
        self.assertEqual(w._prompt_text(w._highlight_phrases_buffer), "Retained phrase")
        self.assertIn("Some settings may already have been written", status.call_args.args[0])
        self.assertEqual(w._session.baseline, baseline)
        self.assertTrue(w.get_visible())
        self.app.on_ai_settings_saved.assert_not_called()

    def test_refresh_error_and_unavailable_catalog_retain_unsaved_identity(self):
        w = self.window()
        models = [ui.PiModel("synthetic", "saved", "Saved"), ui.PiModel("synthetic", "other", "Other")]
        w._finish_pi_model_load(0, models, "", ("synthetic", "saved"), "medium")
        w.pi_model_row.set_selected(1)
        desired = w._selected_pi_model().settings_key
        w._finish_pi_model_load(0, [], "synthetic offline", desired, "medium")
        self.assertEqual(w._selected_pi_model().settings_key, desired)
        self.assertTrue(w._pi_model_selection_changed)
        w._finish_pi_model_load(0, [models[0]], "", desired, "medium")
        self.assertEqual(w._selected_pi_model().settings_key, desired)
        options = w._pi_model_options
        w._finish_pi_model_load(-1, [], "stale", None, "medium")
        self.assertIs(w._pi_model_options, options)
        w._pi_model_closed = True
        w._finish_pi_model_load(0, [], "late", None, "medium")
        self.assertIs(w._pi_model_options, options)

    def test_inline_highlights_structure(self):
        w = self.window()
        self.assertEqual(set(w._navigation.pages), {"home"})
        self.assertEqual(set(w._navigation.save_buttons), {"home"})
        highlights = self.highlights(w)
        view = next(widget for widget in descendants(highlights)
                    if isinstance(widget, ui.Gtk.TextView))
        self.assertIs(view.get_buffer(), w._highlight_phrases_buffer)
        self.assertTrue(view.get_buffer().get_enable_undo())
        self.assertFalse(view.get_accepts_tab())
        self.assertEqual(view.get_wrap_mode(), ui.Gtk.WrapMode.WORD_CHAR)
        scroller = view.get_parent()
        self.assertIsInstance(scroller, ui.Gtk.ScrolledWindow)
        self.assertFalse(scroller.get_vexpand())
        self.assertEqual(scroller.get_policy(), (ui.Gtk.PolicyType.NEVER, ui.Gtk.PolicyType.AUTOMATIC))
        self.assertEqual(scroller.get_min_content_height(), scroller.get_max_content_height())
        expected = view.create_pango_layout("Ag\nAg\nAg").get_pixel_size()[1] + 16
        self.assertEqual(scroller.get_min_content_height(), expected)
        row = scroller.get_parent().get_parent()
        self.assertIsInstance(row, ui.Adw.PreferencesRow)
        self.assertFalse(row.get_activatable())
        self.assertFalse(row.get_selectable())
        labels = [widget for widget in descendants(row) if isinstance(widget, ui.Gtk.Label)]
        self.assertEqual([label.get_text() for label in labels],
                         ["Highlight phrases", "One word or phrase per line. Case-sensitive."])
        self.assertTrue(all(label.get_wrap() for label in labels))

    @staticmethod
    def highlights(w):
        return next(widget for widget in descendants(w._navigation.pages["home"])
                    if isinstance(widget, ui.Adw.ExpanderRow) and widget.get_title() == "Highlights")

    def test_inline_highlights_save_all_repeat_fail_clear_and_close(self):
        w = self.window()
        nav = w._navigation
        highlights = self.highlights(w)
        highlights.set_expanded(True)
        buffer = w._highlight_phrases_buffer
        literal = " word \nbest interests\nreasonable, efforts\nLiteral α\n\nword\nWord\n"
        buffer.set_text(literal)
        highlights.set_expanded(False)
        w._ai_font_size_row.set_value(15)
        baseline = w._session.baseline
        with patch.object(ui, "save_ai_settings", side_effect=OSError("synthetic failure")), \
             patch.object(w, "_show_status_toast") as status:
            nav.save_buttons["home"].emit("clicked")
        self.assertIn("drafts are retained", status.call_args.args[0])
        self.assertEqual(w._session.baseline, baseline)
        self.assertEqual(buffer.get_text(*buffer.get_bounds(), True), literal)
        with patch.object(ui, "save_ai_settings") as save:
            nav.save_buttons["home"].emit("clicked")
            self.assertEqual(save.call_args.args[0].highlight_phrases,
                             ["word", "best interests", "reasonable, efforts", "Literal α", "Word"])
            self.app.update_font_sizes.assert_called_once()
            self.assertEqual(self.app.update_font_sizes.call_args.kwargs["ai_font_size_pt"], 15)
            self.assertTrue(w.get_visible())
            self.assertEqual(nav.view.get_visible_page().get_tag(), "home")
            self.assertEqual(w._session.baseline, w._draft_snapshot())
            highlights.set_expanded(True)
            self.assertEqual(buffer.get_text(*buffer.get_bounds(), True), literal)
            nav.save_buttons["home"].emit("clicked")
            self.assertEqual(save.call_count, 2)
            buffer.set_text("")
            nav.save_buttons["home"].emit("clicked")
            self.assertEqual(save.call_args.args[0].highlight_phrases, [])
            self.assertEqual(w._session.baseline, w._draft_snapshot())
        buffer.insert_at_cursor(" unsaved")
        self.assertTrue(w._on_settings_close_request())
        self.assertFalse(w._pi_model_closed)
        w._session.dialog.response("keep")
        self.assertTrue(w.get_visible())
        self.assertEqual(w._prompt_text(buffer), " unsaved")
        self.assertTrue(w._on_settings_close_request())
        w._session.dialog.response("discard")
        self.assertTrue(w._pi_model_closed)
        self.assertTrue(w._session.closed)

    def test_inline_height_tracks_font_changes(self):
        w = self.window()
        highlights = self.highlights(w)
        highlights.set_expanded(True)
        view = next(widget for widget in descendants(highlights)
                    if isinstance(widget, ui.Gtk.TextView))
        scroller = view.get_parent()
        settings = view.get_settings()
        original = settings.get_property("gtk-font-name")
        self.addCleanup(settings.set_property, "gtk-font-name", original)
        settings.set_property("gtk-font-name", "Sans 24")
        context = ui.GLib.MainContext.default()
        while context.pending():
            context.iteration(False)
        expected = view.create_pango_layout("Ag\nAg\nAg").get_pixel_size()[1] + 16
        self.assertEqual(scroller.get_min_content_height(), expected)
        self.assertEqual(scroller.get_max_content_height(), expected)
        self.assertEqual(w._prompt_text(w._highlight_phrases_buffer), "")

    def test_inline_edit_undo_and_soft_wrap_preserve_literal_text(self):
        w = self.window()
        buffer = w._highlight_phrases_buffer
        literal = "long phrase " * 100
        buffer.set_text(literal)
        buffer.begin_user_action()
        buffer.insert_at_cursor("\nSecond phrase\nUnicode α, β")
        buffer.end_user_action()
        self.assertEqual(buffer.get_line_count(), 3)
        buffer.undo()
        self.assertEqual(w._prompt_text(buffer), literal)
        buffer.redo()
        self.assertEqual(buffer.get_line_count(), 3)
