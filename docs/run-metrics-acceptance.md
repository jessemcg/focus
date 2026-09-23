# Run metrics / Copy Trace removal — partial pilot acceptance

2026-09-22, home desktop; Pi 0.87.1, Node 22.23.1.

## Changes

Copy Trace control/callback/module/export tests, trace polling, preserved-session paths, and wrapper preservation are removed. The wrapper explicitly loads the sibling PiRunMetrics observer when available, keeps `--no-extensions` and exactly `read,focus_record,submit_focus_answer`, and uses `--no-session`. App-owned artifacts and live follow-ups are unchanged. No private configuration/model changes or old-trace deletion.

## Automated evidence

- Isolated tracked-source copy: **309 tests passed** using the checked-in `.pi/settings.json` baseline in the disposable copy only.
- The same isolated tests carrying Jesse's current modified `.pi/settings.json`: **308 passed, 1 failed**. The preexisting hardcoded Pro-0813 model assertion conflicts with the current Flash selection. Neither the original settings nor the assertion was changed.
- Python compilation and wrapper `bash -n` passed.
- Wrapper tests verify exact tools, in-memory session flag, cleanup, explicit second extension, and missing-collector warning without blocking launch.
- Shared observer suite independently exercises offline real SDK in-memory retry/follow-up/terminating-tool/error/abort scenarios and enabled/disabled provider-context equality. Those are SDK tests, not a complete Focus embedded-session acceptance.

## Disposable desktop evidence

`tests/preview_run_metrics.py` uses temporary HOME/config/cache/state and a separately identified synthetic application ID/window. It never invokes a provider or reads a real case.

Linux Computer Use inspected the live preview: Copy Trace absent; Answer and Session present; synthetic answer artifact revisions 1 and 2 accepted, with revision 2 visibly rendered and its phrase styled. Clicking Session displayed the terminal. Clicking Answer was accepted through AT-SPI; the subsequent screenshot was blocked by a transient loss of the GNOME window-control service, so that final visual return is not claimed. The preview emitted a GTK min-content-height warning under its narrow synthetic layout; this was not changed as part of trace removal. The disposable process was closed afterward.

## Remaining

Full synthetic wrapper + real SDK + terminating Focus tool + artifact comparison enabled/disabled, actual interactive follow-up/retry record counting inside the pilot UI, and the shared collector's remaining reload/resume/branch/compaction acceptance. The full four-app rollout is not complete; see sibling PiRunMetrics README. No claims about substantive answer quality.
