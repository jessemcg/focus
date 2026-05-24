# Focus

<img src="focus.png" alt="Focus" width="128" align="left">

Focus is a Libadwaita GTK4 app for browsing court transcript text files with fast paging, grep, images, and AI-assisted summaries/RAG. It is designed to work with a "case_bundle" created with [recordprep](https://github.com/jessemcg/record-prep).

## Features
- Displays one text page at a time, with optional continuous scroll mode
- Mouse wheel scrolls within the current record; hold Ctrl + wheel to load previous/next page
- Page jump (Ctrl+E), gap-tolerant grep (Ctrl+F), and TOC sidebar for navigation
- Grep matches render in red and can show all matching pages in a single scrollable view
- Toggle image view for page scans (Ctrl+I) when images are available
- Dual view buttons to keep two independent browsing states side by side
- AI panel with page/range summaries, RAG Q&A, and a summary-file viewer
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
uv run python focus.py
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
  rag/
    case_overview.txt
    vector_database/
```

## Configuration
Settings are stored in `config.json` next to `focus.py`. Key fields include:
- `input_dir`: root folder for transcripts
- `font_size_pt`, `ai_font_size_pt`
- `highlight_phrases`: newline-separated phrases to highlight
- Summaries: `api_url`, `api_key`, `model_id`, plus `summarization_prompt`
- Page/range summaries: `page_api_url`, `page_api_key`, `page_model_id`, `page_summarization_prompt`,
  `range_api_url`, `range_api_key`, `range_model_id`, `range_summarization_prompt`
- RAG: `rag_api_url`, `rag_api_key`, `rag_model_id`, `rag_prompt`, `rag_chunk_count`
- RAG embeddings: `voyage_api_key`, `voyage_model`
- Summary file viewer: `summary_file`, `summary_read_positions`

Defaults are defined in `focus.py` if a key is missing.

## Project structure
- `focus.py`: application entry point and core UI/logic
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
- Ctrl+E: page jump
- Ctrl+F: grep search
- Ctrl+Shift+A: toggle AI panel
- Ctrl+Shift+C: toggle continuous view
- Ctrl+Shift+Z: toggle TOC sidebar
- Ctrl+I: toggle image view

## License
GPL-3.0-or-later. See `LICENSE`.
