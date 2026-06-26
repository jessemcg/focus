from datetime import date

from focus.core import DEFAULT_EXTRACT_PROMPT, compose_extract_information_prompt


def test_compose_extract_prompt_includes_current_date() -> None:
    prompt = compose_extract_information_prompt(
        "Find child DOBs.",
        today=date(2026, 4, 19),
    )

    assert "April 19, 2026" in prompt
    assert "2026-04-19" in prompt


def test_compose_extract_prompt_preserves_custom_prompt() -> None:
    prompt = compose_extract_information_prompt(
        "Return a table with child names.",
        today=date(2026, 4, 19),
    )

    assert prompt.endswith("Return a table with child names.")


def test_compose_extract_prompt_defaults_blank_prompt() -> None:
    prompt = compose_extract_information_prompt("", today=date(2026, 4, 19))

    assert DEFAULT_EXTRACT_PROMPT in prompt
    assert "calculate the child's current age" in prompt
