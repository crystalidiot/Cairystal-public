# Reusable execution and bilingual delivery

Read-only arithmetic/control checks and before/after A/B comparison are now scripted: [routine consistency checks](routine-consistency-checks.md). Routine finish/delivery stop before submission on definite contradictions; unresolved checks also stop bounded automatic acceptance.

Use these scripts for repeated mechanical work. Keep chemical interpretation, space-group selection, disorder building, restraints, reflection rejection and A/B diagnosis as evidence-based decisions. The scripts do not make or promote automatic model repairs.

## Runtime and scope

- Python 3.10+, Gemmi, python-docx and pypdf. Use the host's approved runtime and package paths; no implicit installs or API/model calls.
- Explicit paths to SHELX/PLATON executables, an available Word COM or LibreOffice renderer, and Poppler `pdftoppm`. For Word, supply the approved host PowerShell path; the scripts do not change execution policies or other security settings.
- Default CLI output is a compact JSON result. Full commands, native logs, hashes, tables and errors stay in the new output directory. Read detailed logs only when the summary or a scientific question requires them.
- Ordinary, single-block, three-index HKLF 4, LIST 4 output is supported. The final bundle must contain matching INS/RES/HKL/CIF/FCF/LST and SHELXL embedded RES/HKL. The delivery gate compares active RES instructions, coordinates, occupancies, ADPs, symmetry, reflection rows and native refinement statistics. It allows actual CIF serialization rounding; it does not silently round away a mismatch.
- Supported HKLF 4 two-domain TWIN/BASF and BASF batch scales use automatic native pairing; see [routine twin routing](routine-twin-routing.md). No concrete twin signal means no additional speculative twin search. HKLF 5, unsupported twin/batch combinations, RESI label mapping, encoded/free-variable ADPs and unsupported settings still need a specific review. The non-twinned HKLF 4, unscaled ABIN route is supported only with its matched FAB and [SQUEEZE checks](squeeze-workflow.md). A rejected routine route does not imply the broader skill cannot treat the structure. ISO/ANI mixtures retain their actual tensor availability.

## 1. Run an explicitly prepared candidate

Prepare and review the candidate INS using the scientific workflow, then run:

```text
python scripts/run_crystal_stage.py --executable <absolute-shelxl-path> --ins <candidate.ins> --hkl <paired.hkl> --output <new-stage-directory> --stem model --reason "Evidence and purpose of this candidate"
```

SHELXT and SHELXD executables are also accepted for explicitly prepared inputs; their output availability is not scientific acceptance. The runner copies inputs, preserves SFAC order, records executable/input hashes, executes without opening Olex2, checks SHELXL completion and convergence, and verifies source hashes. It never overwrites an existing output directory, edits coordinates, changes weights or removes reflections automatically. `--timeout` is a configurable process watchdog, not a scientific trial budget.

Use `inspect_case.py`, `inspect_experiment_metadata.py` and the existing provenance workflow before this step. They remain the tools for finding and interpreting permitted original input/metadata; do not read reference coordinates in a blind test.

## 2. Freeze and validate the chosen model

Finish element/H/disorder decisions, review active versus suggested WGHT, and settle metadata before official submission. Record meaningful candidate comparisons and remaining limitations. Do not repeat unchanged hypotheses just to chase alert counts.

The delivery command consumes a **chosen final candidate**, not an unsolved HKL:

```text
python scripts/crystal_delivery.py run --input <matched-final-bundle> --stem model --output <new-delivery-run> --notes <bilingual-reviewer-notes.json> --platon <absolute-platon-path> --renderer word --powershell <approved-host-powershell-path> --pdftoppm <absolute-pdftoppm-path> --authorize-iucr-upload
```

On a host with LibreOffice, use `--renderer libreoffice --soffice <absolute-path>` instead of Word/PowerShell. Probe once; use a renderer that actually exists. A missing renderer leaves documents/validation evidence preserved but does not produce a completed package.

`--authorize-iucr-upload` records an authorization already established with the user. Do not pass it without authorization to share the structure and reflections with IUCr. The uploader verifies the actual form, submits CIF plus LIST 4 structure factors, disables email and duplicate lookup, saves the unmodified official PDF and structure-factor HTML, checks confirmation of supplied structure factors and no syntax errors, and reconciles parsed alert lines with official summary counts. Repeated alert codes remain separate findings. Ambiguous/failed submissions are preserved without blind automatic resubmission.

The local PLATON preflight is separate from the official result. Its Windows completion guard waits for CIF/FCF markers and stable output files, terminates only its own process when needed, and records that termination accurately.

If metadata remain missing, optional `--metadata-source <permitted-source.cif> --pairing-evidence <record.json>` invokes the existing allowlist-only metadata merge on a new copy. It requires established same-experiment provenance, retains conflicts and unknown fields, and does not import source model/ADP/formula/refinement data. Companion PCF/CIF_OD inspection remains explicit; do not blindly traverse directories or invent defaults as measured facts.

## 3. One dataset for two Word reports

Supply a small JSON notes file with `zh` and `en` objects. Each requires `summary` and `methods`; optional keys are `title`, `limitations`, `provenance`, and `alert_explanations` keyed by the complete official alert code, for example `420_ALERT_2_B`. Both versions must preserve the same degree of uncertainty. Case-specific notes belong in the job, not inside the skill.

```json
{
  "zh": {
    "title": "晶体学报表",
    "summary": "填写本次分析结论及尚未解决的问题。",
    "methods": "填写实际采用的求解、精修与氢原子处理方法。",
    "limitations": "如实说明未确定的信息和重要警告。",
    "provenance": "说明独立求解、参考辅助或工程复现的真实来源。",
    "alert_explanations": {}
  },
  "en": {
    "title": "Crystallographic report",
    "summary": "Provide an equivalent English account of this analysis and unresolved issues.",
    "methods": "Describe the actual solution, refinement and hydrogen treatment.",
    "limitations": "Preserve the same uncertainties and important warnings.",
    "provenance": "State the actual independent, reference-assisted or engineering-replay provenance.",
    "alert_explanations": {}
  }
}
```

Replace these example descriptions with actual review notes before delivery; the renderer does not infer chemistry or translate unsupported claims. Shared numerical tables are extracted once from the frozen CIF: crystal/refinement statistics, all atomic coordinates and occupancies, ANI tensors, non-H bond geometry, donor contacts and symmetry codes. The saved DOCX tables are compared across languages. Missing values stay unknown; low R/zero A/B never becomes a statement of correctness.

Outputs are `晶体学报表_中文.docx`, `Crystallographic_Report_EN.docx` and `IUCr_checkCIF.pdf`, together with matched model/data files. This default native-table layout is reusable; a specifically requested different Word template requires a separate layout adapter with the same dataset and QA checks. No document-rendering PDF is included in delivery or ZIP.

## 4. Review and seal

The run stops at `awaiting_visual_review`, with a compact summary listing metrics, **all A/B findings**, timings and `qa/render_manifest.json`. Read both documents' page images and the official report; inspect any significant C/G findings and scientific limitations. Fix layout or scientific problems in a new run and preserve the previous one. Only after actual review:

```text
python scripts/crystal_delivery.py finalize --run <run-directory> --reviewed-zh --reviewed-en --reviewed-official --review-note "Describe the actual pages and scientific limitations reviewed"
```

Finalization refuses changed inputs, model/report files or QA evidence. It hashes the delivery and creates `structure_and_reports.zip` with an explicit file list. Its status remains `delivery_complete_needs_scientific_review`; automated formatting and validation are not an expert certificate of structural accuracy.

## Exact-file reuse and measurement

For translation/layout reruns of the **identical CIF** in the same authorized job, `--official-cache <previous-run/official>` reuses the official result only after checking the CIF hash, options, submitted CIF, PDF/CKF hashes and report scope/counts. A mismatch fails closed; the agent must make a deliberate new submission decision. It never treats a similar cell, name or low R value as a cache match.

Measure solver runtime, local validation, official validation, DOCX generation, rendering and actual review time separately. Report whether an official result was cached. A final-model delivery benchmark is not a new independent solution benchmark. Do not compare its duration to an entire difficult structure analysis as an end-to-end speedup. Character volume and number of agent turns may be proxies for reduced context, but are not exact token consumption; do not invent token savings.

See `test_delivery_automation.py` for negative controls. Synthetic tests and engineering replay establish software behavior only. Keep private benchmark inputs/outputs and learned chemical cases outside the distributable skill.


## Raw-data sessions and eliminating repeated setup

Use `crystal_session.py` for supported original Bruker P4P/HKLF4 data. This initializer currently supports recorded triclinic P and b-unique monoclinic P/C classes; other settings require an explicitly reviewed INS and the existing stage runner. It reads only explicitly supplied files and writes a new job. It does not discover, identify or import historical structures.

1. `start --hkl <original.hkl> --p4p <original.p4p> --integration-log <original._ls> --absorption-log <original.abs> --specimen <facts.json> --elements C H N O ... --shelxt <exe> --shelxl <exe> --output <new-job>` records original hashes, SFAC, approximate search UNIT, experimental scalars and a Laue seed from the recorded Bravais class with a metric consistency check. Search UNIT is not a measured composition; no default one-atom-per-element assumption. It runs fresh SHELXT and anisotropic baselines, preserving hypotheses and compact neighbor/ADP reviews. The Laue seed does not establish the final space group. Inspect absences and chemistry before selection. Changed solver cells need explicit reflection-transformation auditing.
2. `refine --job <new-job> --source <this-job.res> --plan <this-job-plan.json> --name <new-stage>` applies only an explicit, justified plan. Supported keys are `reason`, `element_changes` by current atom label, `rename`, `hydrogens` (reviewed HFIX records), `cycles`, `suggested_weights`, `weight`, and `post` records. `discover_hbonds: true` with `post: ["HTAB"]` discovers donor geometry and runs a recorded explicit-HTAB output stage. Optional `variant_site` plus `variants` creates independent element trials at unchanged weights. UNIT is recomputed using actual symmetry/SOF accounting, with SFAC order preserved. Select the scientifically supported candidate yourself; a lower R alone does not establish identity. Plans and models outside this session are rejected.
3. `prepare --job <new-job> --stage <chosen-stage> --annotations <job-reporting.json>` creates the selected bundle, merges original experimental metadata with provenance, records conflicts/confirmed overrides, checks file pairing and reviews hydrogen-bond reporting before upload. Permitted report annotations include chemical moiety, methods and computing provenance, never model coordinates. Source temperature has no invented standard uncertainty. A specimen JSON uses `cif_fields` for genuinely confirmed sample facts and carries its provenance separately; draft defaults must not be supplied as measured facts.
4. Run `crystal_delivery.py` once on that selected bundle with both-language notes. Its preflight removes only reporting contacts to a Cl bonded to four short O sites; free halide acceptors remain. It records changes while preserving coordinates/ADPs/reflections and embedded native records. Investigate retained long/bent contacts rather than declaring them strong hydrogen bonds. Translation-equivalent symmetry expressions are compared modulo integer-cell translations, without rewriting CIF symmetry order or geometry codes. Wrong rotations/fractional translations still fail.
5. Actual visual review of every page of both Word documents and the original official PDF remains required. The driver automatically creates official-page previews plus a manifest alongside both Word renders; open those known files in batches, without writing a new preview script. Finalize with the existing review gate, then `crystal_session.py close --job <new-job> --delivery <delivery-run> [--baseline-seconds <known-earlier-total>]` verifies original/skill hashes and generates the HTML index, machine-readable result and timing comparison. No per-case summary script is needed.

Time skill development/testing separately from a subsequent independent phasing run. Session and delivery ledgers record event start/end timestamps and native execution separately; intervals not directly instrumented must be labelled analysis/tool/interaction overhead, not assigned invented active reasoning time. Do not use previous-model replay to substantiate a fresh-solve speedup, and do not omit all-page visual QA to shorten it.

Ueq pairing compares both the reported CIF rounding and the propagated bounds of separately serialized RES Uij terms. This accounts only for file precision, not experimental uncertainties; mismatched tensor values, ADP types, rotations, occupancies or coordinates remain errors. Gemmi rows are converted to lists before slicing, and nearest-neighbor summaries retain all coordinates until every atom has been processed. Regression tests cover these execution paths with synthetic examples.


## Compact routine completion

See [low-token execution](low-token-execution.md) for `routine_finish.py`, bounded weight updates, exact-hash local validation reuse, deterministic bilingual facts and review checkpoints. `crystal_session.py start/refine` now return compact summaries; full atom/neighbor records stay on disk, with `--detail` available for a targeted diagnostic. Anisotropic conversion and ASU formula bookkeeping are explicit initial-baseline options, never implicit changes in a weight-only continuation.
