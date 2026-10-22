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
        with patch.object(ui, "current_project_pi_model", return_value=("synthetic", "saved")), \
             patch.object(ui, "current_project_pi_thinking_level", return_value="medium"), \
             patch.object(ui, "load_ai_settings", return_value=ui.AiSettings(speech_agent_source_file="/synthetic/speech", grep_highlight_color=ui.DEFAULT_MATCH_COLOR, search_chip_color=ui.DEFAULT_SEARCH_CHIP_COLOR)), \
             patch.object(ui.AiSettingsWindow, "_load_pi_models"):
            w = ui.AiSettingsWindow(app)
        w.present()
        self.addCleanup(w.destroy)
        return w

    @staticmethod
    def highlights(w):
        return next(widget for widget in descendants(w._navigation.pages["home"])
                    if isinstance(widget, ui.Adw.ExpanderRow) and widget.get_title() == "Highlights")

    @staticmethod
    def set_grep_color(w, value):
        w._set_color_control_value(w._grep_highlight_color_control, value, ui.DEFAULT_MATCH_COLOR)
        return w._read_color_control_value(w._grep_highlight_color_control, ui.DEFAULT_MATCH_COLOR)

    def test_later_font_write_failure_retains_accepted_baseline(self):
        w = self.window()
        baseline = w._session.baseline
        w._ai_font_size_row.set_value(19)
        draft_color = self.set_grep_color(w, "#ff0000")
        self.app.update_font_sizes.side_effect = OSError("synthetic font write failure")
        with patch.object(ui, "save_ai_settings") as save, \
             patch.object(w, "_show_status_toast") as status:
            w._navigation.save_buttons["home"].emit("clicked")
        save.assert_called_once()
        self.assertEqual(save.call_args.args[0].grep_highlight_color, draft_color)
        self.assertEqual(
            w._read_color_control_value(w._grep_highlight_color_control, ui.DEFAULT_MATCH_COLOR),
            draft_color,
        )
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

    def test_highlights_has_only_retained_color_rows(self):
        w = self.window()
        self.assertEqual(set(w._navigation.pages), {"home"})
        self.assertEqual(set(w._navigation.save_buttons), {"home"})
        highlights = self.highlights(w)
        titles = [row.get_title() for row in descendants(highlights)
                  if isinstance(row, ui.Adw.PreferencesRow)]
        self.assertEqual(set(titles), {"Highlights", "Grep Highlight Color", "Search and Cite Chip Color"})
        self.assertFalse(any(isinstance(widget, ui.Gtk.TextView)
                             for widget in descendants(highlights)))
        self.assertFalse(hasattr(w, "_highlight_phrases_buffer"))
        self.assertFalse(hasattr(w, "_phrase_highlight_color_control"))

    def test_highlights_save_fail_repeat_and_close(self):
        w = self.window()
        nav = w._navigation
        highlights = self.highlights(w)
        highlights.set_expanded(True)
        draft_color = self.set_grep_color(w, "#ff0000")
        highlights.set_expanded(False)
        w._ai_font_size_row.set_value(15)
        baseline = w._session.baseline
        with patch.object(ui, "save_ai_settings", side_effect=OSError("synthetic failure")), \
             patch.object(w, "_show_status_toast") as status:
            nav.save_buttons["home"].emit("clicked")
        self.assertIn("drafts are retained", status.call_args.args[0])
        self.assertEqual(w._session.baseline, baseline)
        self.assertEqual(
            w._read_color_control_value(w._grep_highlight_color_control, ui.DEFAULT_MATCH_COLOR),
            draft_color,
        )
        with patch.object(ui, "save_ai_settings") as save:
            nav.save_buttons["home"].emit("clicked")
            self.assertEqual(save.call_args.args[0].grep_highlight_color, draft_color)
            self.app.update_font_sizes.assert_called_once()
            self.assertEqual(self.app.update_font_sizes.call_args.kwargs["ai_font_size_pt"], 15)
            self.assertTrue(w.get_visible())
            self.assertEqual(nav.view.get_visible_page().get_tag(), "home")
            self.assertEqual(w._session.baseline, w._draft_snapshot())
            highlights.set_expanded(True)
            self.assertEqual(
                w._read_color_control_value(w._grep_highlight_color_control, ui.DEFAULT_MATCH_COLOR),
                draft_color,
            )
            nav.save_buttons["home"].emit("clicked")
            self.assertEqual(save.call_count, 2)
            second_color = self.set_grep_color(w, "#00ff00")
            nav.save_buttons["home"].emit("clicked")
            self.assertEqual(save.call_args.args[0].grep_highlight_color, second_color)
            self.assertEqual(w._session.baseline, w._draft_snapshot())
        unsaved_color = self.set_grep_color(w, "#0000ff")
        self.assertTrue(w._on_settings_close_request())
        self.assertFalse(w._pi_model_closed)
        w._session.dialog.response("keep")
        self.assertTrue(w.get_visible())
        self.assertEqual(
            w._read_color_control_value(w._grep_highlight_color_control, ui.DEFAULT_MATCH_COLOR),
            unsaved_color,
        )
        self.assertTrue(w._on_settings_close_request())
        w._session.dialog.response("discard")
        self.assertTrue(w._pi_model_closed)
        self.assertTrue(w._session.closed)
