from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

import focus.app as focus_app
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


class PromptHarness:
    def __init__(self, citation_label: str | None) -> None:
        self.label = (
            SimpleNamespace(citation_label=citation_label)
            if citation_label is not None
            else None
        )

    def _current_transcript_page_label(self):
        return self.label


class FakeToggleButton:
    def __init__(self, active: bool = False) -> None:
        self.active = active
        self.sensitive = True
        self.tooltip = ""
        self.description = ""

    def get_active(self) -> bool:
        return self.active

    def set_active(self, active: bool) -> None:
        self.active = active

    def set_sensitive(self, sensitive: bool) -> None:
        self.sensitive = sensitive

    def set_tooltip_text(self, tooltip: str) -> None:
        self.tooltip = tooltip

    def update_property(self, _properties, values) -> None:
        self.description = values[0]


class LaunchHarness(PromptHarness):
    def __init__(self, *, scheduled: bool) -> None:
        super().__init__("CT 67")
        self._agent_terminal = object()
        self._agent_question_entry = SimpleNamespace(
            get_text=lambda: "What happened on this page?"
        )
        self._agent_page_context_button = FakeToggleButton(active=True)
        self._agent_terminal_active = False
        self._view_state = SimpleNamespace(agent_question_text="")
        self.scheduled = scheduled
        self.prompt = ""

    def _stop_agent_terminal(self) -> None:
        self._agent_terminal_active = False

    def _stop_agent_answer_polling(self) -> None:
        pass

    def _clear_agent_answer(self) -> None:
        pass

    def _set_agent_subview(self, _name: str) -> None:
        pass

    def _current_view_state(self):
        return self._view_state

    def _compose_agent_prompt(self, question: str, *, include_current_page: bool = False):
        return Focus._compose_agent_prompt(
            self,
            question,
            include_current_page=include_current_page,
        )

    def _write_agent_prompt_file(self, prompt: str) -> Path:
        self.prompt = prompt
        return Path("/tmp/focus-agent-test-prompt.txt")

    def _start_agent_terminal(self, _prompt_path: Path) -> None:
        self._agent_terminal_active = self.scheduled

    def _ai_transient_toast(self, _message: str) -> None:
        pass


def test_pi_project_settings_select_model_without_credentials() -> None:
    settings = json.loads((FOCUS_PI_PROJECT_DIR / "settings.json").read_text())

    assert isinstance(settings.get("defaultProvider"), str)
    assert settings.get("defaultProvider")
    assert isinstance(settings.get("defaultModel"), str)
    assert settings.get("defaultModel")
    assert settings.get("defaultThinkingLevel") == "medium"
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
    assert "question is case-wide" in prompt
    assert "safe `resolved_text_path`" in prompt


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
    assert "not a filtering scope" in skill
    assert "no redundant `lookup` is needed" in skill
    assert "safe `resolved_text_path` directly" in skill
    assert "cache, or database" in skill
    assert "Q/A formatting alone does not establish testimony" in skill
    assert "Do not use web research, RAG, vector" in skill
    assert "Never expose local paths" in skill
    assert "checkboxes, signatures, initials, handwriting" in skill
    assert "`resolved_image_path` directly to PI's `read`" in skill
    assert "current model does not support images" in skill
    assert "sentinel key containing `:missing:`" in skill
    assert "Never invent a record citation" in skill
    assert "(RT 6, 34; CT 140, 190.)" in skill


def test_agent_prompt_omits_resolved_current_page_by_default() -> None:
    harness = PromptHarness("2RT 44")

    prompt = Focus._compose_agent_prompt(harness, "  Who made the finding?  ")

    assert prompt == (
        f"/skill:{FOCUS_PI_SKILL_NAME} <question>\n"
        "Who made the finding?\n"
        "</question>"
    )
    assert "current-focus-citation" not in prompt
    assert str(PROJECT_ROOT) not in prompt


def test_agent_prompt_includes_explicit_current_page() -> None:
    harness = PromptHarness("2RT 44")

    prompt = Focus._compose_agent_prompt(
        harness,
        "Who made the finding?",
        include_current_page=True,
    )

    assert prompt.endswith(
        "<current-focus-citation>\n"
        "2RT 44\n"
        "</current-focus-citation>"
    )


def test_agent_prompt_omits_unresolved_explicit_current_page() -> None:
    harness = PromptHarness(None)

    prompt = Focus._compose_agent_prompt(
        harness,
        "What happened?",
        include_current_page=True,
    )

    assert prompt == (
        f"/skill:{FOCUS_PI_SKILL_NAME} <question>\n"
        "What happened?\n"
        "</question>"
    )
    assert "file page" not in prompt


def test_agent_page_context_disables_and_resets_when_page_becomes_unresolved() -> None:
    harness = PromptHarness("CT 67")
    harness._agent_page_context_button = FakeToggleButton(active=True)

    Focus._sync_agent_page_context_button(harness)

    assert harness._agent_page_context_button.sensitive is True
    assert "CT 67" in harness._agent_page_context_button.tooltip
    assert "CT 67" in harness._agent_page_context_button.description

    harness.label = None
    Focus._sync_agent_page_context_button(harness)

    assert harness._agent_page_context_button.active is False
    assert harness._agent_page_context_button.sensitive is False


def test_agent_page_context_tracks_page_at_submission_time() -> None:
    harness = PromptHarness("CT 67")
    harness._agent_page_context_button = FakeToggleButton(active=True)
    harness.label = SimpleNamespace(citation_label="RT 2737")

    Focus._sync_agent_page_context_button(harness)
    prompt = Focus._compose_agent_prompt(
        harness,
        "Who is speaking?",
        include_current_page=harness._agent_page_context_button.get_active(),
    )

    assert harness._agent_page_context_button.active is True
    assert "RT 2737" in harness._agent_page_context_button.tooltip
    assert "<current-focus-citation>\nRT 2737" in prompt
    assert "CT 67" not in prompt


def test_agent_page_context_is_consumed_only_after_launch_is_scheduled(
    monkeypatch,
) -> None:
    monkeypatch.setattr(focus_app, "Vte", object())
    scheduled = LaunchHarness(scheduled=True)
    failed_preflight = LaunchHarness(scheduled=False)

    Focus._launch_agent_question(scheduled)
    Focus._launch_agent_question(failed_preflight)

    assert "<current-focus-citation>\nCT 67" in scheduled.prompt
    assert scheduled._agent_page_context_button.active is False
    assert "<current-focus-citation>\nCT 67" in failed_preflight.prompt
    assert failed_preflight._agent_page_context_button.active is True
