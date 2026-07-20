# Focus

<img src="focus.png" alt="Focus" width="128" align="left">

Focus is a GTK4/Libadwaita desktop app for navigating a local appellate record
or court-transcript bundle. It combines citation-aware text and image browsing,
record search, organized summary files, configurable LLM workflows, and an
embedded PI Agent for deeper read-only record questions.

Focus is designed primarily for a `case_bundle` created by
[RecordPrep](https://github.com/jessemcg/record-prep), while retaining support
for its earlier `text_record/` and `images/` layout.

## Features

- One-page transcript browsing with record citation labels such as `2CT 606`.
- Citation-aware page jumps, first/last and previous/next navigation, and a TOC
  sidebar.
- Gap-tolerant record grep with per-match navigation and highlighted results.
- Scanned-page image viewing, image previews, and page/image printing.
- Direct navigation between a hearing transcript and its corresponding minute
  order when boundary metadata is available.
- Searchable hearing, report, and minute-order summary views with bookmarks,
  record links, progress, and printing.
- AI panel workflows for single-page and page-range summaries, information
  extraction, RAG questions, RAG audit output, and organized summary files.
- Four configurable LLM profiles with per-task defaults and optional reasoning
  and priority-service settings.
- VoyageAI or Isaacus embeddings for local Chroma-based RAG.
- PI-only Agent questions in an embedded VTE terminal, with the final response
  mirrored into a formatted Answer view.
- PI model selection from the models currently authorized in PI.
- Record-citation insertion into Prose, clipboard fallback, keyboard shortcuts,
  and D-Bus actions for external speech-to-text launchers.
- Current-case integration that can repoint `config.json` at the selected case
  bundle.

## Requirements

- Python 3.13 or newer.
- [`uv`](https://docs.astral.sh/uv/).
- GTK 4, Libadwaita, PyGObject, and their system libraries.
- GTK VTE for the embedded Agent terminal.
- [PI](https://pi.dev/docs/latest) for Agent questions.
- RAG dependencies managed by `uv`, including LangChain, Chroma, VoyageAI, and
  Isaacus.

Ubuntu/Debian package names vary by release, but a typical GTK installation is:

```bash
sudo apt install python3-gi gir1.2-gtk-4.0 gir1.2-adw-1 gir1.2-vte-3.91
```

Install or synchronize the Python environment:

```bash
uv sync
```

### Install and Authorize PI

Focus uses only the
[PI coding agent](https://pi.dev/docs/latest) for embedded Agent questions.
Follow PI's official documentation to install it; Focus does not invoke the
Codex CLI or provide another coding-agent backend.

Authorize every provider you want to use before launching an Agent question:

1. Start `pi` in a separate terminal.
2. Enter `/login`.
3. Select the subscription or API-key provider.
4. Complete the browser login or enter the API key when PI prompts for it.
5. Open Focus Settings, select **Agent**, and refresh the **PI Model** row.

PI also accepts documented provider environment variables. For example, an API
key can be exported in the shell before launching Focus:

```bash
export FIREWORKS_API_KEY="your-api-key"
uv run focus
```

See PI's [quickstart](https://pi.dev/docs/latest/quickstart) and
[provider documentation](https://pi.dev/docs/latest/providers) for supported
providers and their environment-variable names.

Persistent PI authorization is stored in PI's user-level configuration,
including `~/.pi/agent/auth.json`. Do not put provider credentials in Focus's
`.pi/settings.json`, in a case bundle, or in a temporary Agent workspace. Focus
does not read or copy PI's credential file; the embedded terminal inherits
authorization because it runs PI as the same user.

The checked-in project default is
`fireworks/accounts/fireworks/routers/glm-5p2-fast`. The Agent page in Settings
lists the models PI reports as currently available and saves the selected
project-wide default to `.pi/settings.json`. A new selection applies to newly
launched Agent sessions; it does not restart an existing session.

## Run the App

Launch Focus with the case root stored in `config.json`:

```bash
uv run focus
```

Open a specific bundle without changing the saved case:

```bash
uv run focus /path/to/case_bundle
```

The explicit app subcommand is equivalent:

```bash
uv run focus app /path/to/case_bundle
```

Point Focus at the currently selected MCGLAW case bundle:

```bash
uv run focus refresh-current-case
```

Use `--quiet` for launcher scripts:

```bash
uv run focus refresh-current-case --quiet
```

Show the complete CLI:

```bash
uv run focus --help
```

## Record Layout

Focus auto-detects a RecordPrep bundle from `manifest.json`. A representative
layout is:

```text
case_bundle/
  manifest.json
  case_name.txt
  text_pages/
    0001.txt
    0002.txt
  image_pages/
    0001.png
    0002.png
  artifacts/
    toc.txt
    hearing_boundaries.json
    report_boundaries.json
    minutes_boundaries.json
    transcript_page_numbers.json
    transcript_page_number_series.md
    source_map.json
  summaries/
    hearings_sum_organized.txt
    reports_sum_organized.txt
    summarized_minutes.txt
  rag/
    case_overview.txt
    vector_database/
```

The manifest may point to alternate artifact or summary paths. Images,
summaries, boundary files, and RAG assets are optional for ordinary transcript
browsing. Citation-aware Agent answers require a usable
`artifacts/source_map.json`.

The legacy layout remains supported:

```text
case_root/
  text_record/
    0001.txt
    0002.txt
    toc.txt
  images/
    0001.png
    0002.png
```

## Configuration

The Settings window is the primary configuration interface. Machine-local
settings are stored in project-root `config.json`, which is ignored by Git
because it can contain credentials and case-specific paths.

Current settings include:

- Record location, font family and sizes, highlight phrases, and UI colors.
- Four model profiles containing a nickname, abbreviation, API URL, model ID,
  API key, reasoning toggle, and priority-service toggle.
- Default profiles for single-page summaries, page-range summaries,
  information extraction, and RAG answers.
- Page, range, extraction, and RAG prompt templates.
- VoyageAI and Isaacus embedding models and API keys.
- RAG provider, context-chunk count, answer model, and optional audit/deep
  answer model.
- Speech-to-text question-file location for external launchers.
- `pi_agent_command`, which can point Focus at a particular PI executable and
  include compatible options such as a thinking level.

Older individual API URL/model/key fields remain readable for compatibility,
but Settings writes the current model-profile structure. PI provider/model
selection is intentionally separate from `config.json`: it is stored in
`.pi/settings.json`, while PI authorization stays in PI's user configuration.

## Agent Questions

Focus launches PI interactively in the embedded terminal. It does not replace
the terminal session with an RPC Agent backend. A short-lived, offline,
no-session PI RPC process is used only when Settings asks PI for its currently
available models.

Record-question instructions live in
`.pi/skills/focus-answer-record-questions/SKILL.md`. Focus sends PI only the
skill invocation, the user's question, and the current record citation when one
is available.

For each Agent question, Focus:

1. Creates a temporary workspace.
2. Copies the project `.pi` settings and skill into that workspace.
3. Starts PI with `read`, `bash`, `grep`, `find`, and `ls`.
4. Gives the skill access to the active case bundle and the read-only
   `focus.agent_helper` citation lookup.
5. Watches PI's session log and mirrors the latest final answer into the Answer
   view.
6. Removes the temporary workspace when the embedded session ends.

The skill prohibits edits to case files, external web research, and use of the
RAG/vector database. PI searches record text with its ripgrep-backed `grep`
tool, then resolves final citations through `source_map.json`. When a question
depends on visual details such as checkboxes, signatures, handwriting, stamps,
tables, form layout, or ambiguous OCR, the skill can selectively inspect the
paired page image with PI's `read` tool. Image paths are resolved against the
active case bundle at runtime and remain internal to the Agent. A model without
image support must rely on adequate text evidence or state that the visual fact
could not be verified. Focus's separate RAG panel remains available for
vector-based questions.

Command-line model, provider, session, skill, trust, and tool overrides are
rejected for embedded Agent sessions so that project policy remains in force.

## Summaries and RAG

Page summaries, range summaries, and extraction use the selected LLM profile
and prompt from Settings. The profile selector in the AI panel can temporarily
choose another configured profile for a request.

RAG requires:

- `rag/vector_database/`, or the corresponding manifest path.
- `rag/case_overview.txt`, or a supported legacy overview.
- Valid VoyageAI or Isaacus embedding credentials.
- A configured LLM profile for the answer.

The RAG Audit view exposes the retrieved context and request details used for a
question. Organized hearing, report, and minute-order summaries are ordinary
local text/Markdown files and do not require RAG.

## Keyboard and External Commands

Common shortcuts:

- Up / Down: previous or next page.
- Home / End: first or last page.
- Ctrl+E: focus the page field; accepts citations such as `2CT 606`, bare
  transcript pages such as `606`, and file pages such as `file 0876`.
- Ctrl+F: focus record grep.
- Ctrl+G / Ctrl+Shift+G: next or previous grep match.
- Ctrl+Shift+Z: toggle the TOC sidebar.
- Ctrl+I: toggle scanned-image view.
- Ctrl+Shift+A: show case tools and focus the question area.
- Ctrl+Q: focus the RAG question field.
- Ctrl+Alt+Shift+C: insert the current record citation into Prose or copy it.
- Ctrl+Alt+C: start or complete a record citation range.
- F1: open the complete keyboard shortcut reference.

The app menu's **D-Bus Commands** window lists runnable and copyable commands
for page navigation, grep, citation insertion, and speech-submitted RAG or Agent
questions.

## Project Layout

- `focus/app.py`: main GTK/Libadwaita application and record/AI workflows.
- `focus/core.py`: shared settings, record parsing, search, citation,
  rendering, RAG, and PI session-log helpers.
- `focus/pi_runtime.py`: PI model discovery and atomic project-model settings.
- `focus/cli.py`: `focus` command dispatcher.
- `focus/current_case.py`: current-case to `config.json` integration.
- `focus/agent_helper.py`: read-only source-map lookup for Agent sessions.
- `focus/ui/`: Settings and D-Bus command windows.
- `scripts/focus-agent-vte.sh`: temporary-workspace and embedded PI launcher.
- `.pi/settings.json`: project-wide PI provider and model; no credentials.
- `.pi/skills/focus-answer-record-questions/SKILL.md`: record research and
  citation policy.
- `tests/`: automated regression tests.
- `pyproject.toml`: Python runtime, package metadata, and dependencies.

## Local Files and Credentials

Do not commit:

- `config.json`, which can contain LLM, embedding, and case-path settings.
- Client case bundles or record text/images.
- `.venv/`, `.pytest_cache/`, `__pycache__/`, and other generated caches.

The tracked `.pi/settings.json` is safe to share only because it contains the
provider/model choice and skill settings, not authorization. PI credentials
belong in PI's user-level configuration or provider environment variables.

## Tests

Run the complete test suite:

```bash
UV_CACHE_DIR=/tmp/focus-uv-cache uv run pytest -q
```

Run syntax and shell checks:

```bash
uv run python -m py_compile focus/*.py focus/ui/*.py
bash -n scripts/focus-agent-vte.sh
git diff --check
```

For UI changes, also open a sanitized bundle and exercise transcript paging,
grep, TOC navigation, image view, summaries, RAG, PI model refresh/save, and a
new embedded Agent session.

## License

GPL-3.0-or-later. See `LICENSE`.
