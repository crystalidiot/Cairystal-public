# Learn from solved structures without confusing reproduction and discovery

## Declare the exercise before access

- **Reference-guided learning:** inspect the supplied final construction first, then reproduce it on a copy. A checkCIF or a filename containing final does not certify the answer.
- **Independent/no-answer exercise:** read only declared inputs; exclude reference coordinates, ADPs, occupancies, old restraints and answer comparisons. Freeze candidates and failures before authorized answer access.
- **2D-assisted reconstruction:** a chemical graph is allowed, but supplies no experimental conformation or population. Use [chemical-model-and-density](chemical-model-and-density.md). Prior exposure cannot be erased; disclose it instead of calling the run never-seen blind.

A reference CIF used for later experimental metadata must be restricted to [experimental-metadata-preflight](experimental-metadata-preflight.md)'s allowlist. Seeing the same data or chemistry previously limits the claim even if no coordinates are copied this time.

## Worked-example procedure

1. Pair final CIF, embedded RES, HKL/FCF and report by evidence, preserving cell setting, temperature and processing stage. Separate intermediates from proposed final files.
2. Identify chemical components, symmetry, shared sites, PART/FVAR, H membership, geometry/ADP constraints and twin or mask contributions. Trace every variable by index and column, not its position in the FVAR list.
3. Reproduce unchanged instructions on copied inputs with bounded runs. Compare truly matched data/weights/selection; a different HKLF or mask contribution invalidates simple R ranking.
4. Audit composition, local configurations, restraints, uncertainties, density and convergence. An existing answer is useful evidence, not an oracle or a default restraint recipe.
5. For authorized later reconstruction, hide answers and recover positions from fresh density. Freeze before comparing; keep reference-guided revisions separate from blind scores.
6. Retain a concise decision note and positive/negative control. Store specimen coordinates, copyrighted lecture text and detailed histories outside the distributed skill.

For correlated alternatives use [whole-fragment-disorder](whole-fragment-disorder.md); for populations use [disorder-occupancy](disorder-occupancy.md). The following index preserves distinct lessons without repeating the full case narratives.

## Worked-construction index

These are observations of teaching models and selected reproductions, not expert certification.

| Private example | Reusable distinction / unresolved issue |
|---|---|
| Earlier C022, P-1 Cu/I | General-site Cu with SOF .5 is physically half occupied, not full on an inversion centre. Its organic f/1-f disorder is a separate population. |
| Earlier C032, naphthalene | `31/-41` is not exact complementarity; FVAR5 used in Uij is not a fifth population. A long EADP group is not automatically paired equalities. UNIT discrepancy remains unresolved. |
| Earlier C048, R-3 | M=18: q=.5,m=18 gives occupancy .5; q=1/6,m=6 gives .5; q=1/3,m=6 gives 1; q=1/6,m=18 gives 1/6. Audit the existing cutoff and 22 OMIT separately. |
| Earlier C052 | Shared population variables couple fragments; FREE changes connectivity, not occupancy. ABIN needs its paired FAB; a masked model is not explicit independent solvent recovery. |
| Newer C024, CuCl salt | Fresh ring/carbonyl density and connectivity support rebuilding the H model; preserve the actual 100 K metadata. R1 .0314 versus supplied .0313 and local 0A/0B/4C/10G are not a new official report. |
| Newer C709, Fd-3c | With M=192, a missing general-site methyl at q≈1/3 contributes 64 C/cell, not automatically a full special site. Reference-guided new-coordinate recovery converged (R1 .0318); correlations/C/G still require review. |
| Newer C317, P-62c | M=12: Cd q≈1/6,m=2 and Cl q=.5,m=6 are full, while general-site organic q≈1/6 stays partial. Scale-only FVAR does not refine six orientation fractions. Tight priors and differing HTML/CHK versions need audit; existing riding H cannot solve every parameter-count alert. |
| Newer C714, U complex | Full special-site U/O and partial general-site organics can coexist. A separate same-name P-1 version is a different model. Reproduced R1 .0196 includes FAB/mask contribution, not independently recovered solvent. |
| Newer C719, pillar arene | q=.5 on m=8 with M=16 is full occupancy. Small UNIT precision differences, ABIN and existing OMIT remain questions even beside a zero-A/B/C historical report; do not infer chemical vacancies or unknown solvent by rounding. |

The two ID series are different libraries. Newer private evidence: `training_runs/crystal-data_20261014_094818/reference-learning/` and its numbered case jobs. Collection counts refer to versions/combinations, not that many independent crystals solved. Current scope is in [problem-routing](problem-routing.md); software tests and scientific promotion gates are in [acceptance-tests](acceptance-tests.md).
