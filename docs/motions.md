# Motions and usable-summary controls

Focus remains profile-free: preparation rules and summary topics belong to RecordPrep.
The mirrored, reader-only contracts accept content schema **12**/profile API 1,
retaining `motion_naming` eligibility but omitting/rejecting `motions` topic resources.
Historical schemas 1–11 and naming formats 1–5 stay readable without writes or implicit
adoption. Keep **both** `profile_contract.py` and `profile_artifacts.py` byte-identical
to RecordPrep. Dependency 1.15.0 supplies this contract; the application owns every
new motion summary's Request/Reasons method, not Focus or preparation profiles.

Optional validated `motion_groups` describe logical entries over unchanged physical
`documents`. They retain exact member spans, source titles, roles and lead anchors;
source-map aliases and per-page `motion_entries` provide navigation context, never
instructions or authoritative findings. A motion, opposition and reply remain separate
entries, each with its own explicitly linked support. Support can precede the lead or
be nonadjacent. Physical `counts.motions` and logical `counts.motion_entries` are
separate. Missing grouping preserves historical singleton browsing without migration.

Concise labels identify the filing/request, such as **Motion to compel police records**;
the party belongs in metadata/narrative. New motion final metadata schema **6** supports
both nonempty and checked-zero summaries. Fixed-layout PDF editions carry heading links
to the lead anchor, not the lowest member page; supporting-paper quotations still
search original physical source pages. No repagination, research-policy or renderer
layout change is required.

`MOTIONS`, `CT_motion`, `CT_motion_first_page`, motion boundaries and source-map motion
documents map to Motion, distinct from Form/Report. Light rose is **#A04F5F**, adjusted
from the proposed #A04454 to satisfy the existing colored-background contrast contract;
dark rose is **#E39AA8**. Category treatments otherwise preserve the established
selection, image/text and theme behavior.

Sidebar presentation is Forms → Hearings → Reports → Motions → Minute Orders, then
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
