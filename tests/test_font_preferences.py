import json

import focus.core as core
from focus.core import (
    RECORD_FONT_FAMILY_OPTIONS,
    _normalize_record_font_family_name,
)


def test_default_non_table_record_font_is_schola() -> None:
    assert core.DEFAULT_RECORD_FONT_FAMILY_NAME == "TeX Gyre Schola"
    assert core.load_record_font_family_name() == "TeX Gyre Schola"
    assert core._record_font_css_for_name("").startswith('"TeX Gyre Schola"')


def test_existing_record_font_choice_is_preserved() -> None:
    core.CONFIG_FILE.write_text(json.dumps({"record_font_family": "Noto Serif"}))
    before = core.CONFIG_FILE.read_bytes()
    assert core.load_record_font_family_name() == "Noto Serif"
    assert core.CONFIG_FILE.read_bytes() == before


def test_record_font_options_match_open_law_lens() -> None:
    names = [name for name, _css in RECORD_FONT_FAMILY_OPTIONS]

    assert names == [
        "Noto Serif",
        "Bitstream Charter",
        "Linux Libertine O",
        "Caladea",
        "Gentium Book Basic",
        "DejaVu Serif",
        "Century Schoolbook",
        "TeX Gyre Schola",
        "Lato",
    ]


def test_removed_record_fonts_migrate_to_installed_alternatives() -> None:
    replacements = {
        "Georgia": "Caladea",
        "Merriweather": "Bitstream Charter",
        "Source Sans 3": "Lato",
    }

    for removed, replacement in replacements.items():
        assert _normalize_record_font_family_name(removed) == replacement
