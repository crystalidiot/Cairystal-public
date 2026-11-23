# Disordered ADPs: choose supported freedom, not a quieter alert

For PLAT250 or many ellipsoids sharing a major-axis direction, use [systematic-error diagnostics](systematic-error-diagnostics.md) before extending local ISOR/SIMU to the whole structure. PLAT250 is an average-tensor check, not a single-atom shape test.

Use for large minor-component U, NPD, or comparisons of anisotropic (ANI) and isotropic (ISO) refinement. Establish elements, chemistry and populations first via [chemical-model-and-density](chemical-model-and-density.md) and [disorder-occupancy](disorder-occupancy.md).

## Identify the actual defect

- Separate **tensor shape** from **displacement magnitude**. [PLAT213](https://journals.iucr.org/services/cif/checking/PLAT213.html) concerns principal-axis anisotropy; [PLAT220](https://journals.iucr.org/services/cif/checking/PLAT220.html) concerns the Ueq range for an element. Replacing a tensor with a scalar does not establish that a large-U problem is solved.
- Read U/s.u., Cartesian tensor eigenvalues, nearby difference density, occupancy/U/position correlations, overlap of alternatives and the largest shifting parameter. Large U can reflect motion, unresolved sites, misassignment or weak information; it does not identify one cause uniquely.
- Check complete fragment correspondence before SADI/SAME. Similar labels or spatial proximity need not represent equivalent chemical or stereochemical roles. Inspect all targets affecting a pair and flexible 1,3 distances; correcting a mapping need not reduce an unrelated U anomaly.
- A positive-definite restrained tensor is not an independently determined tensor. Record restraint residuals and whether removing/relaxing the prior changes the result materially.

## Choose a comparison

Use the least additional complexity supported by the evidence. Depending on the defect, compare an unchanged ANI baseline with a limited ISO trial, or with a justified local ADP relationship. Whole-minor-component ISO is a separate hypothesis, not a default for every partial atom. Keep HKL, reflection selection, weights, geometry and population topology fixed where possible; list unavoidable changes.

Instruction distinctions, checked against [SHELXL](https://shelx.uni-goettingen.de/shelxl_html.php) on 2026-10-24:

| Instruction | Meaning relevant to the comparison |
|---|---|
| EADP | Exact equality; linked atoms must all be ISO or all ANI. Spatial overlap alone does not prove equality is correct. |
| RIGU / DELU | Bond-direction displacement relationships, not equality of all components. RIGU is ignored for pairs involving ISO atoms. |
| SIMU | Soft similarity of neighbouring displacements; distance selection can include different PARTs. Audit actual pairs and effective sigmas. ISO/mixed pairs need particular caution and suitably weak treatment. |
| ISOR | Soft approximate isotropy of an ANI tensor; it is not conversion to a single independent Uiso. |

Do not tighten sigmas until a letter changes. Terminal or freely rotating groups need not share neighbouring tensors. Preserve a weaker or unrestrained sensitivity control when informative; do not universalize a specimen's SIMU values. A threshold-crossing B-to-C change remains prior-dependent if the B returns when that prior is relaxed.

### Whole-molecule SIMU tests

Separate selection scope from restraint strength. Identify the requested molecular component explicitly, excluding unrelated independent molecules/counterions; replace overlapping SIMU instructions deliberately rather than stacking duplicates. Read the actual LST pair list, including terminal sigmas and cross-PART pairs. A distance-selected pair between mutually exclusive orientations is not a chemical bond and needs its own justification.

For a strength-only sensitivity test, retain the same atoms, distance cutoff, pair list, terminal-to-other sigma ratio and all other model/data choices, changing only the common sigma scale. Changing the cutoff at the same time confounds strength with scope. Compare population/s.u., local residual density, geometry and restraint residuals as well as U and alert letters. Report mixed ISO/ANI coupling and unusually strong priors explicitly; zero A/B alone does not promote the candidate.

## ISO conversion checks

1. Freeze baseline files and hashes. Identify the precise atoms; keep their coordinates, elements, PART and SOF roles.
2. Initialize Uiso from the tensor-derived Ueq in the actual cell metric, not the mean of raw U11/U22/U33 in an oblique cell. Use reliable crystallographic conversion or the paired exported Ueq.
3. Remove/revise incompatible mixed ISO/ANI EADP and no-longer-applicable tensor instructions. Check that a blanket ANIS does not turn the atoms back to ANI. Retain or deliberately test justified scalar restraints; document that choice.
4. Recheck H parent U links, population membership, UNIT/formula and restraint/parameter counts. Read the final RES/CIF, not only the edited input.
5. Compare bounded full-model runs: fit on identical observations/weights, shifts, NPD, local residual density, geometry, occupancy/s.u. and sensitivity to restraint strength. A Q-peak list and extrema are not a complete spatial difference-map inspection; state missing map coverage.

At a general unconstrained site ANI ordinarily has five more displacement parameters than ISO; constraints/special sites change the actual difference. Use the LST count. A small R increase after reducing freedom is not automatically a worse scientific model, and a small R decrease with more freedom is not automatically an improvement.

## Observed limit, not a recipe

The private 2026-10-24 case-20 matched-data experiment retained both models. Whole-minor ISO with inherited local SIMU converged with 49 fewer parameters and 147 fewer restraints, but official checkCIF still had one PLAT220 B (U range 9.2 to 8.7). The unrestricted-ISO control drifted and did not converge after 24 cycles. Thus neither "ISO clears B" nor "remove restraints for a truer answer" was supported. C37B gained an independent scalar, while the large C34B/C35B magnitudes remained unresolved. This is not expert acceptance or a never-seen blind result.

Exact private metrics and original official reports: `training_runs/case20_minor_iso_20261024/`. Preserve failed alternatives even if their preassigned directory name says `converged`; use the actual gate status.

In the subsequent 2026-10-25 case-20 tests, local ISOR did not resolve the magnitude warning. Whole-cation SIMU did lower PLAT220 from B to C, with official validation reaching zero A/B. However, doubling sigmas with the same pair list/cutoff restored B; population shifted and local difference-density improvement was not uniform. This demonstrates restraint sensitivity, not a proven repair of the disorder model. Retain the zero-A/B result as a review candidate alongside the baseline. The actual pair audit included close cross-PART contacts; do not reuse this case's sigmas as a general recipe. Private evidence: `training_runs/case20_isor_20261025/` and `training_runs/case20_whole_simu_20261025/` (comparison, pair audit, maps and exact official report).

## Final artifact

Keep unresolved alerts and significant C/G findings visible. Revalidate the exact changed CIF online when requested/authorized; see [workflow](workflow.md). The Word coordinate table includes both Ueq and Uiso; its tensor table contains only ANI rows. Verify non-H total = ANI + ISO, matching labels, populations and hashes. A smaller model may be a defensible alternative without replacing the original automatically.
