# Focus

<img src="focus.png" alt="Focus" width="128" align="left">

Focus is a Libadwaita GTK4 app for browsing court transcript text files with fast paging, grep, images, and AI-assisted summaries/RAG. It is designed to work with a "case_bundle" created with [recordprep](https://github.com/jessemcg/record-prep).

## Features
- Displays one text page at a time with transcript citation-page context
- Mouse wheel scrolls within the current record; hold Ctrl + wheel to load previous/next page
- Page jump (Ctrl+E), transcript citation-page jump, gap-tolerant grep (Ctrl+F), and TOC sidebar for navigation
- Grep matches render in red and navigate hit-by-hit while keeping one transcript page visible
- Toggle image view for page scans (Ctrl+I) when images are available
- AI panel with page/range summaries, RAG Q&A, and a summary-file viewer
- Agent questioning through either Codex or PI in the same embedded terminal and answer view
- Markdown-style formatting for `*italic*`, `**bold**`, and `#`/`##`/`###` headings in transcript and summary text

## Requirements
- Python 3.13 (see `pyproject.toml`)
- PyGObject, GTK 4, Libadwaita 1
- LangChain + Chroma + VoyageAI (for RAG; managed by `uv`)

Ubuntu/Debian example:
```bash
sudo apt install python3-gi gir1.2-gtk-4.0 gir1.2-adw-1
```

## Setup
Use `uv` to create and sync the environment:
```bash
uv sync
```

## Run
```bash
uv run focus
```

To open a specific record root:
```bash
uv run focus /path/to/case_bundle
```

To point Focus at the currently selected MCGLAW case bundle:
```bash
uv run focus refresh-current-case
```

## Test
```bash
uv run pytest
```

## Data layout
Example legacy transcript folder structure (set `input_dir` to the case root):
```
case_root/
  text_record/
    0001.txt
    0002.txt
    toc.txt
  images/
    0001.png
    0002.png
```

Record-prep layout with `manifest.json` (auto-detected when present):
```
case_root/
  manifest.json
  text_pages/
    0001.txt
  image_pages/
    0001.png
  artifacts/
    toc.txt
    transcript_page_numbers.json
  rag/
    case_overview.txt
    vector_database/
```

## Configuration
Settings are stored in the project-root `config.json`. Key fields include:
- `input_dir`: root folder for transcripts
- `font_size_pt`, `ai_font_size_pt`
- `highlight_phrases`: newline-separated phrases to highlight
- Summaries: `api_url`, `api_key`, `model_id`, plus `summarization_prompt`
- Page/range summaries: `page_api_url`, `page_api_key`, `page_model_id`, `page_summarization_prompt`,
  `range_api_url`, `range_api_key`, `range_model_id`, `range_summarization_prompt`
- RAG: `rag_api_url`, `rag_api_key`, `rag_model_id`, `rag_prompt`, `rag_chunk_count`
- RAG embeddings: `voyage_api_key`, `voyage_model`
- Embedded Agent: `agent_runtime` (`codex` or `pi`), the runtime-specific command,
  and one shared `agent_prompt_template`
- Summary file viewer: `summary_file`, `summary_read_positions`

Defaults are defined in the package modules if a key is missing.

### Choosing an Agent

In Focus Settings, open the Agent page and choose either **Codex** or **PI**.
Both runtimes receive the same Focus record-question prompt and run in the same
embedded VTE terminal, with final responses mirrored into the same Answer view.
Codex remains the default for existing configurations.

The PI runtime uses the provider, model, and authentication configured in
`~/.pi/agent`. PI runs with the permissions of the user account that launched
Focus; the Codex sandbox setting applies only to Codex.

## Project structure
- `focus/`: Python package for the app and helper CLIs
- `focus/app.py`: Libadwaita GTK application class and main document/AI workflow
- `focus/core.py`: shared constants, dataclasses, config helpers, record parsing, search, citation, rendering, RAG, and agent utilities
- `focus/cli.py`: `focus` console command, including app launch and current-case refresh
- `focus/current_case.py`: currently selected case to Focus `config.json` integration
- `focus/agent_helper.py`: read-only record helper used by embedded Codex and PI Agent sessions
- `focus/ui/`: secondary windows, including settings and D-Bus commands
- `config.json`: local settings (do not commit secrets)
- `legacy_versions/`: historical backups (do not edit)
- `prompts/`: prompt history and change notes
- `tests/`: automated regression tests
- `pyproject.toml`, `uv.lock`: dependency and runtime definitions

## Notes
- RAG requires a populated `rag/vector_database` and a `rag/case_overview.txt` (or legacy case overview).

## Keyboard shortcuts
- Up/Down: previous/next page
- Home/End: first/last page
- Ctrl+E: page jump; accepts citation pages like `2CT 606`, bare transcript pages like `606`, and file pages like `file 0876`
- Ctrl+F: grep search
- Ctrl+Shift+A: toggle AI panel
- Ctrl+Shift+Z: toggle TOC sidebar
- Ctrl+I: toggle image view

## License
GPL-3.0-or-later. See `LICENSE`.
