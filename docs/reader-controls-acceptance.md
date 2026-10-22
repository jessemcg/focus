# Two-click citation controls

Implemented and validated locally on Home, 2026-10-22. This report **supersedes
2026-09-25's counter/End here workflow**. The older screenshots in this directory
(`after-*`, `anchored-*`, `before-light`, `split-button-light`) are historical,
not evidence for the current interaction.

## Interaction contract

```text
Resting:     Cite page    Start range
Selecting:   [Cite RT 45–48]    ×
```

- **Cite page** copies the displayed underlying record page and also sends it to
  Prose when available, in one click. Both resting buttons are flat, subdued,
  normal-weight text, with native hover/focus indication.
- **Start range** stores one ephemeral anchor without delivery. Browsing updates
  the same persistent range button immediately. Click that highlighted preview
  to complete; no count, menu, confirmation, End here, or separate preview exists.
- Forward and backward selection normalize to the same ascending, inclusive
  citation. Completion on the anchor uses the existing single-page format.
- Resolution validates the current identities of both endpoints and **every
  physical page** in between. Missing files/labels/metadata, mixed prefixes,
  different series with identical prefixes, record-type changes and numbering
  gaps/restarts fail closed. The canonical formatter's direct reversed-input
  rejection is unchanged.
- Invalid navigation retains the anchor and cancel button. The nonactionable
  preview reads `From RT 45…`; its tooltip and accessible description explain the
  failure. Returning to a valid endpoint restores completion without restarting.
- Cancel only drops the anchor. It never navigates or delivers. Case reset,
  inventory reload and closing discard selection; no state is persisted.
  Image/text and Readable/Original changes preserve it.
- Ctrl+Alt+Shift+C (`insert_current_page_citation`) always cites the displayed page,
  independently of any pending range. Ctrl+Alt+C (`insert_page_citation_range`)
  uses the very same validated start/complete path as the range button.
- Preview refresh and external shortcuts do not move search/reader focus.
  A focused cancel button returns focus to the persistent range button before
  disappearing. There is no global Escape override. Normal GTK button activation
  remains available for the range and accessible **Cancel citation range** button.

## Delivery, feedback and unchanged Prose contract

Explicit page/range completion independently attempts **normal clipboard first,
then Prose dispatch**, even if either fails or raises. Starting, navigating and
canceling do neither. PRIMARY is never written by citation delivery.

| Clipboard | Prose dispatch | Feedback / pending range |
|---|---|---|
| Success | Success | “Citation copied and sent to Prose.” / clear |
| Success | Failed or absent | “Citation copied.” / clear |
| Failed | Success | “Sent to Prose; clipboard unavailable.” / clear |
| Failed | Failed | Neither route available / retain |

Feedback uses existing nonblocking toasts. The main toast overlay is built before
interaction so the first citation toast does not reparent the reader and lose
keyboard focus.

Prose remains an unchanged dependency: `com.mcglaw.Prose`,
`insert-record-citations`, its existing string parameter and object paths. A
successful D-Bus call means **dispatched**, not confirmed inserted. Prose can
reject an insertion internally when busy or without a usable Writer document;
Focus's successful clipboard copy still supplies a fallback. There are no new
acknowledgments, window activation, synthetic pastes, saving, queues or retries.
No Prose, Desktop_Files or XREMAP source changes were needed.

## Layout and accessibility

The citation area remains above the reader, beside image-only **Back to text**.
The toolbar is a linear horizontal allocation rather than a symmetric CenterBox:
search yields horizontal space before the citation controls. Compact local button
padding and bounded metadata labels avoid forcing a larger application minimum.
At very narrow widths the date/raw-total labels and search text can ellipsize;
the controls remain separate, and the range endpoints, × and Back to text remain
usable. Full metadata remains accessible.

The shared **Search and Cite Chip Color** (`search_chip_color`) still owns active
color. The chip remains **26px** within a stable **34px** row. There is no new
setting. Long volume-qualified preview labels may abbreviate the visible prefix
(e.g. `Cite RT 98765–98767`), keeping both printed endpoints rather than clipping
almost the whole citation. The accessible name is still
`Cite 12345 RT 98765–98767`; its tooltip/description includes the complete
`(12345 RT 98765–98767.)`, inclusive count, original anchor and click instruction.

### Synthetic captures

All captures contain invented records only:

- [Resting, light 1100×800](screenshots/reader-controls/two-click-light-1100-idle.png)
- [Resting, dark 900×700](screenshots/reader-controls/two-click-dark-900-idle.png)
- Long-label image selection: [light 1100×800](screenshots/reader-controls/two-click-light-1100-long-image.png), [dark 1100×800](screenshots/reader-controls/two-click-dark-1100-long-image.png)
- Long-label image selection: [light 900×700](screenshots/reader-controls/two-click-light-900-long-image.png), [dark 900×700](screenshots/reader-controls/two-click-dark-900-long-image.png)
- Constrained, populated controls: [light 665×700](screenshots/reader-controls/two-click-light-665-long-image.png), [dark 665×700](screenshots/reader-controls/two-click-dark-665-long-image.png)

The constrained fixture includes a long page label, date, Readable selector,
search text, hit count and both grep navigation buttons, not the lightweight
empty-control prototype. Settled checks require the **actual requested window
width**, positive/nonoverlapping bounds, visible usable chip text, and unchanged
row height. The stress toolbar's minimum allocation was **641px**, fitting the
665px window after its existing 12px side margins. Checks also passed at 780px.

## Validation results

All source execution used disposable Focus source/state and an explicitly
provisioned disposable environment via the absolute UvEnvironments helper, with
paired `--project` / `--environment` overrides. Full pytest used `umask 0022`.
Private production config/Pi settings, cases, documents and production clipboard
were not changed. All test-opened processes were stopped. No paid agents ran.

| Check | Result |
|---|---|
| Citation/action/resolver + retained grep formatter and page-number regressions | **93 passed** |
| Full Focus pytest | **816 passed, 5 skipped, 11 subtests passed** |
| `acceptance_reader_controls.py` | PASS under `G_DEBUG=fatal-criticals` |
| `acceptance_transcript_reading.py` | PASS, offline/synthetic |
| `acceptance_answer_switching.py` | PASS, 320 transitions, 0 GTK criticals, reading position retained |
| Real Prose/Writer/clipboard acceptance | PASS, described below |
| `compileall focus tests`, shell wrapper syntax, Git whitespace | PASS |

Reader-control acceptance uses separate clipboard and Prose spies. It asserts
idle/selecting visibility, live labels/sensitivity, stable button identity/focus,
independent current-page action, same-page completion, backward action completion,
invalid interior recovery, normal GTK button activation, cancel focus return,
Readable/Original and image preservation, page stepping/jumps, TOC activation,
image navigation, grep navigation across pages and source links. Back to text retains reader focus and a 200px scroll offset. Case reset,
inventory reload and empty-record sensitivity are exercised. Unit coverage adds
all four delivery outcomes/exceptions, stale preview revalidation, endpoint and
interior metadata failures, missing physical pages and preserved canonical volume
formatting.

### Real local integration acceptance

`tests/acceptance_citation_delivery.py` is a bounded, opt-in system-Python/UNO
harness (not part of ordinary pytest). It copies Prose package/prompts and
`tests/remap_acceptance_support.py`, uses that helper's private LibreOffice
profile/process group/dynamically allocated localhost listener, and runs real
Prose GApplication actions on a **private D-Bus session**. A separate Xwayland
server provides an isolated clipboard/display; Focus clients execute through the
explicit disposable environment helper. The production port-2004 listener and
real documents are never contacted. The fallback launcher is replaced in the
**disposable test process only** with a fail-closed assertion.

Verified with the actual Prose action and Writer UNO model:

1. One page citation inserted once at the synthetic cursor:
   `LEFT (RT 45.) RIGHT`.
2. One backwards-selected range inserted once at the retained cursor:
   `LEFT (RT 45.) (RT 45–47.) RIGHT`.
3. A selected synthetic `TARGET` was replaced with exactly one page citation,
   producing `LEFT (RT 45.) RIGHT`.
4. Each insertion preserved the established single trailing-space behavior.
   Writer remained modified: the action did not save the synthetic ODT.
5. A **separate process** read the normal clipboard for every completion.
   PRIMARY's separately seeded sentinel stayed unchanged.
6. With Prose absent, clipboard delivery succeeded and feedback was “Citation
   copied.” With Prose registered but no usable Writer document, clipboard still
   succeeded, Focus reported dispatch, and Prose's actual handler showed its
   “Open a Writer document” notice. This explicitly tests dispatch ≠ insertion.

Machine-local evidence: `/tmp/focus-citations-UiL2rr/` (provisioning source/env,
pytest/reader/reading/answer-switching/integration logs),
`/tmp/focus-prose-citation-y840syux/` (private integration artifacts), and
`/tmp/focus-reader-acceptance-nthxepzx/` (final synthetic captures).

### Native observation and limitations

Computer Use observed the actual synthetic 665px dark window and its accessible
full long-volume citation name/description, cancel button and Back to text.
Semantic AT-SPI activation changed the real range controls. Programmatic widget
signals/actions and normal GTK `activate()` passed separately.

Injected native keyboard/pointer events were dispatched by the desktop tools but
did not reliably cause visible state changes. Therefore **physical/native-key
navigation and Space/Enter activation are not independently certified** here;
the normal GTK action path and keyboard-focus invariants are tested, not claimed
as proof that injected input arrived. No global key workaround was added.

There is no outstanding UNO/clipboard integration gap on this computer. GTK runs
had no criticals; they emitted local EGL/portal shutdown diagnostics, and the
an earlier reader harness run emitted one noncritical GtkGizmo snapshot-allocation
warning during activation/resizing (not reproduced in the final run). Full pytest
retained GTK/Adwaita deprecation warnings. These are not represented as warning-free runs.

## Safe repeat commands

First create a disposable **versioned-source-only** Focus copy (omit private
`config.json` and `.pi/settings.json`) and its local environment; include the
optional PiRunMetrics source sibling for its existing integration regressions.
Never provision test dependencies into production:

```sh
P=/home/jesse/Dropbox/MCGLAW/config_files/scripts/PROJECTS/UvEnvironments/project-env
# SRC and ENV must be disposable paths, e.g. /tmp/check/Focus and /tmp/check/env.
"$P" --project "$SRC" --environment "$ENV" sync Focus
# Use a dedicated subshell for these environment exports.
STATE=$(mktemp -d /tmp/focus-test-state-XXXXXX)
for key in HOME XDG_CONFIG_HOME XDG_CACHE_HOME XDG_DATA_HOME XDG_STATE_HOME; do
  mkdir -p "$STATE/$key"
  export "$key=$STATE/$key"
done
export GSETTINGS_BACKEND=memory
umask 0022
"$P" --project "$SRC" --environment "$ENV" run Focus pytest -q
G_DEBUG=fatal-criticals dbus-run-session -- \
  "$P" --project "$SRC" --environment "$ENV" run Focus \
  python tests/acceptance_reader_controls.py
# Repeat similarly for acceptance_transcript_reading.py / acceptance_answer_switching.py.
/usr/bin/python3 "$SRC/tests/acceptance_citation_delivery.py" \
  --focus-project "$SRC" --focus-environment "$ENV" \
  --prose-source /home/jesse/Dropbox/MCGLAW/config_files/scripts/PROJECTS/Prose
```

Reader acceptance makes a further package copy and temporary HOME/XDG of its own.
The integration runner requires Focus source/environment under the system temporary
directory and keeps artifacts for inspection. Its local prerequisites are system
GI/UNO, LibreOffice, Xwayland and a local Wayland compositor. This host lacked
`xvfb-run`, so GTK checks ran in private D-Bus sessions on the native local display;
actual clipboard integration used the separate Xwayland server instead.
