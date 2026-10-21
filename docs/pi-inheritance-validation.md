# Pi preference inheritance — 2026-10-21

## Policy and boundaries

No `DEFAULT_PROJECT_PI_SETTINGS`, startup seeding or application model/effort/general
Pi policy defaults remain. A genuinely missing app file means live user Pi settings,
then Pi's own native behavior. The maintained-checkout/XDG selection and explicit
overrides are unchanged. Existing user files are never migrated/reset.

Settings represents inheritance explicitly, not catalog index zero. Refresh and
unrelated Save do not select a model/effort or create Pi preferences. Model-only
Save does not add effort; explicit efforts still clamp for deliberate model choices.
Capability/display fallback by itself is not a persisted edit. Draft selection,
unavailable values, generation guards and failed-refresh retention remain.

`model-settings --stdin` retains its revision/lock/Apply/Recovery contract without
seeding reasoning on Apply. The guarded store implementation is unchanged. Prompt,
skill, exactly `read,focus_record,submit_focus_answer`, follow-ups, confinement,
cancellation and publication remain app-owned. Private workspaces alone force
`enableSkillCommands: true` for required `/skill:` expansion. Compaction/retry inherit;
explicit synthetic setup verification still uses bounded verification-only settings.

Installation receipt/success still precedes optional Pi setup. Skip, cancellation,
missing Pi and failed optional setup do not undo a completed installation. No
bootstrap or one-line command regeneration is needed: maintenance/bootstrap engines
are unchanged. README files are deliberately unchanged at the user's request.

## Evidence

All execution stayed on Home (RTX 3090), with tracked/new-source-only copies under
`/tmp/pi-defaults-work`, independent `/tmp/pi-defaults-envs` provisioned through
paired UvEnvironments overrides, and temporary HOME/XDG/Pi roots. No production
settings, credentials, cases, saved answers or runtime environments were used for
write-producing tests; no paid inference or other-computer access occurred.

- Full pytest: **711 passed, 5 skipped**, 11 subtests passed (runtime/wrapper/
  resources/model-settings/setup/install/UI included).
- `tests/test_pi_inheritance.py`: missing preferences, model-only saves, unrelated
  preservation, malformed files, skill-only ephemeral staging and refresh failure.
- Native GTK `tests/acceptance_pi_inheritance.py`: Computer Use inspected inherited
  state, invoked unrelated Save, selected a synthetic model, forced refresh failure,
  saved/reopened and verified reasoning remained inherited; synthetic phrase data
  and no preference-file creation were asserted. The same harness supports `--auto`.
- Actual Pi **offline RPC only**, synthetic settings/key: changing global model and
  effort between sessions changed effective state; workspace settings did not copy
  either value. No prompt/API request was sent.
- Actual SDK, network blocked and synthetic stream: required Focus and RecordPrep
  skill bodies expanded (12 skills / 12 asserted synthetic-stream invocations) with global `enableSkillCommands: false`; only workspace
  skill expansion was enabled. No global settings were rewritten.
- Shell syntax, resource/whitespace checks, private-file byte/stat preservation,
  scoped Git review and unchanged README/installer command publication contract.

Machine-local evidence is under `/tmp/pi-defaults-start`; these temporary paths are
not shipped runtime dependencies. Automated acceptance is synthetic/offline, not
paid-model quality evaluation or clean-distro certification. Rollback is a source
revert, never restoration/reset of personal settings or prepared work.
