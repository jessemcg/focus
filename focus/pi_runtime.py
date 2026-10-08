from __future__ import annotations

import json
import os
import subprocess
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Sequence


PROJECT_DIR = Path(__file__).resolve().parent.parent
from .paths import pi_settings_file

PROJECT_PI_SETTINGS_PATH = pi_settings_file()
# `.pi/settings.json` is local runtime state (git-ignored); seed it from these
# application defaults when it is missing so a fresh checkout can run the Agent.
DEFAULT_PROJECT_PI_SETTINGS: dict[str, Any] = {
    "defaultThinkingLevel": "low",
    "enableSkillCommands": True,
    "compaction": {"enabled": False},
    "retry": {"enabled": True},
}
PI_MODEL_DISCOVERY_TIMEOUT_SECONDS = 10
PI_THINKING_LEVELS: tuple[str, ...] = (
    "off",
    "minimal",
    "low",
    "medium",
    "high",
    "xhigh",
    "max",
)


class PiRuntimeError(RuntimeError):
    pass


class PiSettingsError(RuntimeError):
    pass


@dataclass(frozen=True, slots=True)
class PiModel:
    provider: str
    model_id: str
    name: str
    supported_thinking_levels: tuple[str, ...] = PI_THINKING_LEVELS[:5]

    @property
    def label(self) -> str:
        return f"{self.name} — {self.provider}"

    @property
    def settings_key(self) -> tuple[str, str]:
        return self.provider, self.model_id


def clamp_pi_thinking_level(model: PiModel, level: str) -> str:
    supported = model.supported_thinking_levels or ("off",)
    if level in supported:
        return level
    try:
        requested_index = PI_THINKING_LEVELS.index(level)
    except ValueError:
        requested_index = PI_THINKING_LEVELS.index("medium")
    for candidate in PI_THINKING_LEVELS[requested_index:]:
        if candidate in supported:
            return candidate
    for candidate in reversed(PI_THINKING_LEVELS[:requested_index]):
        if candidate in supported:
            return candidate
    return supported[0]


def _supported_thinking_levels(raw_model: dict[str, Any]) -> tuple[str, ...]:
    if raw_model.get("reasoning") is False:
        return ("off",)
    raw_map = raw_model.get("thinkingLevelMap")
    thinking_map = raw_map if isinstance(raw_map, dict) else {}
    levels: list[str] = []
    for level in PI_THINKING_LEVELS:
        if level in thinking_map and thinking_map[level] is None:
            continue
        if level in {"xhigh", "max"} and level not in thinking_map:
            continue
        levels.append(level)
    return tuple(levels) or ("off",)


def _pi_model_from_json(raw_model: Any) -> PiModel | None:
    if not isinstance(raw_model, dict):
        return None
    provider = str(raw_model.get("provider") or "").strip()
    model_id = str(raw_model.get("id") or "").strip()
    if not provider or not model_id:
        return None
    name = str(raw_model.get("name") or model_id).strip() or model_id
    return PiModel(
        provider=provider,
        model_id=model_id,
        name=name,
        supported_thinking_levels=_supported_thinking_levels(raw_model),
    )


def _pi_discovery_command(pi_command: Sequence[str]) -> list[str]:
    base_command = [str(arg) for arg in pi_command if str(arg)]
    if not base_command:
        raise PiRuntimeError("PI command is empty.")

    normalized: list[str] = []
    index = 0
    while index < len(base_command):
        arg = base_command[index]
        if index > 0 and arg == "--mode":
            mode = base_command[index + 1] if index + 1 < len(base_command) else ""
            if mode.strip().casefold() == "text":
                index += 2
                continue
        if (
            index > 0
            and arg.startswith("--mode=")
            and arg.split("=", 1)[1].strip().casefold() == "text"
        ):
            index += 1
            continue
        normalized.append(arg)
        index += 1

    return [
        *normalized,
        "--mode",
        "rpc",
        "--offline",
        "--no-session",
        "--approve",
        "--no-tools",
        "--no-skills",
        "--no-extensions",
        "--no-prompt-templates",
        "--no-themes",
        "--no-context-files",
    ]


def _pi_process_environment(command: Sequence[str]) -> dict[str, str]:
    env = os.environ.copy()
    if not command:
        return env
    executable = Path(command[0]).expanduser()
    if executable.is_absolute():
        env["PATH"] = str(executable.parent) + os.pathsep + env.get("PATH", "")
    return env


def _pi_rpc_response(
    command: list[str],
    request: dict[str, Any],
    *,
    timeout: float,
    environment: dict[str, str] | None = None,
) -> dict[str, Any]:
    from .pi_rpc import response
    try:
        return response(command, request, timeout=timeout,
                        environment=environment if environment is not None else _pi_process_environment(command))
    except (OSError, ValueError, RuntimeError, subprocess.SubprocessError) as exc:
        raise PiRuntimeError(f"PI model query failed: {exc}") from exc


def available_pi_models(
    pi_command: Sequence[str],
    *,
    timeout: float = PI_MODEL_DISCOVERY_TIMEOUT_SECONDS,
    environment: dict[str, str] | None = None,
) -> list[PiModel]:
    command = _pi_discovery_command(pi_command)
    response = _pi_rpc_response(
        command,
        {"type": "get_available_models"},
        timeout=timeout,
        **({"environment": environment} if environment is not None else {}),
    )
    if response.get("success") is not True:
        error = str(response.get("error") or "unknown RPC error").strip()
        raise PiRuntimeError(f"PI could not list available models: {error}")

    data = response.get("data")
    raw_models = data.get("models") if isinstance(data, dict) else None
    if not isinstance(raw_models, list):
        raise PiRuntimeError("PI returned an invalid available-model response.")

    models: dict[tuple[str, str], PiModel] = {}
    for raw_model in raw_models:
        model = _pi_model_from_json(raw_model)
        if model is None:
            continue
        models[model.settings_key] = model

    return sorted(
        models.values(),
        key=lambda model: (
            model.provider.casefold(),
            model.name.casefold(),
            model.model_id.casefold(),
        ),
    )


def _read_pi_settings(path: Path) -> dict[str, Any]:
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise PiSettingsError(f"PI project settings not found: {path}") from exc
    except (OSError, json.JSONDecodeError) as exc:
        raise PiSettingsError(f"Unable to read PI project settings: {exc}") from exc
    if not isinstance(raw, dict):
        raise PiSettingsError("PI project settings must contain a JSON object.")
    return raw


def _write_private_settings_temp(path: Path, settings: dict[str, Any]) -> None:
    """Write a complete private JSON file for atomic publication."""
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as output:
        json.dump(settings, output, ensure_ascii=True, indent=2)
        output.write("\n")


def ensure_project_pi_settings(
    path: Path = PROJECT_PI_SETTINGS_PATH,
) -> None:
    """Seed missing local settings without replacing a concurrent user file."""
    if path.exists() or path.is_symlink():
        return
    temp_path: Path | None = None
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        temp_path = path.with_name(f".{path.name}.{uuid.uuid4().hex}.tmp")
        _write_private_settings_temp(temp_path, DEFAULT_PROJECT_PI_SETTINGS)
        try:
            os.link(temp_path, path)
        except FileExistsError:
            # Another writer (or a dangling symlink) won the race.
            pass
    except OSError as exc:
        raise PiSettingsError(f"Unable to create PI project settings: {exc}") from exc
    finally:
        if temp_path is not None:
            temp_path.unlink(missing_ok=True)


def current_project_pi_model(
    path: Path = PROJECT_PI_SETTINGS_PATH,
) -> tuple[str, str] | None:
    settings = _read_pi_settings(path)
    provider = str(settings.get("defaultProvider") or "").strip()
    model_id = str(settings.get("defaultModel") or "").strip()
    if not provider or not model_id:
        return None
    return provider, model_id


def current_project_pi_thinking_level(
    path: Path = PROJECT_PI_SETTINGS_PATH,
) -> str | None:
    settings = _read_pi_settings(path)
    level = str(settings.get("defaultThinkingLevel") or "").strip().lower()
    return level if level in PI_THINKING_LEVELS else None


def save_project_pi_runtime(
    model: PiModel,
    thinking_level: str,
    path: Path = PROJECT_PI_SETTINGS_PATH,
) -> None:
    normalized_thinking = thinking_level.strip().lower()
    if normalized_thinking not in PI_THINKING_LEVELS:
        raise PiSettingsError(f"Unsupported PI reasoning effort: {thinking_level}")
    ensure_project_pi_settings(path)
    if path.is_symlink():
        raise PiSettingsError("PI project settings is a symlink; refusing to replace it.")
    settings = _read_pi_settings(path)
    settings["defaultProvider"] = model.provider
    settings["defaultModel"] = model.model_id
    settings["defaultThinkingLevel"] = normalized_thinking
    settings.pop("fireworksPriorityServiceTier", None)
    temp_path = path.with_name(f".{path.name}.{uuid.uuid4().hex}.tmp")
    try:
        _write_private_settings_temp(temp_path, settings)
        os.replace(temp_path, path)
    except OSError as exc:
        raise PiSettingsError(f"Unable to save PI project settings: {exc}") from exc
    finally:
        temp_path.unlink(missing_ok=True)


def save_project_pi_model(
    model: PiModel,
    path: Path = PROJECT_PI_SETTINGS_PATH,
) -> None:
    thinking_level = current_project_pi_thinking_level(path) or "medium"
    save_project_pi_runtime(model, thinking_level, path)
