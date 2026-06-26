from focus.core import parse_image_page_selection


def test_parse_single_page() -> None:
    assert parse_image_page_selection("12") == [12]


def test_parse_range() -> None:
    assert parse_image_page_selection("18-22") == [18, 19, 20, 21, 22]


def test_parse_mixed_list() -> None:
    assert parse_image_page_selection("12, 18-20, 30") == [12, 18, 19, 20, 30]


def test_parse_trims_whitespace() -> None:
    assert parse_image_page_selection("  12 , 18 - 19 , 30  ") == [12, 18, 19, 30]


def test_parse_reversed_range() -> None:
    assert parse_image_page_selection("22-18") == [18, 19, 20, 21, 22]


def test_parse_removes_duplicates_in_order() -> None:
    assert parse_image_page_selection("12, 12-14, 13, 16") == [12, 13, 14, 16]


def test_parse_rejects_invalid_selection() -> None:
    assert parse_image_page_selection("12, abc, 20") is None
    assert parse_image_page_selection("") is None
    assert parse_image_page_selection("12-") is None
