# Focus fixed research method

Focus answers the user's particular question from the active prepared record. It is
specialty-neutral and profile-free: every new session, including previously
profile-bound cases, uses application-owned **focus-record-qa**, version **1**.
There is no advanced profile option, first-use confirmation, profile subtitle or
permanent General badge. The normal Settings action/persistence keys are unchanged.
RecordPrep alone retains practice profiles for preparation.

## Evidence and tools

`focus/agent_resources/SYSTEM.md` delegates to the single canonical
`skills/focus-answer-record-questions/SKILL.md`. Neither legacy `.pi` resources,
private profiles, configuration prompt prose nor bundle metadata supplies research
guidance. Exactly `read`, `focus_record`, and `submit_focus_answer` are model-facing.
No shell, web, image or write tools, vector database, outside legal research or
specialty detection is added. Passive metrics and the follow-up bridge stay unchanged.

The question explicitly invokes `/skill:focus-answer-record-questions`; the wrapper
still loads that canonical skill with `--skill`. Its `disable-model-invocation: true`
frontmatter hides the redundant automatic listing/read invitation, not explicit
expansion. The full workflow is already in the question and remains in follow-up
context; the system prompt does not duplicate it.

Prefer returned absolute `resolved_text_path` values for reads. The existing guard
also accepts `text_pages/<path>.txt` from the active case root, or a bare
`<filename>.txt` for a direct child of that case's `text_pages/`. Either alias may
start with `./`; the existing leading `@` convention is preserved. Reject `..`
components before normalization. No citation-to-filename inference, alternate-root
search or workspace fallback occurs. Absolute paths retain canonical boundary
checks and are never reinterpreted. Only verified canonical regular `.txt` source
files are permitted, including checks against escaping symlinks and other cases.
After permission, only `event.input.path` changes to that verified absolute path;
Pi's built-in read, offset/limit, cancellation and truncation remain in control.
Each read still produces one existing observation and increments the existing
permitted-read counter only when authorized; normalization calls no helper.

Question + bundle → fixed method/input pin → private agent workspace → source
search and verified page reads → unchanged answer handoff → immutable displayed
snapshot → optional user-invoked Save Answer.

Prepared summaries, overview and participant metadata help navigation, never replace
original pages as evidence. Use question/record-derived names, dates, terminology,
roles and document descriptions. Verify attribution, allegations versus findings,
contradictions, negative-search coverage, OCR limitations and causal links. Prefer
contemporaneous primary evidence for why/basis questions without a specialty document
catalog. Do not presume party relationships, procedural stages, an appeal or doctrines.

Do not assert an established cause without read source support. If the event is
supported but its reason is not, deliver the supported portion and state the
missing causal link. Continue targeted research for concrete unresolved issues
with useful leads likely to change the answer, including material contradictions;
otherwise deliver with the limitation rather than waiting for complete certainty.
Unavailable sources or failed optional calls do not erase evidence already read.
Avoid unchanged retries; correct a call only when needed and the correction is
clear. “Not established in the material examined” is not a claim that evidence
cannot exist elsewhere. Allegations, recommendations, findings and orders remain
distinct. These are model instructions, not runtime answer checks or delivery gates.

Quotations are continuous, verbatim source phrases normally containing 6–12 words,
usually 8–10. Prefer the shortest natural substantive anchor that distinguishes the
point over boilerplate; preserve negation, qualifications and attribution. Integrate
quotes grammatically without duplicating a paraphrase, padding to a word count, or
adding irrelevant identifiers. Repeated/copied passages may produce multiple useful
hits: there is no uniqueness requirement or extra search to establish uniqueness.
Useful shorter/longer quotations remain valid, with no fixed count or capitalization
transformation. Python and extension lint warn only above 12 words; the warning is
advisory and never blocks, changes, or retries an answer. Historical saved warnings
remain readable unchanged. Concise titles/subtitles and early useful submission are
non-blocking presentation guidance, not formatting-repair loops or research budgets.

## Runtime integrity

`research_runtime.py` owns `ResearchPin.capture(case_root)`, compilation and private
staging. Component SHA-256 covers effective instructions plus relevant helper,
extensions, follow-up/answer protocols and metadata/artifact validators. Wrapper
permissions remain independently validated by the shell and offline-SDK suite. All specialties receive identical resources/component identity.
The pin hashes canonical case identity, consumed source map, source-page inventory and
content, manifest and selected overview, retaining bounded/path/link checks and
collection-time change detection. Retired FOCUS_RESEARCH_PROFILE_REF is stripped.
Direct helper diagnostics need no live-session pin but use the same fixed retrieval.

Recheck before launch, follow-up transport, helper operations and explicit/fallback
capture. Changed method/input bytes or wrong-case reuse require a new session. Failed
preflight and rejected captures preserve previous displayed output, never silently
relabel an answer with new provenance. Search retains diversification, scope errors,
document unions/intersections, participant aliases/source roles, coverage accounting
and safe paths. Ranking uses explicit query dates and lexical quality, frequency,
coverage/proximity and deterministic page ties—not specialty labels or passage anchors.

## Historical compatibility and no migration

Source-map schemas 1–3, participant schemas 2–4 and supported legacy forms and summary
edition layouts remain readable. Unknown specialty identities are acceptable; unknown
structural versions fail explicitly. RecordPrep provenance stays descriptive.

`research_context.py` accepts strict historical context schema 1 without loading a
snapshot. New context schema 2 has only schema_version, research_method
(`id`, `version`, `component_sha256`), inputs_sha256 and preparation_provenance (or
null). New saved answers use schema 3; saved schemas 1/2 remain readable. The separate
agent answer-handoff schema is unchanged. In-memory conversion preserves historical
metadata/schema identity; unknown or invalid metadata gives bounded errors, not a
fabricated neutral-method replacement. Context surfaces describe Focus research and
RecordPrep preparation separately, without Different specialties warnings or controls.

Configuration reads/startup do not rewrite files to discard obsolete keys. Those
values remain inert; explicit Settings saves retain their established retired-key
cleanup behavior. No automatic configuration migration is performed.

**There is no migration:** never rewrite/delete private profile registries, snapshots,
case selections, config, legacy prompts, saved answers or prepared bundles. Missing or
corrupt retired stores are irrelevant because runtime paths do not open them. Restart
Focus and explicitly ask a new question; no dialog, migration flag or RecordPrep
regeneration is needed. Retired `focus profiles …` returns a concise nonzero diagnostic.
Older Focus versions may not read new schema-3 saved answers. Never down-convert or
delete them automatically.

Only `profile_contract.py` and `profile_artifacts.py` remain vendored byte-identically
with RecordPrep. Store/workflow/editor/manager modules are no longer shared. RecordPrep
runtime, bundled guidance, schemas, fingerprints and pipeline are unchanged.

See [current validation](research-method-validation.md). The older
[profile validation log](practice-profiles-validation.md) is historical evidence,
not a description of current controls or authorization paths.
