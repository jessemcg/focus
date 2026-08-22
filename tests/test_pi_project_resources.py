from __future__ import annotations

import json
from pathlib import Path

from focus.app import Focus
from focus.core import (
    FOCUS_PI_PROJECT_DIR,
    FOCUS_PI_SKILL_FILE,
    FOCUS_PI_SKILL_NAME,
    FOCUS_PI_SYSTEM_PROMPT_FILE,
)


PROJECT_ROOT = Path(__file__).resolve().parents[1]
EXTENSION = FOCUS_PI_PROJECT_DIR / "extensions" / "focus-record-agent.ts"


def test_pi_project_settings_preserve_pro_low_and_disable_compaction() -> None:
    settings = json.loads((FOCUS_PI_PROJECT_DIR / "settings.json").read_text())

    assert settings["defaultProvider"] == "fireworks"
    assert settings["defaultModel"] == "accounts/fireworks/models/deepseek-v4-pro-0813"
    assert settings["defaultThinkingLevel"] == "low"
    assert settings["compaction"] == {"enabled": False}
    assert settings["retry"] == {"enabled": True}
    assert settings["enableSkillCommands"] is True
    assert not any("key" in name.casefold() for name in settings)


def test_pi_system_prompt_is_short_and_delegates_to_canonical_skill() -> None:
    prompt = FOCUS_PI_SYSTEM_PROMPT_FILE.read_text(encoding="utf-8")

    assert "read-only appellate-record investigator" in prompt
    assert "not a coding assistant" in prompt
    assert "FOCUS_AGENT_CASE_ROOT" in prompt
    assert "explicitly loaded `focus-answer-record-questions` skill" in prompt
    assert "Never modify the case bundle" in prompt
    assert "page images" in prompt
    assert "two-to-five-word" not in prompt
    assert "resolved_text_path" not in prompt


def test_pi_record_skill_has_bounded_stop_first_workflow_and_soft_style() -> None:
    skill = FOCUS_PI_SKILL_FILE.read_text(encoding="utf-8")

    assert skill.startswith(f"---\nname: {FOCUS_PI_SKILL_NAME}\n")
    assert "action `context` once" in skill
    assert "only for orientation and search planning" in skill
    assert "one `focus_record` action `search`" in skill
    assert "Cover every distinct part" in skill
    assert "full date in at least one event-cause query" in skill
    assert "diversified by query" in skill
    assert "prefer contemporaneous orders" in skill
    assert "historical allegation or later summary alone" in skill
    assert "Run at most one follow-up `search`" in skill
    assert "no corpus-wide grep tool" in skill
    assert "Never mention, quote, or rely on the overview" in skill
    assert "submit_focus_answer" in skill
    assert "first substantively useful answer" in skill
    assert "Do not spend another search or model turn merely to polish" in skill
    assert "two-to-five-word record quote" in skill
    assert "not an acceptance gate" in skill
    assert "Substantive usefulness" in skill
    assert "Q/A formatting alone does not establish testimony" in skill
    assert "Never modify case files" in skill
    assert "page images" in skill
    assert "agent_helper.py" not in skill
    assert "```bash" not in skill


def test_focus_extension_is_shell_free_budgeted_and_terminating() -> None:
    source = EXTENSION.read_text(encoding="utf-8")

    assert 'name: "focus_record"' in source
    assert 'name: "submit_focus_answer"' in source
    assert '"context", "search", "lookup"' in source
    assert "query_groups" not in source
    assert 'args.push("research")' not in source
    assert "pi.exec(python, args" in source
    assert "child_process" not in source
    assert "exec(" not in source.replace("pi.exec(", "")
    assert "OUTPUT_TOKEN_CAP = 8192" in source
    assert "SEARCH_HARD_LIMIT = 6" in source
    assert "PAGE_HARD_LIMIT = 24" in source
    assert 'event.toolName === "grep"' not in source
    assert "MAP_HARD_LIMIT = 1" in source
    assert "terminate: true" in source
    assert 'if (stopReason === "toolUse") return;' in source
    assert 'capture: "assistant_fallback"' in source
    assert 'pi.on("agent_settled"' in source
    assert "sendUserMessage" not in source
    assert "sendMessage" not in source
    assert "writeFile(temporary" in source
    assert "mode: 0o600" in source


def test_agent_prompt_contains_only_the_users_question() -> None:
    prompt = Focus._compose_agent_prompt("  Who made the finding at CT 67?  ")

    assert prompt == (
        f"/skill:{FOCUS_PI_SKILL_NAME} <question>\n"
        "Who made the finding at CT 67?\n"
        "</question>"
    )
    assert "current-focus-citation" not in prompt
    assert str(PROJECT_ROOT) not in prompt
