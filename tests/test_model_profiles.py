import json

import focus.core as focus
from focus.core import (
    CONFIG_KEY_API_KEY,
    CONFIG_KEY_API_URL,
    CONFIG_KEY_MODEL_ID,
    CONFIG_KEY_MODEL_PROFILES,
    CONFIG_KEY_PAGE_API_KEY,
    CONFIG_KEY_PAGE_API_URL,
    CONFIG_KEY_PAGE_MODEL_ID,
    CONFIG_KEY_PI_AGENT_COMMAND,
    CONFIG_KEY_SEARCH_CHIP_COLOR,
    CONFIG_KEY_TASK_DEFAULT_PROFILES,
    MODEL_PROFILE_IDS,
    TASK_PROFILE_PAGE,
    TASK_PROFILE_RANGE,
    AiSettings,
    ModelProfile,
    discover_pi_agent_command,
    incompatible_pi_agent_flag,
    load_ai_settings,
    resolve_pi_agent_argv,
    save_ai_settings,
)


def test_load_ai_settings_builds_profiles_from_legacy_credentials(tmp_path, monkeypatch) -> None:
    config_path = tmp_path / "config.json"
    config_path.write_text(
        """{
  "page_api_url": "https://page.example/v1/chat/completions",
  "page_model_id": "page-model",
  "page_api_key": "page-key",
  "range_api_url": "https://range.example/v1/chat/completions",
  "range_model_id": "range-model",
  "range_api_key": "range-key"
}
""",
        encoding="utf-8",
    )
    monkeypatch.setattr(focus, "CONFIG_FILE", config_path)

    settings = load_ai_settings()

    assert [profile.key for profile in settings.model_profiles] == list(MODEL_PROFILE_IDS)
    assert settings.task_profile_defaults[TASK_PROFILE_PAGE] == "profile1"
    assert settings.task_profile_defaults[TASK_PROFILE_RANGE] == "profile2"
    assert settings.page_credentials() == (
        "https://page.example/v1/chat/completions",
        "page-model",
        "page-key",
    )
    assert settings.range_credentials() == (
        "https://range.example/v1/chat/completions",
        "range-model",
        "range-key",
    )


def test_profile_credentials_override_legacy_values() -> None:
    settings = AiSettings(
        api_url="https://legacy.example",
        model_id="legacy-model",
        api_key="legacy-key",
        page_api_url="https://legacy-page.example",
        page_model_id="legacy-page-model",
        page_api_key="legacy-page-key",
        range_api_url="",
        range_model_id="",
        range_api_key="",
        extract_api_url="",
        extract_model_id="",
        extract_api_key="",
        page_disable_reasoning=False,
        range_disable_reasoning=False,
        extract_disable_reasoning=False,
        page_prompt="Prompt",
        range_prompt="Prompt",
        extract_prompt="Prompt",
        rag_provider=focus.DEFAULT_RAG_PROVIDER,
        voyage_api_key="voyage-key",
        voyage_model=focus.DEFAULT_RAG_VOYAGE_MODEL,
        isaacus_api_key="",
        isaacus_model=focus.DEFAULT_RAG_ISAACUS_MODEL,
        rag_llm_model="",
        rag_deep_llm_model="",
        rag_prompt="Prompt",
        rag_api_url="",
        rag_api_key="",
        rag_deep_api_url="",
        rag_deep_api_key="",
        rag_disable_reasoning=False,
        rag_deep_disable_reasoning=False,
        rag_chunk_count=focus.DEFAULT_RAG_CHUNK_COUNT,
        speech_rag_source_file="",
        highlight_phrases=[],
        grep_highlight_color=focus.DEFAULT_MATCH_COLOR,
        phrase_highlight_color=focus.DEFAULT_HIGHLIGHT_COLOR,
        summary_emphasis_color=focus.DEFAULT_SUMMARY_EMPHASIS_COLOR,
        search_chip_color=focus.DEFAULT_SEARCH_CHIP_COLOR,
        model_profiles=[
            ModelProfile(
                key="profile1",
                nickname="Fast",
                abbreviation="F",
                api_url="https://profile.example",
                model_id="profile-model",
                api_key="profile-key",
                disable_reasoning=True,
            )
        ],
        task_profile_defaults={TASK_PROFILE_PAGE: "profile1"},
    )

    credentials = settings.page_llm_credentials()

    assert credentials.api_url == "https://profile.example"
    assert credentials.model_id == "profile-model"
    assert credentials.api_key == "profile-key"
    assert credentials.disable_reasoning is True


def test_model_profile_short_name_prefers_abbreviation() -> None:
    profile = ModelProfile(
        key="profile1",
        nickname="Long Model Name",
        abbreviation="LM",
        api_url="https://profile.example",
        model_id="profile-model",
        api_key="profile-key",
        disable_reasoning=False,
    )

    assert profile.short_name() == "LM"


def test_model_profile_short_name_falls_back_to_display_name() -> None:
    profile = ModelProfile(
        key="profile1",
        nickname="Long Model Name",
        abbreviation="",
        api_url="https://profile.example",
        model_id="profile-model",
        api_key="profile-key",
        disable_reasoning=False,
    )

    assert profile.short_name() == "Long Model Name"


def test_save_ai_settings_writes_profiles_and_legacy_compatibility(tmp_path, monkeypatch) -> None:
    config_path = tmp_path / "config.json"
    config_path.write_text(
        json.dumps({"agent_prompt_template": "Stale prompt: {question}"}),
        encoding="utf-8",
    )
    monkeypatch.setattr(focus, "CONFIG_FILE", config_path)
    profile = ModelProfile(
        key="profile1",
        nickname="Default",
        abbreviation="D",
        api_url="https://profile.example",
        model_id="profile-model",
        api_key="profile-key",
        disable_reasoning=False,
    )
    settings = load_ai_settings()
    settings.model_profiles[0] = profile
    settings.task_profile_defaults[TASK_PROFILE_PAGE] = "profile1"
    settings.pi_agent_command = "/opt/pi/bin/pi --thinking high"

    save_ai_settings(settings)
    saved = focus._read_config()

    assert saved[CONFIG_KEY_MODEL_PROFILES][0]["nickname"] == "Default"
    assert saved[CONFIG_KEY_TASK_DEFAULT_PROFILES][TASK_PROFILE_PAGE] == "profile1"
    assert saved[CONFIG_KEY_API_URL] == "https://profile.example"
    assert saved[CONFIG_KEY_MODEL_ID] == "profile-model"
    assert saved[CONFIG_KEY_API_KEY] == "profile-key"
    assert "agent_prompt_template" not in saved
    assert saved[CONFIG_KEY_PI_AGENT_COMMAND] == "/opt/pi/bin/pi --thinking high"
    assert saved[CONFIG_KEY_PAGE_API_URL] == "https://profile.example"
    assert saved[CONFIG_KEY_PAGE_MODEL_ID] == "profile-model"
    assert saved[CONFIG_KEY_PAGE_API_KEY] == "profile-key"
    assert saved[CONFIG_KEY_SEARCH_CHIP_COLOR] == focus.DEFAULT_SEARCH_CHIP_COLOR


def test_load_ai_settings_ignores_retired_agent_prompt_template(tmp_path, monkeypatch) -> None:
    config_path = tmp_path / "config.json"
    config_path.write_text(
        json.dumps({"agent_prompt_template": "Shared prompt: {question}"}),
        encoding="utf-8",
    )
    monkeypatch.setattr(focus, "CONFIG_FILE", config_path)

    settings = load_ai_settings()

    assert not hasattr(settings, "agent_prompt_template")


def test_discover_pi_agent_command_finds_installer_layout(tmp_path) -> None:
    pi_path = tmp_path / ".local" / "share" / "pi-node" / "node-v22" / "bin" / "pi"
    pi_path.parent.mkdir(parents=True)
    pi_path.write_text("#!/bin/sh\n", encoding="utf-8")
    pi_path.chmod(0o755)

    assert discover_pi_agent_command(tmp_path, path_env="") == str(pi_path)


def test_resolve_pi_agent_argv_preserves_arguments(tmp_path, monkeypatch) -> None:
    pi_path = tmp_path / "pi"
    pi_path.write_text("#!/bin/sh\n", encoding="utf-8")
    pi_path.chmod(0o755)
    monkeypatch.setattr(focus, "discover_pi_agent_command", lambda **_kwargs: str(pi_path))

    assert resolve_pi_agent_argv("pi --thinking high") == [
        str(pi_path),
        "--thinking",
        "high",
    ]


def test_incompatible_pi_agent_flag_rejects_noninteractive_modes() -> None:
    assert incompatible_pi_agent_flag(["pi", "--print"]) == "--print"
    assert incompatible_pi_agent_flag(["pi", "--mode", "json"]) == "--mode json"
    assert incompatible_pi_agent_flag(["pi", "--mode=text"]) is None


def test_incompatible_pi_agent_flag_rejects_project_policy_overrides() -> None:
    assert incompatible_pi_agent_flag(["pi", "--model", "other"]) == "--model"
    assert incompatible_pi_agent_flag(["pi", "--provider=other"]) == "--provider=other"
    assert incompatible_pi_agent_flag(["pi", "--tools", "read"]) == "--tools"
    assert incompatible_pi_agent_flag(["pi", "--no-skills"]) == "--no-skills"
    assert incompatible_pi_agent_flag(["pi", "--no-approve"]) == "--no-approve"
