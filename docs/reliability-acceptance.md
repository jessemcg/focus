# Record reliability acceptance — 2026-10-06

## Implemented contracts

- Exactly `read`, `focus_record`, `submit_focus_answer`; no shell, discovery,
  session persistence, new model calls, retries, research limits, compaction,
  deduplication policy, persistent search cache or model/reasoning changes.
- Action-specific arguments are checked before Python executes. `document.id`
  comes from returned document metadata; `document[]` is a search scope.
  Lookup requires exactly one citation/file; search requires usable queries;
  map requires a section. Inapplicable fields are rejected, not silently ignored.
- Already-cancelled calls never spawn. Cancellation stays an execution abort;
  killed helpers, nonzero exits and invalid/empty/nonobject payloads never become
  successful evidence. Minimal per-action result shapes accept additional fields
  and source-map v1/v2. Returned failures have fixed codes and nonempty
  `details.error`; argument/executor exceptions stay execution failures.
  The 120-second deadline is unchanged; killed alone does not prove timeout.
- Requested documents form an ordered, deduplicated union, intersected with
  date/witness/counsel filters. Unknown documents or unavailable/unusable requested
  metadata return `scope_unavailable`; a valid empty intersection returns
  `scope_status: empty`. Neither means record-wide absence or case-wide fallback.
- Search and lookup resolve only regular `.txt` source files under canonical
  `text_pages/`. Traversal, summaries, special/nontext targets, escaping file
  symlinks and redirected text roots are rejected. The read guard uses the same
  boundary; feedback distinguishes missing/outside/invalid paths and recommends
  returned absolute `resolved_text_path` or lookup. CLI image-path metadata stays
  separate; the Agent still cannot read images. No source map is repaired.
- Additive search `coverage`: candidate/scanned/missing/unreadable/rejected pages,
  decoding warnings and completeness. Scanned + missing + unreadable + rejected
  equals candidate pages. Invalid UTF-8 uses disclosed best-effort replacement;
  decoding-warning pages count as scanned **and** make coverage incomplete.
  Complete zero hits, incomplete evidence and empty scope remain distinct.
- Query diversification, source-date ranking, snippets, citation collisions,
  attribution distinctions, six-result default, native output limits, answer
  artifact/formatting/follow-up behavior and private selections remain intact.

## Passive diagnostic dependency

Focus emits readiness and fixed outcomes through the existing private observation
bus. Sibling **PiRunMetrics `f3301e5` / collector 0.3.0** adds the matching finite
allowlist and efficiency distributions. See its `docs/focus-diagnostics.md`.
Update/restart that reader and collector **before analyzing new Focus components**,
then restart Focus and start new sessions. Old conversations keep staged resources.
No launcher, app id, public action, desktop entry, XREMAP or settings changes.
Other apps' observation contracts are unchanged. Historical missing components
remain uninstrumented. No prompts, answers, queries, paths, document identifiers,
exception text or argument fingerprints are archived. Read permission is not proof
of successful file I/O; SDK pre-validation failures remain explicitly unclassified.

## Work validation

Host `work`, installed Pi **1.0.4**, Node **22.23.1**, managed Python **3.13.12**.
Disposable sibling current-worktree copies at `/tmp/focus-reliability-q4aUQ9`,
synthetic bundles and temporary HOME/XDG state. The temporary Python environment
was provisioned through the absolute `UvEnvironments/project-env` helper with
paired `--project /tmp/.../Focus --environment /tmp/.../env` overrides. No private
configuration, credentials, real cases, saved answers or archives were copied.
No live provider/session transcripts or original reports were inspected.

- Baseline: **416 Focus passed**, **25 Node passed**, **51 Python passed / 10 skipped**.
- Final: **433 Focus passed** (one existing GTK deprecation warning); copied-source
  compileall and wrapper `bash -n` passed.
- Shared metrics: **26 Node passed**, **54 Python passed / 10 skipped**; compilation
  passed. The skips are opt-in/display tests, not reported passes.
- `focus_extension_contract.mjs` executes the actual extension with installed
  TypeBox/Pi and the native shell-free executor. Injected matrix covers pre-abort,
  cancellation, short test timeout, killed success-shaped output, spawn failure,
  nonzero success-shaped output, malformed/empty/null/array/scalar payloads,
  per-action valid/invalid shapes, invalid/ambiguous inputs and source read denial.
  **Zero false successes**. No automatic recovery/model continuation is added.
- Production wrapper/offline SDK tests now explicitly bind `session_start` and
  verify rejected/schema-invalid/parallel calls, coverage/scope limitations,
  guard outcomes, ready-zero reads and separately settled follow-ups. Synthetic
  archives validate with the production reader. Enabled/disabled/missing/broken
  storage preserves normalized model inputs/results/artifacts/settlement. A
  throwing observation bus preserves actual-extension results; canary content is
  absent from archives. Pi's coercion means a numeric query may become a string;
  an object is used to test genuine pre-Focus schema failure.
- Actual GTK `acceptance_reliability_display.py` passed revisions, partial and
  best-effort display, exact quote-link targets and byte-for-byte saved-answer
  isolation. Native AT-SPI plus screenshot confirmed the uniquely titled synthetic
  Latest Answer, subtitle, linked quote and Answer view. Preview self-terminated.
- Existing switching harness passed **320 transitions**, correct identity/view,
  reading-position fraction **0.5**, and **zero GTK criticals**. Nonfatal GTK width
  measurement warnings occurred; no production GUI code was changed or warning
  suppression added. This is not a claim of warning-free/compositor-fleet acceptance.

## Deterministic helper benchmark

`tests/benchmark_retrieval.py` generates 8- and 400-page bundles; positive, negative,
causal-date and attribution searches; citation ambiguity and incomplete sources.
It makes no model calls and is **not an answer-quality score or provider-speed test**.
For unaffected searches it compares all established result fields against the
pre-change helper (only additive coverage/scope fields removed). Ranked pages,
snippets and citations were equal in every workload.

Alternating baseline/current, 21 rounds, warmed local files (milliseconds):

| Pages | Workload | Baseline median | Current median | Change |
|---:|---|---:|---:|---:|
| 8 | Positive | 0.399 | 0.404 | +1.26% |
| 8 | Negative | 0.300 | 0.304 | +1.39% |
| 8 | Causal date | 0.559 | 0.561 | +0.35% |
| 8 | Attribution | 0.354 | 0.360 | +1.53% |
| 400 | Positive | 17.087 | 17.066 | −0.12% |
| 400 | Negative | 13.589 | 13.393 | −1.44% |
| 400 | Causal date | 27.780 | 28.560 | +2.81% |
| 400 | Attribution | 17.873 | 18.193 | +1.79% |

An initial >10% regression was investigated: repeated per-page text-root resolution
was redundant. Boundary validation is now **request-local**; every source still
resolves and stats independently. There is no persistent source/search cache.
Correct wider union scopes can legitimately scan more pages than the former broken
intersection; that is not an unaffected-workload speed comparison.

Repeat using a disposable baseline helper and the temporary environment:

```sh
P=/home/jesse/Dropbox/MCGLAW/config_files/scripts/PROJECTS/UvEnvironments/project-env
"$P" --project /tmp/source/Focus --environment /tmp/env run Focus \
  python tests/benchmark_retrieval.py --baseline /tmp/baseline_helper.py --rounds 21
"$P" --project /tmp/source/Focus --environment /tmp/env run Focus \
  python tests/acceptance_reliability_display.py
```

## Remaining acceptance and rollback

Home and Laptop installed-runtime/native-executor/wrapper checks are **pending**.
Only Work offline acceptance is claimed; no paid-provider, fleet or human answer-
quality acceptance, and no live latency improvement. Observe subsequent
**user-initiated** work, keeping revisions/Pi versions/configurations separate.
Two comparable windows each need ≥20 eligible observations before descriptive tail
comparisons. No model calls are scheduled for sampling.

All unrelated staged/unstaged work remains in place (`AGENTS.md`, `README.md`,
`focus/app.py`, `tests/test_open_case.py`, and the metrics repository's pending
frontend work). Roll back logical code commits, retaining that work and every case,
answer, archive/report. Metrics can be disabled independently with the existing
switch. No migration, source `.venv`, archive cleanup or private settings rewrite.
