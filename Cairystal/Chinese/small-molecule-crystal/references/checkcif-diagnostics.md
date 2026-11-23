# checkCIF diagnosis and justified repair

Follow the official-upload requirements in [workflow.md](workflow.md). Local PLATON reports are preflight evidence; learning diagnostics may remain local and must not be mislabeled as official IUCr validation.

## Alert handling record

Before using an old report as a teaching success, inspect its validation scope and exact CIF pairing. In a second pass through 151 distinct private checkCIF PDFs, 21 have zero parsed A/B alerts yet state no structure factors were supplied. They are useful historical reports, but not full structure-factor validation. A 'basic structural check' label also differs from full publication checks; structure factors supplied is a prerequisite, not proof every desired option ran. Use `scripts/audit_validation_scope.py` on extracted report text as a read-only aid; confirm original report pages and sections before delivery.

For each material alert retain its exact code/level/text, report version, implicated atoms/reflections, proposed causes, observations, any diagnostic experiment, resulting comparison and residual uncertainty. Consult the current IUCr explanation linked from the official report. An author response copied from an unrelated publication is not evidence for the current specimen.

Separate missing metadata from model and data defects. Recover metadata from the actual experimental records; never fill unknown crystal dimensions, collection statistics or instrument fields with convenient values. An A-level missing datum and a C-level model/data warning concern different issues and do not rank solely by the letter.

For missing experimental fields, use [experimental-metadata-preflight](experimental-metadata-preflight.md) before changing the structure. PLAT183/184/185 refer to cell-measurement reflections and their theta range, not refinement reflection counts/range; PLAT699 requires observed crystal habit. Restore these from paired experiment records, not guesses from HKL. Missing-only completion must be followed by exact-artifact revalidation with resolved and newly introduced alerts recorded.

For skipped/suppressed checks, CIF/FCF or geometry inconsistencies, and historically suggested alert-avoidance tactics, read [validation-evidence.md](validation-evidence.md). Distinguish a quieter report from a corrected model and record coverage gaps explicitly.

A reviewed U-containing P-1 example has a local report with zero A/B but 19 C and 26 G alerts, including no ADDSYM analysis because too many atoms were excluded and mask-related suppression. It still has absorption-metadata, donor-H, cell/uncertainty and structure-factor queries. Use it to teach that zero A/B is not a symmetry check or complete acceptance. Map renamed report labels back through coordinates/elements to the exact model before changing an implicated atom; a matching R value alone does not establish atom-label correspondence.

## PLAT035: absolute-configuration reporting

`PLAT035_ALERT_1_B` reports missing `_chemical_absolute_configuration`, not proof that the model's hand is wrong. For this user's workflow, complete the field from the current evidence before official validation; do not choose a value merely to remove B. The installed Olex2 menu maps these labels directly to CIF values (`etc/gui/tools/report-footer.htm`), so a versioned CIF edit can implement the choice without opening Olex2.

| Evidence / meaning | Menu label | CIF value |
|---|---|---|
| Diffraction anomalous-scattering evidence supports the reported absolute configuration | Anomalous dispersion | `ad` |
| Absolute configuration remains undetermined and there is no firm independent chemical assignment | Unknown | `unk` |
| The item is genuinely inapplicable | Not applicable | `.` |

These meanings follow the [IUCr PLAT035 explanation](https://journals.iucr.org/services/cif/checking/PLAT035.html) and [coreCIF definition](https://www.iucr.org/__data/iucr/cifdic_html/1/cif_core.dic/Ichemical_absolute_configuration.html). `unk` is an explicit conclusion, not a blank `?`. Preserve a justified `rm`, `rmad` or `syn` assignment when independent reference/synthetic evidence actually exists; weak anomalous information alone does not invalidate that separate evidence. Never import such a claim from a withheld reference model or infer it solely from a proposed 2D drawing.

### Assess the evidence before choosing ad

- Read the final applicable estimate as `x(u)`, including method, standard uncertainty and reflection treatment. Compare classical Flack, Parsons and/or Hooft results when available; record disagreements instead of selecting the smallest-looking value. Do not substitute a fixed/unrefined BASF or an estimate from another model. Preserve Friedel-pair information and inspect anomalous-data quality, model convergence and potential systematic errors.
- Evaluate `u` first, then whether `x` is consistent with the claimed hand. Flack & Bernardinelli's [2000 guidance, section 2.1](https://journals.iucr.org/j/issues/2000/04/00/ks0021/ks0021.pdf) uses `u < 0.04` as strong inversion-distinguishing evidence; `u < 0.1` is an enantiopure-sufficient guide only with independent prior evidence of enantiopurity. With adequate information, `|x| < 2u` is a sufficient consistency criterion for their untwinned model assessment. These are diagnostic guides, not universal automatic pass/fail rules or substitutes for checking experimental bias.
- Thus `0.02(3)` is statistically much more informative than `0.02(20)`; the latter cannot be accepted simply because 0.02 looks small. Small negative values within uncertainty may be statistical fluctuations; do not clip them. A precise value significantly different from zero can indicate inversion twinning or model/data problems; a value near one suggests the opposite hand. Preserve these observations and review the interpretation rather than automatically setting `ad`, inverting coordinates or changing TWIN/BASF.
- Distinguish a crystal's absolute structure from a molecule's absolute configuration. Do not assign molecular R/S, sample chemical purity or bulk enantiomeric purity merely because a precise absolute-structure parameter exists. If the required assignment is unsupported, use `unk` where applicable and explain the uncertainty. Use `.` only for genuine inapplicability, not as an alert-avoidance substitute.

### Write, retain and revalidate

In an authorised validation/report workflow, filling the missing method from already established evidence is a reporting step; a newly proposed hand inversion, twin model or unsupported stereochemical assignment still requires the model-change checkpoint. Preserve the previous CIF and record the evidence, method, `x(u)`, chosen value and changed-file hash. Keep `_refine_ls_abs_structure_Flack` and `_refine_ls_abs_structure_details` consistent with the actual method and final model, and record the explanation in the Word report. Preserve this decision in job metadata and reapply/reassess it if SHELXL regenerates the CIF; do not lose it at the next export.

Revalidate the exact amended CIF locally and, within the user's upload authorization, on IUCr. Only the new report establishes whether PLAT035 disappeared or other queries arose. Setting `unk` can resolve missing reporting while leaving absolute configuration scientifically unknown; do not claim the warning or uncertainty vanished without verification. For a paused preliminary model, retain provisional status rather than treating this field completion as final acceptance.

## Focused examples

- [PLAT906](https://journals.iucr.org/services/cif/checking/PLAT906.html): inspect section 7 of the structure-factor validation report. Its binned mean Fo-squared/Fc-squared ratio is expected near unity. Identify which intensity/resolution bins drive the discrepancy and assess integration/background, absorption, scaling and model possibilities. Do not respond by automatically deleting weak/high-angle reflections, changing weights solely to hide the alert, or invoking an unsupported generic explanation.
- [PLAT976](https://journals.iucr.org/services/cif/checking/PLAT976.html): negative density near N/O can indicate a misassigned H atom; consider protonation/tautomerism when chemically relevant. This is not equivalent to 'a hydrogen is missing'. Inspect the minimum location relative to actual H/N/O coordinates and alternative hydrogen arrangements. Do not automatically add H, change occupancy or split O merely from the alert.
- NPD or strongly distorted ADPs: inspect atom types, occupancies, residual density, connectivity and restraint scope, then broader data/symmetry issues. A lower R value after introducing more freedom does not justify accepting NPD atoms.
- Large Ueq range versus tensor anisotropy: distinguish PLAT220 from shape tests. Use [adp-model-selection](adp-model-selection.md); ISO does not automatically resolve excessive scalar displacement.
- Exceptional Fo²/Fc² differences: an intensity outlier is not proof of detector overload. Seek raw frames, overload flags and integration/scaling records. Without them, an explicitly authorized OMIT run is a sensitivity experiment, not confirmed exposure correction. Retain the complete-data model and a fixed, traceable omission list; do not repeatedly enlarge the list to clear alerts.
- High weighting parameters or a good weighted GooF despite poor unweighted statistics: distinguish changed weighting from corrected data/model. Report the weighting and examine structure-factor statistics; a GooF near 1 is not independent proof of correctness.
- Negative or otherwise nonphysical twin fractions: evaluate the twin law against the actual symmetry, the identifiability of the contribution and uncertainty. Do not interpret an out-of-range BASF as a physical population or fix it by blindly clipping the number.

## Stop and revalidate

When comparing an unsplit and split disorder model, audit other simultaneous changes. In the supplied crown-ether/perchlorate example, the split model also introduced numerous DFIX restraints with 0.001 Å s.u., changed HKL contents and increased restraints from 24 to 184. Lower R and improved bond precision therefore do not isolate the benefit of splitting. Record the data hashes, weights, resolution cutoff, restraint targets/strengths, parameter counts, ADPs and residuals; a disorder-percentage annotation in checkCIF is not the component occupancy. Distinguish a Parsons absolute-structure estimate in the report from an actual TWIN/BASF refinement.

When no chemically plausible, numerically stable candidate is supported, keep the baseline and rejected alternatives as diagnostic evidence, mark the case 'needs review', and state what additional evidence is needed. Raw-frame re-integration may be required when an HKL alone cannot identify the source of a discrepancy.

After an accepted change, regenerate CIF/FCF and validate the actual changed final file. Keep unresolved alerts visible. Do not turn teaching collections' advice to truncate data, force ADPs, or reuse published response wording into automatic repair rules.
