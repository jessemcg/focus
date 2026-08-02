from __future__ import annotations

import json
from pathlib import Path
import shutil
import subprocess

import pytest


PROJECT_ROOT = Path(__file__).resolve().parents[1]
EXTENSION = PROJECT_ROOT / ".pi" / "extensions" / "fireworks-priority.js"
NODE = shutil.which("node")


def _run_hook(
    tmp_path: Path,
    *,
    enabled: bool,
    provider: str,
    model_id: str,
) -> dict[str, object]:
    pi_dir = tmp_path / ".pi"
    pi_dir.mkdir()
    (pi_dir / "settings.json").write_text(
        json.dumps({"fireworksPriorityServiceTier": enabled}),
        encoding="utf-8",
    )
    (pi_dir / "fireworks-priority-models.json").write_text(
        json.dumps(
            {"models": ["accounts/fireworks/models/deepseek-v4-flash-0731"]}
        ),
        encoding="utf-8",
    )
    script = """
const extension = require(process.argv[1]);
let handler;
extension({on: (event, callback) => {
  if (event === "before_provider_request") handler = callback;
}});
const payload = {model: process.argv[5], messages: []};
Promise.resolve(handler(
  {type: "before_provider_request", payload},
  {cwd: process.argv[2], model: {provider: process.argv[3], id: process.argv[4]}},
)).then((result) => console.log(JSON.stringify(result ?? payload)));
"""
    completed = subprocess.run(
        [
            NODE or "node",
            "-e",
            script,
            str(EXTENSION),
            str(tmp_path),
            provider,
            model_id,
            model_id,
        ],
        check=True,
        text=True,
        capture_output=True,
    )
    return json.loads(completed.stdout)


@pytest.mark.skipif(NODE is None, reason="Node.js is unavailable")
def test_priority_hook_injects_service_tier_for_enabled_allowlisted_model(
    tmp_path: Path,
) -> None:
    payload = _run_hook(
        tmp_path,
        enabled=True,
        provider="fireworks",
        model_id="accounts/fireworks/models/deepseek-v4-flash-0731",
    )

    assert payload["service_tier"] == "priority"


@pytest.mark.skipif(NODE is None, reason="Node.js is unavailable")
@pytest.mark.parametrize(
    ("enabled", "provider", "model_id"),
    [
        (
            False,
            "fireworks",
            "accounts/fireworks/models/deepseek-v4-flash-0731",
        ),
        (
            True,
            "fireworks",
            "accounts/fireworks/routers/deepseek-v4-flash-fast",
        ),
        (
            True,
            "openai-codex",
            "accounts/fireworks/models/deepseek-v4-flash-0731",
        ),
    ],
)
def test_priority_hook_leaves_ineligible_requests_unchanged(
    tmp_path: Path,
    enabled: bool,
    provider: str,
    model_id: str,
) -> None:
    payload = _run_hook(
        tmp_path,
        enabled=enabled,
        provider=provider,
        model_id=model_id,
    )

    assert "service_tier" not in payload
