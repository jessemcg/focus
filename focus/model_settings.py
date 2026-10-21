"""Focus-owned import-light model settings endpoint."""
from ._model_store import serve
from ._model_schema import pi_slot

def resolve():
    from .paths import pi_settings_file
    paths={'pi':pi_settings_file()}
    return paths,[pi_slot(paths)]

def main(): return serve('focus',resolve)
