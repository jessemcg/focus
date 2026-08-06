# Focus

Focus is a GTK4/Libadwaita desktop app for reading appellate-record text and page images, navigating official RT/CT citations, searching extracted text, viewing RecordPrep summaries, and asking citation-grounded questions through an embedded PI Agent.

## Features

- Page-by-page transcript reading with TOC navigation, page images, printing, and bookmarks.
- Fast ordinary grep with hit navigation and configurable highlighting.
- Official transcript-page/citation lookup from RecordPrep metadata.
- Page and range summarization plus structured information extraction through configurable OpenAI-compatible model profiles.
- Organized hearing, report, and minute-order summary views.
- Agent Q&A in an embedded VTE terminal with a mirrored final answer.
- Read-only, source-map-aware Agent research over the original `text_pages`.
- Database-free helper search with OCR normalization, participant/document scopes, ranked snippets, and record citations.
- Hearing-scoped counsel, witness, and examination context when the bundle has source-map schema v2.
- D-Bus actions for desktop automation and speech-submitted Agent questions.

Focus does not load embeddings, retrieval chunks, Chroma, or any other vector database.

## Requirements

- Python 3.13+
- GTK4 and Libadwaita
- GTK4 VTE (`gir1.2-vte-3.91` and `libvte-2.91-gtk4-0`) for the embedded Agent terminal
- [uv](https://docs.astral.sh/uv/)
- [PI](https://pi.dev/docs/latest) for Agent questions
- A running/configured OpenAI-compatible service only for Focus's optional page/range summary and extraction tools

Install the Python environment:

```bash
uv sync
```

## Install and authorize PI

Install PI and authorize the providers/models you intend to use. Focus copies only its checked-in `.pi` project resources into a disposable workspace; credentials remain in PI's global auth store.

In **Settings → Agent**:

1. Confirm the PI command.
2. Refresh and select the PI model.
3. Choose reasoning effort and Priority preference when available.
4. Confirm the speech-to-text question file. Its default is `/dev/shm/speech.txt`.

New selections apply to newly launched Agent sessions. Focus rejects command-line flags that would override the checked-in project policy.

## Run the app

```bash
uv run focus
```

Or:

```bash
uv run python -m focus
```

The desktop launcher is maintained separately in `config_files/Desktop_Files`.

## Record layout

Focus accepts RecordPrep case bundles such as:

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
    participant_index.json
    source_map.json
  summaries/
    hearings_sum_<case>.txt
    hearings_sum_<case>_organized.txt
    reports_sum_<case>.txt
    reports_sum_<case>_organized.txt
    minutes_sum_<case>.txt
```

Only `text_pages` is required for basic browsing. Citation-grounded Agent answers require `artifacts/source_map.json`. Source-map v1 remains searchable; participant-aware scopes and attribution require RecordPrep source-map v2.

## Configuration

Focus stores local application settings in `config.json` (ignored by Git). Settings include:

- Input directory.
- Model profiles for single-page summary, page-range summary, and extraction.
- Prompt templates for those three tools.
- PI Agent command and speech question file.
- Fonts, highlight phrases, and colors.

Obsolete embedding/vector-question credentials and settings are removed when configuration is loaded or saved. Never commit `config.json` or API keys.

## Agent questions

For every question, Focus creates a private disposable workspace, stages `.pi/SYSTEM.md`, the explicit `focus-answer-record-questions` Agent Skill, PI settings, and the Priority extension, and launches PI with read-oriented tools. The case bundle remains outside the workspace and is treated as read-only evidence.

The Agent workflow is:

1. Read `source_map.json` with `focus/agent_helper.py map --json`.
2. Inspect document ranges and hearing-scoped participant/witness metadata.
3. Run one on-demand helper scan with several query variants and optional date/document/witness/counsel/current-citation scopes.
4. Read every relevant source page and adjacent context.
5. Resolve and cite official labels such as `2RT 44` or `CT 140`.
6. Broaden aliases and terms before reporting that a fact could not be located.

Search snippets, participant entries, and summaries are navigation leads, not proof. The Agent must verify material claims from source pages and use images only for genuinely visual ambiguities. The helper creates no index, cache, or database.

Run the helper directly:

```bash
uv run python -m focus.agent_helper \
  --case-root /path/to/case_bundle map --json

uv run python -m focus.agent_helper \
  --case-root /path/to/case_bundle search \
  --query "maternal grandmother placement" \
  --query "placed with maternal grandmother" \
  --hearing-date "January 2, 2025" --json
```

## Summaries

Focus displays RecordPrep's source and organized hearing, report, and minute-order summaries. In new bundles, hearing summaries begin with deterministic `Counsel:` and `Testimony:` lines generated from the validated participant index. Summary prose is still nonauthoritative and must be checked against the record for Agent answers.

Focus's own page/range summary and extraction tools are independent of Agent Q&A and use the configured model profiles.

## Keyboard and external commands

Important shortcuts:

- Up/Down: previous/next record page.
- Home/End: first/last page.
- Ctrl+F: transcript grep.
- Ctrl+Q: focus Agent Q&A.
- Ctrl+Shift+A: toggle case tools and focus Agent Q&A when opened.
- Ctrl+I: toggle the page image.
- F1: keyboard shortcuts.

Public question actions:

```text
focus_agent_question
submit_speech_agent_question
```

Example:

```bash
gdbus call --session \
  --dest com.mcglaw.Focus \
  --object-path /com/mcglaw/Focus \
  --method org.gtk.Actions.Activate \
  submit_speech_agent_question '[]' '{}'
```

## Project layout

- `focus/app.py`: GTK application, transcript browsing, summaries, and Agent orchestration.
- `focus/core.py`: shared config, record layout, citation, and rendering helpers.
- `focus/agent_helper.py`: read-only map/lookup/document/search CLI for Agent sessions.
- `focus/ui/settings.py`: settings UI.
- `focus/ui/commands.py`: D-Bus command reference.
- `scripts/focus-agent-vte.sh`: disposable PI workspace launcher.
- `.pi/`: checked-in PI system prompt, explicit Agent Skill, settings, and Priority resources.
- `tests/`: pytest coverage.

## Tests

```bash
uv run pytest
uv run python -m compileall -q focus tests
bash -n scripts/focus-agent-vte.sh
```

For a manual smoke test, open a schema-v2 bundle, verify that Agent Q&A is the only record-question view, run a participant-scoped question, confirm the final answer cites actual record labels, and verify that no search index or database is created.

## License

See `LICENSE`.
