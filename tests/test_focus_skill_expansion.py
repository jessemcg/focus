"""Canonical explicit skill expansion using the installed offline SDK only."""
import os
from pathlib import Path
import shutil
import subprocess

import pytest

PROJECT = Path(__file__).resolve().parents[1]


def test_canonical_skill_expands_without_read_advertisement_and_survives_followup(tmp_path):
    node = shutil.which("node")
    if not node:
        pytest.skip("Installed Pi SDK/Node required")
    sdk = Path(os.environ.get("PI_METRICS_TEST_SDK", Path(node).resolve().parent / "../lib/node_modules/@earendil-works/pi-coding-agent"))
    if not (sdk / "dist/index.js").is_file():
        pytest.skip("Installed Pi SDK required (no sibling metrics dependency)")
    env = {key: os.environ[key] for key in ("PATH", "PI_METRICS_TEST_SDK") if key in os.environ}
    for key in ("HOME", "XDG_CONFIG_HOME", "XDG_CACHE_HOME", "XDG_DATA_HOME", "XDG_STATE_HOME", "XDG_RUNTIME_DIR", "TMPDIR"):
        path = tmp_path / key.lower()
        path.mkdir(mode=0o700)
        env[key] = str(path)
    result = subprocess.run([node, str(PROJECT / "tests/focus_skill_expansion.mjs")], cwd=PROJECT,
                            env=dict(env, FOCUS_CONTRACT_ROOT=str(tmp_path)),
                            capture_output=True, text=True, timeout=45)
    assert result.returncode == 0, result.stdout + result.stderr
