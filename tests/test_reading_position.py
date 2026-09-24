from __future__ import annotations

from focus.reading_position import AnswerPosition, AnswerPositionCache


def test_capture_and_get_round_trip() -> None:
    cache = AnswerPositionCache()
    cache.capture("a" * 32, anchor_offset=120, scroll_fraction=0.5)
    position = cache.get("a" * 32)
    assert position == AnswerPosition(anchor_offset=120, scroll_fraction=0.5)


def test_empty_id_is_ignored() -> None:
    cache = AnswerPositionCache()
    cache.capture("", anchor_offset=10, scroll_fraction=0.2)
    assert len(cache) == 0


def test_values_are_clamped() -> None:
    cache = AnswerPositionCache()
    cache.capture("a" * 32, anchor_offset=-5, scroll_fraction=2.0)
    position = cache.get("a" * 32)
    assert position == AnswerPosition(anchor_offset=0, scroll_fraction=1.0)


def test_eviction_is_least_recently_used() -> None:
    cache = AnswerPositionCache(capacity=2)
    cache.capture("a" * 32, anchor_offset=1, scroll_fraction=0.1)
    cache.capture("b" * 32, anchor_offset=2, scroll_fraction=0.2)
    assert cache.get("a" * 32) is not None  # touch a, making b the LRU
    cache.capture("c" * 32, anchor_offset=3, scroll_fraction=0.3)
    assert cache.get("b" * 32) is None
    assert cache.get("a" * 32) is not None
    assert cache.get("c" * 32) is not None
    assert len(cache) == 2


def test_discard_and_clear() -> None:
    cache = AnswerPositionCache()
    cache.capture("a" * 32, anchor_offset=1, scroll_fraction=0.1)
    cache.discard("a" * 32)
    assert cache.get("a" * 32) is None
    cache.capture("b" * 32, anchor_offset=1, scroll_fraction=0.1)
    cache.clear()
    assert len(cache) == 0
