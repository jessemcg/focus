from __future__ import annotations

import json
from pathlib import Path

from focus.app import Focus
from focus.core import (
    FOCUS_PI_PRIORITY_EXTENSION_FILE,
    FOCUS_PI_PRIORITY_MANIFEST_FILE,
    FOCUS_PI_PROJECT_DIR,
    FOCUS_PI_SKILL_FILE,
    FOCUS_PI_SKILL_NAME,
    FOCUS_PI_SYSTEM_PROMPT_FILE,
)


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def test_pi_project_settings_select_model_without_credentials() -> None:
    settings = json.loads((FOCUS_PI_PROJECT_DIR / "settings.json").read_text())

    assert isinstance(settings.get("defaultProvider"), str)
    assert settings.get("defaultProvider")
    assert isinstance(settings.get("defaultModel"), str)
    assert settings.get("defaultModel")
    assert settings.get("defaultThinkingLevel") in {
        "off",
        "minimal",
        "low",
        "medium",
        "high",
        "xhigh",
    }
    assert settings.get("fireworksPriorityServiceTier") is False
    assert settings.get("enableSkillCommands") is True
    assert settings.get("compaction") == {
        "enabled": True,
        "reserveTokens": 8192,
        "keepRecentTokens": 12000,
    }
    assert not any("key" in name.casefold() for name in settings)


def test_pi_system_prompt_has_focus_knowledge_work_contract() -> None:
    prompt = FOCUS_PI_SYSTEM_PROMPT_FILE.read_text(encoding="utf-8")

    assert "read-only appellate-record investigator" in prompt
    assert "not a coding assistant" in prompt
    assert "FOCUS_AGENT_CASE_ROOT" in prompt
    assert "private, disposable runtime workspace" in prompt
    assert "compact `context --json` response" in prompt
    assert "nonauthoritative orientation aid" in prompt
    assert "Questions are case-wide" in prompt
    assert "current-focus-citation" not in prompt
    assert "resolved_text_path" in prompt
    assert "Every substantive paragraph or list" in prompt
    assert "verbatim two-to-five-word record quote" in prompt
    assert "Never display that metadata in the final answer" in prompt
    assert "do not use bold text" in prompt
    assert "Never open or inspect page images" in prompt
    assert "Cite record labels" not in prompt


def test_pi_priority_resources_are_present_and_fail_closed() -> None:
    manifest = json.loads(
        FOCUS_PI_PRIORITY_MANIFEST_FILE.read_text(encoding="utf-8")
    )
    model_ids = manifest["models"]

    assert manifest["source"] == "https://docs.fireworks.ai/serverless/pricing"
    assert manifest["reviewed"] == "2026-08-02"
    assert "accounts/fireworks/models/deepseek-v4-flash-0731" in model_ids
    assert "accounts/fireworks/models/glm-5p2" in model_ids
    assert not any("/routers/" in model_id for model_id in model_ids)

    extension = FOCUS_PI_PRIORITY_EXTENSION_FILE.read_text(encoding="utf-8")
    assert 'pi.on("before_provider_request"' in extension
    assert 'service_tier: "priority"' in extension


def test_pi_record_skill_has_expected_contract() -> None:
    skill = FOCUS_PI_SKILL_FILE.read_text(encoding="utf-8")

    assert skill.startswith(f"---\nname: {FOCUS_PI_SKILL_NAME}\n")
    assert "Run `context --json` once" in skill
    assert "It cannot establish a" in skill
    assert "Run full `map --json` only when needed" in skill
    assert "initially returning at most eight matches" in skill
    assert "which is backed by ripgrep" in skill
    assert 'lookup --file "text_pages/0001.txt" --json' in skill
    assert 'search \\' in skill
    assert '--witness' in skill
    assert "--current-citation" not in skill
    assert "current-focus-citation" not in skill
    assert "no redundant `lookup` is needed" in skill
    assert "safe `resolved_text_path` directly" in skill
    assert "cache, or database" in skill
    assert "Q/A formatting alone does not establish testimony" in skill
    assert "Do not use web research, RAG, vector" in skill
    assert "High-priority final-answer contract" in skill
    assert "every substantive paragraph or list" in skill
    assert "exactly **two to five" in skill
    assert "continuous, verbatim phrase" in skill
    assert "Prefer distinctive" in skill
    assert "Place each quote next to the point it supports" in skill
    assert "Do not use bold text in the final answer" in skill
    assert "omit `citation_label`, `citation_range`, citation keys" in skill
    assert "Citation metadata is internal research" in skill
    assert "never print it in the final answer" in skill
    assert "Never open or inspect page images" in skill
    assert "cannot be determined" in skill
    assert "available text" in skill
    assert "separate two-to-five-word linked quote" in skill
    assert "no prohibited citation or research metadata remains" in skill
    assert "Group citations by exact label" not in skill
    assert "resolved_image_path" not in skill
    assert "current model does not support images" not in skill
    assert "(RT 6, 34; CT 140, 190.)" not in skill


def test_agent_prompt_contains_only_the_users_question() -> None:
    prompt = Focus._compose_agent_prompt("  Who made the finding at CT 67?  ")

    assert prompt == (
        f"/skill:{FOCUS_PI_SKILL_NAME} <question>\n"
        "Who made the finding at CT 67?\n"
        "</question>"
    )
    assert "current-focus-citation" not in prompt
    assert str(PROJECT_ROOT) not in prompt
