# Common-disorder automation

Use `common_disorder.py` on **this run's assembled, paired candidate** when local evidence suggests a common fragment disorder. It generates and executes hypotheses without LLM calls; it does not identify chemistry from a compound database or select a final structure by R/AB alone. Previous stable models and all failed candidates remain available.

## Implemented scope

| Fragment | Scripted hypothesis | Boundary |
|---|---|---|
| CF3 | Identify one C–C axis and three terminal F atoms; test a bounded set of alternate rotations supported by distinct Q peaks. | Averaged geometry must still be identifiable. No automatic special-site accounting or arbitrary splitting of large F ellipsoids. |
| tert-Butyl | Identify a quaternary C and three terminal methyl C atoms; rotate the complete methyl branches and their existing supported riding H. | A chemically ambiguous carbon connectivity is not proof of a tert-butyl group. |
| Short alkyl chain | Identify a distal acyclic C path, 2–7 atoms; require current explicit CH2/CH3 riding-H evidence and single-bond-like geometry; test alternate torsions. | The rule preserves a current H hypothesis; it does not prove hybridization. No long-chain conformer search, branched chain generalization or periodic self-bond handling. |
| Common solvent | Match a whole disconnected heavy-atom topology, with solvent identity supplied for this specimen; test rigid orientations/translations. | No automatic solvent identification from formula alone; no internal ring puckering, flexible ether/chain conformation, water orientation, special-site or fractional solvent treatment. |

The catalog includes methanol, ethanol, diethyl ether, THF, acetonitrile, dichloromethane, chloroform, acetone, DMF, DMSO, toluene and hexane. A catalog entry is a topology hypothesis, not an empirical coordinate template. No historical crystal coordinates are embedded. THF in this version means **whole-molecule alternate orientation**, not a solved envelope/twist disorder model.

## Commands

```text
python scripts/common_disorder.py scan --baseline CURRENT_PAIR --stem model --output NEW_SCAN.json
python scripts/common_disorder.py prepare --baseline CURRENT_PAIR --stem model --possible-solvents ethanol thf --profile PROFILE.json --output NEW_COMPARISON
python scripts/common_disorder.py run --plan NEW_COMPARISON/plan.json
```

`scan` reads only the named RES/CIF and returns fragment candidates and specific reasons for review. Autorun's finishing-stage atom packet includes this screening automatically. It never borrows an old case or guesses a missing solvent identity. Read the compact packet before loading complete logs.

`prepare` first requires the existing paired RES/INS/HKL/CIF/FCF/LST checks, then copies a hash-bound baseline. It tests bounded geometrical poses against the **current native Q list**, rejects severe short contacts, and keeps up to two distinct supported poses per site. Q heights default to at least 0.35 e/Å³ and matching distances at most 0.45 Å; these are screening heuristics, not universal density significance criteria. Require at least two distinct peaks (three for solvents larger than five heavy atoms), displaced from the original element positions. Missing peaks produce a review packet, not invented coordinates. The truncated, phase-biased Q list is not a full difference-density map.

For each retained pose, prepare ISO and ANI diagnostic branches plus one contemporaneous unchanged continuation. Keep at most 16 alternatives for one invocation and explicitly record any deferred candidates. This is a search bound, not a claim that untried models are impossible. Exact native commands, software and implementation hashes, all trial logs, output files and failure reasons are saved. Edited input or code invalidates the prepared plan; create a new comparison.

## Bookkeeping and restraints

- Keep raw HKL and CELL/LATT/SYMM/HKLF, weights, temperature and reflection-selection controls unchanged throughout this comparison. Do not mix automatic OMIT or reweighting into disorder testing.
- One new FVAR controls complementary positive-PART populations. Shared atoms remain once. For an alkyl pivot whose H belong to alternate geometries, duplicate the pivot/H consistently and explicitly tie the pivot coordinates/ADPs with EXYZ/EADP. Keep the label map and modelled UNIT accounting.
  This pivot representation currently triggers the core's conservative overlapping-orbit/EXYZ review gate, even if the populations sum to one. The helper records that exception; it does not bypass the gate. These chain trials are diagnostic candidates requiring a specialist representation/constraint review before final delivery, not automatically deliverable models.
- Move complete supported riding-H groups with their parents, preserve AFIX and parent-linked Uiso, assign the same PART/population, and remove the old AFIX groups with their old H. Never leave an empty fitted-H group or transfer H between parents. Free H, unsupported AFIX, unresolved references and fixed-coordinate encodings require review.
- Compare corresponding 1,2 and 1,3 distances using local SADI; retain a modest local SIMU for the seed. ANI trials add local RIGU. These are stated hypotheses, not proof that original bond lengths or ADPs were right. Restraint tension and number of parameters remain visible.
- Existing PART, RESI, special positions, partial occupancy, ambiguous H, periodic fragments or constraints referencing the split atoms are not silently rewritten. Return the precise unsupported feature and preserve the model.

SHELXL's PART rules govern connectivity and H generation; complementary FVARs are model populations, distinct from special-site SOF. RIGU acts on anisotropic atoms, whereas SIMU/ISOR are approximate ADP restraints. Consult the [official SHELXL instructions](https://shelx.uni-goettingen.de/shelxl_html.php) for PART, AFIX, FVAR, SADI, RIGU and SIMU. Do not automatically replace a difficult disorder model by strong restraints.

## Comparison, handoff and delivery

`run` calls existing native SHELXL and local PLATON for each candidate. One failed trial does not stop the rest. Missing/failed validation stays unknown, not zero A/B. An unchanged control is required for comparisons. If that control fails, no candidate is accepted as an improvement.

`trials/comparison.json` retains individual added/removed/unchanged A/B occurrences, R1/wR2/GoF, convergence/NPD, residual extrema, occupancy and UNIT findings, ADPs, geometry/restraint tension, parameter/restraint counts, minority populations, branch collapse and H/PART/population discrepancies. No automatic winner is declared. Fewer alerts or a small minority population cannot establish correct chemical identity, charge, packing or physical disorder. Occupancy uncertainty, alternative equivalent mappings and unsupported model features still need scientific review.

The agent normally reads this compact comparison and only the exceptional evidence. After a candidate is reviewed and selected, continue through **the existing completion workflow**: native continuation/weights, final naming and file pairing, complete A/B review, authorized IUCr website validation and its original PDF, and Chinese/English Word from that exact final CIF. Place the final customer files in `<original data directory>/Cairystal`, retaining separate diagnostic comparisons. This helper does not upload by itself or claim that generating an INS/CIF finishes the job.

For a reliable host with genuinely diffuse solvent, use the separate consent-aware [SQUEEZE workflow](squeeze-workflow.md). The common-solvent catalog does not authorize SQUEEZE or solvent deletion.

## Validation claims

Native synthetic diffraction tests exercise CF3, tert-butyl, a short chain with riding H and a rigid solvent. They test program execution, bookkeeping, alternative rejection and preserved input, not accuracy on unknown experimental structures. Catalog coverage is not twelve-solvent experimental validation. Report native execution/local checking time separately from reasoning and end-to-end time. Zero LLM calls inside a helper is not a measurement of billed-token savings for a whole crystal job.

For mixed PART/BIND connectivity, ineffective restraints or H geometry after splitting, read [原生限制与氢几何 / native restraint and H audit](part-hydrogen-native-audit.md). This documents diagnostic limits and conditional trials; it does not enable automatic model acceptance.
