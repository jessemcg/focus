# RecordPrep naming-v5 compatibility

The shared `focus/profile_contract.py` mirrors RecordPrep byte-for-byte and accepts
naming resource5: report/form cards may have `naming_mode: fixed` or `source_title`;
absence means fixed. Stable IDs, names/fallbacks and descriptions remain literal
metadata. Naming4 still rejects new fields, schemas7/8 still require naming4, and
unknown versions/modes remain rejected.

RecordPrep Dependency1.13.0 selects agency reports by description and stores their
actual first-page title in the existing `name` field. Its `naming_rule_id` metadata
identifies the selection rule, not a research instruction. Focus's reading/search,
research method, source-map schemas, summaries and UI are unchanged. There is no
profile migration, source-title extraction or new model work inside Focus.

Validation on the current Work computer used a disposable tracked-source checkout,
locked separate environment, temporary HOME/XDG and fictional data. Full pytest:
**860 passed, 16 skipped, 11 subtests passed**, with eight existing deprecation
warnings. Shared validator/artifact byte parity was checked. No private settings,
case/profile files, maintained application or the pre-existing untracked `.pi/`
directory was changed.
