---
name: small-molecule-crystal
description: Cairystal small-molecule crystallography toolbox using local SHELX/PLATON for solution, refinement, A/B diagnosis, official IUCr checkCIF and bilingual Word reports; scripts handle routine work and scientific ambiguities go to an agent or specialist.
---

# Cairystal

Use an isolated job directory, preserve inputs and comparisons, and deliver traceable models and reports. [中文](SKILL.zh-CN.md)

## One entry point

Run `python -B cairystal.py version --json` from this skill directory. Record the actual version and path. `release_info.json` is authoritative; resume existing jobs with their pinned release. See [installation](START.en.md) on a new machine.

```text
python -B cairystal.py workflow
python -B cairystal.py list
python -B cairystal.py describe TOOL --json
python -B cairystal.py run TOOL -- --help
```

Use `autorun` by default. Use `fast` when a quick working model is requested; [fast mode](references/fast-mode.md) bounds trial budgets while retaining chemistry, occupancy, A/B, official validation and report checks.

## Mainline

1. **Input and missing facts.** Pin the profile, permitted inputs, new job directory and original HKL hashes. Read paired PCF/cif_od records first. Ask remaining questions together: colour/habit/three dimensions (e.g. green, block, 0.050 × 0.051 × 0.052 mm), and all possible elements including solvents/counterions or an optional 2D drawing. Leave unknown facts unknown; examples are not measurements and element lists are not stoichiometry. [Intake](references/one-time-intake.md)
2. **Solution and identity.** SHELXT → initial screening → element, connectivity and occupancy review. Compare evidence-based SHELXD hypotheses when appropriate. `chemistry-screen` supports bounded current-run elemental contrasts; low R does not automatically establish identity. [Input routing](references/mainline-and-exceptions.md)
3. **Hydrogens and refinement.** Reviewed chemical graph → `hydrogen-continue` → SHELXL/weights → native H count, UNIT, geometry and displacement checks. Identify inferred graphs honestly, separately from independently supplied 2D structures. [Chemistry continuation](references/chemistry-handoff.md)
4. **Local validation and trials.** `route-problem` finds strategies; `ab-auto` executes supported comparisons. Model changes return to refinement/validation. Resolve scientific ambiguities using current density and candidates instead of merely stopping with “needs AI”. [Shared route map](references/flow-handoffs.md)
5. **Official validation and delivery.** Freeze the selected CIF/structure factors and perform authorized IUCr validation. Resume a matching receipt rather than re-solving. Generate both Word reports, run QA and verify four deliverables in the customer's data directory under `Cairystal`. Give that location and remaining issues in the final reply. [Completion/recovery](references/delivery-completion.md)

## Shared decision rules

- Chemistry and current diffraction evidence precede A/B counts. Zero A/B, low R or convergence alone do not establish correctness. Use reference models only within the authorized scope; preserve blind-test restrictions. [Chemical evidence](references/chemical-first.md)
- Continue routine fallback solution, element/H/weight and supported disorder trials in new directories. Reuse supplied facts and authorization. Ask only for essential customer-only facts, changed objectives or missing upload/SQUEEZE authorization; an unknown answer does not block unrelated work.
- Investigate twin indications with bounded `twin-quick` trials before outlier exclusion. Handle 919/934 through the documented fixed-list OMIT acceptance rules; retain originals and records. SQUEEZE retains case-specific consent and contribution accounting. [Automatic A/B branch](references/automatic-ab-mainline.md)
- Execute assistant-owned next steps in `handoff.json`. Preserve partial models when scientific ambiguity remains. Resume network/report failures from their delivery checkpoint without re-solving. Missing final CIF, IUCr PDF or either Word report must be reported as incomplete.

## Tools on demand

`describe` exposes inputs, outputs, dependencies, effects, boundaries and mainline stages. Native exit codes and logs remain intact. Consult the [tool index](references/toolbox.en.md) only when needed.

Resume by expected HKL and selected CIF fingerprint: [case resume](references/case-resume.md). A displayed route is not evidence that an automatic repair has been implemented or executed.
