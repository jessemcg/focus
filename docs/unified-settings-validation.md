# Unified Settings

Publication: the user subsequently authorized committing and pushing the inline-editor changes. The no-commit/no-push statements below describe validation, not publication; native-input acceptance remains unverified.

## Current interaction contract — inline Highlights, 2026-10-19

Display/Highlights/Agent retain their boxed expandable home and existing color/font/model controls. **Highlight phrases** is now a full-width, non-activatable preferences row directly inside Highlights, not a destination or suffix control. Its labelled, undo-enabled rounded editor shows roughly three font-aware lines with padding, soft wrapping, no horizontal scrolling and bounded vertical scrolling. The helper reads **One word or phrase per line. Case-sensitive.** Both labels wrap at narrow widths. Tab leaves the editor; Enter retains normal multiline TextView behavior.

The existing buffer, load/format/draft-snapshot/normalization/persistence path is unchanged. Explicit Save trims surrounding whitespace, removes blank lines and exact duplicates in order, and preserves literal spaces, commas, Unicode and case distinctions. An empty field saves an empty list. There are no phrase count/length limits, new matching rules, schema changes, automatic saves or migrations.

Save applies all drafts and stays on Settings. Collapsing Highlights retains drafts. Only complete success advances the literal baseline. Pi, AI settings and font preferences remain independent writes; failures report possible partial persistence and retain drafts. Refresh failure or an unavailable pending model retains the unsaved identity. Dirty Close offers **Keep Editing / Discard Unsaved Changes**; accepted closure alone releases ownership. Dirty Settings vetoes main-window teardown before agent/search cleanup.

## Inline-editor validation — Work, 2026-10-19

All write-producing validation used `/tmp/focus-inline-Jel2Re/source` and its separate environment, explicitly provisioned/run with paired UvEnvironments `--project`/`--environment` overrides. HOME/XDG state, preferences, model adapters and persistence were synthetic. Private settings, maintained Focus and real cases were neither read nor modified. No model calls or other-computer actions.

- Focused actual GTK settings/session/model suite: **16 passed**, `G_DEBUG=fatal-criticals`, isolated D-Bus/Xvfb.
- Full isolated pytest: **676 passed, 11 skipped, 11 subtests passed, 1 pre-existing failure**. Skips are the optional sibling PiRunMetrics/installed SDK integration (not copied or installed for this task).
- Remaining failure: `test_readme_has_one_focus_uninstall_command` expects obsolete bold uninstall headings. Reproduced against unchanged HEAD in a separately provisioned disposable baseline. Installer documentation was not changed to mask it.
- Offline actual GTK neutral-method acceptance: **PASS**, including the real menu-to-Settings route, fabricated question staging and retained stores/answers.
- Offline answer switching: **PASS**, 320 transitions, zero GTK criticals, final identity/view and viewport restoration correct. Both acceptance harnesses ran with fatal GTK criticals and isolated D-Bus/Xvfb.
- Updated tests exercise the real home Save button: normalization (single/multiword phrases, commas, Unicode, whitespace, blanks, duplicates and case), clearing, collapsed edits plus another setting, repeated Save, early save failure, later independent font-write failure, truthful status, literal baseline acceptance, dirty Keep/Discard, and undo/redo. Existing pending-model, stale/closed-callback and session/ownership coverage remains.
- Structural assertions: the retained buffer belongs to Highlights; only `home` remains registered; no phrase destination/Save control; non-activatable full-width row, wrapping, accessible label/description, undo, Tab policy and compact scroller bounds. A font-change regression checks the deferred measurement after GTK updates its Pango context.

### Native layout and limitations

A separate synthetic **Synthetic Focus — Inline Highlights** window was rendered on the current GNOME/Wayland desktop. Final source was inspected at **900×720, 520×620 and 469×620**, each in **light/dark** and **Sans 10/Sans 18** (12 combinations). Widget snapshots below are synthetic native GTK renders, not screenshots of the maintained app.

- The short/empty editor stays approximately three lines, rather than filling Settings. Native bounds were about **405×71** at 469px with Sans 10 and **405×115** with Sans 18; widths expand with the row, not a suffix.
- Enlarged helper text wraps without horizontal clipping. At 469×620 with enlarged fonts the outer Settings viewport scrolls, keeping the full editor and Agent section reachable.
- A long single phrase soft-wrapped with unchanged literal text/one buffer line and no horizontal overflow. A 100-line list retained the compact viewport; programmatic adjustment reached its end. Collapse, mocked Save and reopening retained the list and kept Settings visible. These were **programmatic GTK checks**, not delivered keyboard/wheel events.
- Native coordinate click and targeted Tab dispatch reported success but did not change the synthetic window's focused widget. Native pointer placement, keyboard traversal/Enter, selection, multiline clipboard paste, undo shortcuts, wheel delivery and nested-scroll ergonomics are therefore **not accepted**. Buffer undo/redo, scroll adjustments and Save signals are tested, but do not substitute for native input acceptance. No blind text/clipboard replay or desktop settings changes were attempted.
- An initial full run shared a D-Bus application ID with the preview and aborted; final suites used isolated D-Bus/Xvfb. A transient snapshot-harness issue was corrected by retaining its WidgetPaintable; the final matrix completed. Neither was treated as product acceptance evidence.

[900px light](settings-previews/settings-900-light.png) · [520px light](settings-previews/settings-520-light.png) · [520px dark](settings-previews/settings-520-dark.png) · [469px dark](settings-previews/settings-469-dark.png) · [469px enlarged, outer viewport scrolled](settings-previews/settings-home-large-469-dark.png)

Existing preview files were replaced with the inline design, including the historical home aliases. Local evidence: `/tmp/focus-inline-Jel2Re/{focused-final.log,full-final.log,baseline.log,neutral.log,answer.log,matrix.json,long-list.json}` and synthetic preview scripts/images. No dependency, launcher, CLI, mapping or cross-repository changes; no commit, push or maintained-app restart.

## Historical unified-settings validation — earlier 2026-10-19

The earlier, separately committed layout used a retained **dedicated Highlight phrases page with Back**. That presentation is superseded above; its results do not establish inline-editor acceptance.

- Disposable tracked-source/environment with fabricated preferences/catalog/persistence: **684 passed, 11 subtests passed, 1 pre-existing README-heading failure**, reproduced on unchanged HEAD.
- Actual GTK settings/session subset: **5 passed**, fatal GTK criticals. Home/detail Save, hidden edits, repeated Save, independent write failures, baseline acceptance, pending/unavailable models, stale/closed callbacks, dirty Keep/Discard and ownership were covered.
- GTK/Broadway previews at 900×720, 520×620 and 469×620, light/dark and enlarged fonts. The former detail editor measured 496×525 at 520px and 445×525 at 469px; these are historical detail-page dimensions, not current compact-editor bounds.
- The desktop was locked then; Broadway/programmatic signals did not establish native input acceptance. Earlier artifacts were recorded at `/tmp/gtk-rollout-20261019/Focus`. Publication was later authorized as a separate local commit, with no push or maintained-app restart.
