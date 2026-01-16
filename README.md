# Focus

![Focus](focus.png)

Focus is a Libadwaita GTK4 app for browsing court transcript text files with fast paging, grep, and AI-assisted summaries.

## Features
- Displays one text file at a time from a configurable directory
- Mouse wheel scrolls within the current record; hold Ctrl + wheel to load previous/next page
- Page jump entry (Ctrl+E) and gap-tolerant grep entry (Ctrl+F) stay in the header
- Grep matches render in red and can show all matching pages in a single scrollable view
- Ctrl+Shift+A opens the AI panel and focuses the RAG question box
- Keyboard shortcuts: Up/Down = previous/next, Home/End = first/last

## Requirements
- Python 3.12 (see `pyproject.toml`)
- PyGObject, GTK 4, Libadwaita 1

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
uv run focus.py
```

## Data layout
Example transcript folder structure (set `input_dir` to the case root):
```
case_root/
  text_record/
    0001.txt
    0002.txt
  images/
    0001.jpg
    0002.jpg
```

## Configuration
Settings are stored in `config.json` next to `focus.py`. Key fields include:
- `input_dir`: root folder for transcripts
- `regex_dir`: folder containing regex patterns
- AI settings: `api_url`, `model_id`, `api_key`, and related summarization/RAG keys

Defaults are defined in `focus.py` if a key is missing.

## Project structure
- `focus.py`: application entry point and core UI/logic
- `focus (Copy).py`: prior iteration retained for reference
- `useful_code_from_dogear/`: helper scripts and reference implementations
- `legacy_versions/`: historical backups (do not edit)
- `pyproject.toml`, `uv.lock`: dependency and runtime definitions

## Notes
- This project targets GNOME 46; some UI patterns in `useful_code_from_dogear/` are from GNOME 48.
- Automated tests are not set up yet.
