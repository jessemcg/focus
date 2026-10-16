# Compact minute labels and entry spacing — 2026-10-16

Companion to RecordPrep minute contract8 / `recordprep-minute-compact-labels-2`.
The user requested Appearances / Orders / Next in bold with no leading dashes,
then clarified: one blank line between minute entries, none between their four
internal lines (date/hearing plus the three fields).

## Display only

- `core._extract_summary_emphasis_spans` recognizes only exact minute line prefixes
  `Appearances:`, `Orders:`, `Next:` and applies the existing entry-emphasis tag.
  It does not match body prose, old dash-prefixed fields or other summary kinds.
- Current emphasis matches direct quotations: the same theme-aware foreground,
  `Pango.Weight.MEDIUM` (500) and normal scale (1.0), with no separate accent or
  size boost. This also applies to existing hearing/report entry-emphasis spans.
  Theme refresh resets old tags in place without replacing text or selection.
- Settings no longer offers **Summary Emphasis Color**. Its constant, default,
  active settings field and load/save wiring are removed. Historical configuration
  keys are ignored and preserved, not migrated/deleted; new saves do not add them.
- Both continuous and schema-v2 structured displays already use this matcher.
  No Markdown/fake quotation is inserted. Labels never become clickable source-phrase
  links. Actual quotation/page-link behavior remains unchanged.
- Paginated display previously inserted a blank line at every PDF block boundary.
  The minute-only spacing option now uses one newline before each field label,
  leaving one blank line before the next entry's date/type. Visual paragraph wraps
  in the page map are already spaces; individual paper-page boundaries stay separate.
- Structured display remaps validated quote/link offsets through exactly that
  transformation. Legacy paginated rendering and search use the same minute option.
  Continuous canonical TXT already has the requested grouping and is not reformatted.
- No PDF reflow/repagination, page-map/schema/layout change, RecordPrep import,
  research/Agent method change, dependency, launcher or private-settings migration.
  The PDF itself retains its fixed typography; bold labels/grouping are Focus display.

## Validation

Disposable `/tmp/recordprep-selection-ITRpgg/focus-source` and `focus-env`, explicitly
provisioned via UvEnvironments with paired overrides; not the maintained runtime.
New `tests/test_minute_label_emphasis.py` covers exact prefix scope, actual GTK
tag application in continuous/structured paths, no label links or text changes,
blank-line grouping/page edges, and quote/link/search/label offsets after spacing.

Initial label/grouping implementation: five new tests PASS; full pytest **665 passed,
11 skipped, 1 pre-existing failure**, 12.19 s. The quote-style follow-up adds three
regressions in `tests/test_summary_quote_style.py`: real label/quote GTK tag parity
and old-tag refresh under both themes, text/selection/phrase-target preservation,
retired config read/save behavior, and actual Settings UI/save behavior. Latest full
pytest: **668 passed, 11 skipped, 1 pre-existing failure**, 12.40 s. The eight label
and quote-style tests all PASS; active Python compilation and whitespace checks PASS. An unrelated pre-existing
`tests/test_install_lifecycle.py::test_readme_has_one_focus_uninstall_command` fails:
it expects the old bold uninstall heading, while committed README uses level-three
headings. Both files are byte-identical to HEAD; neither is changed here. Do not
alter installer tests/README merely to make this styling follow-up green.

Synthetic answer-switching acceptance PASS: 320 transitions, 327 renders, zero GTK
criticals with fatal diagnostics, exact final answer and retained reading position
(fraction0.5). No production instance was used.

Actual isolated Focus preview consumes a real, fictional RecordPrep TXT/PDF/page map.
The original preview verified six label tags at weight700. The latest quote-style
preview verifies six labels at weight500/scale1.0 and exactly the real quotation
foreground, with no label phrase-link targets, unchanged synthetic case/config
artifacts and the requested entry grouping. Native Settings observation also confirms
only the remaining highlight controls are offered. Native Linux Computer Use
observes only that uniquely named synthetic instance. Ordinary Focus/user cases and
RecordPrep's active testing are not controlled/restarted. No paid calls, real-case
regeneration, maintained sync, commit/push or other-computer access.

Restart Focus when ready to load this display code. RecordPrep's new plain-English
selection/labels require its separate explicit minute rerun; this consumer does not
rename or rewrite old saved summaries.
