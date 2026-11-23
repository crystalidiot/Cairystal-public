# Learn rules, not tutorial shortcuts

New source-conflict checks are in [restraint and accounting audit](restraint-and-accounting-audit.md): EXTI versus systematic absences, PLAT250 scope, SAME ordering/H exclusions and accidental metric symmetry. Keep the original claim and the correction distinguishable; do not promote an example reply into a universal repair rule.

Use when reading supplied manuals, videos, papers or solved templates. Preserve originals; keep private datasets and copyrighted source material outside the distributable skill.

## Evidence ledger

Record source identity/version, reviewed pages or timestamp ranges, extraction method, actual visual inspection, missing content and unresolved claims. Extracted text is not reviewed text; static frames do not cover audio or intervening actions. File hashes identify content, not independent specimens. Translations, cropped clips, revised reports and duplicate teaching decks do not count as independent demonstrations.

For solved models, follow [learning-from-solved-models](learning-from-solved-models.md). Learning a supplied construction, reproducing it and independently recovering it are separate achievements. Use the private reading ledger for counts; do not append a new historical paragraph to this skill for each document.

## Before transferring a procedure

1. **Identify the actual case.** Match specimen, phase, temperature, cell/setting, model and reflections. A tutorial may interleave unrelated screenshots or processing stages. Verify what the GUI wrote into INS/RES and what the program actually executed.
2. **Classify the evidence.** Distinguish observations, model assumptions, restraints, diagnostics, display settings, calculations and property-based interpretations. Published or accepted does not mean independently validated.
3. **Check semantics.** Use the applicable primary manual for the installed engine/version; historical command names, defaults, installers and licensing advice are not current contracts. SHELXT/D/S solution and SHELXL refinement instructions are not interchangeable.
4. **Check invariants.** Preserve signed indices, overbars/subscripts, units, basis/origin and direct/reciprocal conventions. Verify formulas, cell volumes, charge, orbit-weighted composition and uncertainty propagation. Quarantine source-level errors instead of silently converting a plausible correction into fact.
5. **Test bounded alternatives.** Retain inputs and explain what changed. Compare geometry, density, ADPs, uncertainty, coverage and convergence as well as alerts/R. A change made together with cutoff, OMIT, weights or restraints cannot establish a single repair's causality.
6. **Promote only a transferable rule.** Store detailed case reasoning in the private notebook. Add or revise one canonical topic reference only when evidence changes a decision, exposes an implementation defect or supplies a useful negative control. Record limitations; do not enable an untested automatic repair.

## Canonical topic references

| Evidence problem | Read / maintain |
|---|---|
| HKL representation, merging, Friedel treatment, processing selection, absorption | [data-reduction-provenance](data-reduction-provenance.md) |
| Format/version pairing, recovered files and basis transformations | [data-provenance](data-provenance.md) |
| Failed phasing or a recognizable but incomplete fragment | [solution-failure-evidence](solution-failure-evidence.md) |
| Symmetry/twin candidate versus confirmation, absolute structure | [symmetry-and-twins](symmetry-and-twins.md) |
| SOF, multiplicity, shared sites and local configurations | [disorder-occupancy](disorder-occupancy.md) |
| Chemistry, H generation, restraints and density interpretation | [chemical-model-and-density](chemical-model-and-density.md) |
| Mask/SQUEEZE/FAB and experimental limitations | [solvent-and-data-quality](solvent-and-data-quality.md) |
| Motionless output, correlations and parameter stabilization | [nonconvergence](nonconvergence.md) |
| Unsafe historical alert remedies and validator coverage | [validation-evidence](validation-evidence.md) |
| PLATON state, geometry and analysis limits | [platon-analysis-boundaries](platon-analysis-boundaries.md) |
| Report/figure/metadata consistency | [report-model-consistency](report-model-consistency.md) |
| Property, microscopy, computational or phase-transition claims | [supporting-evidence](supporting-evidence.md) |

## Shortcuts to quarantine

- Cosmetic acceptance: fixed Z′, chosen symmetry/metadata, omitted weak or negative data, a deleted minor component, prettier ellipsoids or tight restraints solely to lower R/alerts.
- Inference substitution: axis order for every atom's occupancy; number of PART labels for population; static split sites for molecular dynamics; entropy ratios for refined fractions; a solver score for a solved structure.
- Copy contamination: drawing/DFT/ordered-P1 copies replacing the experimental model; stale R values or embedded RES after deleting atoms; neighboring PCF metadata overriding actual sample records.
- GUI overtrust: empty atom selections, disabled AFIX/save safeguards, success banners without outputs, automatic Q-to-H or fragment merges without checking the resulting model. Work on copies and verify targets.
- Data coercion: satellites stripped of their extra index, FCF renamed as HKL, overlapping twin component rows double-counted, phasing-generated reflections reported as measured.
- False equivalences: EXTI versus systematic absences or absorption; Flack versus optical rotation/solution ee; F-based Rw versus F² wR2; restraints versus exact constraints; display B/U/radii versus refinement parameters.

Read-only upstream analysis must not initialize instrument hardware. Preserve raw frames, metadata and processing variants before authorized reprocessing. A failed or skipped check is not a pass. Final-looking reports still require exact model/factor pairing and the user's official IUCr validation workflow.
