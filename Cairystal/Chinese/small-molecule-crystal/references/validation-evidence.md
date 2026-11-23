# Separate a corrected model from a quieter report

Use when geometry/statistics disagree or a clean report follows unusual processing. This case-free decision framework can be used within a blind test's permitted general guidance. For reference-guided review only, the historical examples in `checkcif-diagnostics.md` may also help. No automatic scientific-repair engine is implied; already-authorized, justified trials follow the workflow's recorded review gates.

## Identify what was actually tested

Track four outcomes separately: model/data correction, truthful metadata correction, a documented program limitation, and a test skipped/suppressed. Only the first two resolve the corresponding issue. A limitation may justify an explanation but does not prove the unchecked property.

For each delivered report record the exact final-file hash, report origin/version, presence of usable structure factors, successful factor-validation sections, skipped tests and remaining limitations. Masking, twinning, large/disordered structures and nonstandard scattering models can limit validation coverage. A submitted factor file is not enough if pairing or parsing failed. Retain the user's official IUCr upload requirement; a stripped-CIF diagnostic copy is not its substitute.

A program crash, truncated report or successful process launch is not validation success. Preserve the error and input identity, determine which checks actually finished, and report unvalidated sections explicitly. A GUI/plotting stack alone does not establish the cause of a scientific-model failure. Track sample damage, replacement and interrupted measurements as separate provenance events; do not silently combine them into a same-crystal reversible temperature cycle.

Historical advice to withhold FCF because Friedel coverage triggers an alert must not be adopted. Insufficient coverage affects absolute-structure evidence, not merely report appearance. Consult [IUCr PLAT915](https://journals.iucr.org/services/cif/checking/PLAT915.html).

## Internal consistency is not a chemical-distance test

If a reported bond differs from recalculation using the same CIF coordinates/cell/symmetry, investigate stale tables, incompatible pasted blocks, labels, settings, operator numbering and rounding before changing the structure. Regenerate geometry from the accepted final model rather than deleting disagreeing rows. [IUCr PLAT701](https://journals.iucr.org/services/cif/checking/PLAT701.html) distinguishes these inconsistencies from physically unusual geometry.

Distinguish three statistic comparisons:

| Comparison | Diagnostic focus |
| --- | --- |
| CIF statistic versus statistic computed from the supplied FCF Fo/Fc | Same refinement run, reflection selection/flags, thresholds, weights and file pairing |
| CIF statistic versus recomputation of Fc from CIF model | In addition: coordinates, ADPs, occupancies, scattering/radiation, twin and solvent contributions |
| Reported versus recalculated difference-map extrema | In addition: map resolution, interpolation and peak-list filters |

A filtered Q list is not the entire difference map; absence of a peak from that list does not prove a validation artefact. Weak data do not by themselves explain two inconsistent numbers allegedly from the same calculation.

Keep units and uncertainties intact. For example, `105.5(19)` is an angular uncertainty of 1.9 degrees, not 0.19 or 0.2. A density peak in electrons per cubic angstrom divided by an atom's electron count is not an integrated-electron percentage.

## CIF and structure-factor consistency workflow

1. Preserve the exact CIF, FCF, INS/RES, LST, HKL/derived data, external contributions and complete validation output. Record hashes, software versions and the final executed command. A matching basename or timestamp is insufficient evidence of a matched pair.
2. Classify the comparison before changing the model. PLAT920 concerns theta-max agreement. PLAT921/922/923 compare reported statistics with those derived from the supplied FCF observations/calculated factors (and relevant CIF weights). PLAT926/927/928 additionally recalculate structure factors from the CIF structural model. Read the actual report and `.ckf` section 10, as validator versions may describe optional recalculation differently. [IUCr PLAT920](https://journals.iucr.org/services/cif/checking/PLAT920.html), [PLAT921](https://journals.iucr.org/services/cif/checking/PLAT921.html), [PLAT922](https://journals.iucr.org/services/cif/checking/PLAT922.html), [PLAT923](https://journals.iucr.org/services/cif/checking/PLAT923.html), [PLAT926](https://journals.iucr.org/services/cif/checking/PLAT926.html), [PLAT927](https://journals.iucr.org/services/cif/checking/PLAT927.html), [PLAT928](https://journals.iucr.org/services/cif/checking/PLAT928.html).
3. For supplied-factor mismatches, first check stale/mixed outputs, active versus suggested WGHT, thresholds, included/excluded observations and the actual refinement/FCF export mode. If pairing is wrong, regenerate a matched output set from the accepted model in a separate directory. Preserve the required model settings and auxiliary contributions. Do not edit the CIF R values, counts or theta limits to match the warning. SHELXL FCF observations may be extinction-corrected: a naive raw-HKL equality comparison can therefore misdiagnose pairing ([PLAT921](https://journals.iucr.org/services/cif/checking/PLAT921.html)).
4. If supplied-factor statistics agree but model-recalculated statistics disagree, inspect CIF coordinates, ADPs, occupancies, setting/symmetry, scattering/radiation, twin treatment and any solvent/mask contribution. Identify what the validator actually included. PLAT927 alone does not establish twinning or authorize a generic TWIN/BASF instruction. A demonstrated unsupported model contribution is a validation limitation to document, not proof of a correct structure or reason to remove structure factors.
5. For PLAT924/925, compare the full difference-map minimum/maximum, map settings and scattering model. Small differences can arise from interpolation; substantial differences need investigation. Check for IAM versus non-spherical-atom calculations before claiming that numerical differences are only interpolation. A filtered Q-peak list is insufficient. [IUCr PLAT924](https://journals.iucr.org/services/cif/checking/PLAT924.html), [PLAT925](https://journals.iucr.org/services/cif/checking/PLAT925.html).
6. Revalidate the exact accepted artifacts. Record `comparison_kind`, `reported_value`, `recomputed_value`, `factor_pairing_evidence`, `confirmed_cause`, `hypotheses`, `trial`, `new_alerts` and `remaining_limitations`; missing values are null. A new internally consistent report fixes a file/statistic issue, not necessarily the underlying chemistry.

### Missing reflections: locate the processing stage

For PLAT910/911/912, read the missing indices from `.ckf` and compare the preserved measured, processed and exported datasets under the same symmetry/setting and resolution interval. Distinguish never measured, excluded during integration/reduction, omitted in refinement and absent only from the submitted FCF. HKLF5 grouping and symmetry/Friedel handling need their own correct interpretation; do not compare line counts as if they were unique reflections.

Inspect beamstop/overload or collection-strategy evidence when available; an overflow is not merely a statistical fluctuation. Without frames/logs, leave the physical cause a hypothesis. Report low-angle, shell and cumulative completeness separately with their resolution bounds. A few missing low-order reflections can matter, particularly for solvent-density work; a small overall missing fraction does not establish negligible impact. Restore a genuinely omitted valid observation only from preserved measurements with documented correspondence, never synthesize its intensity or adjust cutoffs to hide the gap. [IUCr PLAT910](https://journals.iucr.org/services/cif/checking/PLAT910.html), [PLAT911](https://journals.iucr.org/services/cif/checking/PLAT911.html), [PLAT912](https://journals.iucr.org/services/cif/checking/PLAT912.html).

## Data information must not be manufactured

Measured observations, symmetry-independent reflections, above-threshold reflections and refinement entries are different counts. Derive each from its real processing stage. Preserve weak and negative measured intensities under a suitable F-squared workflow; do not replace negatives with zero. Investigate zero uncertainties at source/format level rather than assigning invented sigma values.

HKLF5 overlap/batch records can invalidate naive unique-hkl counting. Retaining Friedel opposites changes counts, but count excess is not precise Bijvoet coverage. Use actual symmetry-aware pairing. Collection index limits are not necessarily the limits of merged representative indices.

Report completeness at its actual resolution, with direction/shell coverage where relevant. Setting a completeness-reporting limit is distinct from truncating refinement data. Do not move theta limits, hand-edit counts, omit weak reflections, or choose a universal `SHEL 999 0.84` merely to reduce alerts. Inspect raw-frame/processing evidence when background, overload, beamstop, secondary domains or decay is suspected. A large Fo/Fc discrepancy is a diagnostic symptom, not proof a reflection is bad.

## Numerically stable is not scientifically identified

Read `nonconvergence.md`. Locate the moving parameter and relevant correlations, and compare consecutive iterations with appropriate numerical controls. Physical motion at room temperature is not the same as parameter oscillation between cycles. Many cycles, near-unit weighted GooF or a damped small shift do not establish a correct, identifiable model.

Soft restraints add prior information; they do not create independent measured reflections. Exact constraints reduce free parameters only when genuinely applied. Report what was restrained/constrained, where, why, with which targets/sigmas and what limitations result. Do not transfer an ambient-pressure bond target to every high-pressure specimen or use a blanket ADP prescription.

Published structures used only to identify connectivity or a recovered phase are not automatically precision standards for bond comparisons, H-bond geometry, populations or absolute configuration.

Audit element identity even when A/B counts are zero. Cross-check labels against CIF type symbols and SHELXL SFAC indices, then inspect symmetry-aware coordination, charge balance under stated oxidation-state assumptions, ADPs and residual density. A short tetrahedral site assigned a large alkali ion while a supposed framework atom lacks plausible short bonds is an element-assignment investigation, not an invitation to force distances with DFIX. Compare alternative assignments only as documented hypotheses; a lower R value does not make an incompatible identity acceptable. A later RES with changed element types/stoichiometry invalidates pairing with an earlier clean PDF, even if the basename is unchanged.

Parse every report section. Structural A/B totals and publication-metadata A/B totals can be reported separately in one checkCIF document; retain both with their scope. Fix missing publication fields only from real supplied information, never invented author/contact/journal data.

## Representation changes can alter more than appearance

For symmetry/centering see `symmetry-and-twins.md`; for population accounting see `disorder-occupancy.md`.

- Synchronize coordinate transformations with ADPs, hydrogens, constraints, geometry symmetry codes and reflection/twin settings as applicable. Do not copy a transform from an old tutorial without checking its determinant: inversion is not ordinary translation and changes handedness.
- A molecule's center of gravity inside the cell does not require every coordinate in `[0,1)`. Networks and special-position fragments need not be duplicated into an artificially complete finite asymmetric-unit molecule.
- H-M, Hall, IT number and symmetry operations must describe the same setting. A group reverse-derived from a faulty operation loop is not proof of the physical space group. Near-equal axes or a monoclinic angle near 90 degrees do not alone justify higher symmetry.
- CIF disorder group signs and SHELXL PART signs require exporter-specific interpretation. Neither is a universal population rule. Special-position factors, shared sites, independent disorder assemblies and H ownership must be audited explicitly.
- A generic TWIN/BASF is not necessarily an inversion twin: `diag(-1,-1,+1)` is not `diag(-1,-1,-1)`. Check the actual law and scattering contribution before identifying BASF with an absolute-structure estimate.
- A consistent factor-of-two change in formula unit and Z can leave cell composition, density and F(000) unchanged. Audit the chosen formula unit and site-orbit totals before changing occupancies. In contrast, an element-specific cell-content deficit requires locating its site, multiplicity and population; a generic "disorder" response does not resolve it.
- Author responses and skipped/suppressed tests are evidence of limitations, not successful repairs. For disordered structures inspect which atom subset ADDSYM actually used; exclusion of many sites may leave symmetry unchecked. For masked solvent preserve uncertainty in composition and contributions to Fc rather than filling a guessed formula to remove a void alert.
- A triclinic lattice can accidentally have right angles; exact imposed angles without uncertainties merit a cell-refinement/setting audit, not fabricated decimals or automatic promotion of symmetry. Strongly restrained geometry can appear very precise even in a poor-fit model; report the prior-information dependence and do not equate displayed precision with experimental accuracy.

For proportionate routine handling, see [routine twin routing](routine-twin-routing.md): supported HKLF 4 models no longer receive a blanket TWIN/BASF delivery rejection; no evidence means no extra twin search, not proof of absence.
