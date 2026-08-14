# Focus

Focus is a GTK4/Libadwaita desktop app for reading appellate-record text and page images, navigating official RT/CT citations, searching extracted text, viewing RecordPrep summaries, and asking record-grounded questions through an embedded PI Agent.

## Features

- Page-by-page transcript reading with TOC navigation, page images, printing, and bookmarks.
- Fast Python-only record search with Unicode/OCR normalization, hit navigation, and configurable highlighting.
- Official transcript-page/citation lookup from RecordPrep metadata.
- Page and range summarization plus structured information extraction through configurable OpenAI-compatible model profiles.
- Hearing, report, and minute-order summary views, with legacy organized-summary compatibility.
- An organized Case Tools workspace with contextual controls for Agent Q&A, summaries, extraction, and page-range summarization.
- Agent Q&A in an embedded VTE terminal with a mirrored final answer and short clickable record quotes.
- Compact nonauthoritative case orientation and source-map capability checks before targeted research over the original `text_pages`.
- Database-free helper search with OCR normalization, participant/document scopes, ranked snippets, safe source paths, and record citations.
- Hearing-scoped counsel, non-counsel participant, witness, and examination context when the bundle has source-map schema v2.
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
3. Choose the reasoning effort.
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
    case_overview.md
    source_map.json
  summaries/
    hearings_sum_<case>.txt
    reports_sum_<case>.txt
    minutes_sum_<case>.txt
```

Only `text_pages` is required for basic browsing. Source-resolved Agent answers require `artifacts/source_map.json`. Source-map v1 remains searchable; participant-aware scopes and attribution require RecordPrep source-map v2.

## Configuration

Focus stores local application settings in `config.json` (ignored by Git). Settings include:

- Input directory.
- Model profiles for single-page summary, page-range summary, and extraction.
- Prompt templates for those three tools.
- PI Agent command and speech question file.
- Fonts, highlight phrases, and colors.

Obsolete embedding/vector-question credentials and settings are removed when configuration is loaded or saved. Never commit `config.json` or API keys.

## Agent questions

Open **Case Tools** from the labeled header control and select **Agent Q&A**. The question composer provides an explicit **Ask** action and inline activity feedback. The **Answer** and **Session** views appear only after Agent output or a live terminal session is available.

For every question, Focus creates a private disposable workspace, stages `.pi/SYSTEM.md`, the explicit `focus-answer-record-questions` Agent Skill, and PI settings, then launches PI with read-oriented tools. The case bundle remains outside the workspace and is treated as read-only evidence.

Final answers use continuous, verbatim two-to-five-word quotes as clickable evidence links. Each substantive paragraph or list item should include a nearby quote, with multiple short anchors when materially different points rely on different passages. The Agent does not print record labels or other research metadata; it uses source-map citation data only internally to resolve and verify the correct text pages.

Agent questions are case-wide by default. To direct the Agent to a particular page, identify its record citation in the question (for example, `CT 177`). The Agent may use that citation for lookup but omits it from the answer.

The normal Agent workflow is:

1. Run `focus/agent_helper.py context --json` once to read the optional versioned case overview and compact source-map status/capabilities.
2. Run one on-demand helper scan with several query variants, initially capped at eight results.
3. Read relevant full source text pages directly through each match's safe `resolved_text_path`; the match's internal metadata already source-resolves that exact page.
4. Expand terms, aliases, or the result cap when results are incomplete, ambiguous, or conflicting.
5. Inspect full `map --json` output only when document ranges, participant/witness/examination attribution, warnings, chronology, scoped follow-up work, or a negative finding requires it.
6. Use `lookup` for pages reached by direct citation, grep/find, or adjacent-page reading rather than redundantly looking up mapped search matches.

The case overview supplies parties, procedural posture, key events, principal issues, and record scope, but it is an orientation aid only. Overview statements, search snippets, participant entries, and summaries are navigation leads, not proof. The Agent must verify material claims from source text pages. Its workflow is text-only: it never opens page images, and it reports when handwriting, checkboxes, layout, signatures, or unresolved OCR cannot be determined from extracted text. Focus's ordinary image viewer remains available to the user. The helper creates no index, cache, or database.

Run the helper directly:

```bash
uv run python -m focus.agent_helper \
  --case-root /path/to/case_bundle context --json

uv run python -m focus.agent_helper \
  --case-root /path/to/case_bundle search \
  --query "maternal grandmother placement" \
  --query "placed with maternal grandmother" \
  --max-results 8 --json

# Optional detailed metadata for complex or scoped research:
uv run python -m focus.agent_helper \
  --case-root /path/to/case_bundle map --json
```

## Summaries

Focus displays RecordPrep's source hearing, report, and minute-order summaries and remains compatible with organized summaries from older bundles. **Hearings** and **Reports** stay directly available in the Case Tools navigation; **More** groups minute orders, summary printing, extraction, and page-range summarization. When content is available, the expanded panel targets about one-third of the app window height, with a 260-pixel total-height floor on shorter windows when space permits. Current RecordPrep bundles no longer create separate organized derivatives. RecordPrep uses the participant index privately for accurate attribution; new hearing summaries do not publish counsel/participant rosters or standalone testimony-status lines. Summary prose and the concise case overview are nonauthoritative and must be checked against the record for Agent answers.

Focus's own page/range summary and extraction tools are independent of Agent Q&A and use the model profiles selected in Settings.

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
- `focus/agent_helper.py`: read-only context/map/lookup/document/search CLI for Agent sessions.
- `focus/ui/settings.py`: settings UI.
- `focus/ui/commands.py`: D-Bus command reference.
- `scripts/focus-agent-vte.sh`: disposable PI workspace launcher.
- `.pi/`: checked-in PI system prompt, explicit Agent Skill, and settings.
- `tests/`: pytest coverage.

## Tests

```bash
uv run pytest
uv run python -m compileall -q focus tests
bash -n scripts/focus-agent-vte.sh
```

For a manual smoke test, open a schema-v2 bundle, verify that Agent Q&A is the only record-question view, and run a participant-scoped question. Confirm that every substantive paragraph or list item has a clickable exact two-to-five-word quote, no record labels or research metadata appear, and no search index or database is created. Ask a visual-only question and confirm that the Agent reports the text limitation without opening an image.

## License

See `LICENSE`.
