from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

from focus.app import Focus
from focus.core import (
    FOCUS_PI_PRIORITY_EXTENSION_FILE,
    FOCUS_PI_PRIORITY_MANIFEST_FILE,
    FOCUS_PI_PROJECT_DIR,
    FOCUS_PI_SKILL_FILE,
    FOCUS_PI_SKILL_NAME,
)


PROJECT_ROOT = Path(__file__).resolve().parents[1]


class PromptHarness:
    def __init__(self, citation_label: str | None) -> None:
        self.label = (
            SimpleNamespace(citation_label=citation_label)
            if citation_label is not None
            else None
        )

    def _current_transcript_page_label(self):
        return self.label


def test_pi_project_settings_select_model_without_credentials() -> None:
    settings = json.loads((FOCUS_PI_PROJECT_DIR / "settings.json").read_text())

    assert isinstance(settings.get("defaultProvider"), str)
    assert settings["defaultProvider"].strip()
    assert isinstance(settings.get("defaultModel"), str)
    assert settings["defaultModel"].strip()
    assert settings.get("defaultThinkingLevel") == "medium"
    assert settings.get("fireworksPriorityServiceTier") is True
    assert settings.get("enableSkillCommands") is True
    assert not any("key" in name.casefold() for name in settings)


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
    assert "PI's `grep` tool, which is backed by ripgrep" in skill
    assert 'lookup --file "text_pages/0001.txt" --json' in skill
    assert "Do not use web research, RAG, vector" in skill
    assert "Never expose local paths" in skill
    assert "checkboxes, signatures, initials, handwriting" in skill
    assert "`resolved_image_path` directly to PI's `read`" in skill
    assert "current model does not support images" in skill
    assert "claim is inherently visual" in skill
    assert "sentinel key containing `:missing:`" in skill
    assert "Never invent a record citation" in skill
    assert "(RT 6, 34; CT 140, 190.)" in skill


def test_agent_prompt_only_invokes_skill_with_question_and_citation() -> None:
    harness = PromptHarness("2RT 44")

    prompt = Focus._compose_agent_prompt(harness, "  Who made the finding?  ")

    assert prompt == (
        f"/skill:{FOCUS_PI_SKILL_NAME} <question>\n"
        "Who made the finding?\n"
        "</question>\n\n"
        "<current-focus-citation>\n"
        "2RT 44\n"
        "</current-focus-citation>"
    )
    assert str(PROJECT_ROOT) not in prompt


def test_agent_prompt_omits_unresolved_current_page() -> None:
    harness = PromptHarness(None)

    prompt = Focus._compose_agent_prompt(harness, "What happened?")

    assert prompt == (
        f"/skill:{FOCUS_PI_SKILL_NAME} <question>\n"
        "What happened?\n"
        "</question>"
    )
    assert "file page" not in prompt
