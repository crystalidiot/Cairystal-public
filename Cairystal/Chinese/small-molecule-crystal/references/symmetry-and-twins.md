# Symmetry, twins and absolute structure

Read with [difficult-data-routing.md](difficult-data-routing.md); this guide explains model discrimination, not raw-frame integration capability.

## Distinguish metric, diffraction and structural symmetry

Equal axes/angles only suggest metric symmetry. Use intensity agreement in candidate Laue groups, systematic absences, complete atom types/coordinates and chemistry to judge structural symmetry. Systematic absences from centering/screw/glide are not SHELXL EXTI extinction corrections. Different settings/origin shifts can describe the same group: compare full operations/Hall symbols and recorded transformations, not just displayed names.

ADDSYM is a candidate generator: record fit, tolerances, excluded atoms and actual symmetry-breaking sites. A high fit of a heavy-atom substructure does not establish exact whole-structure symmetry; low-population organic ordering can break it. An absence of ADDSYM results because too many atoms were excluded is not evidence no symmetry was missed. Avoid averaging away chemically or experimentally supported distinctions just to remove an alert.

For an additional centre, translation or changed Laue class, retain both candidates and a complete cell/basis/origin transformation. Transform HKL and coordinates consistently; regenerate SITE/SOF/H constraints and chemical cell counts rather than copying old occupancies. Compare geometry, residual density, parameter stability/correlations, data support and meaningful uncertainties. A lower-symmetry model often has more parameters, so smaller R alone cannot select it. Conversely, higher symmetry is not inherently better when genuine violations are measured.

Do not infer a transition solely from folders named by temperature. Same-temperature Cc/C2/c alternatives are model hypotheses; different-temperature Cc/C2/c/Cmca examples may reflect real ordering/phase changes and are not a controlled model-comparison pair. Establish specimen identity, cell/reciprocal-space observations and temperature records first.

## Twin/data-format decisions

Determine whether domains are fully, partly or non-overlapping and whether their cells/orientations/twin law are compatible. Crystal movement during collection can mimic multiple orientations; inspect frame/time dependence before calling it a physical twin. Indexing percentages or a nonzero BASF alone do not establish the law.

Equal cells alone cannot distinguish a crystallographic twin from randomly oriented fragments of the same phase. Retain indexing tolerances, absolute peak counts, UB relations and unexplained peaks; tightening a tolerance can expose a second lattice while reducing the headline indexing percentage. The lecture heuristics of 85% indexing or 10% minor-component reflections are not automatic acceptance/deletion thresholds. A reflection-count fraction is not a refined twin volume fraction. Weak-domain exclusion requires a preserved comparison and evaluation of contaminating overlaps, not just a lower Rint. Changing integration masks changes overlap classification, not physical spot separation.

For appropriate merohedral/pseudomerohedral data, TWIN with HKLF4 can model coincident contributions. Non-merohedral HKLF5 retains overlap/component grouping; preserve the batch signs/order and integration provenance. Do not apply an additional TWIN model blindly to an already encoded HKLF5 set or strip its component column to make the solver accept it. A separately produced detwinned/isolated HKLF4 can support initial solution but need not contain all final refinement observations.

Do not reject a TWIN matrix merely because its entries are nonintegers. [Sheldrick 2015](https://pmc.ncbi.nlm.nih.gov/articles/PMC4294323/) describes selective inclusion of transformed indices within0.1 of integers, including some weak-minor-domain near-overlap cases. Verify the engine version and experimental applicability; index-space tolerance is not detector-profile overlap, and the fraction of rows passing it is not BASF. Do not round the matrix to force every index to be integral or treat this approximation as a replacement for appropriate multi-domain integration/HKLF5. The reviewed400 K Sn/Br model uses such a non-inversion law in C2/c; its validity is unresolved, not disproved by centrosymmetry alone.

Interpret BASF in context: with TWIN or HKLF5 it represents twin fractions; with ordinary batched data it can instead be a relative intensity scale. Not every BASF is a population in [0,1]. For twin fractions record the implicit first component, uncertainties, correlations and stability; do not clip negative values or force 0.5 without evidence. Inversion twinning is unidentifiable in a centrosymmetric model. The processing gate must check HKLF5 fractions even when no TWIN card is present.

Centrosymmetric structures can still have other orientation-twin laws: do not remove all twin treatment merely because the space group has inversion. V0020's P-1 HKLF4/HKLF5 demonstration changes coverage, weights and observations; its improved R is not a controlled same-data comparison or official validation. Inspect the loaded reflection file, not a stale window title containing `hklf4`.

The theoretical inversion-mixture intensity is `(1-x)|Fc(h)|² + x|Fc(-h)|²`, compared against observations. Do not replace calculated component intensities with the measured values as in a simplified lecture expression. Inversion-twin/absolute-structure interpretation is not the same as a second conformer or occupancy disorder.

## Absolute structure versus molecular chirality

For `_chemical_absolute_configuration`, choose the method supported by this determination, not a value that removes a missing-field alert. The [IUCr dictionary](https://www.iucr.org/__data/iucr/cifdic_html/1/cif_core.dic/Ichemical_absolute_configuration.html) uses `ad` for anomalous-diffraction evidence, `syn` for a synthetic assignment not established by that evidence, `unk` for undetermined hand and `.` when inapplicable. Record the relevant estimate/s.u., method and applicable chemistry; `ad` does not certify bulk purity. Do not copy the reference answer's hand or infer the method merely from a 2D stereobond.

A Sohncke group permits but does not prove an enantiopure molecular compound; noncentrosymmetric non-Sohncke groups do not establish molecular absolute configuration. Distinguish absolute arrangement of this measured crystal from bulk purity and molecular R/S assignments. In centrosymmetric structures a molecule with a stereocentre can be present as a racemate; do not delete the stereocentre or impose a Sohncke group just because a G alert identifies it.

Keep Friedel-pair processing, wavelength/anomalous scatterers, observation quality and independent pair counts. Report Flack/Parsons/Hooft estimates with standard uncertainties, method and assumptions. Values near 0/1 or 0.5 without meaningful precision are not firm configuration assignments. Disagreement can reflect model/data problems; weak anomalous information may leave absolute structure undetermined. Independent synthetic/reference stereochemistry must be labelled as such, not disguised as diffraction determination.

Beginner gate: ask whether independent enantiopurity evidence exists; do not infer it from a desired R/S assignment. Assess uncertainty before the central value: `0.00(50)` is inconclusive. The classical `u<0.04` strong-discrimination and `u<0.1` enantiopure-sufficient criteria are conditional, not an automatic publication pass. A single crystal does not establish bulk enantiopurity. Preserve right-handed axes through setting transformations. [Flack & Bernardinelli](https://journals.iucr.org/j/issues/2000/04/00/ks0021/).

Do not confuse the 65 Sohncke group types with the 22 chiral group types (11 enantiomorphic pairs); chiral structures can occur in all 65. [IUCr definition](https://dictionary.iucr.org/Chiral_space_group).

Record separately Friedel treatment during scaling, outlier rejection, exported-HKL merging and refinement. A lecture's “unmerged output” statement is version-specific, not proof about a supplied file. Ordinary completeness and anomalous completeness are different; inspect actual pair coverage. A chiral candidate filter must not substitute for symmetry evidence. Preserve the exact HKL identity for every comparison, especially when Olex2 reports that associated and loaded HKL names differ. Lecture V0019 illustrates uncertainty and method-label pitfalls; reviewed static samples, not an independent refinement.

Current delivery support and the no-speculative-search policy are maintained in [routine twin routing](routine-twin-routing.md). This supersedes any blanket routine rejection solely for TWIN/BASF; unsupported HKLF 5 remains a separate format limitation.
