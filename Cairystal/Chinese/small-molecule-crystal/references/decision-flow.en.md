# Evidence-led decisions, handoff timing and staged disorder

Initial reviews now provide a `decision_queue` with atom-specific evidence, tool IDs, argument templates and next actions. Resolve pairing/occupancy/connectivity conflicts before type contrasts. A clean screen is not chemical acceptance. Current-run evidence only; no reference-model lookup.

## Element contrasts

The existing initial-review command remains supported. Optional preparation/execution:

```text
python -B cairystal.py run initial-review -- --directory CURRENT --stem model --elements C N O Cl --output NEW_REVIEW.json --trial-output NEW_TYPES --profile MACHINE.json --run-trials
```

Default bounds are two suspect sites and four one-atom alternatives. Only allowed C/N/O already present in SFAC are considered; an element list is not a formula. Each trial preserves observations, setting and starting weights, and has an unmodified same-cycle control. UNIT is derived from the changed model, not accepted as confirmed chemistry. Relative-U anomalies generate diagnostic contrasts, not identity assignments.

Omit `--run-trials` to prepare only. Execution uses SHELXL plus local PLATON and saves comparisons; no model adoption or upload. A complete paired INS/RES/HKL/CIF/FCF/LST bundle is required. Stale review hashes are rejected. Empty candidate lists preserve explicit reasons without unnecessary native runs.

Existing H, partial/special sites, PART, constraints and geometry conflicts are deferred for evidence-based handling. Conservatively deferring all existing-H models is a current limitation, not a claim that their elements cannot change. The informational absence-of-H note no longer blocks initial atom-type contrasts; it remains recorded. Construct H after chemical assignment. Lowest R/fewest alerts cannot select chemistry.

Autorun handoffs contain the complete decision queue for every first model; atom detail stays in the existing review and need not be recalculated.

## Handoff timing

New autorun checkpoints record `wait_episodes`: reason code, evidence fingerprint, owner, opening/closing times and repeat observations. Observing the same unresolved evidence does not reset its clock. Execution of a next action or changed evidence closes an interval. Missing historical records remain unknown.

```text
python -B cairystal.py run performance -- --workflow-run EXACT_AUTORUN_DIR --output NEW_TIMING.json
```

Reports rank recorded closed intervals, list open waits separately and include top-level action timings. Handoff intervals include waiting/offline work; they are not measured AI time. No token counts are invented. Do not sum nested stage timings. Existing `--run DELIVERY_DIR` behavior remains.

## Staged disorder

Existing disorder tools retain CF3, tert-butyl, established sp3 alkyl chains and identified common-solvent routes. Up to three nested distal paths per chain end explore different single torsion axes. This does not perform an unlimited combinatorial torsion search or flexible-ring solvent fitting.

Current density proposes complete fragments, short refinement schedules bounded finalists, then full native refinement/PLATON restarts them from the same baseline. Every promotion/pruning decision is recorded. Nonfinite/missing metrics cannot rank; chemistry conflicts precede lower R in scheduling. Short-screen AB remains null, never zero. No finalists means no redundant full-control-only run.

Missing split atoms, occupancy problems, special-site migration and collapsed alternatives remain explicit. Branch separation uses periodic boundaries. Special sites produce stabilizer/operator/physical-occupancy/SHELX-SOF evidence and route to occupancy review; the ordinary-site generator is not applied blindly. Automatic special-position disorder solution is not claimed.

Chemical-first selection, final refinement, AB checks, final-CIF-bound official checkCIF and bilingual Word delivery remain required.
