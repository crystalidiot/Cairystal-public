# Solvent contributions, experimental limitations and accounting

For strong low-angle disagreements and a proposed EXTI/SWAT/OMIT change, first use [systematic-error diagnostics](systematic-error-diagnostics.md); retain a controlled baseline and inspect intensity/resolution groups, not only overall GoF.

## Explicit atoms before a solvent contribution

Inspect density throughout voids/channels, not only around the target molecule. A void can be empty/porous or contain missed counterions/solvent: volume alone cannot identify its contents. Coherent peaks, chemistry and composition may support an explicit atomistic/disorder model; a diffuse unresolvable contribution may justify a mask after the main model is defensible. Do not mask away an unidentified part of the target molecule or a charge-balancing species without acknowledging the unresolved chemistry.

Record mask program/version, boundary and volume, recovered electrons per void/cell, uncertainty/limitations, assumed solvent identity/content, and the consequences for formula, charge, Z, density, Mr and F(000). Electron counts depend on low-order data and map/model quality; dividing by a chosen solvent's electron number does not uniquely identify solvent or accurately establish a population. Preserve reasonable alternatives and unknowns.

Separate an attempted void search from an enabled and successfully executed solvent model. A mask log with zero accessible volume, or a leftover FAB beside a RES lacking ABIN, is not proof that the final Fc includes a solvent contribution. Read the active model and run output. Keep geometric void count distinct from solvent-molecule count: supplied YH114 logs include four small zero-electron voids and four large populated regions, not eight identified solvent molecules. Preserve probe/truncation radii and unknown CIF void-content fields; do not tune radii to force a desired solvent formula or automatically fill a small electron-count region with water.

With modern SHELXL ABIN/FAB, preserve measured HKL and add the paired solvent partial structure factors to Fc. Do not count the same solvent twice through explicit atoms and an overlapping mask. Retain matching FAB, symmetry/setting, mask CIF details and unmodified observations. Final FCF must represent the actual atom-plus-solvent calculation. The 2010 PLATON manual's HKP/subtracted-HKL recipe is historical, not this workflow's automatic implementation. Changing to/from a mask changes the model comparison; lower R is not proof of the identity/content of the solvent.

SWAT is a different, global diffuse-solvent model, not a void-specific FAB or a measured solvent population. Inspect its actual g/U, covariance with scale and resolution-dependent effect. A reviewed phosphate has U=.0161 and SWAT/scale correlation .990: its calculated intensity multiplier is still about .524 at d=.84 Angstrom, despite small final shifts. Do not describe that as a correction confined to a few low-angle reflections or copy it into another inorganic model without solvent/data evidence. Check [current SWAT semantics](https://shelx.uni-goettingen.de/shelxl_html.php); a stable fit alone neither identifies solvent nor justifies deleting the term automatically.

## Completeness, precision and absorption

Treat a missing/unreadable FAB as a failed masked-refinement run, even if the GUI still displays plausible R values from the preceding unmasked model. Verify the current run's log, successful termination, basename/paths, timestamps and paired RES/FAB/FCF before reporting new statistics or generating the final CIF. The reviewed PART-negative tutorial visibly ends a mask attempt with `CANNOT OPEN ... .fab`; this is an execution failure, not evidence that the solvent treatment succeeded. Preserve the last valid checkpoint separately.

Evaluate full/maximum resolution completeness, intensity versus resolution, strong missing low-order reflections, data/parameter support and redundancy. Friedel-unmerged counts can give apparent completeness above 1 if compared against a merged expectation; inspect definitions before calling a report '180% complete'. A high Rint or low I/sigma is evidence to investigate, not an automatic rejection threshold for every instrument/material. High-order truncation can reduce R but degrade parameter support and precision.

Absorption, scaling, integration/profile overlap, error modelling, crystal movement and radiation damage can create systematic residuals. Inspect frame/batch and orientation dependencies when the upstream files exist. Transmission factors from empirical normalization and physically calculated values may differ in normalization; do not rewrite them to match an ideal value. Declare the method actually applied, supported by records. Inherited metadata with contradictory fields need clarification, not cosmetic relabelling.

A weighting adjustment during refinement does not redo absorption correction or replace the measurement uncertainty model. Track unweighted and weighted statistics, variance by intensity/resolution and model changes separately. A very small GooF can signal overly large uncertainties/weights rather than exceptional accuracy; a good GooF alone does not prove data quality.

Investigate each proposed OMIT/outlier using its measurement history, residual, detector/overlap/beamstop/saturation evidence and effect on the model. Do not remove statistically inconvenient weak/negative intensities as a class; negative measured Fo² can arise legitimately from background estimation. Preserve every omitted index and reason and regenerate validation. If raw frames/integration records are missing, state which causes cannot be distinguished from HKL alone.

Parse the OMIT form before counting exclusions: `OMIT s 2theta_limit` is not `OMIT h k l`, and atom-name OMIT creates a different calculation. Official SHELXL documentation describes nonpositive s as internal flooring of very negative Fo² at 0.5*s*sigma, not wholesale rejection below s*sigma; preserve raw observations and document the engine's treatment separately. The supplied chloroform-cage template uses `OMIT -3 50`: its LST records 7486 angle-limit rejections from 75117 input observations and 22954 refined unique reflections. Completeness to the resulting .841 Å limit does not establish retention of all measured high-angle data. Verify version-specific behaviour rather than rewriting the original HKL.

## Cell contents and report consistency

Compute explicit modeled cell contents from symmetry/populations, then account separately for any uncertain masked contribution. Define a chemical formula unit before assigning Z; equivalent rescalings of formula/Z can preserve cell mass, density and F(000), so a difference by a factor is not automatically a different composition. Explain representation, do not mechanically set Z′=1 or use model record count as atoms per cell.

UNIT is per-cell count in SFAC order; stale/placeholder UNIT is not proof of sample composition. For each element check the modeled total, H membership and declared formula; charge and solvent uncertainty require chemical judgement. Tiny serialization differences should not become claimed chemical nonstoichiometry. Report actual refined occupancies and meaningful uncertainties, not excess digits, rounded populations forced to sum to 1, or FVAR used in Uij mislabelled as occupancy.

Check final CIF against RES/HKL/FAB/FCF and the exact validation report. Preserve experiment temperature versus SHELXL Celsius TEMP conventions, units, uncertainties and symmetry codes. The report's geometry should describe physically coexisting components, not bonds between mutually exclusive orientations or every short contact as a covalent bond. Generated Word reports inherit layout only, never old scientific values or old validation findings.

## Reviewed sources and limits

`PLATON-MANUAL.pdf` pages195,201–202 and `Reporting and Cif Check` pages53–56 informed void/map interpretation; page201 and pages54–56 respectively were visually checked. `6_Data Finalization in CrysAlisPro - Part 2.pdf` selected pages8,12,17,20 informed absorption/error models and outlier/centering distinctions; no raw-frame integration or mask implementation is newly claimed tested.

In the private C052/C714/C719 reproductions a paired FAB matters. The newer Cmcm U-complex historical report explicitly flags `_smtbx_masks` and says ADDSYM could not run because too many atoms were excluded: 0A/0B is not an independent test of unmasked chemistry or missed symmetry. Keep the user-excluded crystal-jumping specimen out of new exercises.

Primary references: [Spek: PLATON SQUEEZE](https://journals.iucr.org/c/issues/2015/01/00/ln3172/), [SHELXL ABIN/UNIT/ACTA/WGHT](https://shelx.uni-goettingen.de/shelxl_html.php), [IUCr validation interpretation](https://journals.iucr.org/e/issues/2020/01/00/su5533/index.html).
