# PLATON analysis boundaries

Original synthesis from the privately reviewed 241-page PLATON manual dated 2010-09-29. This is historical evidence, not a current executable/API contract. Check the installed version and current primary documentation before implementing any command. Do not distribute the user's source manual or screenshots with the skill.

## Before interpreting output

- Record the precise coordinate file, reflection file, data block, cell, symmetry setting, software/check-definition versions and command parameters. A same-named old FCF may be selected before a newer HKL; inspect the actual loaded input, not just the command-line filename.
- Distinguish fractional coordinates from orthogonal Å coordinates. Missing cell or symmetry must trigger diagnosis, not silent acceptance of a program's defaults. Programs can assume different symmetry in the absence of instructions.
- Preserve `.def` files, saved instructions, masks, inclusion/exclusion lists, Q-peak thresholds and other persistent settings. A reset may not restore every parameter. Preserve original data; isolate candidate outputs and snapshots.
- Verify loaded atom counts, aliases, overlapping sites and symmetry expansion. Display-generated atoms are not new independent observations; residues, ARUs, molecules, asymmetric units and formula units are different objects.

## Disorder and special positions

Distinguish physical site occupancy from a program's special-position-normalized SOF. Under the convention described in the manual, `SOF = physical occupancy / site-symmetry order`; a fully occupied inversion-centre atom can have SOF 0.5 but physical occupancy 1. Evaluate SHELXL free-variable encodings before comparing numbers. Derive cell content from distinct orbit multiplicity times physical occupancy; do not count coinciding symmetry images twice.

Do not infer compatibility from automatic drawing connections or equal occupancies. Independently identify disorder assemblies, mutually exclusive components, shared sites and symmetry-generated alternatives. The historical loader/plotter describes limitations for twofold disorder and occupancy-based suppression of some connections; this does not establish correct handling of three/fourfold or independent disorder assemblies.

## Geometry and display are not refinement

- Record ellipsoid probability levels and actual Uij values. Ball/CPK radius changes, hidden components, absent labels and deleted plotted bonds do not repair the model.
- Distances/angles can be calculated for nonbonded atoms. Metal/alkali radii and tolerances influence classification, not proof of bonding or oxidation state. Selecting the closest five atoms for a five-coordinate calculation does not prove the true coordination number.
- Packing selection can use residue centres; clipping can break complete molecules. Include boundary-crossing neighbours when examining short contacts and coordination.
- For hydrogen bonds record chemical donor/acceptor assignments, component compatibility, hydrogen placement and any X-H normalization. A geometric acceptor list is not chemical proof.
- For derived geometry distinguish rounded CIF coordinates and marginal parameter variances from unrounded refinement coordinates and the full covariance matrix. Do not invent s.u. from a RES file or call omitted uncertainty contributions improved precision.
- Compare symmetry mappings, not raw symmetry-code strings. Preserve coordinate/ADP transformations and check orientation handedness; a matrix with determinant -1 is not a proper rotation. A view-inversion command must not silently change the accepted absolute structure.

## Candidate symmetry and solvent treatment

ADDSYM is a candidate generator. Record tolerances, ignored atom types and nonfitting atoms; an exact-within-tolerance coordinate match does not establish intensity symmetry. Examine raw/intensity evidence, absences, twinning and genuine pseudosymmetry, then refine competing models. Transform coordinates, ADPs, reflection indices, cell and composition bookkeeping consistently. Do not force experimental cell values to idealized angles merely because a candidate requires higher symmetry.

Void geometry, solvent electron count and solvent chemical identity are different evidence. Record probe radius, grid, atomic radii, region volumes and model/mask scope. Broad density can evade peak search; examine appropriately defined 2D/3D maps. Missing or erroneous strong low-angle observations can invalidate an integrated electron-count estimate.

For SQUEEZE, establish a justified solvent region and adequate host model including appropriate H atoms. Do not remove host disorder, counterions or charge evidence. Preserve original observations, solvent contributions and treatment metadata. The reviewed manual describes an old modified-HKL workflow; do not implement it as a current default. Never scalar-subtract intensities where the procedure requires complex structure factors. Final validation must use observations and a calculated model representing the complete treatment, not a solvent-free surrogate presented as raw data.

## Validation and escalation

Local `.chk` output is not the user's requested online IUCr checkCIF with structure factors. Retain the online submission artifact, response and exact submitted-file provenance separately. Missing tests, suppressed twin analysis and absent factors are limitations, not passes.

Treat high U3/U1, rigid-bond differences, TLS mismatch, bond-valence estimates, residual density and outlier lists as diagnostic clues with competing explanations. Do not automatically split atoms, lower occupancies, delete observations or increase restraints just to erase warnings. Synthetic `Fo=Fc` generators are for software testing only: never submit them, fill missing observations with them or use them to improve alert counts.

When formula-unit presentation changes, preserve the same cell composition and cell F(000); recompute consistency among Z, formula mass and density. The historical wording suggesting F(000) must change whenever Z changes is not an accepted rule. Estimated radii flagged by negative table entries are not physical negative radii; historical beta-conversion definitions with missing Uij factors must not become code.

See [validation-evidence.md](validation-evidence.md), [data-reduction-provenance.md](data-reduction-provenance.md) and [solution-failure-evidence.md](solution-failure-evidence.md). These reading-derived guardrails do not enable automatic expert repair or certify case-solving competence.
