# Procedural filings display compatibility

Focus displays the former Form category as **Procedural filing**, and shows both
saved `Forms` and `Procedural filings` TOC headings as **Procedural filings**.
Heading recognition is case-insensitive with surrounding whitespace ignored.
Both aliases keep the existing purple category and first sidebar position.

This is presentation only. `Category.FORM`, `form`, `CT_form` and
`CT_form_first_page` remain compatible identifiers. Canonical parsed TOC titles,
bookmark/document titles, pages and sidebar expansion keys stay literal. Only the
rendered category heading changes; a bookmark actually named Forms is not renamed.
Unknown/custom headings are unchanged. No bundle files or private settings are
rewritten by this change.

RecordPrep recognition-v4 sends standardized substantive requests as CT_motion or
CT_motion_first_page. Focus already reads those as Motion and preserves existing
logical motion groups, physical documents, source navigation and summaries. A stale
Forms TOC entry cannot override explicit motion metadata. Conversely, Focus does not
reclassify historical CT_form pages based on a document title. Regenerate those
classifications in RecordPrep when desired; a display rename does not adopt new
classification semantics. Shared schema files remain byte-identical with RecordPrep.

## Validation

Isolated source/environment and synthetic HOME/XDG under
`/tmp/focus-procedural-validation`; no providers or real cases:

- Focus full pytest: 926 passed, 16 skipped, 11 subtests passed.
- Category/UI tests: 62 passed, including both aliases, unchanged bookmark titles,
  literal expansion keys, metadata precedence, standardized motion inputs and
  byte/mtime preservation.
- `acceptance_procedural_filings.py` under `G_DEBUG=fatal-criticals`: actual GTK labels,
  old/new heading rebind, motion categories and unchanged bundle inventory passed.
  Local Computer Use observed the full Procedural filings label in the sidebar.
- `acceptance_answer_switching.py` under fatal criticals: 320 transitions, no GTK
  criticals, retained reading position passed.

The first full run inherited a group-writable umask and seven unrelated settings
permission tests failed. The isolated runner now uses umask 077; the complete suite
passes without source changes to settings or permission handling.
