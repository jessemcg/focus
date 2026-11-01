# RecordPrep schema 9: metadata compatibility only

The byte-identical vendored `focus/profile_contract.py` accepts RecordPrep content
schemas **1–9**, retaining `profile_api: 1`. RecordPrep schema 9 omits the
`classification_tasks` resource. All structural/page-start/date stage resource
projections are empty, including when validating historical schemas 1–8: retired
prose remains stored/readable, never active instruction authority. Schema 9 retains
naming v1–v4, topic catalogs and minute guidance; malformed, missing, duplicate or
unknown resources and unknown content schemas fail closed.

Only RecordPrep owns the new recognition resource, classification builders,
reference UI, checkpoint work and notice/service routing policy. Focus neither
imports them nor duplicates their pipeline or UI. Focus's fixed neutral research
method, tools, source readers and instruction-free provenance are unchanged.
`profile_artifacts.py` is unchanged and still byte-identical between repositories.
Old snapshots, cases, settings and saved answers are not migrated or regenerated.

`test_recordprep_schema9.py` covers omission, all four naming formats and rejection
of retired/unknown contracts. The existing schemas 1–8 conformance tests continue to
validate historical formats and stored bytes, with inactive classification resource
projections. Full pytest is run in a disposable source/environment/HOME/XDG on the
current computer only; see RecordPrep's `docs/application-classification-validation.md`
for the coordinated local results and UI/quality limits. The earlier
[schemas 7/8 report](recordprep-schema7.md) describes historical format support,
not current instruction ownership.
