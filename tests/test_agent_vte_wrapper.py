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
if [[ "${1:-}" == --version ]]; then printf '0.87.1\\n'; exit 0; fi
{
  printf 'cwd=%s\\n' "$PWD"
  printf 'metrics_root=%s\\n' "$PI_RUN_METRICS_ROOT"
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
  if [[ -n "${PI_CODING_AGENT_SESSION_DIR:-}" ]]; then
    printf 'session_dir=%s\\n' "$PI_CODING_AGENT_SESSION_DIR"
    printf '{"type":"session","cwd":"%s"}\\n' "$PWD" \
      > "$PI_CODING_AGENT_SESSION_DIR/session.jsonl"
  fi
} > "$FOCUS_TEST_OUTPUT"
""",
        encoding="utf-8",
    )
    executable.chmod(0o755)
    return executable


def _run_wrapper(
    tmp_path: Path,
    extra_env: dict[str, str] | None = None,
) -> tuple[list[str], Path, Path, subprocess.CompletedProcess[str]]:
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
    extension_dir = pi_project_dir / "extensions"
    extension_dir.mkdir(parents=True)
    (extension_dir / "focus-record-agent.ts").write_text(
        "// Focus test extension\n", encoding="utf-8"
    )
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
    answer_protocol = tmp_path / "agent_answer.py"
    answer_protocol.write_text("# test protocol\n", encoding="utf-8")
    runtime_dir = tmp_path / "runtime" / "focus" / "agent-answers"
    runtime_dir.mkdir(parents=True)
    executable = _fake_agent(tmp_path)
    env = os.environ.copy()
    for key in ("PI_RUN_METRICS_ROOT", "PI_RUN_METRICS_COLLECTOR", "PI_RUN_METRICS_ENABLED", "PI_CODING_AGENT_SESSION_DIR"):
        env.pop(key, None)
    env.update(
        {
            "XDG_CACHE_HOME": str(tmp_path / "cache"),
            "FOCUS_AGENT_PROMPT_FILE": str(prompt_path),
            "FOCUS_AGENT_CASE_ROOT": str(case_root),
            "FOCUS_AGENT_WORKSPACE": str(workspace),
            "FOCUS_AGENT_RUN_ID": "abcdefghijklmnopqrstuvwx",
            "FOCUS_AGENT_RUNTIME_DIR": str(runtime_dir),
            "FOCUS_AGENT_ANSWER_ARTIFACT": str(runtime_dir / "answer.json"),
            "FOCUS_AGENT_ANSWER_PROTOCOL": str(answer_protocol),
            "FOCUS_PI_PROJECT_DIR": str(pi_project_dir),
            "FOCUS_AGENT_COMMAND_ARGC": "1",
            "FOCUS_AGENT_COMMAND_ARG_0": str(executable),
            "FOCUS_TEST_OUTPUT": str(output_path),
        }
    )
    if extra_env:
        env.update(extra_env)
    completed = subprocess.run(
        ["bash", str(WRAPPER)], env=env, text=True, capture_output=True
    )
    output = (
        output_path.read_text(encoding="utf-8").splitlines()
        if output_path.exists()
        else []
    )
    return output, workspace, prompt_path, completed


def test_pi_wrapper_passes_exact_prompt_in_interactive_mode(tmp_path) -> None:
    output, workspace, prompt_path, completed = _run_wrapper(tmp_path, {"PI_RUN_METRICS_ENABLED": "0"})

    assert completed.returncode == 0
    assert output == [
        f"cwd={workspace}",
        f"metrics_root={WRAPPER.parents[1]}/.run-metrics/runs",
        "arg=--approve",
        "arg=--no-session",
        "arg=--no-extensions",
        "arg=--extension",
        f"arg={workspace}/.pi/extensions/focus-record-agent.ts",
        "arg=--no-skills",
        "arg=--no-prompt-templates",
        "arg=--no-themes",
        "arg=--no-context-files",
        "arg=--system-prompt",
        f"arg={workspace}/.pi/SYSTEM.md",
        "arg=--skill",
        f"arg={workspace}/.pi/skills/focus-answer-record-questions/SKILL.md",
        "arg=--tools",
        "arg=read,focus_record,submit_focus_answer",
        "arg=Exact Focus prompt",
        "with a second line.",
        "settings=staged",
        "model=staged",
        "thinking=staged",
        "system=staged",
        "skill=staged",
    ]
    assert output.count("arg=--extension") == 1
    assert "arg=--no-session" in output
    assert "arg=read,bash,grep,find,ls" not in output
    assert not workspace.exists()
    assert not prompt_path.exists()


def test_pi_wrapper_loads_shared_observer_without_changing_tools(tmp_path) -> None:
    collector = tmp_path / "collector.ts"
    collector.write_text("// synthetic observer\n")
    output, workspace, prompt_path, completed = _run_wrapper(
        tmp_path, {"PI_RUN_METRICS_COLLECTOR": str(collector)}
    )
    assert completed.returncode == 0
    assert output.count("arg=--extension") == 2
    assert f"arg={collector}" in output
    assert "arg=read,focus_record,submit_focus_answer" in output
    assert not any(line.startswith("session_dir=") for line in output)
    assert not workspace.exists()
    assert not prompt_path.exists()


def test_pi_wrapper_preserves_absolute_metrics_root_override(tmp_path) -> None:
    archive = tmp_path / "alternate archive" / "runs"
    output, _, _, completed = _run_wrapper(
        tmp_path, {"PI_RUN_METRICS_ROOT": str(archive)}
    )
    assert completed.returncode == 0
    assert f"metrics_root={archive}" in output


def test_project_metrics_are_git_ignored(tmp_path) -> None:
    subprocess.run(["git", "init", "-q", str(tmp_path)], check=True)
    (tmp_path / ".gitignore").write_text(
        (WRAPPER.parents[1] / ".gitignore").read_text(encoding="utf-8"), encoding="utf-8"
    )
    completed = subprocess.run(
        ["git", "check-ignore", "--no-index", ".run-metrics/runs/2099-01-01/test.jsonl"],
        cwd=tmp_path, text=True, capture_output=True,
    )
    assert completed.returncode == 0


def test_pi_wrapper_missing_observer_is_nonfatal(tmp_path) -> None:
    output, workspace, _, completed = _run_wrapper(
        tmp_path, {"PI_RUN_METRICS_COLLECTOR": "/nonexistent/collector.ts"}
    )
    assert completed.returncode == 0
    assert "collection incomplete or unavailable" in completed.stderr
    assert "arg=--no-session" in output
    assert not workspace.exists()


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
