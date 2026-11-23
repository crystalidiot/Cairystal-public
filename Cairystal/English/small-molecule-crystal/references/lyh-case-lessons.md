# LYH case lessons: 2D-assisted solution and evidence-preserving validation

Use for a worked example of a solver-derived model requiring chemical interpretation, or a zero-A/B delivery that still needs scientific review. This is an original procedural digest, not the specimen's coordinates or an automatically applicable repair recipe. Exact metrics, hashes and private files remain in the project's `crystal_jobs/LYHclean_20261025/exp_5138_20261025_190352/learning_digest_20261025/` record.

## What the case established

Initial phasing was independent of the withheld historical model. The usable basis came from SHELXD, followed by element assignment informed by the user's proposed 2D structure and this run's connectivity/difference density. It was **2D-assisted reconstruction**, not unassisted identification from elements alone. The user paused before new disorder modelling. The later validation operation changed experimental/reporting metadata only, preserving the current RES/INS/HKL/FCF/LST.

Official IUCr validation of that exact upload returned **A0/B0/C15/G20**, with structure factors supplied and no syntax errors. This demonstrates completion of the validation/reporting task, not successful THF/CF3 disorder refinement, established absolute configuration or expert acceptance. The scientific status remains `needs_review`.

## 1. Audit inputs by field, not by filename

The minimal INS conflicted with acquisition records on wavelength and temperature; UNIT was unsuitable for the proposed chemistry, and recorded space-group labels differed. Same-experiment acquisition facts can correct an initial working hypothesis, with provenance. They do not make every item in the acquisition file authoritative: a recorded formula or space-group label still needs independent model/symmetry assessment.

Follow [metadata preflight](experimental-metadata-preflight.md) for allowed experimental fields. Reconcile wavelength and temperature **before** phasing rather than waiting for final checkCIF. Interpret Celsius/Kelvin and theta/two-theta explicitly. Keep the input conflict log and unchanged original files. A missing-only metadata merger is not authorized to overwrite an already present conflicting value; initial input correction is a separately documented decision.

## 2. Solver peaks need a chemical graph and local evidence

Two SHELXT attempts produced no accepted candidate; one timed out. Subsequent bounded SHELXD searches provided a useful scaffold. The FIND35 model supplied the starting assignment; FIND47 supplied corroborating scaffold information from the same data, not independent experimental validation. Neither FIND value is a default for another crystal. Keep failed/timeout runs and the amendment to the search budget.

Some apparent F sites belonged to ring carbon or N/O, while some carbon-labelled peaks belonged to F. Recognize whole rings, substituents and coordination before editing atom types. One missing OCF3 central carbon was added only after a coherent peak appeared in this run's difference map. Review local U, distances, valence, charge and residual density after each assignment. The user's drawing is a chemical hypothesis, not permission to manufacture coordinates or force the expected product. Follow [chemical-model-and-density](chemical-model-and-density.md).

The first H-generation attempt failed because of instruction ordering; a separate corrected run preserved the failed one. Use the [workflow ordering check](workflow.md#stage-3-refine). Idealized riding H remain a model even when a nearby difference peak supports protonation; do not report every generated H as independently located.

## 3. Separate formula basis, special-site SOF and display copies

The printed core formula and the separately drawn solvent were different formula bases. Keep core, complete solvated molecule, ASU and unit-cell composition separate before comparing UNIT or density. A half-core plus solvent in the ASU is not automatically half-occupied material.

The bridging oxygen lay on a twofold special site. Its decoded SHELX SOF of 0.5 normalized multiplicity 4 against general multiplicity 8; chemical/CIF occupancy was 1.0, not 50% disorder. Use the orbit audit in [disorder-occupancy](disorder-occupancy.md); do not copy this numerical factor to other sites. Symmetry-grown display atoms are not additional independent atoms.

Assembly and refinement are separate operations. Keep complete fragments coherent even if fractional coordinates leave 0–1, and preserve tensor/H/occupancy semantics under transformations. Case-specific assembly did not validate a general SHELX writer. Follow [headless assembly](workflow.md#headless-assembly-saving-and-round-trip-check); retain the GUI preference prospectively rather than claiming the entire historical case never used Olex2.

## 4. Freeze the real current version before drawing conclusions

An earlier status record and an earlier alert report did not describe the later files used for final validation. The later current LST/RES were therefore frozen and audited afresh. Do not combine an earlier convergence status, a later R value and a third version's report. If an intervening run is not attributed, record that gap rather than inventing its history.

For metadata-only validation, protect the frozen model tokens and embedded data; a newly generated CIF hash will differ because its metadata changed. Compare model files separately. RES-to-CIF coordinate serialization needs per-token precision handling, not a single tight epsilon. A rounding-related comparison failure is not evidence that atoms moved; conversely, tolerance must not hide changes in actual orbit multiplicity. See [report-model consistency](report-model-consistency.md).

## 5. Resolve missing information without disguising unresolved science

Cell-measurement reflection count and theta limits were recovered from the paired CIF_OD. They were not inferred from the final HKL, raw row count or refinement totals. Instrument/absorption records came from this specimen, not a previously handled sample. Colour, habit and approximate dimensions entered the official CIF only after the user confirmed them for this actual crystal. Keep collection, raw-export, processed-measured and unique-refinement counts distinct; different numbers do not by themselves identify why observations were excluded.

The missing absolute-configuration field was filled with `unk`, based on the current evidence and absence of a firm independent assignment. Classical Flack and Parsons estimates were retained with their uncertainties and methods. The disappearance of PLAT035 removed a reporting omission, not the uncertainty in absolute configuration. Follow [PLAT035 reporting](checkcif-diagnostics.md#plat035-absolute-configuration-reporting) and the [IUCr definition](https://journals.iucr.org/services/cif/checking/PLAT035.html).

No weights were changed during metadata completion. The active WGHT and the unused post-END suggestion were recorded separately. The large second coefficient remained a query; neither a better GooF nor a zero-A/B report proves the unresolved model adequate. Follow [weighting review](workflow.md#weighting-review).

## 6. Pair the upload, delivery files and editable report

The official report and structure-factor report were saved unmodified and paired to the exact uploaded CIF hash. The final package retained matching RES/INS/HKL/FCF/LST, local diagnostics and the template-based Word report. The report used the current CIF for every table, not the older Word specimen. Hash checks preserved source data and the reference template.

Three practical checks matter here: verify the delivered reflection basename/reference, separate length and angle continuation headers, and inspect every rendered report page. The packaged document renderer was unavailable; a recorded background Word-to-PDF/Poppler fallback supplied visual QA. Do not silently drop visual QA or report the unavailable renderer as successful. Detailed checks live in [report-model consistency](report-model-consistency.md), rather than being duplicated here.

## What remains unproved

- THF large/elongated displacement and short within-ring bonds, and elongated CF3 ellipsoids, remained unresolved. A plausible disorder hypothesis is not a refined split model.
- Absolute configuration, bulk enantiopurity and publication readiness were not established.
- This case did not validate general automatic element reassignment, disorder repair, headless assembly or scientific acceptance.

Reusable checks were reinforced with synthetic metadata tests: preserve occupancies/ADPs and embedded inputs, keep cell-measurement counts distinct from reflection statistics, and do not inherit the reference solver or absolute-configuration claim. They test information handling, not whether a molecular model is correct.
