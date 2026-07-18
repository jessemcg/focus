from __future__ import annotations

import os
from pathlib import Path
import subprocess


WRAPPER = Path(__file__).resolve().parents[1] / "scripts" / "focus-agent-vte.sh"


def _fake_agent(tmp_path: Path) -> Path:
    executable = tmp_path / "fake-agent"
    executable.write_text(
        """#!/usr/bin/env bash
set -euo pipefail
{
  printf 'cwd=%s\\n' "$PWD"
  printf 'arg=%s\\n' "$@"
} > "$FOCUS_TEST_OUTPUT"
""",
        encoding="utf-8",
    )
    executable.chmod(0o755)
    return executable


def _run_wrapper(tmp_path: Path, runtime: str) -> tuple[list[str], Path, Path]:
    case_root = tmp_path / "case"
    case_root.mkdir()
    workspace = tmp_path / "workspace"
    prompt_path = tmp_path / "prompt.txt"
    prompt_path.write_text("Exact Focus prompt\nwith a second line.", encoding="utf-8")
    output_path = tmp_path / "agent-output.txt"
    executable = _fake_agent(tmp_path)
    env = os.environ.copy()
    env.update(
        {
            "XDG_CACHE_HOME": str(tmp_path / "cache"),
            "FOCUS_AGENT_RUNTIME": runtime,
            "FOCUS_AGENT_PROMPT_FILE": str(prompt_path),
            "FOCUS_AGENT_CASE_ROOT": str(case_root),
            "FOCUS_AGENT_WORKSPACE": str(workspace),
            "FOCUS_AGENT_COMMAND_ARGC": "1",
            "FOCUS_AGENT_COMMAND_ARG_0": str(executable),
            "FOCUS_TEST_OUTPUT": str(output_path),
        }
    )
    subprocess.run(["bash", str(WRAPPER)], check=True, env=env)
    return output_path.read_text(encoding="utf-8").splitlines(), workspace, prompt_path


def test_pi_wrapper_passes_exact_prompt_in_interactive_mode(tmp_path) -> None:
    output, workspace, prompt_path = _run_wrapper(tmp_path, "pi")

    assert output == [
        f"cwd={workspace}",
        "arg=Exact Focus prompt",
        "with a second line.",
    ]
    assert not workspace.exists()
    assert not prompt_path.exists()


def test_codex_wrapper_preserves_workspace_and_sandbox_arguments(tmp_path) -> None:
    output, workspace, prompt_path = _run_wrapper(tmp_path, "codex")

    assert output == [
        f"cwd={workspace}",
        "arg=-C",
        f"arg={workspace}",
        "arg=--sandbox",
        "arg=workspace-write",
        "arg=Exact Focus prompt",
        "with a second line.",
    ]
    assert not workspace.exists()
    assert not prompt_path.exists()
