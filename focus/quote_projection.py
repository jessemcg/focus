"""Instruction-free metadata-7 display/page-fragment mapping (mirrored in Focus).

NFKC below is ONLY PDF glyph alignment, never source quotation matching. Exact
source destinations are independently validated by the navigation contract.
"""
from __future__ import annotations

import unicodedata
from .profile_artifacts import validate_summary_navigation_metadata


def project_summary(text, metadata):
    """Remove only Python-recorded OUTER delimiters, with raw boundary mapping."""
    validate_summary_navigation_metadata(metadata, text)
    removed = set()
    for quote in metadata['quote_occurrences']:
        start, end = quote['start'], quote['end']
        if start < 1 or end >= len(text) or text[start - 1] != '“' or text[end] != '”':
            raise ValueError('Recorded quotation delimiters disagree.')
        removed.update((start - 1, end))
    output, mapping = [], [0]
    for index, char in enumerate(text):
        if index not in removed:
            output.append(char)
        mapping.append(len(output))
    spans = [dict(start=mapping[q['start']], end=mapping[q['end']],
                  occurrence_id=q['occurrence_id'], phrase=q['display_text']) for q in metadata['quote_occurrences']]
    return ''.join(output), tuple(mapping), spans


def project_lines(text, metadata):
    """Per-source-line plain text and ledger-owned bold spans, without parsing."""
    clean, _mapping, spans = project_summary(text, metadata)
    lines, offset = [], 0
    for number, raw_line in enumerate(clean.splitlines(keepends=True), 1):
        line = raw_line.rstrip('\r\n')
        quotes = []
        for span in spans:
            a, b = max(offset, span['start']), min(offset + len(line), span['end'])
            if a < b:
                quotes.append(dict(span, start=a-offset, end=b-offset))
        lines.append({'line':number, 'text':line, 'quotes':quotes})
        offset += len(raw_line)
    return lines


def _coverage(text):
    for offset, char in enumerate(text):
        for normalized in unicodedata.normalize('NFKC', char):
            if not normalized.isspace() and unicodedata.category(normalized) not in {'Cc','Cf'}:
                yield normalized, offset, 1


def page_fragments(text, metadata, page_texts):
    """Monotonic whole-document glyph alignment, never a phrase/substring search.

    Split fragments have the SAME occurrence id even when their shorter words
    occur elsewhere. Every fragment is checked against the committed ledger.
    """
    clean, _mapping, spans = project_summary(text, metadata)
    source = list(_coverage(clean))
    owned, index = [], 0
    for char, offset, _length in source:
        while index < len(spans) and offset >= spans[index]['end']:
            index += 1
        identity = spans[index]['occurrence_id'] if index < len(spans) and spans[index]['start'] <= offset < spans[index]['end'] else None
        owned.append((char, identity))
    by_id = {s['occurrence_id']:s for s in spans}
    cursor, fragments = 0, {}
    for number in sorted(page_texts):
        page = page_texts[number]
        coverage = list(_coverage(page))
        if cursor + len(coverage) > len(owned):
            raise ValueError('Edition text exceeds committed summary coverage.')
        local = owned[cursor:cursor+len(coverage)]
        if any(a[0] != b[0] for a,b in zip(local, coverage)):
            raise ValueError('Edition text disagrees with committed summary coverage.')
        output, run_id, run_start = [], None, 0
        for position in range(len(coverage) + 1):
            identity = local[position][1] if position < len(local) else None
            if identity != run_id:
                if run_id is not None:
                    a = coverage[run_start][1]
                    b = coverage[position-1][1] + coverage[position-1][2]
                    output.append({'start':a, 'end':b, 'label':page[a:b],
                                   'phrase':by_id[run_id]['phrase'], 'occurrence_id':run_id})
                run_id, run_start = identity, position
        fragments[number] = output
        cursor += len(coverage)
    if cursor != len(owned):
        raise ValueError('Edition omits committed summary content.')
    expected = {s['occurrence_id'] for s in spans if any(True for _ in _coverage(s['phrase']))}
    if {q['occurrence_id'] for qs in fragments.values() for q in qs} != expected:
        raise ValueError('Edition omits quotation occurrences.')
    return fragments
