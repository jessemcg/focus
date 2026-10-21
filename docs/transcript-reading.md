# Reporter transcript reading view

Focus defaults eligible reporter hearing/body pages to **Readable**. A single,
flat **Readable ▾** / **Original ▾** selector shows the current mode with muted,
regular-weight text; its compact menu offers both choices and marks the active one. The choice lasts only for the
running session; it is not a setting. Original text and page images remain
authoritative and available.

## Structural formatting, not rewriting

Readable has one contract for uppercase, lowercase and mixed-case source pages:

- **Keep source capitalization verbatim.** There is no sentence casing, name
  correction, acronym/month dictionary, Unicode case expansion or model call.
- Remove only positively corroborated pleading gutters and associated rules.
  Ambiguous numbers remain. Gutter uncertainty does not disable speaker styling
  or paragraph spacing on an otherwise supported page.
- Bold recognized explicit speaker labels and start each turn in a new paragraph.
  This includes standard `THE COURT:` / `THE WITNESS:` roles, named counsel such
  as `MS. SAMPLE:`, and clearly marked Q/A labels. Labels retain their exact
  spelling and capitalization. The formatter does not infer who is speaking.
- Recognize labels at saved or confirmed recovered line starts. Within flattened
  prose, require an explicit label at a statement boundary or after a retained
  possible line number. Inline Q/A needs both sides of that convention. Obvious
  quoted labels, addressed names without a label, and honorific/initial sequences
  are not new turns. Unsupported or ambiguous labels remain literal text.
- Join physical wrapping within a statement and let the window wrap the result.
  Use the existing viewer font and margins, modest wrapped-line spacing, and one
  blank line between structural blocks. Do not invent topic paragraphs.
- Preserve clear saved paragraphs, examination headings, standalone parenthetical
  directions, page identifiers and timestamp footers. Caption/field rules are
  restricted to front matter; a continuation beginning `IN THE ...` or
  `STATE OF ...` must not become a heading midway through speech.

This is a conservative display formatter, not a guarantee that every flattened
page's original geometry can be recovered. Preparation sometimes makes a line
number indistinguishable from a substantive quantity. Retaining uncertain content
is preferable to deleting testimony or assigning a speaker from context.

## Eligibility and scope

`focus/transcript_reading.py` is GTK-independent and uses no third-party runtime
dependencies. Formatting is current-page only, with a 256 KiB ceiling; the app
keeps only the current presentation. Structured tables and exhibit/numbered lists,
oversized pages, or unsupported mappings retain complete Original text with a
visible fallback status. Unsupported pages are not forced into prose.

Eligibility uses `load_category_index(..., require_nonconflicting_body=True)` on
already supported metadata. Conflicting RT/CT evidence or any explicit
non-body/unknown type vetoes conversion across tiers. Accepted hearing/body
boundaries may establish RT pages, but TOC titles alone cannot. Covers, indexes,
certificates, CT material, summaries, Agent content and saved answers do not use
this formatter. Ordinary sidebar classification precedence is unchanged. No
transcript-content scan is added at startup; the immutable eligible-page set is
passed to viewer search workers.

No participant hints, persistent reading copies, caches/databases, case artifacts,
preferences, model calls, services or preparation changes are involved. Prepared
bundles, source text, settings and research inputs are never rewritten.

## Layout evidence and mappings

The reader and viewer search share conservative gutter analysis. Supported forms
include aligned physical prefixes, detached alternating number/text rows, and
corroborated ascending inline chains left by flattened preparation. Ordinary
numbered/exhibit lists, sparse chains, irregular quantities and ambiguous short
sequences are not treated as gutters.

A nearly complete ordered column can include short answers and empty numbered
rows only with additional long-line, turn/blank-row and page-coverage evidence.
Individual confirmed inline boundaries are retained before adjacent deletion
spans merge. The display uses those boundaries to recover physical starts and
blank rows; it does not insert paragraph breaks into the search projection.
Substantive numbers interrupting the sequence veto this short-row relaxation.

All offsets are half-open Unicode **character** ranges into the saved source
text, not byte offsets. Every retained non-whitespace character is identical to
its source character. The display map handles removed layout and inserted
whitespace without casing substitutions or guessed deltas. Search uses an
interval-only gutter projection; expensive display formatting is not run on each
searched page. Per-scan layout reuse is transient, not a persistent record cache.

## Viewer integration

- Eligible RT pages use literal text buffers in both modes, so punctuation such
  as `**NO**` or `[NO](link)` never activates Markdown. Other views keep their
  existing rendering.
- Grep hit identity/counts, navigation and citations remain source-based.
  Highlights and active-hit scroll positions are mapped into the current view.
- Selections and reading anchors are mapped between Readable and Original.
  Copying and selection-search actions use the visible selected text; citation
  identity remains the source page. Inline speaker tags use actual bold weight.
- A source snapshot invalidates the current presentation when text changes,
  disappears, is rescanned, or the case changes. No stale map is reused for a
  different page or bundle.

## Validation

`tests/test_transcript_reading.py` and `tests/transcript_reading_fixtures.py` use
synthetic data only. They cover verbatim character retention, monotonic maps,
substantive quantities, Unicode, literal punctuation, regular/detached/flattened
columns, partial gutters, short/empty rows, mixed-case labels, inline Q/A,
initials, quoted labels, addressed names and conservative rejection. The same
short-turn fixture is tested as flattened, physically prefixed and unnumbered
physical text, including continuation lines that resemble captions.

`tests/acceptance_transcript_reading.py` uses disposable HOME/XDG/config/bundles
and actual GTK buffers/tags. It checks the flat dropdown's two menu targets,
state/label synchronization, computed regular label weight, no-op/invalid choices, popup selection preservation,
mode retention through unsupported pages, and unchanged fallback indications.
It also checks real bold weights and line spacing, selection-search/citation,
cross-gutter and short-row mapped highlights/scrolling, Original round trips,
ambiguous-number independence, images, fonts, narrow/wide
layouts, RT/CT/table/summary/saved-answer transitions, source changes/missing
pages, rescans, case transitions, and bounded presentation retention over 240
visits. It makes no model calls. Existing answer-switching and neutral-method
GTK acceptance workflows are also rerun.

On the local home desktop (2026-10-21), the disposable full suite passed **782
tests plus 11 subtests**, with 16 skipped. All three GTK workflows passed with
fatal criticals enabled; answer switching completed 320 transitions with zero
GTK criticals. A read-only 36-page / 12-bundle review passed exact retained-text,
label-map and reader/search-layout invariants. Protected source, metadata and app
files were checked without writing them.

`tests/benchmark_transcript_reading.py` reports current-page formatting and viewer
search baseline versus reading-aware search. Final structural-only measurements:

| Sample | Formatting median / p95 | Search baseline → readable-aware |
| --- | --- | --- |
| 36 real pages, 1,080 formats | 0.351 / 0.469 ms | 4.751 → 6.143 ms (+29.3%, about 1.39 ms) |
| 33 synthetic pages, 990 formats | 0.312 / 0.450 ms | 8.952 → 11.645 ms (+30.1%, about 2.69 ms) |

The synthetic sample includes physical-prefix, detached, partial-flattened and
short/empty-row flattened layouts. These search measurements remain above the
earlier 20% overhead target; that target is **not met**. They replace older
sentence-casing measurements and are not hidden by a record-wide cache.
