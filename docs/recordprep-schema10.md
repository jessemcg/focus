# RecordPrep schema 10 compatibility

Focus's vendored `profile_contract.py` remains byte-identical to RecordPrep's.
The validator accepts RecordPrep content schemas **1–10**, with `profile_api: 1`.
Unknown schemas fail closed. Schema 10 removes the `minutes` manifest resource/file
and rejects its reintroduction. Every supported schema compiles an empty minute
profile-resource list. Schemas 1–9 preserve historical bytes without rewriting them.

RecordPrep Dependency1.11.0 applies fixed practice-neutral instructions to every new
minute run, including custom profiles and unassigned contexts. Profiles still own
Report Names/Form Names and hearing/report topics. Existing summaries remain readable
and untouched. Adoption is explicit minute generation with new affected-order model
work, followed by normal optional edition/overview/source-map refresh. No profile
reset/save or upstream rerun is needed solely for this change.

This is reader/metadata compatibility only. No Focus research instructions, runtime,
UI, minute TXT/edition rendering, source-map schema, cross-app runtime imports or
`profile_artifacts.py` changes. Focus's fixed research method never consumes preparation
instructions. The unrelated untracked `.pi/` directory remains untouched.

Tests: `tests/test_recordprep_schema10.py` validates schemas1–10, exact historical
bytes, empty minute components and rejection of reintroduced minutes/unknown schema/API.
Run the full pytest suite and existing minute TXT/edition consumers in an isolated
checkout/environment via the absolute UvEnvironments/project-env helper. Exact local
results are recorded in RecordPrep's `docs/application-minutes-validation.md`.
