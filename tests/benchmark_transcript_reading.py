"""Read-only formatter/viewer-search microbenchmark; reports counts/timings only.

Optional --paths FILE reads newline-separated local page paths (never printed).
No fixtures, source text, maps or case artifacts are written by this script.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import re
import statistics
import time

from focus.core import normalize_text_for_search, normalize_text_for_search_with_map
from focus.transcript_reading import render_readable, search_layout, search_projection
from transcript_reading_fixtures import detached_page, flattened_page, short_flattened_page


def benchmark(pages: list[str], repeats: int = 30) -> dict:
    timings = []
    diagnostics = {}
    for _ in range(repeats):
        for source in pages:
            start = time.perf_counter_ns()
            result = render_readable(source)
            timings.append((time.perf_counter_ns() - start) / 1e6)
            diagnostics[result.diagnostic] = diagnostics.get(result.diagnostic, 0) + 1
    regexes = [re.compile(q, re.I | re.S) for q in ("the", "document", "unlikelysyntheticneedle")]

    def search(reading):
        for regex in regexes:
            for source in pages:
                layout = search_layout(source) if reading else None
                text, _ = search_projection(source, layout=layout) if layout else (source, None)
                projection = text
                normalized = normalize_text_for_search(text)
                if regex.search(normalized) is None:
                    continue
                text, mapping = search_projection(source, mapped=True, layout=layout) if projection != source else (source, None)
                normalized, offsets = normalize_text_for_search_with_map(text)
                for match in regex.finditer(normalized):
                    start, end = offsets[match.start()], offsets[match.end() - 1] + 1
                    if mapping:
                        mapping.source_span(start, end)

    baseline, reading = [], []
    for _ in range(repeats):
        start = time.perf_counter_ns()
        search(False)
        baseline.append(time.perf_counter_ns() - start)
        start = time.perf_counter_ns()
        search(True)
        reading.append(time.perf_counter_ns() - start)
    ordered = sorted(timings)
    return {
        "pages": len(pages), "iterations": len(timings),
        "format_median_ms": statistics.median(timings),
        "format_p95_ms": ordered[int(.95 * (len(ordered) - 1))],
        "search_baseline_median_ms": statistics.median(baseline) / 1e6,
        "search_reading_median_ms": statistics.median(reading) / 1e6,
        "search_overhead_percent": (statistics.median(reading) / statistics.median(baseline) - 1) * 100,
        "diagnostic_counts": diagnostics,
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--paths", type=Path)
    args = parser.parse_args()
    if args.paths:
        pages = [Path(path).read_text(encoding="utf-8", errors="replace")
                 for path in args.paths.read_text().splitlines() if path]
    else:
        prose = "THE COURT: THE DOCUMENT IS NOT AN ORDER.\n" + "THE TESTIMONY CONTINUES ON THIS PHYSICAL LINE.\n" * 26
        gutter = "\n".join(f"{i:2} | THE DOCUMENT IS NOT AN ORDER." for i in range(1, 29))
        pages = ([prose] * 21 + [gutter] * 4 + [detached_page()] * 4
                 + [flattened_page()] * 2 + [short_flattened_page()] * 2)
    print(json.dumps(benchmark(pages), indent=2))
