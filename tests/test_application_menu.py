"""Exercise the real hamburger menu in an isolated synthetic GTK process."""
import os
from pathlib import Path
import subprocess
import sys

import pytest


@pytest.mark.skipif(not (os.environ.get("DISPLAY") or os.environ.get("WAYLAND_DISPLAY")),
                    reason="GTK menu acceptance needs a local display")
def test_hamburger_opens_and_settings_item_activates():
    project = Path(__file__).resolve().parents[1]
    result = subprocess.run(
        [sys.executable, str(project / "tests/acceptance_neutral_method_ui.py")],
        cwd=project,
        env=dict(os.environ, G_DEBUG="fatal-criticals", FOCUS_NEUTRAL_HOLD_MS="0"),
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert "ACTUAL GTK NEUTRAL ACCEPTANCE PASSED" in result.stdout
    assert "Traceback" not in result.stderr
