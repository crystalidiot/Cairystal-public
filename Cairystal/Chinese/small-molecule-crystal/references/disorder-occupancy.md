# Disorder and occupancy: interpretation before intervention

Interpret complete configurations, symmetry orbits and parameter roles before changing PART or SOF. Use [current SHELXL syntax](https://shelx.uni-goettingen.de/shelxl_html.php). Worked answers can contain mistakes; detailed specimen evidence belongs in the private case ledger.

## Three distinct quantities

For a resolved SHELX atom record, distinguish decoded SOF `q`, actual site multiplicity `m` and general-position multiplicity `M`:

- Atoms contributed to the cell: `M*q`.
- Chemical/CIF occupancy of that orbit: `M*q/m`.
- Example: `M=8`, `m=4`, SOF `10.5` gives full chemical occupancy 1 and four atoms per cell. The same SOF on a general site (`m=8`) gives occupancy 0.5, also four atoms per cell. The SOF text alone cannot distinguish them.

A molecule centred on a special position can have individual atoms on general positions. Enumerate orientations and shared/coincident sites; do not normalize every fractional SOF to full occupancy. Symmetry may equate the orientations within each family without equating totals between independent families. A near-axis partial general site and an exactly on-axis full special site can have the same cell count but different physical models.

For coincident symmetry orbits, sum the row contributions before interpreting population. Several fractional H rows can represent one full or partial orbit rather than independently resolved H orientations. Preserve H/carrier stoichiometry over the cell, not the number of H drawn in one view. Conversely, different nearby sites need not be experimentally resolved merely because their orbits are not exactly coincident.

Matching UNIT is bookkeeping, not proof of absolute population: a common occupancy multiplier can correlate with diffraction scale. Check formula/Z, density, charge, special-site normalization and independent chemistry. Do not infer vacancies or multiply all SOFs from UNIT agreement alone. See [orbit-population-case](orbit-population-case.md) and the worked constructions in [learning-from-solved-models](learning-from-solved-models.md).

## PART and free variables

- PART defines connectivity, not a population by itself. Its optional SOF overrides subsequent atom SOFs until the next PART. Negative PART suppresses special-position constraints and associated symmetry-generated bonds; inspect consequences for H generation and restraints.
- With `FVAR scale f`, `21` means `f`, `-21` means `1-f`; special-site half normalization uses `20.5` and `-20.5`.
- Resolve every FVAR by index **and column**, including Uij, coordinates, AFIX/PART overrides and continuation lines. A variable used in Uij is not a disorder population. Concatenate repeated FVAR cards in order.
- `31/-41` is `f3+(1-f4)`, not exact complementarity. SUMP restrains only its listed variables, with an uncertainty; check its effective sigma/residual and final sum. Rounded central values alone do not establish statistical significance without covariance.
- Four PARTs can describe two independent two-way disorders rather than one four-way population. Do not couple unrelated fragments with one variable without a physical reason.
- Distinguish absolute and conditional populations. H/methyl alternatives of .14/.36 on a half-populated carrier sum to .50, not 1; their conditional fractions are .28/.72 only after that normalization and matching multiplicities.
- Shared full-occupancy carriers can need alternative H directions following the branches' populations. Full carrier occupancy does not make all alternative H full. Check each complete configuration's chemistry, charge and H count.
- EXYZ/EADP constrain coordinates/displacements, not population sums. Audit every use of each population variable across the entire model, including element-interchange sites.

## Evidence and model comparisons

Elongated ADPs, residual peaks or a split suggestion justify investigation, not automatic disorder. Compare element errors, missing atoms, data treatment, symmetry and twinning. A proposed component needs coherent connectivity and density; a population with uncertainty comparable to itself is not compelling evidence.

Write a whole-configuration table with shared atoms, branches, chemical correspondence, H ownership and populations; see [whole-fragment-disorder](whole-fragment-disorder.md). Preserve whole-fragment symmetry representatives: independently choosing each atom's nearest image can mix mutually exclusive orientations. PARTs and correct average composition do not prove local joint occupation. A full site cannot coexist with a very close partial alternative simply because a global SUMP is satisfied.

One-temperature Bragg data and ellipsoid shapes do not by themselves separate static from dynamic disorder. Temperature-dependent diffraction or dynamics measurements may constrain that interpretation; simulation snapshots, entropy ratios and relaxation amplitudes are not crystallographic site populations.

Retain a matched-data baseline and bounded alternatives. Compare density, geometry, population uncertainty, correlations, ADPs and convergence as well as R. For restraint mapping, NPD and isotropic versus anisotropic choices, read [adp-model-selection](adp-model-selection.md); fewer alerts or lower R do not override an unphysical model.

## Read-only implementation

Run `scripts/audit_occupancy.py <resolved.res> [--dependency-dir <private-package-directory>]` with Gemmi. It decodes supported explicit SOF/FVAR syntax, checks conventional LATT/SYMM orbits, modeled composition, UNIT discrepancies and coincident-orbit sums. It does not rewrite files or validate chemical clashes and local configurations.

Compare actual RES normalization with exported CIF occupancy. Negative PART plus manually fixed special-site coordinates can lead to an export/accounting discrepancy; do not multiply RES SOF merely to fix the CIF. Decode SHELX parameters before orbit calculations: a coordinate such as `10.75000` encodes fixed `0.75000`, not ten extra cells.

Limits: simple single SFAC lists and explicit SOF/U records; included files, unresolved encoded coordinates and unsupported labels are rejected. Near-special sites, rounded CIF coordinates, special-site ADPs, unusual settings, overlapping H and chemical interpretation need review. No audit warnings is not acceptance.

Run `scripts/test_audit_occupancy.py` for supported numerical controls. Detailed historical counterexamples remain in the original case/reading records and the maintenance backup; this condensed reference retains their decision rules rather than repeating their atom lists.
