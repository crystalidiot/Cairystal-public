# Scripted pipeline: one entry, no model API calls

For continuous exception-only operation, use [automatic dispatch](automatic-dispatch.md), `crystal_autorun.py run --config JOB.json --output NEW_RUN`. It calls the stages below, freezes configuration, retains checkpoints and stops for specific review reasons; it does not weaken these stages' scientific guards.

`scripts/crystal_pipeline.py` links existing tested components. Use it as the default for compatible original Bruker HKL/P4P inputs. Read its compact output first; do not repeatedly read implementations or rewrite per-case shell commands and report builders. Existing specialized tools remain the fallback for unsupported data.

## Once per computer: record the runtime

```text
python scripts/crystal_pipeline.py profile --software-dir SOFTWARE --renderer word --powershell APPROVED_PWSH --pdftoppm PDFTOPPM --module-dir OPTIONAL_PYTHON_PACKAGES --output PROFILE.json
```

Omit `--module-dir` when packages are already available. Alternatively choose `--renderer libreoffice --soffice SOFFICE`. The profile records the executing Python, module directories, executables and hashes. It does not install software, change PATH/security settings, test licensing or assert native execution. Subsequent runs verify executable hashes; actual run logs prove execution. A moved/updated installation requires a new explicit profile. Keep machine-specific profiles outside the distributable skill.

## One command: intake and fresh solving

```text
python scripts/crystal_pipeline.py start --profile PROFILE.json --data-dir ORIGINAL_DIRECTORY --elements C H N O Cl --specimen FACTS.json --output NEW_RUN
```

This records timing from pipeline creation, validates the profile, finds one immediate same-basename HKL/P4P pair, reads measured cell/wavelength/theta metadata, checks reflection layout, preserves input hashes and SFAC order, creates an isolated session, runs SHELXT and anisotropic baselines, and writes `decision_packet.json`. It does not read old CIF/RES/INS files or traverse subdirectories. Choose `--stem` for multiple input pairs. Ambiguous data produce a recorded blocker; unsupported cells/formats do not silently become an assumed P1 structure.

`FACTS.json` has a `provenance` and `cif_fields`, matching the existing specimen schema. Optional `confirmed:false` or `draft_defaults:true` prevents use as measured facts. Provide dimensions in mm as max >= mid >= min. Omit unknown facts instead of inventing values. Omitting the specimen file still permits solving; missing appearance is explicitly recorded for later validation. Reuse confirmed facts already supplied by the user. Add `--prior-conversation-exposure` where applicable.

Only supplied elements are used; rough search UNIT remains bookkeeping, not measured composition. Original P4P metadata and supported absorption logs are handled automatically. PCF/CIF_OD names are surfaced for separate scoped extraction; this first pipeline version does not silently open full companion CIF-like files that may include model data. Other original input modes, twins, special syntax and absent P4P use the existing inspect/native-run workflow.

## Scientific checkpoints, with mechanical execution batched

The candidate packet lists current candidates, numerical metrics, four-neighbor group observations, local ADP anomalies, H counts and evidence paths. A ranking is not automatic acceptance. A person or capable agent supplies a short justified plan; no LLM is required inside the program.

```text
python scripts/crystal_pipeline.py step --run NEW_RUN --source 01_baseline_0 --plan PLAN.json --name 02_test
```

The `PLAN.json` schema is the existing `crystal_session.py refine` plan: `reason`, `element_changes`, `rename`, `hydrogens`, `cycles`, `variants`/`variant_site`, `weight`, `suggested_weights`, `post`, `discover_hbonds`. The pipeline supplies all directories, copies the plan, executes related native calls, preserves every candidate, compares results and refreshes the packet and timing page. Chemical choices, H protonation, disorder and space-group selection are not guessed merely to avoid AI.

## One command: prepare the selected candidate and deliver

If a complete, explicit 2D graph is available, `match` can now generate the plan and provisional mapping automatically. See [graph matching](graph-matching.md) for the bounded C/N/O search, all-candidate refinement and ambiguity thresholds. Example:

```text
python scripts/crystal_pipeline.py match --run NEW_RUN --source 01_baseline_0 --graph CHEMICAL_GRAPH.json --name 02_graph --max-candidates 6 --add-hydrogens --donor-basis "Protonation specified by supplied graph"
```

Inspect its compact status and retained candidates. Continue to `finish` only after current-model review; a successful graph match does not bypass chemistry, residuals, weighting or A/B validation.

```text
python scripts/crystal_pipeline.py finish --run NEW_RUN --source FINAL_STAGE --review REVIEW.json --deliver --authorize-iucr-upload
```

Use upload authorization already granted for these data. `REVIEW.json` requires `chemistry_and_h_reviewed:true` and a meaningful `basis`. Optional `annotations` supports chemical moiety and known computing metadata; it cannot contain coordinates or overwrite the generated experimental-method narrative. Optional `bilingual_notes.zh/en` must preserve equivalent scientific meaning.

The script generates experimental-parameter merging, methods/provenance from actual run records, candidate pairing checks, bounded weight-loop configuration, local PLATON, official IUCr validation, shared-CIF bilingual Word tables, rendered page manifests and the HTML index. It records source processing limitations and user decision statements instead of inventing scientific prose. No per-case bilingual boilerplate or wrapper script is needed. `--max-weight-updates` defaults to four with a hard maximum of six. Abnormal movement, convergence failures, local A/B or unresolved weighting stop in the existing diagnostic state with files preserved.

If intentionally withholding external submission, omit `--deliver`; prepared products and local evidence are retained. To perform a new delivery after a completed local-only pass, use a new `--name` and retain the previous run. Exact-file cache reuse is limited to evidence from the current configured finish route; no old model or unrelated official report is loaded.

## Actual review, sealing and measurement

For the exception-only route after an unambiguous graph/H match, use `crystal_pipeline.py autofinish --run NEW_RUN --source CURRENT_GRAPH_H_STAGE --deliver --authorize-iucr-upload`. [Automatic report review](automatic-report-review.md) defines the bounded scientific checks, evidence-backed bilingual templates, layout checks and automatic sealing. It records no actual visual inspection; unsupported chemistry, A/B or QA findings stop with a specific packet. The manual route below remains available when actual page review is requested.

```text
python scripts/crystal_pipeline.py status --run NEW_RUN
python scripts/crystal_pipeline.py finalize --run NEW_RUN --reviewed-zh --reviewed-en --reviewed-official --review-note ACTUAL_REVIEW_NOTE
```

The three review flags assert actual visual inspection; never set them automatically. Word render logs, image manifests, hashes and shared numerical tables automate consistency checks, but they do not prove pages were viewed. A human may provide this review without AI. Finalization seals the ZIP with the official `IUCr_checkCIF.pdf`, both editable Word reports and matching model files. No extra report PDF is delivered.

Every action updates `pipeline.json`, `result.json`, `decision_packet.json` where appropriate, and `index.html`. Timings include native runs and weight trials, official validation, document creation/rendering and action intervals. Intervals between commands include scientific thinking, tool interaction and review; do not rename them pure CPU or reasoning time. Exact billed Token fields remain null because the pipeline has no access to conversation billing. Full-vs-compact candidate character counts are an explicitly limited proxy. No script calls an LLM/API model.

Failures are preserved with exact stage, arguments and log path. A reused stage/finish name is rejected instead of overwriting. Software changes, modified original inputs, linked paths and changed skill code stop a fixed-version run. Correct the cause and use an explicitly new stage/run; do not introduce uncontrolled retry loops or read reference answers.
