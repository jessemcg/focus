"""Pipe-tolerant phrase search; synthetic sources and unchanged highlight offsets."""
import re
import threading

import pytest
import focus.app as focus_app
from focus.app import Focus
from focus.core import (
    MAX_BREAKS, build_pattern, preprocess_phrase, normalize_text_for_search,
    normalize_text_for_search_with_map,
)

PHRASE = 'WE DID FILE AN ADDENDUM FOR TODAY WITH NEW INFORMATION'
SOURCE = ('1 | COUNSEL: FOR CONSIDERATION, WE DID FILE AN ADDENDUM FOR TODAY WITH NEW '
          '3 | INFORMATION. THERE ARE ADDITIONAL RECOMMENDATIONS.')


def pattern(phrase):
    return re.compile(build_pattern(preprocess_phrase(phrase), MAX_BREAKS), re.I | re.S)


@pytest.mark.parametrize('source', ['new 3 | information', 'new|information', 'new || information',
                                   'new 3|information', 'new | information'])
def test_pipe_is_search_whitespace_not_a_word(source):
    assert pattern('new information').search(normalize_text_for_search(source))
    normalized, offsets = normalize_text_for_search_with_map(source)
    assert normalized == normalize_text_for_search(source)
    assert offsets == list(range(len(source)))
    assert normalized == source.replace('|', ' ')


def test_query_pipe_normalization_and_real_word_mismatch():
    assert pattern('new | information').search(normalize_text_for_search('new information'))
    assert not pattern('new information').search(normalize_text_for_search('new 3 | different information'))
    assert not pattern('new information').search(normalize_text_for_search('new 123456789 | information'))


@pytest.mark.parametrize('reading_pages', [frozenset(), frozenset({26})])
def test_actual_search_worker_preserves_source_and_maps_hit(tmp_path, monkeypatch, reading_pages):
    page = tmp_path / '0026.txt'
    page.write_text(SOURCE)
    protected = page.read_bytes(), page.stat().st_mtime_ns
    completed = {}

    def capture(_callback, generation, hits, matching_pages):
        completed.update(generation=generation, hits=hits, matching_pages=matching_pages)
        return 1

    monkeypatch.setattr(focus_app.GLib, 'idle_add', capture)

    class Harness:
        _read_text_file = Focus._read_text_file
        _map_normalized_span_to_original = Focus._map_normalized_span_to_original
        _grep_search_worker = Focus._grep_search_worker

        def _on_grep_search_finished(self, *_args):
            return False

    Harness()._grep_search_worker(pattern(PHRASE), 1, threading.Event(), [26], {26: page}, reading_pages)
    assert completed['matching_pages'] == [26]
    assert len(completed['hits'][26]) == 1
    start, end = completed['hits'][26][0]
    assert SOURCE[start:end] == PHRASE.replace('NEW INFORMATION', 'NEW 3 | INFORMATION')
    assert (page.read_bytes(), page.stat().st_mtime_ns) == protected
