---
name: focus-answer-record-questions
description: Answer factual, chronological, procedural, hearing, report, and transcript questions from the active Focus record bundle using read-only PI tools, internally source-resolved pages, and short clickable record quotes. Use for any question that must be answered from the supplied case bundle rather than external sources.
---

# Answer Focus Record Questions

Work only from the active record bundle. Do not use web research, RAG, vector
databases, or facts remembered from outside the bundle. Do not modify case files
or run shell commands that write, rename, move, or delete files.

## High-priority final-answer contract

- Lead with the direct answer, and support the lead with a linked quote when it
  makes a substantive factual point.
- Include at least one supporting quote in every substantive paragraph or list
  item. Add more when the paragraph or item makes materially different points
  or relies on different source passages.
- Make every quote a continuous, verbatim phrase of exactly **two to five
  words** from a source text page actually read. Prefer distinctive
  three-to-five-word phrases when available so Focus's phrase search lands
  reliably.
- Place each quote next to the point it supports. Paraphrase longer source
  language around multiple short quote anchors instead of quoting a long
  passage.
- Use double quotation marks only for genuine record language. Put punctuation
  outside the closing quotation mark. Within a linked quote, never use ellipses,
  brackets, stitched fragments, paraphrases, or a full sentence.
- Do not use bold text in the final answer. Focus interprets both quoted and bold
  spans as clickable phrase links, so evidence links must use quotation marks.
- Headings, purely connective text, and honest no-result or insufficient-text
  limitations do not require a quote. Never invent or distort a quote to meet
  the coverage requirement.
- Do not display record citations or research metadata in the final answer. In
  particular, omit `citation_label`, `citation_range`, citation keys,
  parenthetical or bare record labels, local paths, filenames, raw file-page
  numbers, grep line numbers, and tool output.
- Before sending the answer, check that every substantive point has adequate
  linked support, every quote is exact and two-to-five words, no bold evidence
  formatting appears, and no prohibited citation or research metadata remains.

Use these environment variables:

- `FOCUS_AGENT_CASE_ROOT`: active case-bundle root
- `FOCUS_RECORD_AGENT_PYTHON`: Python interpreter for the helper
- `FOCUS_RECORD_AGENT_HELPER`: source-resolving record helper

Run helper commands with:

```bash
"$FOCUS_RECORD_AGENT_PYTHON" "$FOCUS_RECORD_AGENT_HELPER" --case-root "$FOCUS_AGENT_CASE_ROOT" <command>
```

## Research workflow

1. Run `context --json` once. Its `overview` object is optional concise case
   orientation. When available, use it only to identify possible names, aliases,
   dates, phrases, issues, and record scope. It cannot establish a fact, support
   a quotation, or justify a negative finding. The compact `source_map` object
   reports map status, schema versions, counts, citation series, warnings, and
   supported search capabilities without dumping full document or participant
   metadata. If its status is unavailable or invalid, explain that a
   source-resolved, record-grounded answer cannot be produced safely.
2. Decompose the question into distinctive names, dates, phrases, events,
   document types, aliases, and reasonable OCR/synonym variants. Search several
   variants in one read-only scan, initially returning at most eight matches:

   ```bash
   "$FOCUS_RECORD_AGENT_PYTHON" "$FOCUS_RECORD_AGENT_HELPER" \
     --case-root "$FOCUS_AGENT_CASE_ROOT" search \
     --query "maternal grandmother placement" \
     --query "placed with maternal grandmother" \
     --max-results 8 --json
   ```

   Use optional `--document`, `--hearing-date`, `--witness`, and
   `--counsel-role` filters only when compact context or full-map inspection
   shows that the map supports them. The command scans source pages on demand
   and creates no index, cache, or database.
3. Treat ranked snippets and participant metadata only as navigation leads.
   For each relevant search match, pass its safe `resolved_text_path` directly
   to PI's `read` tool and inspect the full text page plus necessary adjacent
   context. A search match's `citation_label` and `citation_key` internally
   source-resolve that exact returned page, so no redundant `lookup` is needed
   after reading it. A missing/false `text_exists` or blank
   `resolved_text_path` is unresolved and must not be guessed.
4. Expand the result cap, aliases, stems, dates, or document scope when results
   are truncated, ambiguous, conflicting, or insufficient. Use PI's `grep`
   tool, which is backed by ripgrep, for unusual regex/OCR patterns. Before a
   negative finding, search aliases, stems, date variants, and the full relevant
   document or examination range.
5. Run full `map --json` only when needed to inspect document ranges, discover
   participant aliases, verify witness/examination or speaker attribution,
   investigate map warnings, plan scoped follow-up research, establish a
   procedural chronology, resolve conflicting results, or support a negative
   finding. Current source-map v2 bundles may provide hearing-scoped counsel,
   non-counsel participant, witness, and examination metadata. Older maps remain
   searchable but may not provide verified participant context.
6. Verify who is speaking from actual appearances, participant evidence, and
   examination evidence. Keep organizations distinct from attorney aliases,
   and keep an unsworn participant distinct from a witness. A question is the
   examiner's speech and an answer is the mapped witness's testimony only within
   a verified examination. Q/A formatting alone does not establish testimony.
7. Use `lookup --file "text_pages/0001.txt" --json` for pages discovered through
   `grep`, `find`, adjacent-page reading, or other direct file access. Use
   `lookup --citation "CT 6" --json` to follow a record citation identified in
   the user's question. Pass lookup's `resolved_text_path` directly to `read`.
   Lookup remains required whenever a page did not come from a mapped search
   result or its mapping is unresolved. Citation metadata is internal research
   data only: use it to resolve the right source page, verify scope and
   attribution, and fail safely, but never print it in the final answer.
8. Use `document --id "document-id" --json` when document boundaries, titles,
   dates, or internally resolved citation ranges matter. Compare all relevant
   passages before answering. The overview and summaries are nonauthoritative
   leads and must be checked against source text pages.
9. Keep the Agent workflow text-only. Never open or inspect page images. Base
   material factual claims only on source text actually read. If handwriting,
   checkboxes, layout, signatures, stamps, crossed-out text, or unresolved OCR
   cannot be established from the extracted text, say it cannot be determined
   from the available text and do not guess.

If a reasonable set of searches finds no support, say the requested fact could
not be located in the provided bundle. If source texts conflict, make the
uncertainty explicit and include a separate two-to-five-word linked quote from
each competing passage. State uncertainty plainly when the bundle is mixed,
incomplete, or silent.
