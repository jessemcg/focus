from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import patch

from focus.pi_runtime import PiModel
from focus.ui.settings import AiSettingsWindow


class FakeComboRow:
    def __init__(self) -> None:
        self.selected = 0
        self.model: object = None
        self.sensitive = False
        self.subtitle = ""

    def get_selected(self) -> int:
        return self.selected

    def set_selected(self, selected: int) -> None:
        self.selected = selected

    def set_model(self, model: object) -> None:
        self.model = model

    def set_sensitive(self, sensitive: bool) -> None:
        self.sensitive = sensitive

    def set_subtitle(self, subtitle: str) -> None:
        self.subtitle = subtitle


class FakeButton:
    def __init__(self) -> None:
        self.sensitive = False

    def set_sensitive(self, sensitive: bool) -> None:
        self.sensitive = sensitive


def model_window(
    original: tuple[str, str] | None,
) -> SimpleNamespace:
    window = SimpleNamespace(
        _pi_model_closed=False,
        _pi_model_generation=1,
        _pi_model_options=[],
        _pi_model_applying=False,
        _pi_model_selection_changed=False,
        _original_pi_model_key=original,
        pi_model_row=FakeComboRow(),
        pi_model_refresh_button=FakeButton(),
    )
    def selected_pi_model() -> PiModel | None:
        return AiSettingsWindow._selected_pi_model(window)  # type: ignore[arg-type]

    window._selected_pi_model = selected_pi_model
    window._update_pi_model_subtitle = (  # type: ignore[attr-defined]
        lambda: AiSettingsWindow._update_pi_model_subtitle(window)  # type: ignore[arg-type]
    )
    return window


def test_available_models_select_current_project_model() -> None:
    window = model_window(("openai-codex", "gpt-5.6-sol"))
    models = [
        PiModel(
            provider="fireworks",
            model_id="accounts/fireworks/models/glm-5p2",
            name="GLM 5.2",
        ),
        PiModel(
            provider="openai-codex",
            model_id="gpt-5.6-sol",
            name="GPT-5.6 Sol",
        ),
    ]

    with patch(
        "focus.ui.settings.Gtk.StringList.new",
        side_effect=lambda labels: list(labels),
    ):
        result = AiSettingsWindow._finish_pi_model_load(  # type: ignore[arg-type]
            window,
            1,
            models,
            "",
            ("openai-codex", "gpt-5.6-sol"),
        )

    assert result is False
    assert window.pi_model_row.selected == 1
    assert window.pi_model_row.sensitive is True
    assert window._pi_model_selection_changed is False
    assert (
        window.pi_model_row.subtitle
        == "Project-wide setting: openai-codex / gpt-5.6-sol"
    )


def test_unavailable_current_model_is_preserved() -> None:
    window = model_window(("openai-codex", "retired-model"))
    available = PiModel(
        provider="fireworks",
        model_id="accounts/fireworks/models/glm-5p2",
        name="GLM 5.2",
    )

    with patch(
        "focus.ui.settings.Gtk.StringList.new",
        side_effect=lambda labels: list(labels),
    ):
        AiSettingsWindow._finish_pi_model_load(  # type: ignore[arg-type]
            window,
            1,
            [available],
            "",
            ("openai-codex", "retired-model"),
        )

    assert window.pi_model_row.selected == 0
    assert window.pi_model_row.sensitive is True
    assert window._pi_model_selection_changed is False
    assert "currently configured; unavailable" in window.pi_model_row.model[0]

    window.pi_model_row.selected = 1
    AiSettingsWindow._on_pi_model_selected(  # type: ignore[arg-type]
        window,
        window.pi_model_row,
        object(),
    )
    assert window._pi_model_selection_changed is True


def test_model_query_failure_disables_row_without_changing_model() -> None:
    window = model_window(("openai-codex", "gpt-5.6-sol"))

    with patch(
        "focus.ui.settings.Gtk.StringList.new",
        side_effect=lambda labels: list(labels),
    ):
        AiSettingsWindow._finish_pi_model_load(  # type: ignore[arg-type]
            window,
            1,
            [],
            "PI model query failed.",
            ("openai-codex", "gpt-5.6-sol"),
        )

    assert window.pi_model_row.sensitive is False
    assert window.pi_model_refresh_button.sensitive is True
    assert window.pi_model_row.subtitle == "PI model query failed."
    assert window._selected_pi_model().settings_key == (
        "openai-codex",
        "gpt-5.6-sol",
    )


def test_empty_model_list_prompts_for_pi_authorization() -> None:
    window = model_window(None)

    with patch(
        "focus.ui.settings.Gtk.StringList.new",
        side_effect=lambda labels: list(labels),
    ):
        AiSettingsWindow._finish_pi_model_load(  # type: ignore[arg-type]
            window,
            1,
            [],
            "",
            None,
        )

    assert window.pi_model_row.model == ["No authenticated PI models found"]
    assert window.pi_model_row.sensitive is False
    assert "Authorize a provider in PI" in window.pi_model_row.subtitle


def test_stale_model_query_result_is_ignored() -> None:
    window = model_window(("fireworks", "current"))
    window._pi_model_generation = 2

    result = AiSettingsWindow._finish_pi_model_load(  # type: ignore[arg-type]
        window,
        1,
        [PiModel("fireworks", "stale", "Stale")],
        "",
        ("fireworks", "stale"),
    )

    assert result is False
    assert window._pi_model_options == []
