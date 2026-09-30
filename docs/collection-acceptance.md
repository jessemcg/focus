# Collection-first acceptance — 2026-09-30

Jesse approved shared Pi-version provenance repair and Focus action attribution,
not research/recovery behavior changes. The compatible implementation belongs to
sibling **PiRunMetrics**; Focus does not vendor or change the observer or its
model-facing record extension. Deploy the sibling collector/reader and these
Focus tests/docs together, then restart/new embedded sessions on each computer.

See [shared contract, all-app audit and per-computer checklist](../../PiRunMetrics/docs/collection-provenance.md).
Collector 0.1.2 prefers the adapter's strictly numeric runtime version; future
known-version cohorts stay separate from historical null-version records.
Focus finished records carry `focus_record_execution_errors` (including `{}`),
with only context/search/lookup/document/map/unknown counters for existing
`isError=true` executions. This breakdown is attribution, not another error total.
Legacy absence is not instrumented; complete instrumented empty objects are
eligible zeros. Old diagnostic/application-error meanings and failure semantics
are unchanged; context.ok need not mean a valid source map.

## Disposable checks

From a private current-worktree/ tracked-source **copy** (no private config or
real .pi/settings.json), preserve the sibling PiRunMetrics layout and use temporary
HOME, XDG_STATE_HOME/CACHE_HOME/CONFIG_HOME/RUNTIME_DIR and TMPDIR. Use installed
venv dependencies without modifying the real environment. Existing GTK widget
regressions require display access: retain explicit DISPLAY/XAUTHORITY and use
GDK_BACKEND=x11 when supported, not inherited provider credentials. With no
display, run only the collection tests and disclose the remaining GUI regressions.
A scrubbed no-display full-suite attempt crashed an existing widget test; the
explicit-display rerun passed all 414 tests with HOME/XDG/TMP still isolated:

```sh
/path/to/installed/Focus/.venv/bin/python -m pytest
/path/to/installed/Focus/.venv/bin/python -m compileall -q focus tests
bash -n scripts/focus-agent-vte.sh
```

`tests/test_collection_acceptance.py` runs ten offline contract cases:

- `focus_extension_contract.mjs` loads the actual extension using installed Pi's
  jiti/dependencies and synthetic helpers. Tests all five actions, enum/type-invalid
  inputs, missing arguments, broken transport, guarded and symlink-escaping reads,
  malformed/empty/nonobject helper responses and shell-free literal arguments.
  Native executor checks cover missing executable/helper, cancellation and a
  short **test-only** timeout; requested production timeout stays 120000ms.
- `focus_metrics_sdk_fixture.mjs` is a test-only Pi executable launched through
  the **production wrapper** and shared adapter. It runs the real SDK with network
  fetch forbidden, a scripted provider, synthetic bundle/settings/skill, exactly
  read/focus_record/submit_focus_answer, disabled discovery and in-memory sessions.
  No credentials are passed to it. It verifies a retry stays in one run, a settled
  literal followup creates a new run, and enabled/disabled model context and answer
  artifacts match after normalizing only variable timestamps, artifact elapsed
  time and temporary publication IDs. Submission terminates without another turn;
  fallback/partial/empty/actual abort/publication-failure behavior is retained.
- Four missing search/lookup/document/map arguments remain four execution errors,
  now correctly attributed without returned action diagnostics. Valid calls and
  missing/invalid source maps retain existing result and application-error counts.
- Disabled, missing, unsupported/unrecognized, relative/unwritable archive modes
  keep the answer/context/tool behavior and never claim finished capture. A valid
  absolute override records two private content-free files. Inherited version
  99.99.99 is replaced by the synthetic executable's probed 0.99.1.

The fixture's 0.99.1 is controlled probe data, **not** a claim about the installed
SDK version on a receiving computer; record that version separately. Requires
installed Pi/Node plus sibling collector; skips are explicit and not acceptance.

Home full suite: **414 passed**, GTK CSS deprecation warning only. Shared metrics:
19 Node tests passed; 44 Python tests with six optional GUI skips. Other-app
bridge/passivity evidence and host runtime versions are in the shared document.
No GUI behavior was changed, no live question/provider or real case used.

## Limits and handoff

Native Pi 0.99.1 executor tests expose an existing caveat: a signal-killed helper
can report code=0/killed=true/empty stdout, which Focus currently accepts as `{}`.
This instrumentation change deliberately preserves it. It is not evidence about
historical failures and any repair needs a separate approved behavioral plan.

Home/work/laptop must each run installed-runtime synthetic checks and verify
content-free metadata from the next **user-initiated** ordinary run. Dropbox's
combined archive alone does not prove host collection. Work/laptop and all next
ordinary-run checks are pending. Do not upgrade Pi, change model/reasoning/prompts,
add budgets/retries/deduplication, grade answers or schedule calls to fill samples.
Keep private settings, case bundles, saved answers, original archives and reports
untouched. No desktop/XREMAP change/synchronization command is required.
Rollback changes code only or disables collection with PI_RUN_METRICS_ENABLED=0;
retain every historical and newly collected record.

The pre-existing staged README and unstaged app.py/test_open_case.py changes remain
outside this collection commit. Tests used a current-worktree disposable copy so
those changes were preserved and included in regression coverage, not rewritten.
