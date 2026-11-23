---
name: small-molecule-crystal
description: Set up Windows crystallography software and guide beginners through small-molecule single-crystal inspection, solution, refinement and checkCIF validation from a data directory containing SHELX-format files.
---

# Small-Molecule Crystal Structure

Preserve source data. Work in a new job directory and keep the model, reflections, processing history and reports together.

## Start here

For exception-only execution, start with [automatic dispatch](automatic-dispatch.md) and `crystal_autorun.py run`. The current short SKILL.md takes precedence over historical per-stage wording here. Normal supported steps run consecutively; compact handoff packets identify exceptions. Automatic report QA is a measured rules check and never asserts actual visual inspection.

Default to [beginner-mode](beginner-mode.md): one question at a time, plain-language outcomes, and a directory path as the starting input. Ask for chemistry/sample history when needed for a defensible decision.

- **Software missing or installation requested:** use [windows-install](windows-install.md), including `scripts/install_preflight.py --target <directory> --json`. Present official source, destination, size, licence question and changes before approval. Do not overwrite existing installs or change global PATH implicitly. Recheck current official downloads.
- **Software locations unknown or moving to another computer/agent:** use [portable environment](portable-environment.md) and `scripts/probe_environment.py --software-dir <directory> --profile solve --json`. File availability is separate from actual execution. [local-environment](local-environment.md) is historical workstation evidence, not target-machine configuration.
- **Data supplied:** follow the [specimen intake](beginner-mode.md#each-new-specimen-chemistry-and-experiment-facts-before-solving): ask for expected chemistry and all plausible elements, including solvents/counterions; a 2D structure is helpful but optional. Explicitly record the element hypothesis and SFAC order. Run `scripts/inspect_case.py <directory> --json`. Check same-experiment companion metadata, especially Rigaku `.cif_od`/`cif_od` and Bruker `.pcf`, and ask once for colour, habit and three dimensions (reuse already supplied facts); see [metadata preflight](experimental-metadata-preflight.md). Unknown appearance uses separately labelled draft defaults, never confirmed experimental values. Resolve missing/ambiguous pairs before invoking software. Once ready, run `scripts/setup_job.py <directory> --software-dir <directory> --output-root <directory> --json`; use `--stem` to select an identified pair.
- **Solve/refine/validate:** read [workflow](workflow.md). Default to command-line/file-based processing without opening Olex2, including audited fragment assembly and saving; retain `LIST 4`. Open Olex2 only on user request or for an explained review need that cannot be met headlessly. Finish with the official `IUCr_checkCIF.pdf` and two separate editable crystallographic Word reports (`.docx`), **one Chinese and one English**, derived from the same final CIF. A report-rendering PDF is internal QA only; do not deliver or link it unless requested. Follow the [efficient execution and staged delivery](workflow.md#efficient-execution-and-staged-delivery) guidance.

For repeated execution and final-candidate delivery, use [reusable automation](routine-automation.md): `run_crystal_stage.py` runs prepared SHELX candidates; `crystal_delivery.py` checks paired files, runs local/official validation and generates both Word reports from one dataset. Read compact JSON summaries first; open full logs only for a diagnostic need. Scientific model choices and actual page review remain required. For supported raw Bruker P4P/HKL jobs, `crystal_session.py` reuses fresh solving, explicit candidate plans, pre-upload reporting checks and complete timing/HTML summaries; see the raw-data session section in that reference.

Do not load the entire reference library. Read the relevant branch below.

## Problem routing

| Situation | Reference |
|---|---|
| Strong low-angle residuals, EXTI/PLAT031, weighting trends or PLAT250 | [systematic-error diagnostics](systematic-error-diagnostics.md): distinguish systematic absences, extinction correction and global ADP effects |
| SAME/H/CHIV scope, density/F(000) inconsistencies, temperature-series tables or conflicting tutorial advice | [restraint and accounting audit](restraint-and-accounting-audit.md): case-free checks and evidence boundaries |
| Multiple versions, CIF/archive recovery, missing INS, transformed HKL | [data-provenance](data-provenance.md) |
| Satellites, indexing/cell problems, twins or unsupported data | [difficult-data-routing](difficult-data-routing.md) |
| Carbon-only/light-atom trial, few independent reflections, high symmetry or shell-like density | [sparse light-atom solution](sparse-light-atom-solution.md): case-free symmetry encoding, parameter semantics and hypothesis limits |
| Model interpretation or repair selection | [problem-routing](problem-routing.md) |
| 2D formula/image supplied; C/N/O or H assignment uncertain | [chemical-model-and-density](chemical-model-and-density.md): establish a chemical graph before atom mapping |
| Worked 2D-assisted solution with a clean A/B report but unresolved model features | [LYH case lessons](lyh-case-lessons.md): input conflicts, atom assignment, metadata-only validation and delivery limits |
| Disorder, PART/FVAR or special-site occupancy | [disorder-occupancy](disorder-occupancy.md); [whole-fragment-disorder](whole-fragment-disorder.md) for correlated orientations or element-interchange sites; [orbit-population-case](orbit-population-case.md) for mixed multiplicities |
| Large minor-component U, unstable anisotropy, SIMU/EADP or ISO comparison | [adp-model-selection](adp-model-selection.md) |
| Nonconvergence or unexpectedly motionless refinement | [nonconvergence](nonconvergence.md) |
| Routine weight review, suggested WGHT or abnormal GooF | [weighting review](workflow.md#weighting-review): compare active and suggested weights, with a preserved baseline |
| PLAT080/934/939/919/430/306/234/242/420; fixing coordinates, AFIX 3, H placement, local ADP restraints or limited OMIT | [A/B action playbook](ab-alert-action-playbook.md): case-free diagnostic rules, evidence gates and before/after records |
| PLAT920–928; inconsistent CIF/FCF statistics or residual density; PLAT910–912 missing reflections | [validation evidence](validation-evidence.md#cif-and-structure-factor-consistency-workflow): case-free file-pairing, recalculation and missing-data triage |
| Other validation alerts / reference-guided review | [ab-priority-refinement](ab-priority-refinement.md), then [checkcif-diagnostics](checkcif-diagnostics.md); these references include historical examples |
| PLAT035 / missing absolute-configuration method | [checkcif-diagnostics](checkcif-diagnostics.md#plat035-absolute-configuration-reporting): evidence-supported `ad`, otherwise `unk` when applicable; assess Flack with its uncertainty, not its value alone |
| Before validation, especially CIFs regenerated from INS/HKL | [experimental-metadata-preflight](experimental-metadata-preflight.md): recover same-experiment metadata without importing the reference model |
| Learning from tutorials / solved examples | [critical-reading](critical-reading.md) / [learning-from-solved-models](learning-from-solved-models.md) |
| Preparing or checking a report | [report-model-consistency](report-model-consistency.md) |

## Non-negotiable boundaries

- A/B resolution is the first **diagnostic priority among defensible models**. Accuracy, truthful metadata and preserved evidence are prerequisites. Zero A/B, a low R1 or normal program exit is not scientific acceptance; retain significant C/G findings.
- Never run against the only copy. Record input hashes, absolute executable/version, command, output/exit state and metrics. Keep rejected alternatives.
- Distinguish reference-guided learning, independent solution and 2D-assisted reconstruction before reading inputs. In a no-answer exercise, do not open reference coordinates, ADPs, occupancies, restraints or answer-comparison files until the result is frozen and comparison is authorized. Prior exposure must be disclosed.
- For a strict blind test, use the case-free A/B action playbook and permitted generic documentation; do not load worked-case or historical-example branches. A user-authorized later skill update applies prospectively: preserve the benchmark's recorded version and results, and snapshot the new version for a new evaluation.
- Model changes require evidence and a recorded before/after review. Within an authorized autonomous task, execute justified, reversible candidate trials in separate versions without repeated permission questions. A checkpoint can be the logged decision; adoption still requires scientific assessment. No validated blanket unattended model-repair engine is provided. Respect explicit pauses, blind-test boundaries and permissions genuinely absent from the task.
- Stop the affected operation on missing input, execution failure, divergence, implausible chemistry or exhausted justified trials. Preserve logs; continue unrelated safe analysis.
- A complete delivery requires the **official IUCr online checkCIF with structure factors** and two separate editable crystallographic Word reports, one Chinese and one English, following the supplied template and the same final CIF. The user-facing PDF is `IUCr_checkCIF.pdf`; report PDF/PNG previews stay in internal QA, outside the delivery directory and ZIP. Local PLATON alone does not satisfy this request. Follow upload and delivery safeguards in workflow.

## Implemented tools and limits

Inspection/job setup, read-only SOF/orbit accounting (`audit_occupancy.py`, Gemmi), output gating (`refinement_gate.py`), local alert parsing (`parse_platon_alerts.py`) and historical report-scope auditing (`audit_validation_scope.py`) are implemented. Layout passing does not establish HKLF grouping; alert parsing does not prove completion or obtain an online report. Execution, numerical convergence and scientific acceptance remain separate states.

`prepare_validation_metadata.py` (Gemmi) fills missing experimental scalars in a **new** CIF after separately established specimen/reflection pairing. It records field-level provenance and verifies that all other CIF values remain unchanged. Existing-value conflicts and source-unknown fields are retained, not silently repaired.

`inspect_experiment_metadata.py` (Gemmi) reads one permitted CIF-text source, including a headerless PCF/CIF_OD fragment, and emits only allowlisted experimental scalars with source hash/block/tag and unresolved states. It neither merges values nor establishes specimen identity. It reads the whole source, so it cannot be used to bypass a blind test's forbidden-file boundary; see [metadata preflight](experimental-metadata-preflight.md#read-only-companion-inspection).

Coordinate/symmetry rendering and equivalence audits have been used on individual cases; a general headless SHELX fragment-assembly writer is not yet a validated bundled tool. Use audited case-specific transformations within supported syntax; preserve unsupported files and explain the review need rather than silently opening Olex2 or claiming automatic coverage.

Routine execution and final-model delivery are now bundled: `run_crystal_stage.py`, `crystal_runtime.py`, `iucr_validation.py`, `bilingual_report.py` and `crystal_delivery.py`. The supported HKLF 4/LIST 4 route checks embedded and public model/data consistency, retains every A/B finding, submits to IUCr after established upload authorization, checks exact-file validation reuse, renders both DOCX files and requires recorded visual review before packaging. Unsupported twin/RESI/encoded-ADP cases are routed to specialist handling. These helpers do not choose chemistry, modify models automatically or replace scientific acceptance; see [scope and commands](routine-automation.md).

See [acceptance-tests](acceptance-tests.md) for verified scope and the still-unmet automatic-repair promotion gates.
