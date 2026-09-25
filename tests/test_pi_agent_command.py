import focus.core as focus
from focus.core import (
    discover_pi_agent_command,
    incompatible_pi_agent_flag,
    resolve_pi_agent_argv,
)


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
    assert incompatible_pi_agent_flag(["pi", "--thinking", "high"]) == "--thinking"
    assert incompatible_pi_agent_flag(["pi", "--thinking=high"]) == "--thinking=high"
    assert incompatible_pi_agent_flag(["pi", "--tools", "read"]) == "--tools"
    assert incompatible_pi_agent_flag(["pi", "--no-skills"]) == "--no-skills"
    assert incompatible_pi_agent_flag(["pi", "--theme", "home.json"]) == "--theme"
    assert incompatible_pi_agent_flag(["pi", "--no-context-files"]) == "--no-context-files"
    assert incompatible_pi_agent_flag(["pi", "-nc"]) == "-nc"
    assert incompatible_pi_agent_flag(["pi", "--no-approve"]) == "--no-approve"
