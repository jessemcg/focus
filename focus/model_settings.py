"""Focus-owned import-light model settings endpoint."""
from ._model_store import serve
from ._model_schema import pi_slot

def resolve():
    from .paths import pi_settings_file
    paths={'pi':pi_settings_file()}
    from .pi_runtime import DEFAULT_PROJECT_PI_SETTINGS
    return paths,[pi_slot(paths,seed_if_missing=DEFAULT_PROJECT_PI_SETTINGS)]

def main(): return serve('focus',resolve)
