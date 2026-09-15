# Record-category acceptance — 2026-09-15

## Result

Implemented four display-only categories and text-first minute-order navigation.
The reader category bar was subsequently removed at the user's request; page
colors and rails remain, without a label or reserved space above the text.
No application dependencies, launch commands, D-Bus interfaces, citation logic,
Agent policy, summary behavior, or private configuration were changed.

| Category | Light paper/chrome accent | Dark chrome accent |
|---|---|---|
| Hearing | `#3F6696` | `#8EB3D8` |
| Report | `#2C7A70` | `#79B9AA` |
| Minute order | `#8A6944` | `#C8AC84` |
| Form | `#78618F` | `#B6A1CD` |

Reader paper is white mixed with 10% light accent; its rail is 4px.
The existing 16px rounded reader corners are preserved by tinting only the
scroller/viewport, leaving inner text nodes transparent.
TOC rails are 3px, headings have stronger fills than bookmarks, and labels use
normal theme foregrounds. Active-page bold text and keyboard-focus outline
are separate from category color. Active-row box outlines were removed at the
user's request. High contrast retains neutral cues.
Default black reader text has at least 18.3:1 contrast on all four paper tints.
Custom user highlight colors remain untouched.

## Automated evidence

- `uv run pytest -q`: **327 passed, 1 unrelated failure**. The existing
  `test_pi_project_settings_preserve_pro_low_and_disable_compaction` expects
  `deepseek-v4-pro-0813`; the pre-existing modified `.pi/settings.json` selects
  `deepseek-v4p1-flash`. Neither that setting nor its test was changed.
- `uv run python -m compileall -q focus tests scripts/preview-record-categories.py`,
  `bash -n scripts/focus-agent-vte.sh`, and `git diff --check`: pass.
- Classifier tests cover producer tokens, unnumbered pages, physical-page joins,
  tier precedence, explicit unknowns, duplicates/conflicts, RT/CT identities,
  missing/malformed/legacy files, date-independent/reversed/overlapping ranges,
  exact TOC fallback and no inferred form continuation.
- Actual GTK widget harness passes in normal and real process-local high contrast:
  all four categories and neutral pages; page stepping, citation entry, TOC
  activation, grep navigation; row rebind; image-to-minute-text and return after
  browsing; missing exact target; stale generation/case callbacks; empty case reset.
- Theme checks preserve buffer identity/text, selection, page, scroll, TOC model
  and expansion, tag count, and link metadata. Accepted TOC delivery updates
  appearance without reloading the text; stale deliveries are ignored.

## Reproduce safely

```bash
# Interactive synthetic preview only; F6 changes theme, F7 checks preservation.
uv run python scripts/preview-record-categories.py

# Private Xvfb screenshots and actual-widget assertions; no live-desktop capture.
# Optional test utilities: xvfb-run and ImageMagick import (not app dependencies).
uv run python scripts/preview-record-categories.py --check --screenshots
uv run python scripts/preview-record-categories.py --check --screenshots --high-contrast
```

Each invocation creates a new temporary HOME/XDG/config/bundle and unique app ID.
It prints its artifact path. No API calls or real case data are used. Xvfb may
print DRI3 software-rendering warnings; both assertion runs exit successfully.
Final run artifacts after restoring rounded reader corners:
`/tmp/focus-categories-hrgp4fu8` and `/tmp/focus-categories-barl_4j5`
(temporary, not required to reproduce). Retained screenshots were refreshed.
The rounded-corner follow-up passed all 43 category tests and both GUI harness
runs; the dark screenshot confirms all four reader corners are rounded.

## Visual evidence and limits

The native desktop preview was inspected in light/dark chrome and high contrast,
including 780×760 wrapping, category/active cues, minute text and return. Only the
synthetic preview windows were targeted for interaction; both were closed afterward.
A focus-raced external screenshot briefly captured Writer and was removed immediately.
All retained PNGs below were subsequently generated on a private Xvfb display,
not by capturing the user's desktop.

- [Light hearing](category-screenshots/light-hearing.png)
- [Light report](category-screenshots/light-report.png)
- [Light minute order](category-screenshots/light-minute-order.png)
- [Light form](category-screenshots/light-form.png)
- [Dark chrome / light paper](category-screenshots/dark-hearing.png)
- [High contrast](category-screenshots/light-hc-hearing.png)
- [Search highlighting and selection](category-screenshots/search-selection.png)
- [Narrow high-contrast form](category-screenshots/narrow-hc-form.png)

No live AI requests, printing, or real-bundle workflows were run for this display
change. Existing regression tests remain the evidence for those unchanged paths.
The running production Focus instance was not restarted or reloaded.
