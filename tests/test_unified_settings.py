"""Native settings with fabricated preferences and model adapters."""
import unittest
from unittest.mock import Mock, patch
from focus.ui import settings as ui


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
        self.app.update_font_sizes.side_effect = OSError("synthetic font write failure")
        with patch.object(ui, "save_ai_settings") as save:
            w._navigation.save_buttons["home"].emit("clicked")
        save.assert_called_once()
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

    def test_highlights_destination_save_all_repeat_fail_and_close(self):
        w = self.window()
        nav = w._navigation
        nav.open("highlight-phrases")
        buffer = w._highlight_phrases_buffer
        buffer.set_text("Literal α\nSecond phrase")
        baseline = w._session.baseline
        with patch.object(ui, "save_ai_settings", side_effect=OSError("synthetic failure")):
            nav.save_buttons["highlight-phrases"].emit("clicked")
        self.assertEqual(w._session.baseline, baseline)
        self.assertEqual(buffer.get_text(*buffer.get_bounds(), True), "Literal α\nSecond phrase")
        with patch.object(ui, "save_ai_settings") as save:
            nav.save_buttons["highlight-phrases"].emit("clicked")
            self.assertTrue(w.get_visible())
            self.assertEqual(nav.view.get_visible_page().get_tag(), "highlight-phrases")
            self.assertEqual(w._session.baseline, w._draft_snapshot())
            w._ai_font_size_row.set_value(15)
            nav.save_buttons["home"].emit("clicked")
            self.assertEqual(save.call_count, 2)
        buffer.insert_at_cursor(" unsaved")
        self.assertTrue(w._on_settings_close_request())
        self.assertFalse(w._pi_model_closed)
        w._session.dialog.response("keep")
