# RecordPrep schemas 7/8 reader conformance

Only `focus/profile_contract.py` mirrors RecordPrep byte-identically for historical
metadata/snapshot validation. `record_categories.py` additionally maps the new
`CT_report_first_page` marker to the existing Report category, so sidebar/reading
classification does not treat that first page as unknown. No category or UI layout
is added. `profile_artifacts.py`, artifact formats, Focus's neutral research
method, prompts and tools are unchanged.

The validator accepts immutable RecordPrep content schemas **1–8**. Schema 7 still
requires classification version 2: `page_types.rt` / `.ct` exact application key
sets and `first_pages` with exactly the original three keys. Schema 8 requires
classification version 3 with a fourth key, **first_report**. Both structured
formats retain nonempty bounded descriptions and fixed Basic output identities.
The new positive start marker is `CT_report_first_page`, not a Basic category.

Classification v3 also accepts a lossless compatibility editor object: the seven
historical flat task strings, `schema_version: 3`, and `first_report`. All old
custom strings and inert dates remain literal, without splitting recognition prose.
This representation can coexist with old naming in a manifest-schema-6 draft,
consistent with independently versioned resource support.

Naming version 4 retains `reports` and `forms` arrays of `{id, name, guidance}`;
IDs and canonical names are unique, guidance may be empty. Old naming formats
remain readable. Unknown/cross-side/duplicate keys, unsafe paths and malformed or
oversized resources fail closed. Historical date text is not selected by
`classification_dates` compilation. No profile instructions supply Focus research
behavior; validating a RecordPrep snapshot does not authorize compiling it as
Focus research.

The RecordPrep-only pipeline now detects report starts independently and uses
catalogs for naming only. Focus reads its accepted boundary/source-map output with
existing formats; this shared validation change does not implement or duplicate
that preparation behavior.

Run `tests/test_practice_profiles.py`, `tests/test_recordprep_schema7.py`, and the
profile artifact/map-reader tests in a disposable Focus checkout/environment.
Do not replace the pre-existing uncommitted schema-6 changes or include unrelated
`.pi/` material. No personal stores, case files, settings or research instructions
are migrated, selected or modified by this reader support. Local result:
profile/schema tests **64 passed, 6 subtests passed**; the category/reading
regressions bring the combined focused suite to **182 passed, 6 subtests passed**.
See RecordPrep's chronological validation report.
