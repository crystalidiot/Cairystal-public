# Audit the report against the exact model

For explicit recalculation of formula/Z/Mr/density/F(000), restraint mapping and temperature-series pitfalls, use the case-free [restraint and accounting audit](restraint-and-accounting-audit.md). Matching a published table alone is not a consistency check.

Use before treating a report as a learning target or preparing a deliverable. Preserve source reports. Generated prose, a reviewer response, a publication label and zero A/B are not acceptance evidence by themselves.

For supported routine HKLF 4/LIST 4 bundles, [reusable automation](routine-automation.md) performs file consistency checks, official validation, shared-data bilingual report generation and sealed packaging. Review its declared limitations; its completion status is not a scientific certificate.

## 1. Identity and processing lineage

Pair the exact CIF, embedded RES, HKL/FCF, LST and validation report using hashes or documented comparisons. A shared filename, atom label or cell is insufficient. Keep each phase/temperature/version distinct; do not mix a newer R with older geometry or metadata.

At resumption, re-read the actual current model/log and freeze a hash manifest before using a dashboard, `status.json` or an earlier answer. These summaries can lag behind a later file version. File modification time is a discovery aid, not proof of a coherent run. An old alert report can identify historical problems but cannot provide an exact matched before/after baseline unless its CIF is paired. Do not silently update frozen history or attribute an intervening change whose author/run is unrecorded.

Trace instrument, wavelength, temperature, dimensions, absorption method, transmission limits and processing statistics to the actual collection/reduction stage. A PCF template supplies fields, not measurements. Multi-stage absorption logs may change scans, fitted subsets and correction parameters; do not combine one stage's R statistics with another's transmission factors without explanation. Unknown values remain unknown.

Record collection, merge, cutoff, OMIT and refinement counts separately; twin component rows are not automatically independent observations. Prefer native LST semantics over a GUI footer that calls input observations “all data.” Preserve actual pre-END instructions separately from suggested weights or historical comments after END.

## 2. Symmetry and composition

Verify space-group operations/number, setting, origin and basis transformations; preserve overbars and translations. A HKLF index transform is not a twin law. Compare formula × Z, cell volume, density and F(000) on a consistent formula basis before diagnosing missing atoms or vacancies.

Use [disorder-occupancy](disorder-occupancy.md) for decoded SOF, actual orbit multiplicity, shared sites and H weights. Count distinct weighted orbits, not coordinate-table rows or an unexpanded ASU drawing. The same SOF can represent full special-site and partial general-site populations. Matching UNIT and formula is necessary bookkeeping, not proof of chemistry or local joint configurations.

For near-special sites, compare full-precision RES and serialized CIF coordinates, declared symmetry order and computed orbits. Rounding onto a symmetry element can change the distinct orbit. Do not repair it by multiplying SOF or adding cosmetic digits; resolve the physically supported model and regenerate output.

Separate two checks: a metadata-only edit must preserve the candidate's protected CIF tokens exactly; a RES-to-CIF serialization audit uses the precision of each written numeric token (including exponent), not one fixed coordinate epsilon or the atom's experimental s.u. `matches_cif_precision` in `scripts/audit_occupancy.py` supports the latter numerical comparison. It does not establish model identity, symmetry equivalence or unchanged site multiplicity by itself. Reject unexplained changes instead of increasing tolerance until they pass.

Separate ASU, whole-ion/molecule, unit-cell, explicit-solvent and masked-total formula bases. Bound/free counterions and coordinated/lattice solvent are different roles. Missing label numbers do not establish missing atoms.

## 3. Chemistry, hydrogen and geometry

Verify element assignment, connectivity, protonation, formal charge/counterions and independently supported sample identity. Heavy atoms can give low residuals while an organic fragment is wrong. The same formula can conceal different connectivity. Historical C/N averaged-scatterer approximations remain approximations, not chemical identification.

Report H coordinate freedom, displacement treatment and occupancy separately. AFIX/riding/rigid/fixed-coordinate H geometry is not independently observed; a fixed H may still have refined Uiso. Check actual H counts, neighbors, generated geometry and component membership. A chemically wrong H model can still agree with UNIT. For radicals/non-innocent ligands, do not impose a closed-shell H count without evidence. See [chemical-model-and-density](chemical-model-and-density.md).

Build geometry for **coexisting configurations** and exact symmetry neighbors:
- Retain atom order, table-specific symmetry dictionaries and lattice translations. A #1 operator may mean something different in another table.
- Exclude mutually exclusive cross-component contacts from chemical bond tables but retain them as model-audit findings. Do not use this exclusion to excuse impossible within-component geometry.
- For hydrogen bonds identify D/H/A, D–H, H···A, D···A and angle separately. Check the actual CIF loop, not merely an HTAB instruction or caption.
- Define centroid/plane atom sets, periodic unfolding, geometric versus mass-weighted center, perpendicular separation and lateral offset. Contact surfaces and attractive-looking chains do not establish interaction energy.
- Do not infer coordination number from superposed alternatives, or a regular polyhedron from trans angles alone. Display radii, hidden atoms, ellipsoid probability and rotations are presentation choices.

## 4. Constraints, precision and comparison

Audit actual instruction scope, atom pairs and effective strengths. Include reversed/symmetry-equivalent duplicate targets, conflicting DFIX, nonbonded restraints, shared ADP variables and missing counterparts. FVAR references in Uij are not occupancies; similar rounded tensors do not establish EADP. Exact equality, soft restraint and fixed parameters have different meanings.

Check restraint residuals, restrained goodness of fit, covariance/correlations and plausible geometry alongside ordinary R/S. A tight target copied from the current uncertain bond can downgrade a precision alert without improving the model. Likewise different imposed targets across temperatures are not measured thermal bond changes.

Zero or missing s.u., a blank bond category or precision 0.0000 is not perfect certainty. Determine whether it reflects fixing, symmetry, missing covariance or export failure. Changing parameter count or reflection selection to cross an alert threshold is not new evidence. Compare candidates on explicit retained data, coverage denominators, model freedom and validator version.

## 5. Validation scope and outstanding issues

Record validator date/version, datablocks, structure-factor supply and basic versus publication-check scope. Track each check as executed with findings, executed without findings, skipped, failed or unknown. PLAT811/ADDSYM skipped and PLAT915/Flack not performed are not passes. A legacy report does not validate later edits.

Use [checkcif-diagnostics](checkcif-diagnostics.md) and [ab-priority-refinement](ab-priority-refinement.md). An explanation does not make an alert disappear. VRF placeholders or a referee's acceptance are not specimen-specific evidence. Significant C/G defects remain relevant after A/B reduction.

Distinguish actual TWIN/BASF parameters from post-fit Flack/Parsons/Hooft estimates and estimated twin fractions. Inversion twinning is not atomic disorder, solution ee or a measured ferroelastic population. An extreme or uncertain fraction is not a physical conclusion. See [symmetry-and-twins](symmetry-and-twins.md).

## 6. Delivery and non-crystallographic claims

For mixed ANI/ISO models, list all non-H sites in the coordinate table with the correct Ueq/Uiso designation, but only ANI sites in the tensor table. Check that total non-H = ANI + ISO and verify labels, values and populations against the delivered CIF. Do not create fictitious Uij rows for ISO atoms or claim that they retain independent anisotropic refinement. Delivery/model hashes and the official report must correspond to the same final variant.

A complete user deliverable requires the official IUCr online structure-factor report `IUCr_checkCIF.pdf` and two separate editable Word reports, one Chinese and one English, following the supplied template; local CHK/CKF is not the same service. Retain the exact submitted artifact and returned report. Mark incomplete deposition IDs, missing measurements and unresolved alerts honestly; do not invent funding/authorship/instrument statements.

Check that titles, table headings, captions, methods, conclusions and alert explanations use the intended language in each of the Chinese and English documents. Both versions must refer to the same final CIF hash and contain the same numerical values, uncertainties, atom labels, units, symmetry codes, occupancies, table row counts, official alert codes/counts and unresolved limitations. Check that translation preserves the scientific meaning and degree of certainty. Keep the official IUCr PDF unmodified. Internal report PDF/PNG renders belong in the QA directory and must be excluded from the user-facing file list, result-page links and delivery ZIP unless requested. Reuse one final CIF-derived table dataset for both reports and all formatting passes; translation or DOCX-only layout edits do not change the validated structure or require another IUCr submission while the CIF hash remains unchanged. Render and inspect every page of both language versions before marking their delivery complete.

Separate bond-length and bond-angle table schemas, including their repeated continuation headers and units. In Word, adjacent tables with compatible formatting can join visually; use distinct table boundaries and a separating paragraph when needed, then inspect the exported continuation pages. Check the full coordinate/ANI/geometry row counts against the exact CIF, with deliberate exclusions stated. Record the actual renderer and any fallback; a successful alternative rendering does not mean a failed packaged renderer passed. The [LYH case lessons](lyh-case-lessons.md) retain the observed version and table-boundary failure modes.

If property figures, microscopy, phase transitions or computational interpretations enter the report, read [supporting-evidence](supporting-evidence.md). They can constrain hypotheses but cannot replace diffraction-based symmetry, identity or occupancy evidence. Reviewer suggestions and service forms are source material, not authorization for model changes or data removal.

Private case details and historical contradictions belong in the reading ledger, not repeated in this checklist. Keep earlier interpretations traceable when new evidence resolves them.
