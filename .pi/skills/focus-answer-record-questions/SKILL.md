---
name: focus-answer-record-questions
description: Answer factual, chronological, procedural, hearing, report, and transcript questions from the active Focus record bundle using read-only PI tools and source-map record citations. Use for any question that must be answered from the supplied case bundle rather than external sources.
---

# Answer Focus Record Questions

Work only from the active record bundle. Do not use web research, RAG, vector
databases, or facts remembered from outside the bundle. Do not modify case files
or run shell commands that write, rename, move, or delete files.

Use these environment variables:

- `FOCUS_AGENT_CASE_ROOT`: active case-bundle root
- `FOCUS_RECORD_AGENT_PYTHON`: Python interpreter for the helper
- `FOCUS_RECORD_AGENT_HELPER`: citation-aware record helper

Run helper commands with:

```bash
"$FOCUS_RECORD_AGENT_PYTHON" "$FOCUS_RECORD_AGENT_HELPER" --case-root "$FOCUS_AGENT_CASE_ROOT" <command>
```

## Research workflow

1. Run `context --json` once. Its `overview` object is optional concise case
   orientation. When available, use it only to identify possible names, aliases,
   dates, phrases, issues, and record scope. It cannot establish a fact, support
   a quotation, justify a negative finding, or supply a citation. The compact
   `source_map` object reports map status, schema versions, counts, citation
   series, warnings, and supported search capabilities without dumping full
   document or participant metadata. If its status is unavailable or invalid,
   explain that a citation-grounded answer cannot be produced safely.
2. A supplied `<current-focus-citation>` means the user explicitly enabled Page
   context for this one question. Resolve and inspect it when relevant to the
   question. Its presence does not make it proof. When the tag is absent, treat
   the question as case-wide and do not investigate the page merely displayed
   in Focus.
3. Decompose the question into distinctive names, dates, phrases, events,
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
   shows that the map supports them. `--current-citation` is only a proximity-
   ranking hint, not a filtering scope; use it only when explicit Page context
   was supplied. The command scans source pages on demand and creates no index,
   cache, or database.
4. Treat ranked snippets and participant metadata only as navigation leads.
   For each relevant search match, pass its safe `resolved_text_path` directly
   to PI's `read` tool and inspect the full page plus necessary adjacent context.
   A search match's `citation_label` and `citation_key` are the source-map
   resolution for that exact returned page, so no redundant `lookup` is needed
   after reading it. A missing/false `text_exists` or blank
   `resolved_text_path` is unresolved and must not be guessed.
5. Expand the result cap, aliases, stems, dates, or document scope when results
   are truncated, ambiguous, conflicting, or insufficient. Use PI's `grep`
   tool, which is backed by ripgrep, for unusual regex/OCR patterns. Before a
   negative finding, search aliases, stems, date variants, and the full relevant
   document or examination range.
6. Run full `map --json` only when needed to inspect document ranges, discover
   participant aliases, verify witness/examination or speaker attribution,
   investigate map warnings, plan scoped follow-up research, establish a
   procedural chronology, resolve conflicting results, or support a negative
   finding. Current source-map v2 bundles may provide hearing-scoped counsel,
   non-counsel participant, witness, and examination metadata. Older maps remain
   searchable but may not provide verified participant context.
7. Verify who is speaking from actual appearances, participant evidence, and
   examination evidence. Keep organizations distinct from attorney aliases,
   and keep an unsworn participant distinct from a witness. A question is the
   examiner's speech and an answer is the mapped witness's testimony only within
   a verified examination. Q/A formatting alone does not establish testimony.
8. Use `lookup --file "text_pages/0001.txt" --json` for pages discovered through
   `grep`, `find`, adjacent-page reading, or other direct file access. Use
   `lookup --citation "CT 6" --json` to follow a record citation, including
   explicit Page context. Pass lookup's `resolved_text_path` directly to `read`.
   Lookup remains required whenever a page did not come from a mapped search
   result or its mapping is unresolved.
9. Inspect a paired page image only when visual appearance could change the
   answer, such as checkboxes, signatures, initials, handwriting, stamps,
   crossed-out text, tables, field alignment, form identity, or ambiguous OCR.
   Treat `page_type` as a hint rather than a reason to inspect every image. When
   `image_exists` is true, pass `resolved_image_path` directly to PI's `read`
   tool and inspect only the smallest necessary set of pages. If PI reports that
   the current model does not support images, the image is missing, or the scan
   is unclear, do not claim visual verification or guess. If OCR and the image
   conflict, treat the image as controlling only for visual properties and
   describe the discrepancy without overstating an unclear scan.
10. Use `document --id "document-id" --json` when document boundaries, titles,
    dates, or citation ranges matter. Compare all relevant passages before
    answering. The overview and summaries are nonauthoritative leads and must be
    checked against source pages.

If a reasonable set of searches finds no support, say the requested fact could
not be located in the provided bundle. If sources conflict, cite the competing
evidence and make the uncertainty explicit.

## Answer requirements

- Lead with the direct answer.
- Base every material factual claim on record text actually read or, when the
  claim is inherently visual, on the corresponding page image after resolving
  its record citation.
- Use only `citation_label`, `citation_range`, or citation keys resolved through
  `source_map.json` as final citations.
- Never expose local paths, `resolved_text_path`, `resolved_image_path`,
  `text_pages` filenames, raw file-page numbers, grep line numbers, or tool
  output as final citations.
- An image does not supply a missing record citation. Use an image-bearing page
  without a resolved citation only as context when a citable page independently
  supports the claim. Otherwise explain that the material has no source-map
  record citation. Treat a blank `citation_label`, a `status` of `missing`, or a
  sentinel key containing `:missing:` as unresolved rather than as a citation.
  Never invent a record citation for an appended or unnumbered page.
- Put each citation in the sentence or paragraph it supports.
- Group citations by exact label, de-duplicate pages, sort pages within each
  label, and compress only truly consecutive pages. Put reporter-transcript
  groups before CT-family groups and separate label groups with semicolons:
  `(RT 6, 34; CT 140, 190.)`
- Never turn nonconsecutive pages into a range. Use
  `(RT 5, 45, 500-503; 2RT 10-11; CT 400, 556.)`, not `(RT 5-45.)`.
- Keep direct quotations short, ordinarily two to five words, and reproduce
  them exactly.
- State uncertainty plainly when the bundle is mixed, incomplete, or silent.
