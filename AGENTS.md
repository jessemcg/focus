# Repository Guidelines

## Project Structure & Module Organization
- `focus.py`: Libadwaita GTK4 application entry point; handles transcript browsing, TOC sidebar, dual-view state, image view, grep, and AI panel (summaries + RAG).
- `config.json`: user-specific settings (input_dir, font sizes, API credentials, prompts); do not commit secrets.
- `legacy_versions/`: historical snapshots; avoid editing unless you intend to port fixes back.
- `prompts/`: change notes and UI prompt history.
- Always use modern Libadwaita GUI elements over plain vanilla GTK4. Buttons should always be in the flat style.
- `pyproject.toml` and `uv.lock`: define the Python 3.13 runtime and dependencies (PyGObject, langchain/chroma/voyageai); keep them in sync when adding packages.

## Build, Test, and Development Commands
- `uv sync`: resolve and install dependencies into the managed environment.
- `uv run python focus.py`: launch the GTK viewer using the active case configuration.

## Coding Style & Naming Conventions
- Follow PEP 8: 4-space indentation, snake_case for functions and variables, CapWords for classes.
- Preserve existing type hints and annotate new GTK callbacks for clarity.
- Keep module-level configuration grouped near the top of each script; prefer constants with uppercase snake_case.

## Testing Guidelines
- Automated tests are not yet in place; add new coverage under `tests/` using `pytest` when introducing non-trivial logic.
- For UI changes, exercise core flows manually: open a transcript, step pages, run a grep search, toggle TOC sidebar, switch views, try continuous view + image view, and verify AI panel summary/RAG flows.
- Document any manual test steps in PR descriptions until automated coverage exists.

## Commit & Pull Request Guidelines
- Repository history is empty; adopt imperative, scope-leading commit messages (e.g., `Add combined grep view toggle`).
- One logical change per commit; keep case configuration edits separate from features.
- PRs should summarize user-facing changes, reference related case IDs, and include screenshots or short screen recordings for UI updates.
- Ensure the commands above succeed on a clean checkout before requesting review.

## Case Configuration Notes
- Do not commit real client data; point `input_dir` at sanitized fixtures when possible.
- `input_dir` can be a legacy transcript root (`text_record/`, `images/`) or a record_prep root with `manifest.json`.
- Record-prep layout expects `text_pages/`, `image_pages/`, `artifacts/toc.txt`, and optional `rag/` assets (`vector_database/`, `case_overview.txt`).
- Summary files can live under `summaries/` (hearing/reports) or be referenced via `manifest.json` using `summarized_minutes`.
- Store machine-specific credentials outside the repo and reference them via environment variables or local `config.json`.
