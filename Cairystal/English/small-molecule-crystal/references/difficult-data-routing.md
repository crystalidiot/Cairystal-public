# Route difficult data before modelling disorder

Read when solution fails, reciprocal-space images show unexplained peaks, the cell is suspicious, or twinning/modulation is proposed.

## Separate the causes

An elongated ellipsoid, high R or residual density can reflect disorder, an incorrect element, incorrect symmetry, twinning, absorption/scaling problems, crystal movement, poor integration or missing data. Whole-molecule disorder is not a default rescue for every poor model. Compare explicit hypotheses against the observations and chemistry; retain the rejected alternatives and their reasons.

## Twinning

Use reciprocal-space/domain evidence and a defensible twin law. Non-merohedral cases need integration information about separated/overlapping reflections and their domains. Keep the final HKLF5 file paired with its model; do not strip the component column or relabel it HKLF4. An appropriately produced detwinned HKLF4 may be useful for solution, but is not interchangeable with the final overlap-aware refinement data.

Indexing percentage alone neither proves a twin nor measures completeness. Distinct lattices may instead indicate multiple crystals. In a centrosymmetric structure an inversion operation already belongs to the structure symmetry: an inversion-twin fraction is then unidentifiable, not evidence for racemic twinning. Flag it for review rather than changing the model automatically.

## Incorrect cell and modulation

Require original frames, instrument calibration/orientation matrices, integration settings and compatible software before promising re-integration. The present skill does not independently reintegrate raw frames using SHELXL.

For satellites, record the basic cell, basis transformation, q-vector(s), uncertainties and satellite indices together. Preserve hklm data. A q component near 1/9 is not proof of exact commensurability. Do not delete satellite indices, combine cell/q values from different processing stages, or force a large 3D supercell to obtain a low R. Route supported aperiodic models to a JANA workflow after checking installation/licence/input compatibility. Such a route remains an escalation, not a tested automatic feature.

Read main- and satellite-order statistics separately. A processing option allowing satellites through order four is not evidence that all fourth-order peaks are reliable; conversely, poor high-order averages do not justify discarding strong low-order satellites. Check whether reported completeness covers only main reflections. Keep exclusions used to fit an uncertainty model distinct from observations actually removed from exported HKL, and do not interpret an overlap-pixel percentage as a twin fraction. The supplied exp_13370 log explicitly distinguishes these stages; a placeholder HKLF4/UNIT1 input alongside it is not a solved aperiodic model.

## Alternative solution

Check field layout, not the extension or a nearby HKLF card. The supplied exp_13370 HKL contains four fixed-width indices followed by intensity, uncertainty and run; its HKLTMP uses a different layout and its starter INS still says HKLF4. Do not shift/truncate columns to make it load. `inspect_case.py` and `setup_job.py` conservatively screen external HKLF3/4/5 for three-index fixed-width records and stop on incompatible records, reporting possible four-index evidence. This is a layout check, not a general aperiodic parser; ambiguous layouts, alternate Fortran encodings and other HKLF types require review. Matching numeric layout does not establish observation grouping or model compatibility.

A finite SHELXS or explicitly prepared SHELXD trial is a legitimate diagnostic alternative to SHELXT failure. A peak list, correlation coefficient or solver exit alone does not establish an atom model. Keep chemistry, element assignments, setting and connectivity review between solution and refinement. The library's supplied SHELXD FIND/MIND/PLOP settings belong to that specimen; do not transfer them to an unrelated sample.

Primary references: [SHELX program roles](https://shelx.uni-goettingen.de/), [SHELXL HKLF/TWIN documentation](https://shelx.uni-goettingen.de/shelxl_html.php), [JANA2020 scope](https://jana.fzu.cz/about-jana).
