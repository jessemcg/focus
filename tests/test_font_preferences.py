from focus.core import (
    RECORD_FONT_FAMILY_OPTIONS,
    _normalize_record_font_family_name,
)


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
