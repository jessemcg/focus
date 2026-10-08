import sys
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


@pytest.fixture(autouse=True)
def isolated_app_config(monkeypatch, tmp_path):
    """Tests must never load/migrate the user's real application settings."""
    import focus.core as core
    monkeypatch.setattr(core, "CONFIG_FILE", tmp_path / "config.json")
    import focus.setup_pi as setup_pi
    monkeypatch.setattr(setup_pi, "config_file", lambda: core.CONFIG_FILE)
    monkeypatch.setattr(setup_pi, "pi_settings_file", lambda: tmp_path / "focus-settings/pi/settings.json")
    monkeypatch.setattr(setup_pi, "verification_file", lambda: tmp_path / "pi-verification.json")
