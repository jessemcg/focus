# Repository Guidelines

Public source installation is standalone: see docs/source-install.md. Focus must
complete installation without Pi, login, model selection or paid verification.
Save the completed receipt and show success before offering optional Pi installation;
skipping/canceling/failing Pi must never turn Focus into an incomplete install.
Users authenticate with Pi `/login` afterward and choose models in Focus Settings.
The maintained runtime below is Jesse's separate workflow, not a public installer dependency.
Installer tests use disposable HOME/XDG/source/runtime paths and synthetic providers;
never run installers, onboarding or paid verification against real settings/credentials.

## README style

Keep `README.md` minimalistic and streamlined. Add only important user-facing
information, with explanations that are short and to the point. Put detailed
technical explanations, implementation notes and validation reports in `docs/`,
not the README.

## Machine-local runtime

Read ../UvEnvironments/README.md. Use `../UvEnvironments/project-env sync Focus`
for locked provisioning and `../UvEnvironments/project-env run Focus COMMAND`
for execution (managed Python 3.13, all hosts). Before any uv examples below, source
`../UvEnvironments/terminal.sh Focus` in a dedicated subshell and stop on failure;
it verifies local runtime and disables automatic sync/downloads. Cross-project calls
select the callee explicitly; same-project Python children use sys.executable.
Never create a Dropbox .venv or use production environments for disposable tests.

## Fixed research method (profile-free)

See `docs/research-method.md` and `docs/research-method-validation.md`. Every new
Q&A uses application-owned focus-record-qa v1, with no profile/store/selection
argument, confirmation or advanced option. Only `profile_contract.py` and
`profile_artifacts.py` remain vendored byte-identically with RecordPrep for historical
compatibility/validation. No UI/store/workflow parity requirement remains. Never
import sibling code or instructions at runtime; preparation provenance is descriptive.

`research_runtime.py` compiles and privately stages canonical application resources,
pins canonical case identity and consumed map/source inventory/content/manifest/overview,
and revalidates at launch, follow-up, helper operations and final/fallback capture.
Strip inherited FOCUS_RESEARCH_PROFILE_REF; it cannot authorize guidance or ranking.
Changed resources/inputs require a new session. Failed preflight preserves prior output.
`research_context.py` validates instruction-free metadata: schema 2 identifies the
fixed method and schema 1 remains historical without snapshot lookup. New saved answers
use schema 3; saved schemas 1/2 remain readable and must never be silently relabeled.
Retired private stores/config/prompts/answers remain untouched. No migration or bundle
regeneration. Search ranks literal match quality, frequency, coverage, proximity and
explicit dates, not specialty document/causal lists. Navigation aids never replace
verified original source text. Exactly read, focus_record, submit_focus_answer remain
model-facing; no shell/web/image/write tools or new dependencies.
Read RecordPrep participant schema 4 alongside legacy 2/3: role_label and counsel
represents are source descriptions, not a specialty role catalog. Preserve free-form
examiner labels in map context. RecordPrep profile content schema 4 removes roles
and participant instructions; the shared editor has no Participants / Witnesses area.
RecordPrep content schema 5 also removes overview instructions and the shared
RecordPrep editor's Case Overview category. Its fixed overview remains the same
five-section schema-1 nonauthoritative orientation consumed by Focus; historical
profile overview resources stay readable but inert. Focus always uses the fixed neutral method.

Keep private configuration/cases/profiles untouched. Configuration reads/startup
must not clean obsolete keys or write settings; explicit Settings saves retain their
established retired-key cleanup. Current neutral regressions are
`test_research_runtime.py`, `test_research_session_integration.py` and
`acceptance_neutral_method_ui.py`; profile-contract/consumer tests are historical
compatibility checks, not active research selection.
Preserve source-map schemas 1–3,
participant schemas 2–4/legacy forms and summary-edition layouts. Unknown specialty
identities are accepted; unknown structural schemas fail closed. Run isolated GTK
workflows and synthetic answer switching plus full pytest after runtime/UI changes;
use simulated/offline agents only unless live-model quality evaluation is separately
authorized. Older releases may not read schema-3 saved answers; never down-convert.

## Project Structure & Module Organization
- `focus/`: Python package for the Libadwaita GTK4 app and helper CLIs.
- `focus/app.py`: main `Focus` application class; owns transcript browsing, the always-visible TOC sidebar (Forms first, then Hearings/Reports/Minute Orders to match the Case Tools strip), the always-visible Case Tools panel, dual-view state, image view, grep, summary browsing, and embedded Agent orchestration.
- `focus/core.py`: shared constants, dataclasses, config helpers, record layout/index parsing, summary discovery, citation formatting, and markdown/link rendering. Minute-only exact line prefixes Appearances: / Orders: / Next: use the summary-emphasis tag in continuous and structured edition views, with the same theme-aware foreground, medium weight and normal scale as direct quotations, but not their quote/phrase links. Summary Emphasis Color is retired: ignore historical values without rewriting private settings. Current minute entries keep adjacent date/field lines and one blank line between entries, using the same display/search offset mapping. Preserve text, offsets, other summary kinds and edition schemas; see docs/minute-labels.md.
- `focus/pi_runtime.py`: PI runtime integration for authenticated model discovery and atomic updates to the project-local PI provider/model setting.
- `focus/cli.py`: `focus` console command. Keep GUI/helper launch behavior routed through this module instead of adding root entry scripts.
- `focus/current_case.py`: updates project-root `config.json` from the shared currently selected case file.
- `focus/agent_helper.py`: read-only compact research context, source-map lookup, targeted map inspection, and database-free per-query diversified lexical search with explicit-query-date proximity and specialty-neutral lexical ranking used by embedded PI Agent sessions.
- `focus/summary_editions.py`: strict page-map loader and page renderer for RecordPrep's page-matched summary editions; accepts every supported RecordPrep schema/layout pairing (schema v1 with current v2 or legacy v1 Letter editions, schema v2 with the v3 Letter edition that records bold quoted-phrase spans) and validates sidecars as a unit (hashes, paths, link and quote spans) without repaginating or parsing the PDF layout, exposing the loaded `layout_id` and `schema_version` for migration and state decisions. Paginated display text applies a paragraph-spacing transformation (normally one empty line per block; new minute fields stay adjacent with only one blank line between entries, never at page edges or across paper-page boundaries) for display and paginated search only; stored sidecar text, link offsets, and legacy continuous summaries are unchanged. Schema v2 editions additionally expose a structured paginated display representation (literal text plus validated bold/phrase and page-link spans remapped through the paragraph-spacing transformation, with page-link syntax reinserted only for the legacy entry-emphasis patterns); legacy editions keep the established link-synthesis pipeline.
- `focus/agent_answer.py`: non-blocking answer lint categories plus strict app-owned answer-artifact parsing and runtime cleanup helpers.
- `focus/agent_followup.py`: GTK-independent client and protocol types for the bounded Unix-socket follow-up bridge; creates/removes the application-owned runtime directory, validates path/token/type, and raises typed busy/unavailable/uncertain/protocol failures without queueing or replaying prompts.
- `focus/answer_metadata.py`: GTK-independent recognition of the leading `# Title` / `*Subtitle*` answer metadata, normalized labels, and the protected metadata-prefix offset used to keep those labels out of transcript-search link targets.
- `focus/answer_presentation.py`: GTK-independent saved-date, quality-status and research-provenance formatting for the saved-answer popover rows; malformed dates degrade to readable text. The Answer/Session header has no metadata line; snapshots and saved artifacts retain their metadata internally.
- `focus/reading_position.py`: bounded least-recently-used in-memory cache of per-answer viewport anchors plus scroll fractions; eviction only loses a reading position.
- `focus/research_runtime.py`: fixed-method resource compiler, private staging and canonical case/input session pins; never reads retired profile stores.
- `focus/research_context.py`: strict instruction-free context schema-1/2 metadata; historical profiles are descriptive only, new metadata records focus-record-qa.
- `focus/saved_answers.py`: strict schema-1/2/3 durable per-case saved-answer store at `<record-layout-root>/.focus/saved-answers/<answer-uuid>.json`, with typed GTK-independent list/load/save/delete results, atomic private publication, and safe handling of malformed, unknown-schema, symlinked, hard-linked, special, or broad-permission entries.
- `focus/ui/`: secondary Libadwaita widgets and windows such as the saved-answer split-button popover, settings, and the D-Bus command reference.
- Existing `.pi/settings.json` (or standalone XDG `pi/settings.json`): private PI provider/model selection for embedded Agent sessions. The application seeds it from `DEFAULT_PROJECT_PI_SETTINGS` in `focus/pi_runtime.py` when missing; never commit it.
- `focus/agent_resources/SYSTEM.md`: short identity, evidence-scope, and safety prompt copied into each private embedded-Agent workspace; the explicit skill is canonical for workflow and answer style.
- `focus/agent_resources/skills/focus-answer-record-questions/SKILL.md`: canonical embedded-Agent record research and citation instructions and the canonical titled-answer style (opening `# Title` plus `*Subtitle*`, then the substantive body). `focus/agent_resources/SYSTEM.md` delegates to this skill rather than duplicating the style rule; title/subtitle formatting is non-blocking and never triggers a retry.
- `focus/agent_resources/extensions/focus-record-agent.ts`: the sole model-facing explicitly loaded extension. It registers the shell-free structured record tool and terminating answer handoff, guards text-page access, leaves the provider/model output limit unchanged (no Focus-imposed token cap or search/page/map budget), and captures one best-effort fallback answer.
- `focus/agent_resources/extensions/focus-followup-bridge.ts`: the explicitly loaded, non-model-facing follow-up bridge. It starts a private Unix-domain socket on `session_start`, closes/unlinks it idempotently on `session_shutdown`, tracks starting/busy/ready/closed state from `agent_start`/`agent_settled`, rejects concurrent or non-idle submissions, and forwards literal user text with `pi.sendUserMessage(text, { expandPromptTemplates: false })`. It registers no tools and must never read transcripts, prompts, or credentials.
- `scripts/focus-agent-vte.sh`: disables extension discovery, explicitly loads the staged Focus record extension, the staged follow-up bridge when present, and the optional sibling `PiRunMetrics/run-collector.ts` observer, and uses `--no-session`. Preserve live follow-ups, answer artifacts, workspace cleanup, and exactly `read,focus_record,submit_focus_answer`. The observer registers no tools and must not alter prompts or results. Copy Trace and transcript preservation are removed; old archives remain untouched. By Jesse's explicit storage preference, metrics default to the Git-ignored project directory `.run-metrics/runs/` (which may sync through Dropbox), with private permissions. A separate Focus-owned saved-answer library (`<case>/.focus/saved-answers/`) is user-invoked only (the Save Answer control) and must never be written by metrics, tests, or one-off commands. Preserve the absolute `PI_RUN_METRICS_ROOT` override. Never store transcripts, use case bundles, modify private configuration, or migrate/delete old archives implicitly.
- `config.json`: user-specific settings (input_dir, fonts, highlights, Agent command and speech file); do not commit it.
- `legacy_versions/`: historical snapshots; avoid editing unless you intend to port fixes back.
- `prompts/`: change notes and UI prompt history.
- Always use modern Libadwaita GUI elements over plain vanilla GTK4. Buttons should always be in the flat style.
- `pyproject.toml` and the reproducible `uv.lock`: define the Python 3.13 runtime and dependencies (PyGObject and markdown-it-py); keep the environment in sync when packages change.

## Build, Test, and Development Commands
- `../UvEnvironments/project-env sync Focus`: explicitly provision locked local dependencies.
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
- Keep PI credentials in PI's global auth store, outside this repository; do not copy them into case bundles or `config.json`.
