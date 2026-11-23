# Different orbit multiplicities: complementary SOFs are not molecular populations

Read this when complementary FVAR/PART encodings appear to validate a disorder assembly automatically. This is a read-only diagnostic lesson, not an accepted refinement recipe.

For SHELX effective SOF q, general-position multiplicity M and actual orbit multiplicity m, the ordinary physical site occupancy is q*M/m; the atom count per cell is q*M. Account for coincident alternative records and their intended assembly before summing. Never interpret an encoded 21 or -21 directly as physical occupancy.

## Local counterexample

The supplied dimethylammonium/tin chloride 400 K model has Immm, M=16, Z=2 and f=0.58525. Cl1 has q=f on an orbit with m=16; Cl2 has q=1-f on an orbit with m=8. Their physical occupancies are therefore 0.58525 and 0.82950, not two molecular populations summing to one. Their cell contributions are 9.364 and 6.636 Cl, totaling 16 Cl per cell or 8 per Sn. UNIT and the generated CIF both agree with that count; a bookkeeping audit can pass while the intended chemistry remains unresolved.

The paired 200 K model instead has Cl6 per Sn. In manuscript/SI versions, the 400 K formula was changed to Cl6 and formula mass423.58 while F(000)=480 and density2.113 still follow the Cl8 model. Do not fix this by editing just UNIT or report text. Reconstruct chemically coherent alternatives from density, symmetry and complete molecular populations, then re-refine and regenerate all linked quantities from the accepted version. No such repair has yet been demonstrated for this example.

## Review gates

- Determine each orbit and complete each molecular orientation, including shared sites. PART labels and complementary FVAR syntax alone do not define mutually exclusive whole molecules.
- Inspect geometry separately within each physically possible alternative. A short contact between mutually exclusive positions is not automatically a real chemical bond or a valid geometry-table entry.
- Audit restraint-imposed geometry. In this example, two N–C DFIX targets1.43 and C···C target2.475 impose an approximately120-degree triangle. Very tight targets and small reported uncertainties are not independent experimental support for that angle.
- Check actual instructions before describing methods: tight SIMU is not EADP; generic report prose about disorder restraints may be false for a file containing no such restraints.
- Preserve the original files, unresolved chemistry and historical alerts. Historical structure-factor reports are useful evidence but are not a new online checkCIF validation of a modified model.

Source trail: workspace `training_runs/full-reading/二甲胺锡氯盐模型与稿件核查笔记.md`, inventory D0776–D0784. Sources were read and arithmetic audited; no refinement or upload was performed.
