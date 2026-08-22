# Focus

<img src="focus.png" alt="Focus icon" width="128" align="left">

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

For every question, Focus creates a private disposable workspace, stages its short system prompt, canonical record-question skill, settings, and sole trusted Focus extension, then launches PI with `--no-session`. Global and project extension discovery stays disabled, no case-content JSONL is written to PI's global session directory, and credentials remain in PI's global auth store.

The checked-in default is Fireworks DeepSeek V4 Pro 0813 at low reasoning. Focus disables auto-compaction for these one-question sessions, keeps transient provider retry enabled, and caps each model response at 8,192 output tokens.

The Agent has only guarded `read`, the shell-free structured `focus_record` tool, and terminating `submit_focus_answer`. Record reads are confined to the active bundle's `text_pages/`; images remain forbidden, and corpus-wide grep is not available to the Agent. The structured tool provides navigation-only context, compact ranked search (six results by default), citation/page lookup, document inspection, and one targeted map section. Search diversifies results across individual query variants, reports each match's query indexes and source-document label, and favors date-matched contemporaneous event materials over later historical summaries for causal queries. Research receives a synthesis warning after two searches or eight page reads and hard stops at six searches, 24 page reads, and one map inspection.

The preferred workflow is one context call that exposes the nonauthoritative overview for search planning, one discriminative search covering every question subpart, parallel full reads of the best pages and necessary adjacent context, then immediate submission of the first substantively useful answer. Event-cause searches include an overview-provided event date and prefer contemporaneous orders, detention materials, petitions, hearings, and jurisdiction/disposition materials. A historical allegation alone does not prove why a later action occurred; a follow-up search is reserved for that missing causal link or another material unanswered subpart, ambiguity, conflict, attribution, negative findings, and requested chronology. Overview prose is never answer evidence and must not be mentioned or quoted.

`submit_focus_answer` atomically writes an app-owned mode-600 runtime artifact and terminates without another model turn. If the model omits the tool, Focus captures one final plain assistant message as a best-effort fallback; `toolUse` narration is never treated as final. Output-limit and interrupted answers with usable text remain visible as partial answers. Formatting diagnostics are category-only and never reject, alter, suppress, or rerun an answer.

Short continuous two-to-five-word record quotes, punctuation outside quotes, no record labels, and no bold remain preferred because they improve clickable links. They are not acceptance gates: a useful answer with a long quote, metadata, bold text, or imperfect paragraph support is displayed unchanged.

The case overview, map metadata, snippets, participant entries, and summaries remain navigation leads rather than proof. The Agent verifies material claims from source text pages. If handwriting, checkboxes, layout, signatures, or unresolved OCR cannot be established from extracted text, it states that limitation instead of opening an image or guessing.

Run the helper directly:

```bash
uv run python -m focus.agent_helper \
  --case-root /path/to/case_bundle context --json

uv run python -m focus.agent_helper \
  --case-root /path/to/case_bundle search \
  --query "named father section 342 petition" \
  --query "named father caretaker absence incapacity" \
  --max-results 6 --json

# Exceptional follow-up when returned full pages leave a subpart unanswered:
uv run python -m focus.agent_helper \
  --case-root /path/to/case_bundle search \
  --query "placement order reason" --json

# Optional targeted metadata for complex or scoped research:
uv run python -m focus.agent_helper \
  --case-root /path/to/case_bundle map --section documents --json
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
- `focus/agent_helper.py`: compact context, targeted map, lookup, document, and ranked search CLI for Agent sessions.
- `focus/agent_answer.py`: answer-artifact transport checks and non-blocking category linter.
- `focus/ui/settings.py`: settings UI.
- `focus/ui/commands.py`: D-Bus command reference.
- `scripts/focus-agent-vte.sh`: ephemeral PI launcher with discovery disabled, exactly one explicit Focus extension, no persisted session, and the strict `read,focus_record,submit_focus_answer` tool allowlist.
- `.pi/`: checked-in PI system prompt, canonical Agent Skill, settings, and Focus record/answer extension.
- `tests/`: pytest coverage.

## Tests

```bash
uv run pytest
uv run python -m compileall -q focus tests
bash -n scripts/focus-agent-vte.sh
```

For a sanitized manual smoke test, confirm Pro 0813 / low, then ask an affirmative identity/reason question, a negative-finding question, an attribution question, and a text-insufficient visual question. Confirm the first useful answer appears without a formatting retry; representative short quotes resolve, while longer or imperfect quotes do not suppress the answer. Verify best-effort and partial statuses are unobtrusive, no compaction occurs, and no Focus JSONL appears in PI's global session directory.

## License

See `LICENSE`.
