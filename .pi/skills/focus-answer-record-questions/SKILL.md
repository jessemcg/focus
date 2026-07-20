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

1. Run `map --json` before substantial research. Review the citation series,
   document metadata, paths, counts, and warnings.
2. Use PI's `grep` tool, which is backed by ripgrep, to search the bundle's
   `text_pages` directory. Begin with distinctive names, dates, phrases, or
   events. Try reasonable variants and synonyms when the first search is
   incomplete.
3. Treat grep results only as leads. Use `read` to inspect each relevant full
   page and any adjacent pages needed for context.
4. Resolve every page used in the answer with
   `lookup --file "text_pages/0001.txt" --json`. Use
   `lookup --citation "CT 6" --json` to follow a record citation.
5. Inspect a paired page image only when visual appearance could change the
   answer, such as checkboxes, signatures, initials, handwriting, stamps,
   crossed-out text, tables, field alignment, form identity, or ambiguous OCR.
   Treat `page_type` as a hint rather than a reason to inspect every image. When
   `image_exists` is true, pass `resolved_image_path` directly to PI's `read`
   tool and inspect only the smallest necessary set of pages. If PI reports that
   the current model does not support images, the image is missing, or the scan
   is unclear, do not claim visual verification or guess. Use clear text
   evidence when sufficient and state any remaining limitation. If OCR and the
   image conflict, treat the image as controlling only for visual properties
   and describe the discrepancy without overstating an unclear scan.
6. Use `document --id "document-id" --json` when document boundaries, titles,
   dates, or citation ranges matter.
7. Compare all relevant passages before answering. Do not rely on a search
   snippet alone. Treat an optional current Focus citation as a navigation hint,
   not evidence by itself.

If the source map is missing or invalid, explain that a citation-grounded answer
cannot be produced safely. If a reasonable set of searches finds no support,
say the requested fact could not be located in the provided bundle. If sources
conflict, cite the competing evidence and make the uncertainty explicit.

## Answer requirements

- Lead with the direct answer.
- Base every material factual claim on record text actually read or, when the
  claim is inherently visual, on the corresponding page image after resolving
  its record citation.
- Use only `citation_label`, `citation_range`, or citation keys resolved through
  `source_map.json` as final citations.
- Never expose local paths, `image_path`, `resolved_image_path`, `text_pages`
  filenames, raw file-page numbers, grep line numbers, or tool output as final
  citations.
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
