# Repository Guidelines

## Project Structure & Module Organization
- `focus.py`: python and Libadwaita application entry point for browsing case transcripts. Holds UI wiring, grep logic.
- `focus (Copy).py`: prior iteration retained for reference; avoid editing unless you intend to port fixes back.
-  Always use modern Libadwaita GUI elements over plain vanilla GTK4. Buttons should always be in the flat style.
- `useful_code_from_dogear/`: auxiliary scripts (`copy_by_number.py`, `pdf_marker.py`, `post_processing/remove_dup_lines.py`) reused for preprocessing source material. `regexes/Reporters_Transcript.txt` stores sample regex patterns.
-  Ultimatly, `focus.py` will adopt many of the features from doghear. Therefore, reference code in `useful_code_from_dogear/` to get ideas on how to impliment similar features in `focus.py`. However, dogear was made with gnome 48 and grephound is still on gnome 46 so some of the styling will not transfer over.
-  The `prior_versions` directory contains major versions that I might need to roll back to, so don't touch them.
- `pyproject.toml` and `uv.lock`: define the Python 3.12 runtime and PyGObject dependency; keep them in sync when adding packages.

## Build, Test, and Development Commands
- `uv sync`: resolve and install dependencies into the managed environment.
- `uv run python focus.py`: launch the GTK viewer using the active case configuration.
- `PYTHONPATH=. uv run python useful_code_from_dogear/post_processing/remove_dup_lines.py`: example pattern for executing helper scripts; adjust inputs via script arguments or module constants.

## Coding Style & Naming Conventions
- Follow PEP 8: 4-space indentation, snake_case for functions and variables, CapWords for classes.
- Preserve existing type hints and annotate new GTK callbacks for clarity.
- Keep module-level configuration grouped near the top of each script; prefer constants with uppercase snake_case.

## Testing Guidelines
- Automated tests are not yet in place; add new coverage under `tests/` using `pytest` when introducing non-trivial logic.
- For UI changes, exercise core flows manually: open a transcript, step pages, run a grep search, and verify highlight colors.
- Document any manual test steps in PR descriptions until automated coverage exists.

## Commit & Pull Request Guidelines
- Repository history is empty; adopt imperative, scope-leading commit messages (e.g., `Add combined grep view toggle`).
- One logical change per commit; keep case configuration edits separate from features.
- PRs should summarize user-facing changes, reference related case IDs, and include screenshots or short screen recordings for UI updates.
- Ensure the commands above succeed on a clean checkout before requesting review.

## Case Configuration Notes
- Do not commit real client data; point `CASE_DIR` at sanitized fixtures when possible.
- Store machine-specific credentials outside the repo and reference them via environment variables if scripting requires access.
