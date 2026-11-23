# Reproducible metadata and disorder comparisons

Use the new helpers on explicit authorized sources and current-run models. They do
not read answer models, infer unidentified solvent or accept a structure.

## Experimental metadata ledger

`experiment_metadata_state.py collect --config SOURCES.json --output NEW_LEDGER`
creates one immutable ledger for an experiment. Sources are explicit, hash-frozen
and paired with the exact HKL; no directory traversal occurs. Supported kinds:
`p4p` (documented Bruker CELL/SOURCE/SAINGL/CSIZE dialect), `cif_metadata`
(allowed CIF-text PCF/CIF_OD/metacif, including headerless fragments), `phil_metadata`
(literal diffractometer only; source line and brand-only scope retained), `sadabs_log`
(explicit output-HKL filename and reflection-count checks), and `confirmed_json`
(actual confirmed observations, not author defaults). Other formats need explicit
extraction and provenance; this is not a universal instrument parser.

Before adding project-side records, use [project metadata inspection](project-metadata-companions.md). Its read-only findings are not a pairing authorization or a measured-value confirmation. Preserve cross-folder HKL differences even when related raw companions have matching hashes. The inspector never imports one temperature field as the other.

Config example, with actual paths/hashes and a specific pairing basis:

```json
{
  "hkl": "current_input/data.hkl",
  "sources": [{
    "path": "current_input/data.p4p",
    "kind": "p4p",
    "source_sha256": "actual source hash",
    "hkl_sha256": "actual HKL hash",
    "same_experiment_confirmed": true,
    "basis": "Specific original acquisition/reduction linkage",
    "temperature_scope": "both"
  }]
}
```

P4P temperature scope is `diffraction`, `cell`, `both`, or `unconfirmed` according
to source meaning. Do not infer it from a filename alone. All original scalar
tokens and locators are retained. Conflicting sources, impossible values, reversed
size/theta ranges and unhandled loops are recorded or blocked. Missing values and
`.` remain distinct. No atom counts, model geometry, calculated density, reference
refinement statistics or space group are imported.

After **every selected refinement regeneration**, run:

```text
python scripts/experiment_metadata_state.py sync --ledger NEW_LEDGER/metadata_ledger.json --cif CURRENT/model.cif --res CURRENT/model.res --hkl CURRENT/model.hkl --output NEW_SYNC
```

It verifies source hashes, HKL lineage, available cell setting and embedded RES;
fills missing experimental scalars in a new CIF and proves all other parsed values
unchanged. Existing conflicts remain visible. `native_refinement_required` routes
TEMP problems to `temperature_consistency.py`, renewed SHELXL/H review, and then
another sync. Never overwrite embedded RES to simulate a rerun. A new source fact
requires a new ledger. Cell basis changes require separately established mapping.
`--basis-audit` supports explicitly reviewed signed axis permutations only. It
checks the native HKLF matrix, frozen current-run transformation evidence and the
transformed metric. A declared, bounded angular idealization remains
`candidate_symmetry_requires_review`; metadata synchronization cannot certify a
new space group. General transformations remain unsupported, rather than guessed.

The ordinary `crystal_pipeline.py start/step` path now initializes a session ledger
and writes a separate synchronized CIF for each new candidate. The normal pipeline
passes the ledger to `routine_finish.py`; after weight refinements and before
freezing/submission it synchronizes again and blocks unresolved field/TEMP
conflicts. Native solver outputs remain retained. A source parser failure is
recorded separately from solution success and blocks final delivery until reviewed.
PCF/CIF_OD/confirmed observations may be added through an explicit new source
configuration; they are not discovered by reading reference CIFs during a blind run.

SADABS: never use its approximate cell or wavelength in place of integration
measurements. Preserve estimated transmissions, software version, additional
spherical `mu*r` correction and the source warning that transmission ratios are
more reliable than absolute values. These are processing facts, not evidence that
the chosen absorption correction suits the specimen. If the native CIF already
contains the same-version literature citation, the narrowly scoped helper appends
the verified output note without removing that citation. Different versions or
contradictory `mu*r` values remain conflicts. This exception does not apply to
numeric scalar disagreements or arbitrary narrative text.

The ledger is reused after weight or disorder trials so regenerated CIFs do not
silently lose recovered fields. Use that exact synchronized CIF for local PLATON,
authorized IUCr validation and both Word reports. Unknown observation fields remain
listed even when they produce metadata A/B. No report can assert that every
experimental fact was recovered if the source does not contain it.

## Stronger disorder comparison

`candidate_trials.py` now records exact HKL hash, frozen cell/symmetry/selection/
weight/TEMP controls, SFAC order, final restraint-tension screening and aggregate
ADP extremes. `compare_diagnostic_trials.py` verifies this context before treating
trials as comparable, retains each A/B occurrence, and flags residual-positive and
residual-negative deterioration separately. It reports added parameters and the
observations/parameter ratio without inventing a statistical significance test.

Use a contemporaneous unchanged continuation; compare chemically supported local
restraints, complete-fragment disorder alternatives and alternative initial seeds.
Interpret populations with symmetry multiplicity and FVAR coupling. Inspect the
actual region/atom packets and full density where needed: maximum Ueq alone does
not diagnose a fragment. A short-bond/elongated-ADP problem can involve incorrect
elements, mixed positions, protonation, symmetry, twins or data errors; DFIX is only
appropriate for an independently supported geometric hypothesis.

Fewer A/B plus conflicting DFIX/DANG, rising residual density, poor convergence,
NPD, unexplained occupancy or uncontrolled extra parameters is not acceptance.
No listed disagreeable restraint does not prove correct geometry or rule out
over-restraint. Geometry and occupancy sensitivity remain scientific review tasks.
For an unresolved model, produce clearly labelled research-candidate reports and
retain official A/B findings; do not rename them final solved structures.

## Diagnostic ordering confirmed in actual trials

`diagnostic_priorities.py` is called by `structure_diagnostics.py`. It only
prioritizes evidence; it does not issue model-edit instructions automatically.

- Inspect the parameter named in the final LST shift listings. Repeated sign changes
  in `tors H...` can indicate a rotating methyl-H instability rather than positional
  disorder. Compare an appropriate fixed riding orientation supported by chemistry;
  preserve the starting orientation and inspect the residual/H-bond evidence.
- ADDSYM 112/113 precedes a split-model interpretation. Its coordinate fit is a hint;
  test transformed reflections, systematic absences and equivalent merging. Keep
  cell-angle deviations visible. Comparisons across space groups have different
  independent data/parameter counts and are not identical-context R comparisons.
- SHELXL NPD=0 does not imply healthy ellipsoids. PLAT211 may still detect a nearly
  flat, positive tensor. Check Cartesian eigenvalues and the official alert.
- A local ISO alternative can identify an unsupported tensor but may create PLAT201
  or expose another problem. Do not make an entire organic component ISO solely to
  lower the alert count. ISOR, RIGU and SIMU each need a local physical rationale.
- A split can lower R, residual density and B counts while leaving several DFIX/DANG
  errors above 5 sigma. Reject acceptance of that hypothesis and preserve the result;
  do not automatically tighten restraints to force a nominal bond length.
- Before HFIX, reserve unique SHELXL-compatible atom/H labels. Generated labels can
  collide or exceed the parser's label syntax when many long labels share prefixes.
  After adding H, recount UNIT from the actual generated model before reporting;
  the pre-H UNIT is not an experimentally known formula.

The fixed-weight trials diagnose model changes. They do not replace a final weight
review once the chemistry is acceptable. Unresolved geometry/protonation is not
permission to tune WGHT merely to make GoF approach one.

Primary technical definitions: [PLATON ADDSYM](https://platonsoft.nl/platon/pl000401.html),
[SHELXL instructions](https://shelx.uni-goettingen.de/shelxl_html.php), and
[IUCr absorption process details](https://www.iucr.org/__data/iucr/cifdic_html/3/CORE_DIC/Iexptl_absorpt.process_details.html).

## Reproducibility

Run scripts via absolute paths and tests from a clean job directory. A historical
same-named Python module in the current working directory can shadow the tested
version under `python -m unittest`; capture module origins/version hashes. Preserve
failed environment attempts and rerun with the corrected, unchanged source version.
Do not modify the stable release or other chats' frozen skill copies during tests.

Fresh-sample selection should check prior input hashes/run records as well as
filenames. A previously used HKL can exist under an unfamiliar source path. No
hash match is evidence of a new input file, not proof of unseen chemical identity
or absence of a transformed/scaled equivalent; state this limit in the benchmark.

## 重复同步和失败恢复

同一批原始输入的 ledger 只有在输入绑定、所有来源哈希、冲突和格式检查均通过时才可复用。重复同步生成新的尝试目录，保留上一次证据；成功后清除旧的 metadata_sync_error，失败则留下具体原因。局部差值图必须同时匹配晶胞与对称操作，非整数反射指数拒绝处理，不截断取整。

## Explicit user temperature convention

A project-specific, explicitly authorized 293 K room-temperature assumption is handled separately under [user-temperature-default](user-temperature-default.md). It requires a completed permitted-source check, no unresolved contradiction, a retained assumption record, TEMP 19.85 degrees Celsius and renewed native/validation/report steps after changes. It is not a recovered measurement or a confirmed_json measured-source entry. Without such authorization, the unknown-value rules above remain unchanged. Reuse an existing applicable user choice instead of repeatedly asking for it.
