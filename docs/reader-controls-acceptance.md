# Anchored citation controls acceptance

Validated 2026-09-25 with disposable source copies, temporary HOME/XDG state,
a unique application ID and synthetic three-page records. Prose delivery and
clipboard writes were stubbed. Production Focus, private config, local PI settings
and case files were not modified or restarted by the acceptance runs.

## Behavior

- Resting controls are **Cite − +0 +**, without a dropdown. Cite inserts the
  displayed page; minus is disabled.
- The first plus anchors the start. **+2** includes that page and the next two.
  Subsequent navigation does not move the anchor or change the count.
- A visible preview such as **RT 45–47** sits immediately left of Cite, using
  the same `dim-label` styling as the date and raw page number. Appearing or
  extending the preview grows the group leftward without moving the + button.
  **End here** appears away from the anchor; it can extend or shorten the endpoint
  to the displayed page without inserting. It is disabled before the start or at
  an incompatible endpoint, with a reason in its tooltip.
- Minus to zero, or entering zero, cancels the anchor. The editable count accepts
  Enter; Cite also commits a valid edited count before inserting.
- Successful Prose delivery or clipboard fallback clears the range. Failed delivery
  retains it; no range state is persisted. Case reset clears both endpoints.
- Every intermediate page must exist, have a citation, remain in the same series,
  and continue the numbering. Plus and End here cannot silently skip unavailable
  pages, cross series, or cross numbering gaps/restarts.
- Existing public actions and shortcuts retain their contracts: current-page
  citation always means the displayed page; the two-press range shortcut still
  starts at one page and completes at the then-current page. Its initial pending
  start appears as a single-page anchored preview at +0; minus can cancel it.
- **Back to text** remains image-only and preserves reader focus/scroll behavior.

## Measurements and screenshots

Logical pixels under the same theme and application CSS:

| Action group | Width | Height |
| --- | ---: | ---: |
| Original Cite / Range / image toggle | 185 | 34 |
| Previous split-button proposal, text mode | 70 | 34 |
| New Cite / minus / count / plus, resting | 135 | 34 |
| New anchored preview + End here (RT 1–3) | 285 | 34 |
| New resting controls + Back to text | 259 | 34 |

The resting group is 27% narrower than the original, but deliberately wider than
just the split button: direct adjustments no longer need a popover. Active range
information uses additional space only when needed. A 6px start margin keeps the
action group separate from search; hidden controls reserve no internal spacing.
The toolbar remains 34px high. Highlighted Cite uses a lower-profile 26px chip
with the search chip's 10px corner radius and 4px vertical padding. Settings calls
the shared color **Search and Cite Chip Color**; the stored `search_chip_color`
key is unchanged. GUI assertions compare the chip's bounds to a search chip's
measured height and confirm that the toolbar and plus position stay unchanged.
Light/dark 900×700 and 1100×800 synthetic windows
showed readable active state and no control clipping or search overlap.

- [Original controls](screenshots/reader-controls/before-light.png)
- [Previous split button](screenshots/reader-controls/split-button-light.png)
- [Current resting controls](screenshots/reader-controls/after-light.png)
- [Muted preview to the left of Cite](screenshots/reader-controls/anchored-at-start.png)
- [Browsing page 2 with the range still anchored at page 1](screenshots/reader-controls/anchored-browsing.png)
- [Pending range, dark/narrow](screenshots/reader-controls/after-dark-pending.png)
- [Image-only return control](screenshots/reader-controls/after-image.png)

All screenshots contain synthetic content. The transient image-error toast in
some captures comes from deliberately attempting the corrupt second-page PNG.

## Verification

- Full isolated pytest suite: **398 passed**, one existing GTK CSS API deprecation
  warning. The disposable environment included the sibling PiRunMetrics source
  needed by existing wrapper tests.
- `python -m compileall -q focus tests` and `bash -n scripts/focus-agent-vte.sh` pass.
- Synthetic GUI harness passes under `G_DEBUG=fatal-criticals` with no GTK criticals.
- Settled GTK allocation checks confirm that + stays at the same horizontal
  position through both the first and second plus clicks; the preview precedes
  Cite and shares the metadata labels' CSS class.
- Actual widget signals verify single-page insertion, two plus clicks, anchor
  retention across navigation, preview/count synchronization, End here shortening,
  insertion/reset, typed counts, current-page shortcut independence, and the
  existing two-press range action.
- Unit tests additionally cover invalid typed counts, zero cancellation, disabled
  empty-record controls, missing intermediate pages/labels, incompatible series,
  numbering restarts, and retention after failed clipboard fallback.
- Native desktop inspection confirmed the live synthetic counter/preview and
  End here changing RT 1–3 to RT 1–2 without insertion.
- Thumbnail/image-action entry, Back to text, corrupt/missing images, and focus
  transfer still pass. A 200px reader scroll position survives image return and
  subsequent GTK settling.

Repeat safely:

```sh
G_DEBUG=fatal-criticals uv run python tests/acceptance_reader_controls.py
```

The harness copies source and checked-in PI resources into a disposable source
root before importing Focus. It never copies private config or local PI settings,
prints its temporary screenshot directory, and exits nonzero on assertion failure.
