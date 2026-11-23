# Chemical reasonableness first; A/B alerts second

The user's decision of 2026-11-23 supersedes the former A/B-first preference. Full validation remains required. checkCIF assesses consistency and integrity; its alert count is not chemical correctness. [IUCr service description](https://checkcif.iucr.org/)

After initial solution, assess atom identities, connectivity/valence, geometry/conformation, H/protonation and charge, composition, occupancy/special positions, ADPs and residual density against the current diffraction data. Supplied chemistry and references are priors to test, not answers to force onto the data. Review known chemical contradictions even without alerts.

Preserve the baseline and rejected trials. Prefer the chemically better, diffraction-supported model; only then compare A/B outcomes among comparably supported candidates. A defensible model may retain alerts or have a slightly higher R. Explain remaining concerns without claiming that explanation removed an alert. Continue refinement, weights, local PLATON, authorized official checkCIF and both Word reports on the selected version.

## Evidence-based comparison

`chemical_priority` records supported, not_assessed, needs_review or contradicted. No screening flag does not mean a chemical pass. Ranking schedules review and never accepts a structure. Ordinary work continues through the agent; this is not another customer questionnaire.

After actual review, rerank preserved trials without repeating refinement:

```text
python -B scripts/compare_diagnostic_trials.py --control CONTROL/result.json --results TRIAL/result.json --chemical-reviews REVIEWS.json --output NEW_COMPARISON.json
```

Map each trial name to a record with the actual `paired/case.cif` `model_sha256`, a specific `basis`, and `checks`: `connectivity_and_elements`, `geometry_and_hydrogens`, `composition_charge_occupancy`, `symmetry_and_disorder`, `adps_and_density`, `diffraction_support`. Values are pass, not_applicable, uncertain or fail. Unknown is not pass. These are recorded reviewer judgments, not independently proven software conclusions.

An interpreted screening exception, such as genuine strained geometry, needs a specific explanation under `addressed_flags`; original findings remain visible. Non-positive ADPs and H/parent PART-population mismatches cannot be overridden by prose. Fixed-list OMIT comparisons remain available, but unresolved pre-existing geometry/restraint conflicts no longer permit automatic working-model adoption.

## Reference-assisted work

Use supplied or authorized structure models in ordinary tasks, including existing CIF/RES/INS models in the specimen directory the user supplied, without repeatedly asking merely because the work becomes reference assisted. Establish whether the reference is the same sample, an analogue or chemical-connectivity guidance. Verify cell/setting and model-data correspondence, full components and occupancy semantics. Refine against the current reflections. Coordinates, populations, H and restraints inherited from a reference remain hypotheses; its R or lack of alerts is not an adoption criterion.

Explicit blind/no-old-model/read-scope restrictions still govern those runs. Do not search hidden answers. Record inherited information and distinguish reference assistance from independent solution and from reference-scored correctness.

The existing review JSON for finish/complete may add `model_origin: "reference_assisted"` and `reference_model` with an authorized local `path`, actual `sha256`, `use` (starting_coordinates, chemical_connectivity or comparison_only), and a specific `comparison_basis`. Keep the existing `chemistry_and_h_reviewed` and actual `basis`. The script checks mode conflicts before reading the reference for hashing, validates the fingerprint, and adds equivalent provenance to both Word narratives. It imports no coordinates and does not establish scientific validity. See the [JSON layout](chemical-first.md).
