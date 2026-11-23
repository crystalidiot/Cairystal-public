# Cairystal toolbox

The standard-library router selects existing reusable tools; it does not reimplement crystallographic algorithms. Humans or agents with local file and terminal access can call it. Inputs are paths and explicit configurations, not cached atom assignments or coordinates.

Run from the skill directory or use the absolute path to toolbox.py. Quote paths with spaces. Replace uppercase placeholders.

    python -B scripts/toolbox.py --language en list
    python -B scripts/toolbox.py --language en describe complete
    python -B scripts/toolbox.py run complete -- --help
    python -B scripts/toolbox.py plan complete -- --input CANDIDATE --profile PROFILE.json --review REVIEW.json --output NEW_OUTPUT --data-dir ORIGINAL_DATA

list --json and describe TOOL --json expose contracts from assets/toolbox.json. **plan only previews argv; it does not validate scientific inputs, grant authorization or execute.** run TOOL -- arguments forwards arguments without a shell, implicit profile injection, permission injection, retry or success reinterpretation. It preserves stdout, stderr and the underlying exit code. Router errors return 2. Business output schemas remain tool-specific.

## Routine route

    python -B scripts/toolbox.py run doctor -- --profile PROFILE.json
    python -B scripts/toolbox.py run intake-form -- --language en --output NEW_FORM
    python -B scripts/toolbox.py run intake-accept -- --input ANSWERS.json --profile PROFILE.json --output NEW_INTAKE
    python -B scripts/toolbox.py run autorun -- run --config NEW_INTAKE/autorun_config.json --output NEW_RUN

The existing dispatcher continues routine steps. On needs_review, blocked or nonzero exit, read the compact handoff/decision packet and evidence; do not restart the entire workflow to bypass a gate. Automatic initialization currently supports HKL/P4P; other inputs use inspect/setup/stage and the [workflow](workflow.md). Native tool arguments and schemas remain unchanged.

| Task | Tools |
|---|---|
| Environment/version | probe, doctor, profile, verify |
| Inputs/metadata | intake-form, intake-accept, inspect, metadata, project-metadata |
| Solve/refine/schedule | setup, stage, pipeline, autorun |
| Graph/hydrogens | match, hydrogen-plan |
| Diagnostics/disorder/solvent | diagnose, occupancy, disorder, trials, squeeze |
| Numbering/completion | labels, finish, complete |
| Validation | platon, checkcif, recover-checkcif, compare-ab |
| Reports/delivery | deliver, check-delivery, viewer |
| Support/regression | support, test |

Read each tool's describe and native --help. metadata reads one explicitly permitted source. Restrict project-metadata with explicit allowed --source arguments in blind tests. The toolbox is not a filesystem sandbox; input scope remains the caller's responsibility.

Image recognition is not a verified chemical graph. Hydrogen plans need protonation and symmetry review plus refinement/validation. Disorder tools retain a baseline and do not automatically adopt candidates. SQUEEZE preserves model-specific consent and scientific checks.

deliver run checks a paired native bundle and produces official validation plus bilingual Word; it is not an unchecked CIF-to-Word converter. Local PLATON is not an official PDF. Upload flags must reflect existing authorization. Independent tool execution is not a complete delivery. Support files stay local.

The SOP defines sequence, evidence and deliverables; tools calculate and record; AI or a specialist handles scientific ambiguity. Read the [detailed protocol](operating-protocol.en.md) only as relevant. Existing direct CLIs remain available; running jobs stay pinned. Offline synthetic tests do not establish crystal correctness or cross-agent compatibility.

For a sealed local finish, use **resume-delivery** instead of repeating complete, followed by **report-qa** and deliver finalize. See [checkpoint and reliability details](workflow-reliability.md).

New public entries: `initial-review`, `route-problem`, `session`, and `restraint-tension`. Use describe for inputs. See [problem routing](problem-tool-library.en.md).

`repair-plan` exposes six bounded recipes with an unchanged control, native execution and comparison. See [evidence-repair-tools.en.md](evidence-repair-tools.en.md).

Special-site solvent disorder: `fragment-orbits` audits complete molecules, shared atoms and riding-H consistency. [Details](complete-configurations.en.md).

## Further reading by situation

- [automatic A/B](automatic-ab-mainline.md)
- [material-derived tools](material-derived-tools.md)
- [method sources](learning-method-map.md)
- [disorder/PART](disorder-occupancy.md)
- [SQUEEZE](squeeze-workflow.md)
- [shells, correlations, population starts, restraint strengths and solver fallback](five-tool-enhancements.md)
- [comparison and continuation](evidence-repair-tools.md)
- [native resource policy](native-performance.md)
- [staged screening](density-disorder-screening.en.md)
- [symmetry configurations](symmetry-configurations.en.md)
- [Unified entry, release identity and new automatic branches](unified-mainline.md)
- [speed diagnostics](speed-diagnostics.md)
