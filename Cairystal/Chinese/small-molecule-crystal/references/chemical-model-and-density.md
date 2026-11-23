# Chemical interpretation, H models, ADPs and residual density

## Atom identity and connectivity

Use synthesis/sample information as a hypothesis, not an instruction to force the desired product. Identify all chemically coherent components including counterions, solvent, hydrolysis/protonation or an unexpected reaction product. Peak height alone cannot reliably separate nearby-Z elements or establish bonding/oxidation state. Test a disputed assignment using density at the site, relative U, chemically meaningful distances/angles and charge/stoichiometry; seek spectroscopy/elemental analysis where diffraction is insufficient.

Scattering power, occupancy and ADPs can compensate for one another. An over-heavy assignment may yield an anomalously large U and negative local residual; an under-heavy assignment may yield a small U and positive residual. These are clues, not deterministic element-identification rules. Compare alternatives on equivalent data and inspect the affected site's geometry/density, not only a tiny overall R reduction. Recheck hydrogen count, UNIT and formula after a justified type change.

Generate molecular connectivity with periodic symmetry and PART alternatives in mind. Distance-only bonds can mistake coordination/contact for covalent bonding or join mutually exclusive disorder orientations. Examine complete fragments and packing, including symmetry-generated coordination; do not identify chemical connectivity from a clipped asymmetric-unit picture. Database or tabulated bond values must match the chemical environment/oxidation state, not become universal target distances.

## 2D-assisted assignment

Transcribe a supplied drawing into a checkable chemical graph: explicit heteroatoms, bond orders, formal charge, rings, substituents and counterions. Mark ambiguous lines, abbreviations and stereobonds; ask for a clearer image/SMILES/MOL when an ambiguity changes chemistry. A plausible-looking AI-generated image is not a validated molecular graph. For a programmatically drawn structure, retain its source identifier/SMILES and check the graph and drawing against each other.

The graph constrains plausible connectivity and H counts, not the crystal's 3D conformation, actual solvent, protonation, population or absolute configuration. Do not invent stereocentres absent from the source. Treat a proposed synthesis product as a hypothesis that can be contradicted by diffraction.

Map the graph to the current solution by complete fragments and symmetry-aware bonds. Review C/N/O assignments with valence, charge, distances, local U and residual density; do not simply relabel the highest peaks. Save the atom-role mapping and each correction, then regenerate H and recompute UNIT/formula before constructing supported alternatives. In a no-answer task, obtain geometry from this run, not from reference coordinates or old restraint lists; follow [learning mode boundaries](learning-from-solved-models.md).

## H placement and protonation

First establish the carrier's element, valence, component and protonation hypothesis. Choose riding, rotating or independently refined H according to data support and chemical environment; typical Uiso multipliers are model conventions, not measured H temperatures. Inspect actual temperature and bonding before generation. H on shared/special sites and each disordered component must have correct population and no mutually exclusive contacts misreported as simultaneous bonds.

For N/O donors, review residual maps, plausible acceptors, protonation/tautomerism and charge balance. A missing acceptor alert is a prompt for investigation, not proof the H must be deleted. Positive/negative density near an H can indicate placement/protonation errors but also map/data artifacts. Water H orientations need supporting geometry/density and uncertainty; if not located, disclose the model limitation rather than inventing observations. Neutron and X-ray nuclear/electron-density distances are not interchangeable. X-ray riding H are not independently observed nuclei.

If an authorized trial uses idealized water H directed toward plausible acceptors, label the positions as a chemical hypothesis, not peaks located in a map. Check local negative density, geometry, charge and restraint deviations afterwards. A missing-H alert disappearing does not rescue a contradicted H orientation; retain the H-free baseline when the orientation is unresolved.

Check both population and parameter freedom for H on a special-position carrier. In the reviewed C2/c YH114 model, each full oxygen orbit has multiplicity4 while the associated general-position half-occupied H orbit contributes4 H per cell: average H/O=1, not a fully occupied water inferred from two displayed symmetry-related H positions. Its +10-encoded H coordinates are fixed while Uiso remains free, with uncertainty almost as large as Uiso. A small formal O–H distance uncertainty does not include uncertainty in those fixed H coordinates; do not describe it as a precisely located proton or infer simultaneous occupancy from a displayed H–O–H angle.

Current AFIX code semantics combine initial geometry and the refinement constraint; HFIX generates the corresponding group. Confirm the installed/current syntax and carrier connectivity, especially for rotating methyl/OH groups. Never apply the historical printed room-temperature distances to every data set. A model change removing H freedom is documented as such; it does not automatically establish the orientation.

AFIX 6 before O/H/H retains the starting rigid-group geometry; it does not idealize an arbitrary water or independently refine its internal angle. A reviewed mirror-site water has full O and two general-site half-occupied H orbits, correctly totaling H2O. Its within-orientation angle is109.4 degrees, while a21-degree angle joins mirror alternatives. Audit those separately; do not restrain the cross-alternative angle. One reported restraint in a polar model can instead be an automatically generated floating-origin restraint, not a water distance restraint. Check LST and the [official AFIX semantics](https://shelx.uni-goettingen.de/shelxl_html.php).

## ADPs and restraints

UNIT agreement can conceal a hydrogen-model error. In the supplied HEPZBiBr low-temperature P1 model, one hydroxylethyl carbon has AFIX43 and one H while its counterpart has AFIX23 and two; UNIT was already set to the resulting odd H35 per cell. Check carrier connectivity and chemistry before deciding whether H is missing; do not merely edit the formula or interpret fractional formula H17.5 as physical proton disorder. Likewise, fixed-relative AFIX3 donor H positions can generate short H···H contacts without establishing experimentally located protons. Correct the model through an authorized, validated refinement rather than deleting H to remove an alert.

Assess the actual tensor/ellipsoids, anisotropy, neighbouring atoms at similar environments and parameter uncertainty. NPD indicates an unphysical or unsupported tensor requiring review. A distorted but positive tensor can still indicate a deficient model. Investigate wrong element, partial site, unmodelled orientation, shared sites, temperature/motion, poor data and missed symmetry/twinning before adding constraints. Static disorder and thermal motion cannot always be separated by one-temperature Bragg data.

| Instruction | Physical/model role | Failure to avoid |
| --- | --- | --- |
| EXYZ | Exact equality of coordinates | Equating genuinely distinct alternative positions merely to stabilize them |
| DFIX / DANG | Target 1,2 / 1,3 distances with chosen uncertainties | Imposing an unrelated textbook distance or inventing chemistry |
| SADI / SAME | Similar distances / corresponding fragment geometry | Wrong correspondence/order or bonds generated across alternative PARTs |
| FLAT | Approximate coplanarity | Flattening a chemically nonplanar fragment |

For EADP, RIGU, SIMU, ISOR and ANI/ISO alternatives, use [adp-model-selection](adp-model-selection.md). This is the maintained comparison procedure; do not repeat a specimen's restraint recipe here.

Inspect restraint deviations/counts and the real parameter count, not only input cards. Reassess restraint dependence as the model improves; constraints reduce independent variables, restraints add weighted information. Neither justifies pretending geometric precision came solely from the diffraction experiment. Shared-site population/U constraints require explicit orbit/composition accounting.

## Read the whole residual map

For nonstandard wavelengths, verify wavelength-dependent dispersion and absorption terms before interpreting element/absorption alerts. The local 0.630 and 0.68882 Å examples needed appropriately calculated terms, not a copied reference absorption coefficient. Check the chosen program's implementation and [SHELXL DISP](https://shelx.uni-goettingen.de/shelxl_html.php); regenerate model-derived quantities from the current model.

Record extrema, local map noise, locations/distances to atoms, symmetry repetition and chemically plausible peak clusters. A missing atom should be supported by coherent geometry and survive a justified trial. Near-heavy-atom shells of alternating positive/negative density can reflect absorption/scaling, truncation or model inadequacy; do not fill them with light atoms by peak height alone. Bond-centred residual density can reflect the spherical-atom approximation rather than a missing atom.

Continuous ridges/plateaus in a void may be invisible in a short Q-peak list: inspect sections/3D maps. An empty peak list does not prove no solvent remains. Do not require extrema to be exactly equal and opposite, or adopt one universal e/Å³ cutoff across wavelengths, resolution and scattering powers. PLAT971/972/976 and Hirshfeld alerts need their actual site and current explanation, not a canned author's response.

## Reviewed teaching evidence

`9 - Reporting and Cif Check - Fraser White 20200715.pdf` pages 53–56 (53 text-read; 54–56 text-read and visually checked) distinguishes missed density, incorrect elements, rotational substitutional disorder and missing counterions. Its simplified density/U tendencies are diagnostic hints, not universal algorithms. `加氢指令.pdf` pages 1–5 were text-reviewed; historical H/deuterium advice must be checked against current software and diffraction type. The library's new-coordinate C024/C709 exercises support connectivity/temperature checks and difference-map rebuilding, not general automatic atom assignment.

Primary syntax: [SHELXL AFIX/HFIX/constraints/restraints](https://shelx.uni-goettingen.de/shelxl_html.php). Alert interpretation: [IUCr PLAT971](https://journals.iucr.org/services/cif/checking/PLAT971.html), [PLAT972](https://journals.iucr.org/services/cif/checking/PLAT972.html), [PLAT976](https://journals.iucr.org/services/cif/checking/PLAT976.html).
