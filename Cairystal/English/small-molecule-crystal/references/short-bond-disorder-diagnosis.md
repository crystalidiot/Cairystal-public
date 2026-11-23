# Short bonds together with PLAT214: model first, restraint sensitivity second

Use this case-free route when a short organic contact coexists with an elongated ADP or unexplained density. It contains no sample identities or reference coordinates.

1. Identify the exact atom pair, symmetry operation, lattice translation and PART compatibility. A short distance between mutually exclusive alternatives is not a simultaneous chemical bond. The same labels can have both a short direct distance and a different long symmetry contact.
2. Check SFAC assignment, valence, local geometry, H ownership, occupancies and the Cartesian ADP axes. SHELXL does not switch the carbon scattering factor between sp2 and sp3: hybridization/bond order is represented by the chemical connectivity, geometry and H model. Do not change AFIX or a bond target from one distance alone.
3. A supported chemical bond may benefit from DFIX/SADI; select the target and uncertainty for that bond type, not merely a larger number. Compare convergence, residual density, ADPs, neighbouring geometry and restraint conflicts using the same observations and initial weights. If a stronger restraint improves a warning but leaves strong geometric conflict or unexplained density, keep the candidate provisional.
4. If several adjacent sites have abnormal tensors/short bonds, calculate an omit map for the whole suspect fragment. This removes **model atoms**, not measured reflections. Fit complete competing configurations from the present density and symmetry; avoid independently choosing nearest images for atoms and accidentally mixing incompatible conformations.
5. In inversion-related orientational disorder, a whole molecule can have two equal alternatives. For a single fully populated solvent site, each general-position alternative has occupancy 0.5; this is different from a single atom on an inversion centre. PART -1 controls generated connectivity but does not delete the inversion mate or set occupancy. Review atom-level orbit counts and **molecular alternative sums** separately. A free total population above one is a warning about the hypothesis/ADP/scale model, not an acceptable way to add scattering density.
6. Compare shared-site, split-site and complete-fragment models if the map supports them. Test soft geometry and a rigid fragment separately. Geometry created by AFIX 66 is imposed; it does not validate a benzene identity. EADP should have a physical overlap rationale, not be a universal way to stabilize unrelated atoms. Unknown solvent identity remains unknown even when the fit or A/B count improves.
7. Preserve all baseline/failed candidates. Reconcile UNIT/formula/F(000) **after** HFIX has generated atoms or occupancies have changed. Recheck H PART/SOF, all non-H ADPs, final shifts and original HKL hashes. Consider weights after diagnosing the model; do not tune them solely to force GoF=1.
8. Submit the exact paired CIF+structure factors for authorized official checkCIF, retain the original PDF, and show metadata A/B separately from structural A/B. “No structural A/B” is a validation observation, not final scientific acceptance. Provisional CIF prose and reports must say which identity/geometry is unresolved.

## Deterministic assistance

`scripts/restraint_tension.py model.lst --output restraint_tension.json` reads only the final SHELXL disagreeable-restraint listing. `structure_diagnostics.py` includes the result automatically. It flags listed DFIX/DANG conflicts at or above 5 restraint sigmas for review and preserves unparseable/missing evidence. This is not a universal statistical acceptance cutoff. An empty list cannot detect an overconstrained rigid model or certify chemistry; compare explicit geometry and density as well.

For AFIX 66 setup, fit six contiguous non-H sites first; place HFIX before atom records. If manually nesting riding H within an established rigid group, resume the group with the appropriate AFIX 5 and close it explicitly. Keep failed instruction-order attempts rather than attributing them to the crystal.

## Sources

- [SHELXL instruction reference](https://shelx.uni-goettingen.de/shelxl_html.php): AFIX, DFIX, DANG, PART, FVAR, SFAC, UNIT and LIST. The recommendations above are a workflow synthesis; they are not copied solvent-specific recipes.
- [IUCr PLAT214 explanation](https://journals.iucr.org/services/cif/checking/PLAT214.html): the principal rms-axis ratio diagnoses strongly elongated displacement ellipsoids and can indicate unresolved disorder.
