# Repository Guidelines

## Project Structure & Module Organization
- `focus/`: Python package for the Libadwaita GTK4 app and helper CLIs.
- `focus/app.py`: main `Focus` application class; owns transcript browsing, the always-visible TOC sidebar (Forms first, then Hearings/Reports/Minute Orders to match the Case Tools strip), the always-visible Case Tools panel, dual-view state, image view, grep, summary browsing, and embedded Agent orchestration.
- `focus/core.py`: shared constants, dataclasses, config helpers, record layout/index parsing, summary discovery, citation formatting, and markdown/link rendering.
- `focus/pi_runtime.py`: PI runtime integration for authenticated model discovery and atomic updates to the project-local PI provider/model setting.
- `focus/cli.py`: `focus` console command. Keep GUI/helper launch behavior routed through this module instead of adding root entry scripts.
- `focus/current_case.py`: updates project-root `config.json` from the shared currently selected case file.
- `focus/agent_helper.py`: read-only compact research context, source-map lookup, targeted map inspection, and database-free per-query diversified lexical search with source-date/document ranking used by embedded PI Agent sessions.
- `focus/summary_editions.py`: strict page-map loader and page renderer for RecordPrep's page-matched summary editions; accepts every supported RecordPrep schema/layout pairing (schema v1 with current v2 or legacy v1 Letter editions, schema v2 with the v3 Letter edition that records bold quoted-phrase spans) and validates sidecars as a unit (hashes, paths, link and quote spans) without repaginating or parsing the PDF layout, exposing the loaded `layout_id` and `schema_version` for migration and state decisions. Paginated display text applies a paragraph-spacing transformation (newline runs collapse to exactly one empty line, never at page edges or across paper-page boundaries) for display and paginated search only; stored sidecar text, link offsets, and legacy continuous summaries are unchanged. Schema v2 editions additionally expose a structured paginated display representation (literal text plus validated bold/phrase and page-link spans remapped through the paragraph-spacing transformation, with page-link syntax reinserted only for the legacy entry-emphasis patterns); legacy editions keep the established link-synthesis pipeline.
- `focus/agent_answer.py`: non-blocking answer lint categories plus strict app-owned answer-artifact parsing and runtime cleanup helpers.
- `focus/agent_followup.py`: GTK-independent client and protocol types for the bounded Unix-socket follow-up bridge; creates/removes the application-owned runtime directory, validates path/token/type, and raises typed busy/unavailable/uncertain/protocol failures without queueing or replaying prompts.
- `focus/answer_metadata.py`: GTK-independent recognition of the leading `# Title` / `*Subtitle*` answer metadata, normalized labels, and the protected metadata-prefix offset used to keep those labels out of transcript-search link targets.
- `focus/answer_presentation.py`: GTK-independent saved-date and quality-status formatting shared by the displayed answer context line and the saved-answer popover rows; malformed dates degrade to readable text.
- `focus/reading_position.py`: bounded least-recently-used in-memory cache of per-answer viewport anchors plus scroll fractions; eviction only loses a reading position.
- `focus/saved_answers.py`: durable per-case saved-answer store at `<record-layout-root>/.focus/saved-answers/<answer-uuid>.json`, with typed GTK-independent list/load/save/delete results, atomic private publication, and safe handling of malformed, unknown-schema, symlinked, hard-linked, special, or broad-permission entries.
- `focus/ui/`: secondary Libadwaita widgets and windows such as the saved-answer split-button popover, settings, and the D-Bus command reference.
- `.pi/settings.json`: Git-ignored local PI provider/model selection for embedded Agent sessions. The application seeds it from `DEFAULT_PROJECT_PI_SETTINGS` in `focus/pi_runtime.py` when missing; never commit it.
- `.pi/SYSTEM.md`: short identity, evidence-scope, and safety prompt copied into each private embedded-Agent workspace; the explicit skill is canonical for workflow and answer style.
- `.pi/skills/focus-answer-record-questions/SKILL.md`: canonical embedded-Agent record research and citation instructions and the canonical titled-answer style (opening `# Title` plus `*Subtitle*`, then the substantive body). `.pi/SYSTEM.md` delegates to this skill rather than duplicating the style rule; title/subtitle formatting is non-blocking and never triggers a retry.
- `.pi/extensions/focus-record-agent.ts`: the sole model-facing explicitly loaded extension. It registers the shell-free structured record tool and terminating answer handoff, guards text-page access, leaves the provider/model output limit unchanged (no Focus-imposed token cap or search/page/map budget), and captures one best-effort fallback answer.
- `.pi/extensions/focus-followup-bridge.ts`: the explicitly loaded, non-model-facing follow-up bridge. It starts a private Unix-domain socket on `session_start`, closes/unlinks it idempotently on `session_shutdown`, tracks starting/busy/ready/closed state from `agent_start`/`agent_settled`, rejects concurrent or non-idle submissions, and forwards literal user text with `pi.sendUserMessage(text, { expandPromptTemplates: false })`. It registers no tools and must never read transcripts, prompts, or credentials.
- `scripts/focus-agent-vte.sh`: disables extension discovery, explicitly loads the staged Focus record extension, the staged follow-up bridge when present, and the optional sibling `PiRunMetrics/run-collector.ts` observer, and uses `--no-session`. Preserve live follow-ups, answer artifacts, workspace cleanup, and exactly `read,focus_record,submit_focus_answer`. The observer registers no tools and must not alter prompts or results. Copy Trace and transcript preservation are removed; old archives remain untouched. By Jesse's explicit storage preference, metrics default to the Git-ignored project directory `.run-metrics/runs/` (which may sync through Dropbox), with private permissions. A separate Focus-owned saved-answer library (`<case>/.focus/saved-answers/`) is user-invoked only (the Save Answer control) and must never be written by metrics, tests, or one-off commands. Preserve the absolute `PI_RUN_METRICS_ROOT` override. Never store transcripts, use case bundles, modify private configuration, or migrate/delete old archives implicitly.
- `config.json`: user-specific settings (input_dir, font sizes, API credentials, prompts); do not commit secrets.
- `legacy_versions/`: historical snapshots; avoid editing unless you intend to port fixes back.
- `prompts/`: change notes and UI prompt history.
- Always use modern Libadwaita GUI elements over plain vanilla GTK4. Buttons should always be in the flat style.
- `pyproject.toml` and the local ignored `uv.lock`: define the Python 3.13 runtime and dependencies (PyGObject and markdown-it-py); keep the environment in sync when packages change.

## Build, Test, and Development Commands
- `uv sync`: resolve and install dependencies into the managed environment.
- `uv run focus`: launch the GTK viewer using the active case configuration.
- `uv run focus /path/to/case_bundle`: launch Focus with a one-time input directory override.
- `uv run focus refresh-current-case --quiet`: update Focus `config.json` from the currently selected case.
- `uv run python -m focus.agent_helper --case-root /path/to/case_bundle context --json`: read the navigation-only overview prose and compact source-map capabilities before choosing search terms.
- `uv run python -m focus.agent_helper --case-root /path/to/case_bundle overview --json`: read the optional nonauthoritative case overview.
- `uv run python -m focus.agent_helper --case-root /path/to/case_bundle map --section documents --json`: inspect a targeted citation-aware source-map section; unsectioned output remains available for direct diagnostics.
- `uv run python -m focus.agent_helper --case-root /path/to/case_bundle lookup --file text_pages/0001.txt --json`: resolve a searched text page to its record citation.
- `uv run python -m focus.agent_helper --case-root /path/to/case_bundle search --query "placement" --json`: scan source pages without creating an index or database; defaults to six compact matches and omits attribution arrays.

## Coding Style & Naming Conventions
- Follow PEP 8: 4-space indentation, snake_case for functions and variables, CapWords for classes.
- Preserve existing type hints and annotate new GTK callbacks for clarity.
- Keep module-level configuration grouped near the top of each script; prefer constants with uppercase snake_case.

## Testing Guidelines
- Add or update coverage under `tests/` using `pytest` when introducing non-trivial logic.
- For UI changes, exercise core flows manually: open a transcript, step pages, run grep, switch between Agent Q&A and the Hearings/Reports/Minute Orders summaries, try image view, and verify the TOC sidebar and Case Tools panel are always visible.
- For Agent answer switching, run the bounded synthetic acceptance harness: `uv run python tests/acceptance_answer_switching.py` (optionally under `G_DEBUG=fatal-criticals`). It uses a temporary HOME/XDG, a unique application id, synthetic saved answers plus a paginated schema-v2 hearing edition and a continuous report summary, and exits non-zero on any GTK critical, wrong final view, or identity mismatch. It makes no model calls and never touches a real case.
- Document any manual test steps in PR descriptions until automated coverage exists.

## Commit & Pull Request Guidelines
- Repository history is empty; adopt imperative, scope-leading commit messages (e.g., `Add combined grep view toggle`).
- One logical change per commit; keep case configuration edits separate from features.
- PRs should summarize user-facing changes, reference related case IDs, and include screenshots or short screen recordings for UI updates.
- Ensure the commands above succeed on a clean checkout before requesting review.

## Case Configuration Notes
- Do not commit real client data; point `input_dir` at sanitized fixtures when possible.
- `input_dir` can be a legacy transcript root (`text_record/`, `images/`) or a record_prep root with `manifest.json`.
- RecordPrep layout expects `text_pages/`, optional `image_pages/`, `artifacts/toc.txt`, an optional nonauthoritative `artifacts/case_overview.md`, and a citation-aware `artifacts/source_map.json`; current schema-v2 bundles may include participant-index schema v2 with separate counsel, non-counsel participant, witness, and examination metadata.
- Summary files can live under `summaries/` (hearing/reports) or be referenced via `manifest.json` using `summarized_minutes`.
- Store machine-specific credentials outside the repo and reference them via environment variables or local `config.json`.
