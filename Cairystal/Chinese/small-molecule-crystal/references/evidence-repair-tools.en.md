# Evidence-backed local repair trials

Use `route-problem` and `diagnose` to investigate the current model, then `repair-plan` to prepare and run explicit alternatives. An alert number does not establish its cause. This tool does not accept a final structure or upload data.

```powershell
python -B scripts/toolbox.py run repair-plan -- list
python -B scripts/toolbox.py run repair-plan -- prepare --baseline CURRENT --stem model --request REQUEST.json --profile PROFILE.json --output NEW_COMPARE
python -B scripts/toolbox.py run repair-plan -- run --plan NEW_COMPARE/plan.json
```

Provide paired INS/RES/HKL/CIF/LIST-4 FCF/LST files from the same refinement. Preparation verifies pairing, freezes inputs, generates INS previews and records the current diagnosis. Execution rechecks hashes and compiles the request again before running separate SHELXL/local PLATON trials. Every alternative starts from the same baseline and is compared with a newly refined unchanged control. HKL, WGHT, cell, symmetry, TEMP, OMIT, twin and ABIN controls remain unchanged.

Every request requires `recipe`, `parameters`, `reason`, `evidence`; optional `cycles` defaults to20 (1–100). Evidence must describe this case, not a historical solution. User-supplied evidence text is not independently verified by the compiler.

| Recipe | Parameters | Scope |
|---|---|---|
| element_scan | atom; elements such as ["C","N","O"] | One supplied C/N/O site; alternatives must exist in SFAC. Recompute modeled UNIT, not a confirmed molecular formula. Reject a parent with existing riding H. |
| adp_local | atoms; methods chosen from RIGU,DELU,SIMU,ISOR,ISO; optional sigma,terminal_sigma,cutoff | Separate local non-H ANI trials. Defaults0.04/0.08 and SIMU cutoff1.7 are trial settings, not optimized universal values. |
| geometry_local | restraint; atoms; sigma; basis; target for DFIX/DANG | One distance pair, multiple SADI pairs, or >=4 FLAT atoms. Require chemical target/equivalence/planarity evidence; supported trial sigma0.005–0.2. |
| h_freeze | parent | Existing standard riding H group to AFIX3, preserving H count, SOF and U settings. Does not idealize an incorrect vector. |
| oh_rotate | parent; anchor; angles | Rotate an existing single H about a gathered C–O bond, preserving O–H distance and angle. Full occupancy PART0 only,1–8 supplied angles; AFIX3 trials. |
| omit_map | atoms | Local atom-omission diagnostic: L.S.0, LIST6, no ACTA. Removes associated riding children. Not reflection OMIT or a refined candidate. |

Example (labels are placeholders):

```json
{"recipe":"oh_rotate","parameters":{"parent":"O1","anchor":"C1","angles":[0,180]},"cycles":20,"reason":"Check a possible wrong OH orientation","evidence":["Current donor environment and density observations must be supplied here"]}
```

Explicit bounded labels only; no wildcard/global or cross-PART/RESI restraint recipes. Existing H editing validates AFIX count, parent, occupancy, external restraints and coordinates. Special sites, water H, partial-occupancy OH and dependent parent groups require a separate reviewed route.

Read `trials/comparison.json`, native logs and candidate models. Compare R1/wR2/GoF, shift/esd, NPD, parameter/restraint counts, density extrema, full AB changes, occupancy and restraint conflicts. Failed/map-only results have null AB metrics, not zero. H trials additionally report before/after D–H distances, potential N/O/F/Cl contacts, symmetry, D–H···A angles and very short contacts. These are geometric candidates: protonation, acceptor identity and difference density still need review. Only the nearest image per symmetry operation is recorded.

No automatic winner is selected. Once reviewed, return to `complete` / `resume-delivery` for weighting, final pairing/local AB checks, authorized official IUCr PDF and both Word reports. Local trial validation is not the official final checkCIF report.

See [source-method mapping](learning-method-map.en.md). Offline and native synthetic tests are engineering evidence, not experimental structure-solution accuracy.
