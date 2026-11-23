# Whole-fragment alternatives: from an abnormal site to a testable model

Read after [disorder-occupancy](disorder-occupancy.md) for correlated orientations or element-interchange sites. This is an evidence-guided review workflow, not an enabled automatic repair rule.

## Build a configuration table before PART instructions

For each complete alternative, list shared carriers, branches, terminal elements, H ownership and population. Keep two mappings separate:

- **Chemical roles:** corresponding bonds/atoms in equivalent orientations, used to assess comparable geometry.
- **Spatial pockets:** sites occupying the same region, which can be different elements. Nearest neighbours or matching labels are not necessarily chemically equivalent.

For example, two whole orientations of a chloromethyl/ethyl-substituted ammonium group can exchange Cl and methyl between two pockets. An abnormal apparent carbon can therefore represent an averaged orientation, not an isolated wrong element. Check competing element, symmetry and data explanations.

A supported full N pivot stays once in PART 0; alternative branches and H follow their own populations. Use one population for pockets belonging to the same physical configuration, not independent invented substitutions; do not couple other disorders without evidence. Check complete chemistry and cell contents.

Start alternate coordinates from this run's density and chemically plausible geometry. Coordinates taken from a revealed answer make the result reference-assisted. A molecular graph alone supplies no experimental disorder ratio.

## Separate data, twin, disorder and restraint effects

Keep HKL grouping, resolution/OMIT selection, weights and extinction fixed for a local comparison. Twin BASF is not molecular orientation FVAR. Supplied HKLF5 is upstream information, not evidence that this agent independently integrated twin domains.

Compare the unsplit baseline and justified split candidate: parameters/restraints, population/s.u., local density, geometry, tensor eigenvalues and convergence. More flexible models tend to lower R; that alone does not select them. Use [adp-model-selection](adp-model-selection.md) for restraint sensitivity and limited/whole-component ISO alternatives.

PART suppressing an impossible bond does not prove mutually exclusive physical configurations. Rebuild H after coherent non-H connectivity, including alternative H directions on shared carriers. A BAD AFIX message can expose a mixture of conformers rather than a software defect.

## Observed limits

Private 2026-10-21 reference-assisted N3 comparison, same 4,966 HKLF5 observations and fixed weights, no new OMIT/EXTI:

| Candidate | R1 | NPD | Max shift/esd | Interpretation |
|---|---:|---:|---:|---|
| Unsplit | .0505 | 0 | .000 | Stable but incomplete alternatives |
| Split, tight ADP restraints, 24 cycles | .0463 | 0 | .535 | Not converged |
| Split, relaxed restraints, 24 cycles | .0445 | 1 | .181 | Unphysical tensor remains |
| Same relaxed split, one C ISO, 24 cycles | .0445 | 0 | .001 | Numerically stable; local A4/B1/C5/G37 still requires review |

This is neither independent blind solving nor a new official IUCr report. Do not compare these R values with a differently filtered HKLF4 answer. Evidence: `training_runs/disorder_learning_20261021/`.

## Input and interpretation controls

- Missing elements invalidate a complete-element blind test. A reviewed Cu/I input omitted Cs/Cl; verify chemistry and documented HKL reindexing before proliferating partial heavy atoms or masking solvent.
- Layered disorder may require explicit complete configurations or a clearly labelled marginal model. Two half-populated frameworks plus terminal C/Cl mixtures are not described by a single PART fraction. Do not multiply every population by .5 again.
- An off-axis half-populated atom and an on-axis full site can contribute identically to the cell while imposing different physical constraints; use actual orbit multiplicity.
- Audit reference restraint targets, including reversed pairs, before reuse. Conflicting 1.54/1.79 Å targets or unusually tight sigmas remain defects even in a converged published construction. Changed observations/weights/priors invalidate simple R ranking.
- Label repairs can remove PLAT017 without improving the structure. Preserve a renaming map, validate exact outputs, and reject unsupported atom-label syntax rather than silently dropping atoms.

## Transfer test

Select different reflection datasets, not renamed teaching data. Declare allowed inputs and prior exposure; exclude source coordinates, ADPs, PART/FVAR, restraints, OMIT and twin fractions unless specifically part of the test. Preserve the necessary HKLF indexing/grouping information.

Freeze candidates, rejected alternatives and limitations before authorized answer access. Score framework, connectivity, configurations/populations, convergence and validation separately. Do not modify a frozen result after revealing an answer and count it as blind success.

The private Co/Cl, Cu/Br and Fe/Cl transfer reached convergence for Co/Cu but not Fe; the Cu all-ANI alternative had seven NPD sites. Local A/B counts were 4/5, 4/0 and 8/12 (four common A concern unavailable metadata). No case was accepted as a complete independent disorder solution or newly submitted to IUCr. Frozen results and post-reveal analysis remain in `training_runs/blindtest_20261021/`.

### Ring success versus over-split chain: answer-withheld repeat

The 2026-10-25 organic cases 11 and 06 were freshly solved from coordinate-free inputs; prior collection exposure was disclosed. All candidates and failures were frozen before reference access. Evidence: `training_runs/disorder_transfer_20261025/` (local PLATON only, human review pending).

- **Use internal evidence without importing an answer:** case 11's own difference peak and independently solved second molecule supported a ring/methyl alternative. Removing SIMU/RIGU and then SADI retained convergence, positive tensors and improved local density. Final R1 .0516, zero distance/ADP restraints and local A0/B1 supported the local disorder; shared EXYZ/EADP and riding-H constraints remained. The B concerned missing absolute-configuration reporting, not the disorder. This is a supported candidate, not automatic acceptance.
- **Count physical split sites, not PART rows:** case 06 split six chain sites while three upstream pairs were shared by EXYZ/EADP. A quieter validation result still contained a 1.360 Å within-conformer C–C bond and initialization-dependent populations. The revealed reference split only three physical sites. Treat the independent result as partial, not repaired merely because PLAT360 disappeared; the reference is itself a model, not ground truth.
- **Audit reference comparability:** case 11's 54/46 populations were fixed, not experimentally refined with an s.u.; case 06's reference used nine OMITs. Both reference datasets had resolution limits and different weights. Compare full configurations after consistent molecular symmetry/origin alignment, distinguish fixed from refined populations, and do not rank unmatched R values or borrow exclusions to improve a blind score.

If a revealed model suggests a better split scope, start a separately labelled reference-assisted experiment. Do not overwrite the frozen partial result or retrospectively count that repair as independent success.

### Chain endpoints and prior sensitivity after reference access

The separate reference-assisted follow-up is recorded in `training_runs/case06_reference_repair_20261025/`. It does not revise the independent score.

- Test the split boundary rather than copying the answer. A highly elongated/high-U shared next carbon with adjacent positive/negative residual density can justify a bounded extension test. It does not establish a second position by itself. Compare equal-data/equal-weight candidates, opposite initial orientations and local map samples at identical centers.
- Shared carbon positions can require alternative H directions. If using duplicated carriers to represent these H configurations, constrain the shared coordinates and tensors explicitly (EXYZ/EADP), use complementary occupancies, and audit the summed orbit and H composition. Count physical split sites separately from PART rows; do not count a shared endpoint twice.
- Identify the parameter that oscillates. Here the heavy chain was essentially stationary while a low-population methyl rotor moved. A chemically justified staggered riding methyl stabilized it without artificially fixing the carbon displacement parameter. Do not globally freeze H or heavy atoms merely because maximum shift is high.
- Check the reference's chemistry too. Its shorter split scope and converged published values retained strained bonds/high displacement. In the follow-up, extending three split carbons to four improved the next-carbon local density, but only strong DFIX/DANG priors produced plausible saturated-chain distances; stronger priors worsened fit and other local residuals. Report that dependence instead of presenting restrained s.u. values as independently measured accuracy.
- A different converged reverse-seed minimum is evidence against uniqueness. Preserve both branches and mark the selected candidate for human review, even with all positive anisotropic tensors and no A alerts.

This follow-up retained all 4809 independent reflections. Official IUCr validation returned A0/B1/C4/G22; the remaining intensity-outlier B and strong geometry-prior dependence preclude claiming a complete disorder solution. Case-specific numbers are evidence for this bounded lesson, not transferable thresholds or automatic repair defaults.
