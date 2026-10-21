"""Validate user overrides and stage private workflow settings; never seed a user file."""
import importlib.util
from pathlib import Path
import sys

root = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("focus_model_store", root / "focus/_model_store.py")
store = importlib.util.module_from_spec(spec)
spec.loader.exec_module(store)
try:
    settings = store.read_ordinary(Path(sys.argv[1]))
except FileNotFoundError:
    settings = {}
# /skill: is required by Focus's fixed workflow, irrespective of global UI policy.
settings["enableSkillCommands"] = True
store.save_ordinary(Path(sys.argv[2]), dict(settings))
