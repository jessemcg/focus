from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

from focus.app import Focus
from focus.core import FOCUS_PI_PROJECT_DIR, FOCUS_PI_SKILL_FILE, FOCUS_PI_SKILL_NAME


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


def test_pi_project_settings_pin_fireworks_model() -> None:
    settings = json.loads((FOCUS_PI_PROJECT_DIR / "settings.json").read_text())

    assert settings == {
        "defaultProvider": "fireworks",
        "defaultModel": "accounts/fireworks/routers/glm-5p2-fast",
        "enableSkillCommands": True,
    }
    assert not any("key" in name.casefold() for name in settings)


def test_pi_record_skill_has_expected_contract() -> None:
    skill = FOCUS_PI_SKILL_FILE.read_text(encoding="utf-8")

    assert skill.startswith(f"---\nname: {FOCUS_PI_SKILL_NAME}\n")
    assert "PI's `grep` tool, which is backed by ripgrep" in skill
    assert 'lookup --file "text_pages/0001.txt" --json' in skill
    assert "Do not use web research, RAG, vector" in skill
    assert "Never expose local paths" in skill
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
