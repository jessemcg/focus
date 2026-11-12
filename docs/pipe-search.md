# Pipe-tolerant phrase search

Focus Find and historical phrase-link search treat ASCII `|` as a space in the
query and temporary source-search copy. The rule lives in `NORMALIZE_REPLACEMENTS`
in `focus/core.py`, so both the fast page-rejection pass and the mapped highlight
pass use it. RecordPrep's `recordprep/quote_search.py` mirrors the rule under
`focus-phrase-search-2`; neither app imports the sibling at runtime.

For example, `NEW INFORMATION` matches source `NEW 3 | INFORMATION`: the pipe
becomes whitespace and the existing bounded numeric bridge skips `3`. The rule
works even if transcript layout detection cannot recognize a flattened gutter.
Adjacent bars separate words rather than concatenating them; substantive extra
words and the existing numeric-bridge limits still prevent a match. Other
punctuation is not broadly stripped. Search does not certify semantic accuracy.

Source files and displayed record characters remain literal. Replacing one bar
with one space preserves normalized-to-source offsets; a hit highlights the full
original span, including any intervening number/bar. Exact occurrence-ledger
navigation is unchanged and must not fall back to phrase search.

No configuration, bundle migration, generated-summary rewrite, new model call or
launcher change is required. Restart an already-running Focus instance to load
changed source. RecordPrep's changed extraction identity requires explicit summary
generation for old saved verification labels to change; nothing is relabeled on read.

## Validation

- `tests/test_pipe_search.py` covers bars with/without spaces, query bars, retained
  word mismatches/numeric limits, mapped offsets and the actual search worker in
  both hearing-eligible and raw modes, using synthetic sources with byte/mtime guards.
- 180 direct comparisons with RecordPrep's updated matcher passed.
- Full isolated Focus suite: 996 passed, 16 skipped, 19 subtests passed.
- Full isolated RecordPrep suite: 1069 tests, OK with 8 skips.
- A separate synthetic Focus app instance exercised real asynchronous search,
  showed `1 / 1`, and visibly highlighted the phrase across `NEW 3 | INFORMATION`.
  Desktop observation confirmed the bar remains in the displayed record. The
  synthetic app's source bytes/mtime were unchanged. No real settings were used.
- The user's reported quote on file page 26 matched both updated implementations
  in a read-only check; its source bytes/mtime were unchanged.

Source changes remain separate in the Focus and RecordPrep repositories. Existing
unrelated uncommitted work in both is preserved; no commit, deployment or restart
of the user's running applications was performed.
