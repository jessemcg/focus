# Focus

The passive metrics wrapper now delegates to sibling `PiRunMetrics/launch_adapter.py` using system Python, with bounded executable-only version/Git probes. Collection requires Pi >=0.87.1; unavailable/incompatible collection warns and fails open without upgrading Pi. The source-project archive default and code-owned tags no longer depend on a staged configuration root or inherited parent-app tags. Existing answer artifacts, model/tools and `--no-session` remain unchanged. New embedded launches use the updated wrapper; use sibling **Pi Run Metrics** for readiness, reports and an existing-session PiPlanner request. No archived data is moved or removed.

<img src="focus.png" alt="Focus icon" width="128" align="left">

Focus is a GTK4/Libadwaita desktop app for reading appellate-record text and page images, navigating official RT/CT citations, searching extracted text, viewing RecordPrep summaries, and asking record-grounded questions through an embedded PI Agent.

## Features

- Page-by-page transcript reading with TOC navigation, page images, printing, and bookmarks.
- Metadata-backed hearing, report, minute-order, and form colors.
- Fast Python-only record search with Unicode/OCR normalization, hit navigation, and configurable highlighting.
- Official transcript-page/citation lookup from RecordPrep metadata.
- Page and range summarization plus structured information extraction through configurable OpenAI-compatible model profiles.
- Hearing, report, and minute-order summary views, with legacy organized-summary compatibility.
- An organized Case Tools workspace with contextual controls for Agent Q&A, summaries, extraction, and page-range summarization.
- Agent Q&A in an embedded VTE terminal with a mirrored final answer, short clickable record quotes, titled answers, and a per-case saved-answer library.
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
    editions/
      hearings_sum_<case>.pdf
      hearings_sum_<case>.pages.json
      reports_sum_<case>.pdf
      reports_sum_<case>.pages.json
      minutes_sum_<case>.pdf
      minutes_sum_<case>.pages.json
```

Only `text_pages` is required for basic browsing. Source-resolved Agent answers require `artifacts/source_map.json`. Source-map v1 remains searchable; participant-aware scopes and attribution require RecordPrep source-map v2.

## Record category display

The reader uses a 10% paper tint and 4px rail: **hearing blue**, **report teal**,
**minute-order bronze**, and **form violet**. There is no category label bar above
the page. Unknown/index pages remain neutral. Paper stays light even with dark
application chrome. High contrast removes category colors while retaining neutral
rails/outlines.

Classification is read-only and keyed by physical file page, in this order:

1. `transcript_page_numbers.json` per-page `page_type`.
2. `source_map.json` per-page `page_type`.
3. Hearing/report/minute boundary ranges, independent of dates.
4. Exact bookmark pages beneath canonical TOC headings: Hearings, Reports,
   Minute orders, Forms. No propagation to following pages.
5. Neutral when metadata is absent, unknown, or conflicting.

Explicit unknown types block weaker fallbacks. Conflicting selected-tier types,
overlapping different boundary categories, or contradictory RT/CT metadata remain
neutral. RT is not assumed to be a hearing, CT is not assumed to be a minute order,
and no form ranges are inferred. Canonical TOC headings have stronger tints than
bookmarks; bookmark colors use the same page classifier as the reader. Active rows
use bold text without a box outline; keyboard focus retains its own outline.
Theme changes update appearance without replacing the reader buffer or TOC model.
These display categories do not change citations, navigation targets, Agent tools,
summaries, or record metadata.

**Ctrl+Shift+M** (or the minute-order toolbar button) opens the matching existing
minute-order **text**, even when an image was visible. Press again to return to the
originating hearing text, including after browsing elsewhere. Missing exact target
text produces an unavailable message rather than jumping to a neighboring page.
**Ctrl+I** remains the independent manual image toggle.

See [category acceptance and screenshots](docs/record-category-acceptance.md).

## Configuration

Focus stores local application settings in `config.json` (ignored by Git). Settings include:

- Input directory.
- Model profiles for single-page summary, page-range summary, and extraction.
- Prompt templates for those three tools.
- PI Agent command and speech question file.
- Fonts, highlight phrases, and colors.

Obsolete embedding/vector-question credentials and settings are removed when configuration is loaded or saved. Never commit `config.json` or API keys.

## Agent questions

Open **Case Tools** from the labeled header control and select **Agent Q&A**. The composer has two equal-width question fields with inline activity feedback. **New question…** starts a new query when you press Enter and replaces the current conversation. **Follow up…** continues the live Pi conversation when you press Enter, never starts a new query, and becomes available only after a question has started a live session. The **Answer** and **Session** views appear only after Agent output or a live terminal session is available.

Starting a new question creates one private disposable workspace and stages its system prompt, skill, settings, Focus extension, and explicit follow-up bridge. PI uses `--no-session`; live interactive follow-ups and app-owned answer artifacts remain available without persisted transcripts. Extension discovery stays disabled. The sibling PiRunMetrics observer is explicitly loaded when available, with the same tool allowlist and model selection. Credentials remain in PI's global auth store.

The checked-in default is Fireworks DeepSeek V4 Pro 0813 at low reasoning. Focus disables auto-compaction for these embedded sessions and keeps transient provider retry enabled. Focus does not override the model/provider's native output limit; any response ceiling comes from Pi's model definition or the provider.

The Agent has only guarded `read`, the shell-free structured `focus_record` tool, and terminating `submit_focus_answer`. Record reads are confined to the active bundle's `text_pages/`; images remain forbidden, and corpus-wide grep is not available to the Agent. The structured tool provides navigation-only context, compact ranked search (six results by default), citation/page lookup, document inspection, and targeted map-section inspection. Search diversifies results across individual query variants, reports each match's query indexes and source-document label, and favors date-matched contemporaneous event materials over later historical summaries for causal queries. Search, page reading, and targeted map inspection are uncapped by Focus; the only finite limits are the provider's context window and output size.

The preferred workflow is one context call that exposes the nonauthoritative overview for search planning, one discriminative search covering every question subpart, parallel full reads of the best pages and necessary adjacent context, then immediate submission of the first substantively useful answer. Event-cause searches include an overview-provided event date and prefer contemporaneous orders, detention materials, petitions, hearings, and jurisdiction/disposition materials. A historical allegation alone does not prove why a later action occurred; run additional targeted follow-up searches while the causal link or another material subpart, ambiguity, conflict, attribution, a negative finding, or requested chronology remains unresolved. Overview prose is never answer evidence and must not be mentioned or quoted.

`submit_focus_answer` atomically writes an app-owned mode-600 runtime artifact and terminates without another model turn. If the model omits the tool, Focus captures one final plain assistant message as a best-effort fallback; `toolUse` narration is never treated as final. Output-limit and interrupted answers with usable text remain visible as partial answers. Formatting diagnostics are category-only and never reject, alter, suppress, or rerun an answer.

After the first question, the live **Session** terminal keeps the same non-persisted workspace and context. The **Follow up…** field submits literal text to that same live session through a private Unix-socket bridge loaded inside Pi; slash commands and control characters are sent as ordinary user text and never expanded. Each completed follow-up submits a newer revision of the answer artifact rather than replacing the transport; Focus re-runs the same Markdown cleanup, GTK4 text styling, clickable short-quote links, and page links, then returns to **Answer** showing the latest final answer. Immediately after submission Focus switches to the live **Session** so the run can be watched for obvious problems; it returns to the formatted **Answer** view when the final answer arrives. Intermediate answers remain in the **Session** transcript. Follow-ups reject while the Agent is still working without queueing or steering the current answer, and the submitted question stays in the field, like the initial-question field, until a new question replaces it. While a historical saved answer is displayed, return to **Latest Answer** (or **Session**) before submitting a follow-up. Stopping the terminal, switching case, or starting a new question invalidates the channel and cleans up the application-owned runtime directory.

Answers now open with a compact `# Title` and `*Subtitle*` (specific to the question, with the bottom line and its uncertainty) before the body. The title/subtitle are presentation metadata: a missing or imperfect one never suppresses, delays, or retries an otherwise useful answer, and recognized metadata is never turned into a transcript-search link target.

Short continuous two-to-five-word record quotes, punctuation outside quotes, no record labels, and no bold remain preferred because they improve clickable links. They are not acceptance gates: a useful answer with a long quote, metadata, bold text, or imperfect paragraph support is displayed unchanged.

### Saved answers

A flat **Save Answer** control beside **Answer**/**Session** saves an immutable snapshot of the displayed answer only on an explicit click; answers are never archived automatically. The snapshot stores the original Markdown, status (including Partial/Best-effort), and question label, so repeated clicks do not duplicate it and each newer live revision saves separately. The control is disabled when there is no usable answer and shows **Saved** once a snapshot is stored.

Saved answers live with the case at `<record-layout-root>/.focus/saved-answers/<answer-uuid>.json` (one self-contained mode-600 file per answer in a mode-700 directory) so the library follows the case through Dropbox. Browsing rebuilds the list from files with no index database, reads owned files even when synchronization broadened their modes (warning rather than hiding them), and leaves malformed, unknown-schema, or unfamiliar files untouched and reported. The directory association is authoritative: moving or copying the whole case with `.focus` keeps its library. Saved answers are historical prose, not transcripts; reopening one searches the current case text, and missing quotes fall back to the existing no-match feedback.

The icon-only **star** (**Saved Answers**) control beside **Agent Q&A** lists this case's answers newest first with a search field, saved date, and Partial indicator. Selecting an entry opens it in the upper **Answer** pane; the latest live answer is retained separately, so a newly arriving revision offers **Latest Answer** instead of replacing the saved view. Choosing **Session** returns to the current live workflow and synchronizes the displayed snapshot to the live answer (or keeps the historical identity when no live answer exists), so returning to **Answer** never mislabels an old saved answer as the latest. The trash control deletes immediately — no confirmation — and removes only that one saved file, never transcripts, configuration, session files, or other answers. A failed delete leaves the entry in place and reports the failure. No bulk delete, pruning, editing, renaming, or export is offered.

A displayed answer carries a compact context line beneath the Answer/Session strip: historical snapshots read `Saved answer · <local date>` and live snapshots read `Latest answer`, with explicit **Partial** or **Best-effort** text when applicable; the original question is available as the line's tooltip. The line belongs to the displayed snapshot (not the transient activity status) and is hidden in **Session**.

Focus remembers a bounded, case-local, in-memory reading position for each displayed answer, keyed by immutable answer ID and holding a viewport text anchor plus a scroll-fraction fallback. First opening an answer starts at the top; returning from Hearings/Reports, switching back from **Session**, or reopening an already visited saved answer restores the position within about one visible line. A new live revision has a new answer ID and starts at the top. Positions are never written to saved-answer files; they are cleared on case change and shutdown, and deleted answers are evicted. A late saved-answer load or position restore that is superseded by a newer user choice is discarded.

### Operational metrics pilot

Copy Trace is removed; Answer and Session remain. New embedded sessions explicitly load `../PiRunMetrics/run-collector.ts` with `app=focus`, `workflow=record_question`. Content-free records are stored at `Focus/.run-metrics/runs/YYYY-MM-DD/<run-uuid>.jsonl`. The entire `.run-metrics/` directory is ignored by Git. Because the project is under Dropbox, these records may sync through Dropbox; Git ignore is not a sync exclusion. Permissions remain private (`0700` directories, `0600` files). Existing XDG-state records are not moved or deleted.

From the Focus directory, run `python3 ../PiRunMetrics/analyze_runs.py --root "$PWD/.run-metrics/runs" --app focus --days 14` for an on-demand batch report. Reports still go to private XDG state; Jesse alone judges answer quality.

Set `PI_RUN_METRICS_ROOT` to an absolute archive path to override the project default, `PI_RUN_METRICS_ENABLED=0` to disable collection, or `PI_RUN_METRICS_COLLECTOR` to an absolute collector path for isolated deployment. Missing code warns without preventing questions. See PiRunMetrics README for archive controls, privacy boundaries, validation status, and rollback. Old saved traces are untouched.

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

# Additional targeted follow-ups while evidence remains incomplete are permitted:
uv run python -m focus.agent_helper \
  --case-root /path/to/case_bundle search \
  --query "placement order reason" --json

# Optional targeted metadata for complex or scoped research:
uv run python -m focus.agent_helper \
  --case-root /path/to/case_bundle map --section documents --json
```

## Summaries

Focus displays RecordPrep's source hearing, report, and minute-order summaries and remains compatible with organized summaries from older bundles. **Hearings** and **Reports** stay directly available in the Case Tools navigation; **More** groups minute orders, extraction, and page-range summarization. When content is available, the expanded panel targets about one-third of the app window height, with a 260-pixel total-height floor on shorter windows when space permits. Current RecordPrep bundles no longer create separate organized derivatives. RecordPrep uses the participant index privately for accurate attribution; new hearing summaries do not publish counsel/participant rosters or standalone testimony-status lines. Summary prose and the concise case overview are nonauthoritative and must be checked against the record for Agent answers.

When a bundle includes RecordPrep's page-matched summary editions (`summaries/editions/` plus the manifest `summarized_<kind>_pdf`/`summarized_<kind>_pages` companion keys), Focus browses each summary one printable page at a time with flat Previous/Next controls, an editable page number, and `Page N of M` numbering that matches the PDF exactly. Each displayed page preserves paragraph separation with exactly one empty line between paragraphs (the PDF remains the immutable pagination authority; the sidecar text itself is never rewritten). Search still covers every page in document order, Enter follows matches across page transitions, and paper-page boundaries act as search boundaries. Set Bookmark writes a version-3 paper-page bookmark recording the page, a `line` fallback, the `source_sha256` summary freshness guard, the edition `pdf_sha256`, and the `layout_id`: the exact page is restored only while both hashes still match, a matching source with a changed PDF (a repaginated edition) is mapped back through the saved source line with a notification, and a source mismatch falls back safely to page 1. Legacy version-2 page bookmarks validate the source hash and then map their stored line fallback instead of trusting an obsolete page number, and version-1 line bookmarks still return approximately until the next Set Bookmark. **Open PDF** opens the canonical Letter PDF in the default document viewer, preserving fixed page membership and footer numbers; use the viewer's own print command to print it, so the edition's pagination is never re-flowed by Focus. Focus accepts every supported RecordPrep schema/layout pairing (schema v1 with the denser `recordprep-summary-letter-v2` or legacy v1 sidecars, and schema v2 with `recordprep-summary-letter-v3`), validates the sidecar against both the summary text and the PDF by hash, and rejects it as a unit if anything is missing, malformed, path-escaping, or stale, degrading safely to the continuous scrolling, percentage, and line-bookmark behavior. Schema v2 editions carry required per-page quote spans: RecordPrep renders recognized quoted phrases in bold without their outer double quote delimiters, and Focus applies its existing bold/phrase styling and phrase clicks directly from those validated spans (using the stored complete phrase for fragments that wrap across a paper-page boundary) instead of reparsing quote-free text; malformed or missing quote spans reject the whole sidecar. Cached in-session paper-page positions are honored only while the loaded edition's PDF hash still matches, so switching summaries or rebuilding an edition can never restore a stale page number.

Focus's own page/range summary and extraction tools are independent of Agent Q&A and use the model profiles selected in Settings.

## Keyboard and external commands

Important shortcuts:

- Up/Down: previous/next record page.
- Home/End: first/last page.
- Ctrl+F: transcript grep.
- Ctrl+Q: focus Agent Q&A.
- Ctrl+Shift+A: toggle case tools and focus Agent Q&A when opened.
- Ctrl+I: toggle the page image.
- Ctrl+Shift+M: open matching minute-order text / return to originating hearing text.
- F1: keyboard shortcuts.

Public question actions:

```text
focus_agent_question
submit_speech_agent_question
focus_agent_followup
submit_speech_agent_followup
```

`focus_agent_followup` reveals the composer and focuses the follow-up field without submitting. `submit_speech_agent_followup` reads the configured speech question file, normalizes it, and submits it through the same live-session controller as Enter; the existing `submit_speech_agent_question` keeps starting a new session. A successful `gdbus` activation only means the app received the action; the app reports delivery acceptance or failure, and an ambiguous delivery tells you to inspect **Session** before retrying.

Example:

```bash
gdbus call --session \
  --dest com.mcglaw.Focus \
  --object-path /com/mcglaw/Focus \
  --method org.gtk.Actions.Activate \
  submit_speech_agent_question '[]' '{}'

gdbus call --session \
  --dest com.mcglaw.Focus \
  --object-path /com/mcglaw/Focus \
  --method org.gtk.Actions.Activate \
  submit_speech_agent_followup '[]' '{}'
```

## Project layout

- `focus/app.py`: GTK application, transcript browsing, summaries, and Agent orchestration.
- `focus/core.py`: shared config, record layout, citation, and rendering helpers.
- `focus/record_categories.py`: read-only file-page display classifier and palette.
- `focus/agent_helper.py`: compact context, targeted map, lookup, document, and ranked search CLI for Agent sessions.
- `focus/agent_answer.py`: answer-artifact transport checks and non-blocking category linter.
- `focus/answer_metadata.py`: GTK-independent title/subtitle recognition and protected-prefix offsets.
- `focus/answer_presentation.py`: GTK-independent saved-date and quality-status formatting shared by the answer context line and the saved-answer popover.
- `focus/reading_position.py`: bounded least-recently-used in-memory cache of per-answer viewport anchors and scroll fractions.
- `focus/agent_followup.py`: bounded GTK-independent Unix-socket client and protocol types for live follow-up delivery.
- `focus/saved_answers.py`: durable per-case saved-answer store with typed list/load/save/delete operations.
- `focus/ui/saved_answers.py`: the Saved Answers popover menu.
- `focus/ui/settings.py`: settings UI.
- `focus/ui/commands.py`: D-Bus command reference.
- `scripts/focus-agent-vte.sh`: ephemeral PI launcher with discovery disabled, explicit Focus record/bridge and optional sibling metrics extensions, `--no-session`, and the strict `read,focus_record,submit_focus_answer` tool allowlist.
- `.pi/`: checked-in PI system prompt, canonical Agent Skill, settings, the Focus record/answer extension, and the explicitly loaded live follow-up bridge extension.
- `tests/`: pytest coverage.

## Tests

```bash
uv run pytest
uv run python -m compileall -q focus tests
bash -n scripts/focus-agent-vte.sh
```

For a sanitized manual smoke test, confirm Pro 0813 / low, then ask an affirmative identity/reason question, a negative-finding question, an attribution question, and a text-insufficient visual question. Confirm the first useful answer appears without a formatting retry; representative short quotes resolve, while longer or imperfect quotes do not suppress the answer. Verify best-effort and partial statuses are unobtrusive, no compaction occurs, no Focus JSONL appears in PI's global session directory, and each settled question creates a separate content-free metrics record when collection is enabled.

## License

See `LICENSE`.
