# Repository Guidelines

## Project Structure & Module Organization
- `focus/`: Python package for the Libadwaita GTK4 app and helper CLIs.
- `focus/app.py`: main `Focus` application class; owns transcript browsing, TOC sidebar, dual-view state, image view, grep, AI tools, and embedded Agent orchestration.
- `focus/core.py`: shared constants, dataclasses, config helpers, record layout/index parsing, summary discovery, citation formatting, and markdown/link rendering.
- `focus/pi_runtime.py`: PI runtime integration for authenticated model discovery and atomic updates to the project-local PI provider/model setting.
- `focus/cli.py`: `focus` console command. Keep GUI/helper launch behavior routed through this module instead of adding root entry scripts.
- `focus/current_case.py`: updates project-root `config.json` from the shared currently selected case file.
- `focus/agent_helper.py`: read-only compact research context, source-map lookup, targeted map inspection, and database-free per-query diversified lexical search with source-date/document ranking used by embedded PI Agent sessions.
- `focus/agent_answer.py`: non-blocking answer lint categories plus strict app-owned answer-artifact parsing and runtime cleanup helpers.
- `focus/ui/`: secondary Libadwaita windows such as settings and D-Bus command reference.
- `.pi/settings.json`: project-local PI provider/model selection for embedded Agent sessions.
- `.pi/SYSTEM.md`: short identity, evidence-scope, and safety prompt copied into each private embedded-Agent workspace; the explicit skill is canonical for workflow and answer style.
- `.pi/skills/focus-answer-record-questions/SKILL.md`: canonical embedded-Agent record research and citation instructions.
- `.pi/extensions/focus-record-agent.ts`: the sole explicitly loaded extension. It registers the shell-free structured record tool and terminating answer handoff, guards text-page access, leaves the provider/model output limit unchanged (no Focus-imposed token cap or search/page/map budget), and captures one best-effort fallback answer.
- `scripts/focus-agent-vte.sh`: launches an ephemeral `--no-session` embedded Agent with extension discovery disabled and exactly the staged Focus extension loaded explicitly. It passes the staged system prompt and skill and restricts tools to `read,focus_record,submit_focus_answer`; corpus-wide grep is unavailable.
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
- For UI changes, exercise core flows manually: open a transcript, step pages, run grep, toggle TOC sidebar, switch views, try image view, and verify summary/extraction plus Agent Q&A flows.
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
