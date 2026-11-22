"""Focus-owned import-light model settings endpoint."""
from ._model_store import Failure, serve
from ._model_schema import pi_slot, slot
from .paths import pi_settings_file
from .research_skills import preferences_path, read_preferences


def resolve():
    paths = {"pi": pi_settings_file(), "research-skills": preferences_path()}
    preferences, _ = read_preferences(paths["research-skills"])
    try:
        slots = [pi_slot(paths)]
    except Failure as exc:
        if str(exc) != "missing_effective_model" or preferences.model_key is None:
            raise
        # A named skill choice is still maintainable when ordinary Pi has
        # no named default (its runtime may choose an authenticated model).
        slots = [{"role": "pi", "inactive": True, "public": {
            "slot_id": "shared-pi", "status": "unconfigured", "reason": "no_named_model_selection",
        }}]
    if preferences.model_key is not None:
        provider, model = preferences.model_key

        def replace(data, target):
            data.update(provider=target["provider"], model=target["model"])

        slots.append(slot("research-skills", "research-skills", {"provider": provider, "model": model},
                          {"requested": preferences.effort or "inherit"}, replace))
    return paths, slots

def main(): return serve('focus',resolve)
