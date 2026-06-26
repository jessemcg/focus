from focus.core import normalize_text_for_search, normalize_text_for_search_with_map


def test_normalize_text_for_search_standardizes_search_punctuation() -> None:
    assert normalize_text_for_search("Court’s\r\norder\u00a0\u2014 final") == (
        "Court's\norder - final"
    )


def test_normalize_text_for_search_with_map_tracks_original_characters() -> None:
    normalized, normalized_to_original = normalize_text_for_search_with_map("A\u00a0B")

    assert normalized == "A B"
    assert normalized_to_original == [0, 1, 2]
