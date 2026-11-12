# Exact quotation navigation for topic-note summaries

## Producer status after the RecordPrep rollback

RecordPrep's quote-integrated topic-note redesign was rolled back to `63f9e13`.
The current producer retains the digest/quote-bank pipeline, with record-wide
Focus-style verification and historical phrase-link navigation. The consumer
support described below is retained compatibility code; it does **not** mean
RecordPrep currently generates schema-5 topic notes or metadata-7 summaries.
References below to matching RecordPrep copies describe the earlier coordinated
implementation, not the current rolled-back producer tree.

## Retained consumer implementation

Focus consumes RecordPrep's quote-integrated topic-note summaries in the actual
reader, not just an isolated loader. New work uses row schema **5**, Markdown
**4**, final metadata **7**, and edition page-map **3**. Historical formats keep
their recorded behavior and are never converted on read. Profile schema 14/API 1,
research instructions, answers, citation-range handling and private settings are
unchanged.

There is **no quotation-repair or approval workflow**. Unresolved quotations stay
readable, have no guessed source link, and produce an accessible warning. They do
not stop RecordPrep's automatic preparation or require lawyer intervention.

## Rendering and navigation

- `quote_navigation.py` independently validates the committed TXT/metadata pair,
  final-text and navigation hashes, permitted physical inventory, original UTF-8
  source hashes and Unicode-codepoint spans. Source text is not phrase-searched.
- `app.py` loads navigation before editions. Continuous and paginated summaries
  tag validated occurrences by their exact occurrence ID; unresolved occurrences
  receive emphasis without a navigation tag. Clicks revalidate the current final,
  metadata, source and occurrence before changing pages.
- Raw source ranges map through CRLF/CR-to-LF normalization and the selected
  readable/original transcript presentation. Exact later repeated occurrences are
  highlighted and scrolled into view, not replaced with the first phrase match.
- `quote_projection.py` is byte-identical to RecordPrep's copy. It removes only
  ledger-owned delimiters, maps display boundaries and projects PDF fragments.
  Glyph alignment is whole-document and monotonic; it is not source matching.
- `summary_editions.py` accepts schema3 with unchanged Letter-v3 typography.
  Fragments spanning PDF pages retain one occurrence identity. It recomputes
  fragment coverage and rejects changed labels, IDs, offsets or navigation hashes.
  Physical record-heading links retain exact PDF glyph labels (including `ﬃ`);
  their literal text slice and physical target remain validated. Typography-only
  glyph equivalence in the producer is not a fuzzy source quotation search.
- Missing/damaged/unknown new-contract metadata, a changed final, or an interrupted
  committed pair disables trusted navigation. Schema3/prior-new identity prevents
  downgrade to historical phrase-search authority, even if a sidecar disappears.
  Historical schema1/2 maps are not accepted for a current metadata7 summary with
  identical visible TXT. A stale edition may fall back to independently valid
  continuous ledger rendering, never to guessed phrase navigation.
- Unsafe paths, symlinks, hard links, special/oversized sources and destinations
  outside the selected bundle's permitted inventory are refused. One stale or
  unresolved occurrence does not disable other independently valid occurrences.

`load_summary_navigation()`, `navigation_display()` and
`revalidate_destination()` are read-only. Hash agreement proves integrity, not
semantic fidelity, proper-name casing, authorship or legal correctness.

## Acceptance evidence

All testing used disposable sources/environments, synthetic HOME/XDG/Pi state,
fictional records, `umask 077`, and metrics disabled on the current Home computer:
`/tmp/quote-topics-7CWoMq`.

- Full Focus suite: **991 passed, 5 skipped**, 11 passing subtests. The skips are
  existing owner-policy controls, not new-navigation acceptance. Final run/logs
  are recorded in RecordPrep's implementation report.
- Independent loader/integration tests cover all three summary kinds, source
  and final staleness, missing/damaged metadata, case-adjusted excerpts, repeated
  phrases, raw/display offsets, actual GTK activation handlers, schema3 physical
  PDF splits, fragment damage, navigation-only edition invalidation and downgrade
  refusal. These are not claims of native input for every unit scenario.
- Native input in the disposable Focus application verified three actual quote
  activations: paginated summary → readable transcript; continuous → readable;
  continuous → original. Each selected the intended **second** “notice before
  entry” occurrence, with exactly three physical-page events and no phrase-search
  events. The unresolved quotation remained readable with a disabled link and
  visible warning.
- Changing the fictional source before a native click increased the warning to
  two unverified/stale quotations, without another page or phrase-search event.
  Evidence: `focus-native-automatic/native-acceptance.json`,
  `native-before-stale.json`, `native-stale-refusal.json`, and the state/event log.
  Only that disposable application was closed; its fictional source bytes and
  timestamps were restored. Maintained real-record windows were not manipulated.
- Independent read-only acceptance loaded all **24** current study6 summaries and
  schema3 PDFs, validated **281** source-bound occurrences, and revalidated each
  through the activation-time destination function. All passed, with no fallback
  or unresolved occurrences. See `final-paid-output-consumer-acceptance.json`.
  This is not native input for all 281 occurrences or proof of narrative fidelity.
- A real current producer PDF/map with a `Traffic` → `Traﬃc` physical heading
  loads in Focus with exact literal offsets, page-12 target and retained quote
  fragments; see `ligature-link-acceptance/{producer,consumer}.json`. That is
  cross-project loader acceptance, not a new claim of native input while the
  desktop is locked.
- Compile/resource checks and byte-equality of shared validators/projection are
  part of final integrated validation. Earlier failed setup/permission/test-harness
  runs remain retained; their existence is not relabeled as passing acceptance.

## Delivery and adoption

See RecordPrep's `docs/quote-integrated-topic-notes-implementation.md` and
`docs/quote-integrated-topic-notes-comparison.md` for producer behavior and the
separate bounded fictional writing study. Mechanical/navigation acceptance does
not establish writing quality.

Deliver the compatible consumer source before producer source. Source delivery
is not a running-process upgrade: restart **Focus first** before explicitly
creating/opening new-format summaries. Existing bundles are not regenerated or
migrated automatically. Commit/push, deployment, maintained-app restarts and real-
record adoption are separate actions, not performed by these tests.
