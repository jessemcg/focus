"""Configuration reads are inert; only explicit Settings saves retire keys."""
import ast
import json
from pathlib import Path
from unittest.mock import Mock

from focus import core


def synthetic_config():
    return {
        **{key: "obsolete sentinel" for key in core.OBSOLETE_SEARCH_CONFIG_KEYS},
        **{key: "retired sentinel" for key in core.RETIRED_SUMMARIZATION_CONFIG_KEYS},
        "summary_read_positions": {"old": 0.5},
        "summary_file": "old-summary.txt",
        "page_kimi_reasoning": True,
        "page_deepseek_reasoning": True,
        "range_kimi_reasoning": True,
        "range_deepseek_reasoning": True,
        "unknown_future_key": {"preserve": True},
        core.CONFIG_KEY_SPEECH_AGENT_SOURCE_FILE: "/tmp/synthetic-speech.txt",
        core.CONFIG_KEY_PI_AGENT_COMMAND: "/usr/bin/true",
        core.CONFIG_KEY_HIGHLIGHT_PHRASES: ["motion denied"],
        core.CONFIG_KEY_GREP_HIGHLIGHT_COLOR: "#112233",
        core.CONFIG_KEY_PHRASE_HIGHLIGHT_COLOR: "#223344",
        "summary_emphasis_color": "#334455",  # Retired; preserve stored bytes, never use.
        core.CONFIG_KEY_SEARCH_CHIP_COLOR: "#445566",
    }


def test_load_supported_settings_never_writes_or_changes_bytes(monkeypatch):
    config = synthetic_config()
    original = (json.dumps(config, indent=3) + "\n\n").encode()
    core.CONFIG_FILE.write_bytes(original)
    writer = Mock(side_effect=AssertionError("A read must not write config"))
    monkeypatch.setattr(core, "_write_config", writer)
    for _ in range(2):
        settings = core.load_ai_settings()
        assert settings.speech_agent_source_file == "/tmp/synthetic-speech.txt"
        assert settings.pi_agent_command == "/usr/bin/true"
        assert settings.highlight_phrases == ["motion denied"]
        assert settings.grep_highlight_color == "#112233"
        assert settings.phrase_highlight_color == "#223344"
        assert not hasattr(settings, "summary_emphasis_color")
        assert settings.search_chip_color == "#445566"
        assert core.CONFIG_FILE.read_bytes() == original
    writer.assert_not_called()


def test_startup_has_no_deprecated_cleanup_hook():
    assert not hasattr(core, "prune_deprecated_summary_bookmarking_config")
    app_source = (Path(core.__file__).parent / "app.py").read_text()
    tree = ast.parse(app_source)
    assert not any(isinstance(node, ast.Name)
                   and node.id == "prune_deprecated_summary_bookmarking_config"
                   for node in ast.walk(tree))


def test_explicit_settings_save_preserves_established_cleanup():
    config = synthetic_config()
    core.CONFIG_FILE.write_text(json.dumps(config))
    settings = core.load_ai_settings()
    settings.pi_agent_command = " /usr/bin/false "
    core.save_ai_settings(settings)
    saved = json.loads(core.CONFIG_FILE.read_text())
    removed = core.OBSOLETE_SEARCH_CONFIG_KEYS | core.RETIRED_SUMMARIZATION_CONFIG_KEYS
    assert not removed.intersection(saved)
    for key, value in config.items():
        if key not in removed and key != core.CONFIG_KEY_PI_AGENT_COMMAND:
            assert saved[key] == value
    assert saved[core.CONFIG_KEY_PI_AGENT_COMMAND] == "/usr/bin/false"
