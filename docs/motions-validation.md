# Motions / availability validation

2026-11-06, current **work** computer only; uncommitted and undeployed.
See [behavior and compatibility](motions.md) and RecordPrep's companion
`docs/motions-validation.md` for the complete cross-repository evidence.

- Full disposable pytest: **879 passed, 16 skipped**, plus **11 passing subtests**,
  11.35 s. Evidence: `/tmp/recordprep-motions.NqinRQ/focus-full-final.log`.
- RecordPrep producer regression: **940 tests, 932 passed, 8 skipped**.
- Both shared files (`profile_contract.py`, `profile_artifacts.py`) byte-identical.
- Schema-11 validation, historical schemas 1–10, strict historical task keys,
  naming 1–5, rose contrast, sidebar filtering and availability tests pass.
- Readable legacy text, matching-hash zero metadata (including the separate minute
  envelope), exact empty titles, unreadable/corrupt/intermediate files, preferred
  current finals, cache invalidation/case identity and case-name keyword collisions
  have offline coverage. Null-category document headings remain available.
- Wheel/sdist built offline with read-only cached Hatchling requirements through the
  helper-selected disposable Python; all **41 wheel application files** and included
  sdist payloads match source. Extracted-wheel schema/category/discovery smoke passes.
  Compilation and Git whitespace checks pass. No packaging/dependency/entry-point
  declaration changed.

## Actual producer-to-reader GTK acceptance

Run RecordPrep `tests/prepare_motion_acceptance.py` in its own disposable environment,
then run `tests/acceptance_motions.py --bundle <printed synthetic path>` in Focus's
own environment. Use the absolute UvEnvironments helper with explicit `--project`
and `--environment` for each callee, `GDK_BACKEND=x11 GSK_RENDERER=cairo`, Xvfb and
`G_DEBUG=fatal-criticals`. No model or inherited combined runtime is required.

**PASS** (`/tmp/recordprep-motions.NqinRQ/crossrepo-gtk-final.log`): three independent
motion papers, real RecordPrep final metadata/PDF/page map/source map; loaded edition
identity; source-page categories; only populated sidebar groups; all four summary
buttons/wrappers; direct Motions action; active-summary disappearance fallback; and
read-only phase file byte/mtime preservation. Later deliberate synthetic changes
populate every button for layout stress. At **486 px** the mode strip wraps over
two rows; at **1270 px** it fits one. GTK-rendered light/dark screenshots are under
`/tmp/focus-motions-acceptance-42uzatvn/`. The existing pagination controls additionally
wrap vertically at the narrow size; this change does not redesign them.

Native Computer Use was attempted locally: the synthetic window appeared in AT-SPI,
but targeting became unavailable and portal capture was black. Native visual/input
acceptance is not claimed. No desktop setup/unlock or maintained-app restart was
attempted; the bounded synthetic instance exited. Xvfb snapshots and assertions are
separate successful runtime evidence, not native screenshot claims.

No real case, private configuration, provider, migration, deployment or other computer
was used. Pre-existing untracked `.pi/` is untouched. Launcher/XREMAP references were
inspected read-only; existing paths/IDs/actions stay unchanged. Publish compatible
Focus before RecordPrep only if publication is separately authorized.
