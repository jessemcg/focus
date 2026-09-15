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
