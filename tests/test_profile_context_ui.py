import tempfile
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

from focus import profile_integration as ui
from focus.practice_profiles import bundled_profile_directory, validate_profile_directory
from focus.profile_contract import ProfileError


def test_unconfirmed_and_missing_research_are_not_labelled_legacy():
    with tempfile.TemporaryDirectory() as temporary:
        root = Path(temporary)
        button = Mock()
        app = SimpleNamespace(_practice_profile_button=button, _record_layout=SimpleNamespace(root=root))
        with patch.object(ui, "read_selection", return_value=None):
            ui.update_indicator(app)
            button.set_label.assert_called_with("Research: Choose profile")
        profile = validate_profile_directory(bundled_profile_directory("general")).draft
        with patch.object(ui, "read_selection", return_value=SimpleNamespace(profile_ref=profile.ref)), patch.object(ui, "profile_store") as store:
            store.return_value.load_profile_snapshot.side_effect = ProfileError("snapshot_unavailable", "selection")
            ui.update_indicator(app)
            button.set_label.assert_called_with("Research: unavailable")
            assert "Selected research instructions unavailable" in ui.context_description(root)
            store.return_value.load_profile_snapshot.side_effect = None
            store.return_value.load_profile_snapshot.return_value = profile
            ui.update_indicator(app)
            button.set_label.assert_called_with("Research: General Court Record")
