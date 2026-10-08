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
4. Once primary source text directly answers every part of an affirmative question, stop researching and submit. For a why, basis, or causation question, do not submit unless a read source explicitly connects the action asked about to the stated reason, or is a contemporaneous recommendation, petition, hearing, or order governing that action. A historical allegation or later summary alone does not establish why a different event occurred. Run as many additional targeted `search` calls as needed to resolve a remaining causal link or any other material subpart, including ambiguity, conflict, attribution, a negative finding, or an explicit chronology request.
5. Use `lookup` with exactly one nonempty `citation` or `file` for a supplied citation or a page reached outside mapped search. Use `document` with singular `id` from `matches[].documents[].id` or the document map for boundaries; `document[]` instead restricts a search. Multiple search documents form a union, intersected with other filter types (hearing date, witness, counsel role). Use one targeted `map` section via `map_section` only when detailed documents, participants, citation series, or warnings are genuinely needed.
   - Read only returned absolute `resolved_text_path` values under the active bundle's canonical `text_pages/`; use `lookup` for adjacent paths instead of guessing relative to the disposable workspace.
   - An unknown/unavailable scope is an error, not a broader search. `scope_status: empty` means the valid filters selected no pages, not record-wide absence. Check search `coverage`: missing, unreadable, rejected or decoding-warning pages make coverage incomplete. Treat these as evidence limitations, never as a complete negative finding; continue necessary verification where available or state the limitation. A zero-hit search with complete coverage describes only its resolved candidate scope.
6. Submit the first substantively useful answer with `submit_focus_answer`. Choose `answered`, `not_found`, or `insufficient_text`, provide the proposed Markdown, and make submission the last tool call.
7. Do not spend another search or model turn merely to polish quote length, punctuation, Markdown, metadata, or paragraph support, and stop once the question is substantiated. Do not run extra searches just to format or debug already-complete results.

For attribution, verify the speaker from appearances, participant evidence, and examination evidence. Keep organizations, counsel, unsworn participants, and witnesses distinct. Q/A formatting alone does not establish testimony. For negative findings, search reasonable aliases, stems, date variants, and the relevant document range before concluding that support was not located.

The workflow is text-only. If extracted text cannot establish handwriting, checkboxes, layout, signatures, stamps, crossed-out text, or an OCR-ambiguous fact, say it cannot be determined from the available text.

## Preferred answer style

- Open the answer with a compact title and bottom-line subtitle on their own lines, before the body:

  ```markdown
  # Supervised Visits Continued
  *Weekly visits remained supervised*

  The record describes “weekly supervised visits”...
  ```

  The title is specific to the record question (about 3–8 words, at most 64 characters). The subtitle states the bottom line in about 2–5 words (at most 40 characters) and must not repeat the title, use a generic label, or overstate certainty. Both must reflect any material uncertainty accurately.
- Lead the body directly with the direct answer and usually finish within two to four short paragraphs or list items.
- Include only allegations, findings, or history that directly explain the event asked about; do not add merely related background.
- Anchor important points with direct source quotations using the guidance below.
- Prefer no bold text because Focus also makes bold spans clickable.
- Omit record labels, citation keys, paths, filenames, page numbers, grep lines, and tool output from the answer.
- State material uncertainty plainly and never invent a quote or fact.

## Direct quotations from source material

- Select a continuous, verbatim two-to-five-word record quote from a source text page you have actually read. Prefer distinctive three-to-five-word anchors that help the reader locate the relevant passage through Focus's clickable phrase search. Never quote navigation snippets, overview prose, participant metadata, or generated summaries as source evidence.
- Weave short direct quotations into your own sentences, integrating each quotation grammatically instead of stating a paraphrase and then duplicating it as a quotation. For example, if a synthetic source says `The agency recommended continued supervised visitation`, write: The agency recommended “continued supervised visitation”. Do not write: The agency recommended that visits remain supervised; it recommended “continued supervised visitation”.
- The full source passage supplies the meaning and context; a short quote is an exact-wording anchor, not independent proof of an inferred proposition. Use a quotation only when its relationship to the point is unambiguous, and paraphrase otherwise. Preserve speaker attribution, denials, uncertainty, material qualifications, and event dates around the quoted words. Do not turn an allegation or recommendation into a finding or order, or trim away a negation to imply the opposite meaning.
- Copy source wording exactly: do not stitch fragments, insert ellipses or bracketed substitutions, silently clean up OCR, or change words to fit your sentence. Choose a different intact phrase or paraphrase when a faithful short quotation will not work. Never invent a quotation when no suitable anchor exists.
- Use double quotation marks only for genuine record language, with punctuation outside the closing quotation mark. Keep each quoted phrase continuous, without a line break or sentence-ending punctuation inside it. Do not emit RecordPrep quote-id placeholders or manufacture Markdown links; Focus makes the quoted words clickable.
- Distribute useful anchors across the answer's important points rather than clustering them in one passage or repeating the same quote unnecessarily. There is no fixed quote count per paragraph, list item, or answer. A quotation should help locate source language, not force an extra sentence, insignificant detail, or unrelated background into the answer.

These length, linking, and presentation conventions are not an acceptance gate; source fidelity and factual accuracy remain required. A missing title/subtitle or an imperfect subtitle must never suppress, delay, or trigger a retry of an otherwise useful answer. Substantive usefulness, factual care, and speed take priority. Submit an imperfect but useful answer unchanged rather than initiating a self-audit or corrective turn.
