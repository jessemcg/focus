from __future__ import annotations

import json
import os
import stat
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

from focus.pi_runtime import (
    DEFAULT_PROJECT_PI_SETTINGS,
    PiModel,
    PiRuntimeError,
    PiSettingsError,
    _pi_discovery_command,
    _pi_process_environment,
    _pi_rpc_response,
    available_pi_models,
    clamp_pi_thinking_level,
    current_project_pi_model,
    current_project_pi_thinking_level,
    ensure_project_pi_settings,
    save_project_pi_model,
    save_project_pi_runtime,
)


def test_ensure_project_pi_settings_seeds_defaults_when_missing(tmp_path: Path) -> None:
    path = tmp_path / ".pi" / "settings.json"

    ensure_project_pi_settings(path)

    assert json.loads(path.read_text(encoding="utf-8")) == DEFAULT_PROJECT_PI_SETTINGS
    assert stat.S_IMODE(path.stat().st_mode) == 0o600
    assert list(path.parent.glob(".settings.json.*.tmp")) == []


def test_ensure_project_pi_settings_preserves_existing_file(tmp_path: Path) -> None:
    path = tmp_path / "settings.json"
    path.write_text('{"defaultModel": "local-choice"}', encoding="utf-8")

    ensure_project_pi_settings(path)

    assert json.loads(path.read_text(encoding="utf-8")) == {"defaultModel": "local-choice"}


def test_ensure_project_pi_settings_does_not_replace_concurrent_file(
    tmp_path: Path,
) -> None:
    path = tmp_path / "settings.json"
    original_link = os.link

    def concurrent_create(source: Path, destination: Path) -> None:
        path.write_text('{"defaultModel": "user-choice"}', encoding="utf-8")
        original_link(source, destination)

    with patch("focus.pi_runtime.os.link", side_effect=concurrent_create):
        ensure_project_pi_settings(path)

    assert json.loads(path.read_text(encoding="utf-8")) == {"defaultModel": "user-choice"}
    assert list(tmp_path.glob(".settings.json.*.tmp")) == []


def test_ensure_project_pi_settings_preserves_dangling_symlink(
    tmp_path: Path,
) -> None:
    path = tmp_path / "settings.json"
    path.symlink_to("missing-settings.json")

    ensure_project_pi_settings(path)

    assert path.is_symlink()
    with pytest.raises(PiSettingsError, match="not found"):
        current_project_pi_model(path)


def test_save_project_runtime_does_not_replace_symlink(tmp_path: Path) -> None:
    target = tmp_path / "other-settings.json"
    target.write_text('{"defaultModel": "user-choice"}', encoding="utf-8")
    path = tmp_path / "settings.json"
    path.symlink_to(target)

    with pytest.raises(PiSettingsError, match="symlink"):
        save_project_pi_runtime(PiModel("provider", "model", "Model"), "low", path)

    assert path.is_symlink()
    assert json.loads(target.read_text(encoding="utf-8")) == {"defaultModel": "user-choice"}


def test_save_project_runtime_seeds_missing_file(tmp_path: Path) -> None:
    path = tmp_path / "settings.json"

    save_project_pi_runtime(
        PiModel("fireworks", "accounts/fireworks/models/glm-5p2", "GLM 5.2"),
        "high",
        path,
    )

    saved = json.loads(path.read_text(encoding="utf-8"))
    assert saved["defaultProvider"] == "fireworks"
    assert saved["defaultModel"] == "accounts/fireworks/models/glm-5p2"
    assert saved["defaultThinkingLevel"] == "high"
    assert saved["compaction"] == {"enabled": False}
    assert saved["retry"] == {"enabled": True}
    assert stat.S_IMODE(path.stat().st_mode) == 0o600


def test_available_models_uses_rpc_and_sorts_deduplicated_models() -> None:
    response = {
        "type": "response",
        "command": "get_available_models",
        "success": True,
        "data": {
            "models": [
                {
                    "provider": "openai-codex",
                    "id": "gpt-5.6-sol",
                    "name": "GPT-5.6 Sol",
                    "reasoning": True,
                    "thinkingLevelMap": {
                        "off": "none",
                        "minimal": None,
                        "low": "low",
                        "medium": "medium",
                        "high": "high",
                        "xhigh": "xhigh",
                        "max": None,
                    },
                },
                {
                    "provider": "fireworks",
                    "id": "accounts/fireworks/models/glm-5p2",
                    "name": "GLM 5.2",
                    "reasoning": False,
                },
                {
                    "provider": "fireworks",
                    "id": "accounts/fireworks/models/glm-5p2",
                    "name": "GLM 5.2",
                    "reasoning": False,
                },
                {"provider": "", "id": "invalid"},
            ]
        },
    }
    with patch(
        "focus.pi_runtime._pi_rpc_response",
        return_value=response,
    ) as rpc:
        models = available_pi_models(
            ["pi", "--thinking", "high", "--mode=text"]
        )

    assert [model.settings_key for model in models] == [
        ("fireworks", "accounts/fireworks/models/glm-5p2"),
        ("openai-codex", "gpt-5.6-sol"),
    ]
    assert models[1].label == "GPT-5.6 Sol — openai-codex"
    assert models[0].supported_thinking_levels == ("off",)
    assert models[1].supported_thinking_levels == (
        "off",
        "low",
        "medium",
        "high",
        "xhigh",
    )
    command = rpc.call_args.args[0]
    assert command[:3] == ["pi", "--thinking", "high"]
    assert "--mode=text" not in command
    assert command[command.index("--mode") + 1] == "rpc"
    assert "--offline" in command
    assert "--no-extensions" in command
    assert rpc.call_args.args[1] == {"type": "get_available_models"}


def test_empty_pi_command_is_rejected() -> None:
    with pytest.raises(PiRuntimeError, match="empty"):
        _pi_discovery_command([])


def test_absolute_pi_command_prepends_its_directory_to_path(
    tmp_path: Path,
) -> None:
    executable = tmp_path / "pi"
    environment = _pi_process_environment([str(executable)])

    assert environment["PATH"].split(":")[0] == str(tmp_path)


def test_rpc_keeps_stdin_open_until_response() -> None:
    response = _pi_rpc_response(
        [
            sys.executable,
            "-c",
            (
                "import json,sys;"
                "request=json.loads(sys.stdin.readline());"
                "print(json.dumps({'type':'response','command':request['type'],"
                "'success':True,'data':{'models':[]}}),flush=True);"
                "sys.stdin.read()"
            ),
        ],
        {"type": "get_available_models"},
        timeout=2,
    )

    assert response["success"] is True


def test_rpc_reports_timeout() -> None:
    with pytest.raises(PiRuntimeError, match="timed out"):
        _pi_rpc_response(
            [
                sys.executable,
                "-c",
                "import sys,time;sys.stdin.readline();time.sleep(5)",
            ],
            {"type": "get_available_models"},
            timeout=0.05,
        )


def test_rpc_rejects_missing_response() -> None:
    with pytest.raises(PiRuntimeError, match="did not return"):
        _pi_rpc_response(
            [
                sys.executable,
                "-c",
                (
                    "import json,sys;"
                    "sys.stdin.readline();"
                    "print(json.dumps({'type':'response','command':'get_state',"
                    "'success':True}),flush=True)"
                ),
            ],
            {"type": "get_available_models"},
            timeout=2,
        )


def test_available_models_reports_rpc_failure() -> None:
    with patch(
        "focus.pi_runtime._pi_rpc_response",
        return_value={
            "type": "response",
            "command": "get_available_models",
            "success": False,
            "error": "authentication failed",
        },
    ):
        with pytest.raises(PiRuntimeError, match="authentication failed"):
            available_pi_models(["pi"])


def test_reads_and_atomically_updates_project_model(tmp_path: Path) -> None:
    path = tmp_path / "settings.json"
    path.write_text(
        json.dumps(
            {
                "defaultProvider": "openai-codex",
                "defaultModel": "gpt-5.6-sol",
                "defaultThinkingLevel": "medium",
                "enableSkillCommands": True,
                "futureSetting": {"enabled": True},
            }
        ),
        encoding="utf-8",
    )

    assert current_project_pi_model(path) == (
        "openai-codex",
        "gpt-5.6-sol",
    )
    assert current_project_pi_thinking_level(path) == "medium"
    save_project_pi_runtime(
        PiModel(
            provider="fireworks",
            model_id="accounts/fireworks/models/glm-5p2",
            name="GLM 5.2",
        ),
        "high",
        path,
    )

    saved = json.loads(path.read_text(encoding="utf-8"))
    assert saved["defaultProvider"] == "fireworks"
    assert saved["defaultModel"] == "accounts/fireworks/models/glm-5p2"
    assert saved["defaultThinkingLevel"] == "high"
    assert "fireworksPriorityServiceTier" not in saved
    assert saved["enableSkillCommands"] is True
    assert saved["futureSetting"] == {"enabled": True}
    assert stat.S_IMODE(path.stat().st_mode) == 0o600
    assert list(path.parent.glob(".settings.json.*.tmp")) == []


def test_missing_or_invalid_project_reasoning_uses_ui_default(tmp_path: Path) -> None:
    path = tmp_path / "settings.json"
    path.write_text(
        '{"defaultProvider":"provider","defaultModel":"model"}',
        encoding="utf-8",
    )
    assert current_project_pi_thinking_level(path) is None

    path.write_text('{"defaultThinkingLevel":"unknown"}', encoding="utf-8")
    assert current_project_pi_thinking_level(path) is None


def test_save_project_runtime_rejects_invalid_reasoning(tmp_path: Path) -> None:
    path = tmp_path / "settings.json"
    path.write_text("{}", encoding="utf-8")

    with pytest.raises(PiSettingsError, match="Unsupported"):
        save_project_pi_runtime(
            PiModel("provider", "model", "Model"),
            "extreme",
            path,
        )

    assert json.loads(path.read_text(encoding="utf-8")) == {}


def test_clamp_reasoning_prefers_next_supported_level() -> None:
    model = PiModel(
        "provider",
        "model",
        "Model",
        supported_thinking_levels=("off", "low", "high"),
    )

    assert clamp_pi_thinking_level(model, "medium") == "high"
    assert clamp_pi_thinking_level(model, "max") == "high"
    assert clamp_pi_thinking_level(model, "unknown") == "high"


def test_invalid_project_settings_are_not_overwritten(tmp_path: Path) -> None:
    path = tmp_path / "settings.json"
    path.write_text("{invalid", encoding="utf-8")

    with pytest.raises(PiSettingsError):
        save_project_pi_model(
            PiModel(
                provider="openai-codex",
                model_id="gpt-5.6-sol",
                name="GPT-5.6 Sol",
            ),
            path,
        )

    assert path.read_text(encoding="utf-8") == "{invalid"
