# Problem-to-tool routing

The console and `route-problem` use the same rule source, `assets/console/workflow-data.json`. Query by a three-digit PLAT code, phenomenon or initial-review packet. A route contains triggers, actions, available tools, acceptance checks, return points and missing automation. Retrieval performs no repair, upload or scientific acceptance; unmatched alerts remain unresolved.

    python -B scripts/toolbox.py run route-problem -- --alerts PLAT242 PLAT420 --json

Topics include post-solution C/N/O/connectivity, H/water/OH, short bonds, ADP shape versus magnitude, common group/solvent disorder, PART/FVAR/special positions, SQUEEZE, convergence, intensity-outlier controls, weights, metadata/TEMP, absolute-configuration reporting, evidence-triggered symmetry/twin review, systematic errors and artifact pairing/delivery. The rule source is currently Chinese; tool IDs and JSON keys are stable. This index contains no reference coordinates or sample identities. Do not follow private case links during blind testing.

New executable helpers: `initial-review` (read-only, connected to initial candidate baselines) and `route-problem` (retrieval only). `session` and `restraint-tension` expose existing script functionality through toolbox. Existing scientific scopes and evidence requirements remain in place. Automatic SHELXT-to-SHELXD fallback, a complete existing-OH reorientation engine, arbitrary water-H placement and unrestricted chemical acceptance are not implemented by this release.

Update: repair-plan adds six bounded local native-trial recipes, including simple existing-OH rotation. route-problem also provides a source-page/official-link index for501 PLAT codes; an indexed code without a route remains unmapped, not repaired. See [repair tools](evidence-repair-tools.en.md).
