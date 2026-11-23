# Acceptance tests before automatic repair

A blanket unattended scientific model-repair engine is not validated. Its promotion requires representative expert-reviewed cases establishing each intervention's success and failure boundaries. This does not prohibit agent-led, evidence-supported candidate trials already authorized by the user: record the rationale, preserve the baseline, evaluate the result and reject unsupported changes. Software regression tests alone cannot promote scientific repair.

## Current verified scope

Routine automation maintenance check, 2026-10-27: **109 synthetic regression tests passed** (80 existing controls + 29 execution/delivery controls), with skill-format and relative-link checks passing. The added controls exercise active versus suggested SHELX records, required SFAC ordering, supported HKLF scope, negative intensities/batch handling, finite values, coordinate serialization including exponents, cell/wavelength and atom/element/occupancy/ADP mismatches, repeated official A/B codes, incomplete/mismatched validation reports, exact-file cache rejection, and post-review file integrity. Tests do not prove chemical correctness.

A private engineering replay of one previously finalized HKLF 4/LIST 4 heavy-atom model actually ran SHELXL, local PLATON, a new authorized IUCr structure-factor validation and seven-page Chinese/English Word reports. R values, source hashes and all official A/B findings were preserved; both Word reports and the official PDF were visually reviewed. The installed code was also exercised with exact-CIF official-result reuse. This was final-model reproduction/delivery, not a new independent solution benchmark. Timing includes automated steps only; scientific interpretation, bilingual review notes and visual review are separate. Case data, all logs and timings remain outside the distributable skill.

Latest gap-review maintenance check, 2026-10-26: **80 synthetic tests passed** on Windows/Python 3.12 with Gemmi 0.7.5 (71 previous controls + 9 companion-metadata inspection controls). New controls cover headerless CIF fragments without cell fabrication, unchanged inputs, exclusion of model/embedded values from output, multiple-block conflicts, unknown versus not-applicable tokens, case/Unicode/multiline values, loop review, invalid/unsupported inputs, explicit encoding, bounded reads and CLI errors. These tests do not establish support for all real instrument variants or scientific accuracy. No crystal was newly solved and no official checkCIF was generated for this maintenance task. Full commands/logs and before/after hashes are kept outside the skill.

The earlier environment-inventory maintenance check on the same date passed **71 synthetic tests** (63 existing controls + 8 environment-inventory controls). Those added stage-specific availability, SHELXD detection, missing/unreadable executables, stale-log exclusion, PATH non-substitution and CLI profile behavior. A read-only probe of the installed bundle and format validation also passed.

The preceding cross-agent handoff remains a separate, unmodified 63-test frozen release. Its package/extraction checks passed, but no WorkBuddy or specific Intern/书生 client execution was tested. Updating this live skill does not update that archive or validate cross-agent scientific equivalence; see [portable environment](portable-environment.md).

Local regression at 2026-10-24: **60 tests passed**, including the prior 53 occupancy/metric/serialization, processing, input-layout, alert-parser and validation-scope controls, plus 7 experimental-metadata controls. These test software behavior, not universal crystallographic correctness. An initial sandbox temp-directory permission failure was resolved by using a task-local tempdir without altering tests or business scripts. Format and relative-link checks accompany the private maintenance record.

Covered controls include special versus general-site SOF, repeated FVAR concatenation, metric compatibility, serialization tolerance, DAMP/no-shift jobs, BLOC/positive-XNPD review, HKLF5 BASF versus ordinary batch scales, conservative three-index fixed columns, negative intensities, report scope and partial/overflow alert parsing. Passing layout does not validate HKLF5 grouping or turn a modulation file into conventional data.

Real-file checks include unchanged source hashes, agreement with selected SHELXL CIF occupancies and explicit rejection of a four-index input. A near-special/riding-H discrepancy remains a review case. Detailed results and prior counts are in the private workspace ledger; do not distribute user datasets with the skill.

The [LYH case lessons](lyh-case-lessons.md) add a real-file metadata-only delivery with official structure-factor validation and unresolved model features. Synthetic controls extend metadata protection to occupancy/ADP loops and embedded inputs, distinguish cell-measurement counts from reflection statistics, and exclude inherited solver/absolute-configuration claims. These checks do not promote automatic scientific repair. Current rerun results belong in the private `maintenance/lyh_skill_digest_20261025/` record; the dated 60-test result above remains historical.

Historical exercises profiled many input **versions**, ran bounded solution/refinement hypotheses and local validation, and produced two deeper reconstruction examples. They do not establish mastery of every crystal, independent expert acceptance or new official online reports. Successful numerical reproduction, independent phasing and reference-guided recovery must remain separately labeled.

Retained negative examples:
- The 2026-10-26 carbon-only exercise did not independently yield an accepted structure. Corrected symmetry encoding and search-parameter errors were separated from valid unsuccessful trials. A later mathematically constructed cage was model-assisted, with R1 0.1391 but unresolved geometry/ADPs; it remained partial/unsolved. Lower R from an insignificant EXTI parameter was not adopted. Case-free lessons are in [sparse light-atom solution](sparse-light-atom-solution.md); coordinates, formula/population recipes and raw data are not distributed with that guidance.
- The 2026-10-21 matched-HKLF5 reference-assisted split model lowered R1 but either failed convergence with tight ADP restraints or retained one NPD with relaxed restraints. A one-site isotropic trial reached numerical convergence; this does not promote general automatic disorder repair. See [whole-fragment-disorder.md](whole-fragment-disorder.md).
- A three-case same-family transfer test reached numerical convergence for Co/Cu candidates but not the Fe case. The Cu whole-component anisotropic trial had seven NPD sites. Final local A/B counts were 4/5, 4/0 and 8/12; no case was declared a complete independent disorder solution. Frozen blind outputs and post-reveal reference analysis remain separate.
- Lower-R propyl-disorder alternatives produced 6 or 11 NPD atoms and were declined.
- An unsupported inversion-twin model in a centrosymmetric example did not become accepted when its parameter was removed.
- A normally finished frozen/no-shift job is `needs_review`, not demonstrated convergence.
- Zero A/B without supplied structure factors is incomplete validation.
- The 2026-10-24 case-20 whole-minor ISO trial converged with fewer parameters but retained one official PLAT220 B; its unrestrained ISO control failed to converge after 24 cycles. A preassigned directory name containing `converged` is not a gate result. See [adp-model-selection](adp-model-selection.md).
- Missing-water-H, OMIT and strong-SIMU trials from the organic20 collection remain conditional where density, overload provenance or restraint sensitivity are unresolved. Do not turn fewer local alerts into scientific acceptance.

## Representative scientific cases

Include routine light-atom and heavy-atom structures; centrosymmetric, noncentrosymmetric-achiral and chiral structures with useful absolute-structure evidence; positional and solvent/counterion disorder; inversion/non-merohedral twins; ambiguous symmetry; and deliberately invalid/incomplete inputs.

Use authorized, de-identified data or published teaching material. An expert-reviewed reference is needed for scientific acceptance; an existing file labeled final is insufficient.

## Required observable behavior

- Sources remain byte-identical; reruns create new jobs.
- Executable/version, command, inputs and changes are recorded.
- Completion is checked against outputs as well as process state. Empty/error outputs never become success.
- Metrics agree with the correct native logs and reflection/count conventions.
- Incomplete or unsupported inputs fail closed with a concrete explanation.
- Execution, numerical convergence and scientific acceptance remain separate.
- Full special-site occupancy, partial populations and overlapping orbits are distinguished within supported syntax.
- Alerts are preserved/classified; beginner summaries agree with expert review.
- Failed or bounded trials retain logs and a recovery path.

## Promotion gates

Promote inspection only after routine, ambiguous and missing-input controls pass. Promote solution after at least three known cases yield acceptable hypotheses, unchanged-model refinement after convergence/failure detection works across routine and difficult cases, and validation after completion/timeout/parsing checks are reliable.

Promote an **automatic repair rule** only when that particular intervention works on appropriate positive cases, declines negative controls, preserves provenance and passes independent expert review. Unit tests or fewer alerts alone cannot promote it.
