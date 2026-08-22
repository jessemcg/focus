---
name: focus-answer-record-questions
description: Answer factual, chronological, procedural, hearing, report, and transcript questions from the active Focus record bundle using the structured read-only Focus record tool, verified source text, and clickable record quotes. Use for any question that must be answered from the supplied case bundle rather than external sources.
---

# Answer Focus Record Questions

Work only from the active record bundle. Do not use web research, RAG, vector databases, outside facts, or page images. Never modify case files. Treat the nonauthoritative overview, map metadata, search snippets, and participant data as navigation leads, not proof. Use overview prose only to choose effective search terms. Never mention, quote, or rely on the overview in an answer.

## Fast research workflow

1. Call `focus_record` with action `context` once. Read the optional overview only for orientation and search planning. If the source map is missing or invalid, give the best honest limitation and do not guess.
2. Run one `focus_record` action `search` with several discriminative variants in its `queries` array. Cover every distinct part of the question. When the overview gives a date for the event asked about, put that full date in at least one event-cause query. Prefer variants that combine distinctive names with event, document, allegation, order, or legal-basis terms suggested by the overview; do not rely only on generic terms such as children, father, court, or removal. Put event-cause queries before identity-only queries when the question asks why an action occurred. Search is case-wide unless the question supplies a citation, document, hearing, witness, or role scope.
3. Search results are diversified by query and identify the matching query indexes and source-document labels. For an event's reason or legal basis, prefer contemporaneous orders, detention materials, petitions, hearing text, and jurisdiction/disposition materials over later status, permanency, adoption, or legal-history summaries. Read the best full source pages through their safe `resolved_text_path`, preferably in parallel, plus only necessary adjacent pages. The Agent has no corpus-wide grep tool; use a targeted follow-up `search` instead of broad text dumping.
4. Once primary source text directly answers every part of an affirmative question, stop researching and submit. For a why, basis, or causation question, do not submit unless a read source explicitly connects the action asked about to the stated reason, or is a contemporaneous recommendation, petition, hearing, or order governing that action. A historical allegation or later summary alone does not establish why a different event occurred. Run at most one follow-up `search` if this causal link or another material subpart remains unverified, or if ambiguity, conflict, attribution, a negative finding, or an explicit chronology request genuinely requires verification.
5. Use `lookup` for a supplied citation or a page reached outside mapped search. Use `document` for boundaries. Use one targeted `map` section only when detailed documents, participants, citation series, or warnings are genuinely needed.
6. Submit the first substantively useful answer with `submit_focus_answer`. Choose `answered`, `not_found`, or `insufficient_text`, provide the proposed Markdown, and make submission the last tool call.
7. Do not spend another search or model turn merely to polish quote length, punctuation, Markdown, metadata, or paragraph support.

Research budgets are enforced by the tools. A synthesis warning means answer now unless the question truly requires expansion. At a hard limit, answer from verified evidence already read or state that the available text is insufficient.

For attribution, verify the speaker from appearances, participant evidence, and examination evidence. Keep organizations, counsel, unsworn participants, and witnesses distinct. Q/A formatting alone does not establish testimony. For negative findings, search reasonable aliases, stems, date variants, and the relevant document range before concluding that support was not located.

The workflow is text-only. If extracted text cannot establish handwriting, checkboxes, layout, signatures, stamps, crossed-out text, or an OCR-ambiguous fact, say it cannot be determined from the available text.

## Preferred answer style

- Lead with the direct answer and usually finish within two to four short paragraphs or list items.
- Include only allegations, findings, or history that directly explain the event asked about; do not add merely related background.
- Prefer a nearby continuous, verbatim two-to-five-word record quote for each substantive paragraph or list item. Distinctive three-to-five-word anchors make Focus links more reliable.
- Put punctuation outside the closing quotation mark. Use double quotation marks only for genuine record language; do not stitch fragments or place ellipses inside a quote.
- Prefer no bold text because Focus also makes bold spans clickable.
- Omit record labels, citation keys, paths, filenames, page numbers, grep lines, and tool output from the answer.
- State material uncertainty plainly and never invent a quote or fact.

These are preferred linking and presentation conventions, not an acceptance gate. Substantive usefulness, factual care, and speed take priority. Submit an imperfect but useful answer unchanged rather than initiating a self-audit or corrective turn.
