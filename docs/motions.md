# Motions and usable-summary controls

Focus remains profile-free: preparation rules and summary topics belong to RecordPrep.
The mirrored, reader-only contracts accept content schema **14**/profile API 1,
omitting/rejecting `hearings`, `motion_naming` and `motions` resources. Motion naming is
application-owned in RecordPrep; report/form naming remains profile-owned. Historical
motion catalogs are readable data, never compiled instructions.
Historical schemas 1–13 and naming formats 1–5 stay readable without writes or implicit
adoption. Keep **both** `profile_contract.py` and `profile_artifacts.py` byte-identical
to RecordPrep. Dependency 1.17.0 supplies this contract; the application owns every
new motion summary's Request/Reasons method, not Focus or preparation profiles.

Hearing topics are also fixed, with practice-neutral Appearances. New hearing
row4/Markdown3/meta6 data uses the strict `recordprep-hearing-topics-1` descriptor;
summary availability accepts valid empty/nonempty hearing metadata without writes.
Historical headings/catalogs remain as recorded. The serialized `parent_appearances`
ID stays stable, but new display text is Appearances. Report topics and report/form
naming remain profile-owned in RecordPrep; none supplies Focus research instructions.

Optional validated `motion_groups` describe logical entries over unchanged physical
`documents`. They retain exact member spans, source titles, roles and lead anchors;
source-map aliases and per-page `motion_entries` provide navigation context, never
instructions or authoritative findings. New grouping schema **2** /
`recordprep-motion-organization-2` is deterministic classification continuity: from a
named explicit lead, every following adjacent motion page shares one entry until a
non-motion page or missing classification interrupts it. Independent motions,
oppositions, replies, parties, dates and titles do not split that run. Unnamed internal
components keep empty source titles; only the lead must be named. The first component
owns the entry ID/anchor/title/date, including unknown dates. Neutral `motion packet`
metadata and `lead`/`continuation` roles make no finding of substantive support.

Schema **1** retains its historical legal-relationship semantics, nonadjacent support,
support preceding the lead, historical names/dates and saved coverage statuses. New
maximal-continuity restrictions never apply to those artifacts. Unknown version/contract
pairs fail closed. Physical `counts.motions` and logical `counts.motion_entries` stay
separate; schema-2 map validation checks exact physical documents, aliases, page membership
and both counts against its inventory. No source-map schema or research method changes.
Missing grouping preserves historical named-singleton browsing without migration.

New packet labels use the lead's recorded source title, even if an independent or
opposing filing follows it. One summary section explains all included requests and
reasons with party attribution and distinct positions; grouping does not imply support.
“Complete” in new grouping means selected-inventory accounting, not legal relationship
review or inclusion of every motion fragment. Historical labels stay literal. New motion final metadata schema **6** supports
both nonempty and checked-zero summaries. Fixed-layout PDF editions carry heading links
to the lead anchor, not the lowest member page; supporting-paper quotations still
search original physical source pages. No repagination, research-policy or renderer
layout change is required.

`MOTIONS`, `CT_motion`, `CT_motion_first_page`, motion boundaries and source-map motion
documents map to Motion, distinct from Procedural filing/Report. Standardized substantive
requests use these same motion identifiers; see [Procedural filings](procedural-filings.md). Light rose is **#A04F5F**, adjusted
from the proposed #A04454 to satisfy the existing colored-background contrast contract;
dark rose is **#E39AA8**. Category treatments otherwise preserve the established
selection, image/text and theme behavior.

Sidebar presentation is Procedural filings → Hearings → Reports → Motions → Minute Orders, then
custom groups. Hide known **and custom** groups only when they have neither a bookmark
nor their own page. Preserve the canonical parsed TOC, bookmark order, own-page groups
and expansion state across reloads. This is presentation, not a rewrite of `toc.txt`.

The top mode strip wraps using a FlowBox. Motions opens the final motion summary,
including validated PDF/page-map editions and the established text/quote navigation.
The direct case-tool action is `show_motions_summary`, alongside existing summary
actions. Source inference recognizes `motions_sum_*`, manifest `summarized_motions`
and optional `summarized_motions_pdf` / `summarized_motions_pages`; source-map displays
use the paper's actual title and date, preserving individual paper identities.

All four summary buttons (Hearings, Reports, Motions, Minutes) are visible only when
a usable, nonempty final exists. `summary_availability.py` is read-only and independent
of GTK/profiles/model freshness. It distinguishes available, empty, missing, unreadable
and intermediate content. It rejects digest/facts artifacts and reserved digest markers;
reads legacy prose without demanding metadata; and treats matching-hash supported
final metadata with zero item IDs as empty. Invalid/stale metadata adds a diagnostic,
not a false zero. Exact title-only and title-plus-this-case-name historical outputs are
empty; a real document heading with null categories remains a document. Do not classify
arbitrary short prose or a missing/unreadable file as an empty record.

Preferred current manifest finals outrank directory legacy fallbacks. A selected empty
final must not fall through to a stale populated legacy file. Availability is cached
per case and file/sidecar signatures, bounded per kind; recompute on TOC reload/window
reactivation. Hide the FlowBox wrapper as well as the button. If the active summary
becomes unavailable, return to Agent Q&A, preserving the saved summary/edition on disk.
Direct actions use the same availability decision, not separate filename-only logic.

No private configuration/case migration, provider call, app restart, deployment,
dependency or entry-point changes are needed. Publish this compatible consumer before
the RecordPrep producer if publication is separately authorized. See RecordPrep's
`docs/motions-workflow.md` and the offline validation report for workflow/adoption and
actual validation evidence. See [grouped-motion validation](grouped-motions-validation.md)
for the current checks; [the original motion/category validation](motions-validation.md)
remains historical evidence.
