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
  if [[ -f .pi/settings.json ]]; then
    printf 'settings=staged\\n'
    if grep -q '"defaultModel":"test-model"' .pi/settings.json; then
      printf 'model=staged\\n'
    fi
    if grep -q '"defaultThinkingLevel":"medium"' .pi/settings.json; then
      printf 'thinking=staged\\n'
    fi
  fi
  if [[ -s .pi/SYSTEM.md ]]; then
    printf 'system=staged\n'
  fi
  if [[ -f .pi/skills/focus-answer-record-questions/SKILL.md ]]; then
    printf 'skill=staged\\n'
  fi
} > "$FOCUS_TEST_OUTPUT"
""",
        encoding="utf-8",
    )
    executable.chmod(0o755)
    return executable


def _run_wrapper(tmp_path: Path) -> tuple[list[str], Path, Path]:
    case_root = tmp_path / "case"
    case_root.mkdir()
    workspace = tmp_path / "workspace"
    prompt_path = tmp_path / "prompt.txt"
    prompt_path.write_text("Exact Focus prompt\nwith a second line.", encoding="utf-8")
    output_path = tmp_path / "agent-output.txt"
    pi_project_dir = tmp_path / "pi-project"
    skill_dir = (
        pi_project_dir
        / "skills"
        / "focus-answer-record-questions"
    )
    skill_dir.mkdir(parents=True)
    (pi_project_dir / "settings.json").write_text(
        '{"defaultProvider":"fireworks","defaultModel":"test-model",'
        '"defaultThinkingLevel":"medium"}',
        encoding="utf-8",
    )
    (pi_project_dir / "SYSTEM.md").write_text(
        "Focus record knowledge work", encoding="utf-8"
    )
    (skill_dir / "SKILL.md").write_text(
        "---\nname: focus-answer-record-questions\ndescription: Test skill.\n---\n",
        encoding="utf-8",
    )
    executable = _fake_agent(tmp_path)
    env = os.environ.copy()
    env.update(
        {
            "XDG_CACHE_HOME": str(tmp_path / "cache"),
            "FOCUS_AGENT_PROMPT_FILE": str(prompt_path),
            "FOCUS_AGENT_CASE_ROOT": str(case_root),
            "FOCUS_AGENT_WORKSPACE": str(workspace),
            "FOCUS_PI_PROJECT_DIR": str(pi_project_dir),
            "FOCUS_AGENT_COMMAND_ARGC": "1",
            "FOCUS_AGENT_COMMAND_ARG_0": str(executable),
            "FOCUS_TEST_OUTPUT": str(output_path),
        }
    )
    subprocess.run(["bash", str(WRAPPER)], check=True, env=env)
    return output_path.read_text(encoding="utf-8").splitlines(), workspace, prompt_path


def test_pi_wrapper_passes_exact_prompt_in_interactive_mode(tmp_path) -> None:
    output, workspace, prompt_path = _run_wrapper(tmp_path)

    assert output == [
        f"cwd={workspace}",
        "arg=--approve",
        "arg=--no-extensions",
        "arg=--no-skills",
        "arg=--no-prompt-templates",
        "arg=--no-themes",
        "arg=--no-context-files",
        "arg=--system-prompt",
        f"arg={workspace}/.pi/SYSTEM.md",
        "arg=--skill",
        f"arg={workspace}/.pi/skills/focus-answer-record-questions/SKILL.md",
        "arg=--tools",
        "arg=read,bash,grep,find,ls",
        "arg=Exact Focus prompt",
        "with a second line.",
        "settings=staged",
        "model=staged",
        "thinking=staged",
        "system=staged",
        "skill=staged",
    ]
    assert not workspace.exists()
    assert not prompt_path.exists()


def test_pi_wrapper_rejects_missing_system_prompt(tmp_path) -> None:
    case_root = tmp_path / "case"
    case_root.mkdir()
    prompt_path = tmp_path / "prompt.txt"
    prompt_path.write_text("Question", encoding="utf-8")
    pi_project_dir = tmp_path / "pi-project"
    pi_project_dir.mkdir()
    (pi_project_dir / "settings.json").write_text("{}", encoding="utf-8")
    env = os.environ.copy()
    env.update(
        {
            "XDG_CACHE_HOME": str(tmp_path / "cache"),
            "FOCUS_AGENT_PROMPT_FILE": str(prompt_path),
            "FOCUS_AGENT_CASE_ROOT": str(case_root),
            "FOCUS_PI_PROJECT_DIR": str(pi_project_dir),
        }
    )

    completed = subprocess.run(
        ["bash", str(WRAPPER)], check=False, env=env, text=True, capture_output=True
    )

    assert completed.returncode == 2
    assert "Focus PI system prompt not found or empty" in completed.stderr


def test_pi_wrapper_rejects_missing_project_resources(tmp_path) -> None:
    case_root = tmp_path / "case"
    case_root.mkdir()
    prompt_path = tmp_path / "prompt.txt"
    prompt_path.write_text("Question", encoding="utf-8")
    env = os.environ.copy()
    env.update(
        {
            "XDG_CACHE_HOME": str(tmp_path / "cache"),
            "FOCUS_AGENT_PROMPT_FILE": str(prompt_path),
            "FOCUS_AGENT_CASE_ROOT": str(case_root),
            "FOCUS_PI_PROJECT_DIR": str(tmp_path / "missing"),
        }
    )

    completed = subprocess.run(
        ["bash", str(WRAPPER)],
        check=False,
        env=env,
        text=True,
        capture_output=True,
    )

    assert completed.returncode == 2
    assert "Focus PI project settings not found" in completed.stderr
    assert not prompt_path.exists()
