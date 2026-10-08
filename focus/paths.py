"""GTK-independent configuration and embedded-resource locations.

No migration: an existing checkout-local configuration remains authoritative unless
an explicit standalone launcher override selects XDG storage.
"""
from __future__ import annotations

import os
from pathlib import Path

PROJECT_DIR = Path(__file__).resolve().parent.parent
AGENT_RESOURCES = Path(__file__).resolve().parent / "agent_resources"


def config_dir() -> Path:
    override = os.environ.get("FOCUS_CONFIG_DIR")
    if override:
        path = Path(override).expanduser()
        if not path.is_absolute():
            raise ValueError("FOCUS_CONFIG_DIR must be absolute")
        return path
    if (PROJECT_DIR / "config.json").exists() or (PROJECT_DIR / ".pi/settings.json").exists():
        return PROJECT_DIR
    return Path(os.environ.get("XDG_CONFIG_HOME", str(Path.home() / ".config"))) / "focus"


def config_file() -> Path:
    return config_dir() / "config.json"


def pi_settings_file() -> Path:
    root = config_dir()
    return root / ".pi/settings.json" if root == PROJECT_DIR else root / "pi/settings.json"


def verification_file() -> Path:
    return config_dir() / "pi-verification.json"
