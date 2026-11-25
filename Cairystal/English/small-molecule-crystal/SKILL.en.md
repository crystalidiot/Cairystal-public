---
name: small-molecule-crystal
description: Cairystal small-molecule crystallography toolbox. Run local SHELX/PLATON for solution, refinement, A/B diagnosis, official IUCr checkCIF and bilingual Word reports. Script routine operations; refer scientific ambiguity to an agent or specialist.
---

<!-- fast_model_20261125_01 -->
## 快速版入口 / Fast edition

本副本用于尽快获得可查看的合理候选模型，默认用工具 `fast`（显式 execution_mode=fast）；先阅读 [快速模式](references/fast-mode.md)。减少试探轮数、先出模型，保留本地AB检查及已授权的官网/中英文Word。快速模式不要求AB清零，报告标为临时模型；明确的化学、占有率或数据配对错误仍需解决。下文通用主线与快速模式冲突时，以快速模式的试修预算和停止规则为准；未变化的科学/权限规则继续适用。

This opt-in copy uses the `fast` tool by default. Read [Fast mode](references/fast-mode.md). Bound trial budgets and publish a provisional local model before authorized official reports. Do not chase zero AB automatically; retain chemistry, occupancy and data-pairing checks. Fast-mode budgets take precedence over the general workflow below. The previous standard release stays unchanged.


# Cairystal small-molecule structure determination

Customers can give the agent a data folder, paste checkCIF alerts, or ask it to finish an existing report. The agent operates the local tools, records evidence and explains the result. [中文](SKILL.zh-CN.md)

**Model priority: chemical reasonableness supported by the current diffraction data first; checkCIF A/B alerts second.** Review atom identities, connectivity/valence, H and charge, composition, occupancy/special positions, geometry and density before comparing alerts among comparably defensible models. Fewer alerts never justify chemically worse modelling; preserve and explain unavoidable alerts on a supported model. Supplied or authorized structure models may guide the work after checking their relationship to this sample and recording inherited information. Explicit blind/no-old-model restrictions continue to govern those runs. See [chemical-first selection and references](references/chemical-first.en.md).

### Decisions the agent handles

When autorun returns `needs_attention`, read `next_step` in `handoff.json`. If `owner=assistant`, perform that step this turn. With no 2D graph, inspect the current first model, residual peaks, geometry and displacement parameters. Try routine hydrogens, weighting, fallback solving and evidence-supported disorder alternatives in separate working copies. For a special-position cation, check whole orientations under symmetry, shared atoms, occupancies and composition before comparing split and unsplit models. Report any unresolved ambiguity alongside the established part of the model.

Use sample records and facts already supplied first. Ask once for consequential facts only the customer can supply, a material change of objective or missing authorization for external submission or SQUEEZE. Continue unaffected work after an unknown answer. Reuse consent within its recorded scope. Respect explicit blind-test, preview-only and pause instructions.

If a P4P lacks BRAVAIS, intake uses the cell and measured HKLF 4 rotation mates for a provisional search seed. If centring or Laue symmetry remains ambiguous, compare candidate seeds in this job and record the evidence.

For delegated or resumed work, carry the requested case label and original HKL. Check autorun status/resume with `--expected-hkl` and use the selected CIF to match the official receipt. See [case-bound recovery](references/case-resume.md). Review flagged disorder bonds before accepting a lower R.

For PLAT919/934, use the [fixed-list working-model rule](references/automatic-ab-mainline.md). The normal finish runs the OMIT comparison, selects the supported working set, and records each exclusion in the CIF and both report languages. An existing chain restraint alone does not block the comparison.

## Main workflow

1. **Identify inputs.** Pin the release, machine profile, permitted files and a fresh output directory. Preserve original HKL and hashes. Limit blind runs to authorized inputs and check whether a starting INS is allowed. Autorun supports HKL with P4P. For HKL with INS alone, use the [input and exception routes](references/mainline-and-exceptions.md). For a new machine see [setup](START.en.md).
2. **Ask once for missing facts.** Read paired experimental records first. Collect missing colour, habit and three dimensions (e.g. green, block, 0.050 × 0.051 × 0.052 mm), plus possible elements including solvents and counterions. Accept an optional 2D drawing. Retain provenance and unknowns. Resolve only conflicting fields. Element names alone give no stoichiometry. [Intake and permission](references/one-time-intake.md)
3. **Solve and refine.** Start with SHELXT. Review symmetry, C/N/O assignments, geometry and occupancy. Consider an evidence-supported SHELXD fallback. Compare the SHELXL candidates, hydrogen treatment and weights. Preserve the model for scientific review when chemistry, disorder or a special position remains ambiguous. [Tool and diagnostic index](references/toolbox.en.md)
4. **Address alerts.** Start with A and B. Use current density, connectivity, displacement and reflection evidence for each trial. Keep the original model and comparison. SQUEEZE requires a reliable host and case-specific permission. Preserve original HKL and the justification and comparison for reflection omissions. [Problem routes](references/problem-strategy-tools.md)
5. **Deliver or resume.** Validate the final CIF with structure factors, normally LIST 4. Use case-specific authorization for IUCr submission. From an existing receipt recover the reports, build both Word files and check layout and hashes. Return links to the CIF, official PDF and both Word reports under the data folder's Cairystal directory, with any unresolved issues. Report missing stages explicitly. Low R or zero A/B alone cannot establish correctness. [Delivery and recovery](references/delivery-completion.md)

For a declared primitive orthorhombic indexing, autorun tests observed intensity pairs for all three twofold rotations. It starts SHELXT only when all support an mmm search. For merged, weak or contradictory data inspect laue_review in pipeline.json and use an independently reviewed INS when available. The Laue search hypothesis is distinct from a space-group determination. At the first chemical decision, first_models in handoff.json links candidate RES files, indicators and paired atom reviews.

With a complete chemical graph, document the protonation evidence for N–H or O–H using the current sample records or density. Routine C–H uses graph valence and checks the generated H sites against UNIT. A checked H-free graph proceeds with the selected heavy-atom refinement. See [graph matching](references/graph-matching.md).

Compare candidates once per round; review complete-fragment geometry before fixing the model, validating and building reports. Reuse existing tools and fingerprint-matched artifacts; rerun only affected outputs while retaining scientific and delivery checks. See [avoiding repeated work](references/usage-and-cost.en.md).

Initial decision queues provide evidence-linked tools and bounded C/N/O contrasts. Autorun records reason-coded handoffs; staged disorder records promotions and deferrals. See [decision flow](references/decision-flow.en.md).

## Agent entry

In the skill directory run `python -B cairystal.py guide` for common requests, `describe TOOL` for tool details and `run TOOL -- --help` for native help. The workbench is optional. Resume an existing job with its pinned version.

For paired PCF or cif_od records, inspect fields with `metadata`, collect paired sources with `metadata-ledger` and pass `--metadata-ledger` to `intake-form`. Use `initial-review` after phasing, `ab-auto` for supported local trials, and `check-delivery` for the final four files. Load references for the current step.

- New case: `run autorun -- run --config JOB.json --output NEW_RUN` using a configuration prepared from the permitted inputs.
- Pasted report: `run route-problem -- --alert-text "PLAT306_ALERT_2_B ..." --json`. Retain unmapped IDs.
- Maintenance: use the [plain-language acceptance template](references/owner-guide.en.md) with an example and a counterexample. [Detailed operating protocol](references/operating-protocol.en.md)

For an explicitly paired instrument record, run `intake-form --hkl A.hkl --paired-record A.pcf --pairing-basis "acquisition record" --output NEW_FORM`. Check the acquisition evidence when only filenames match. Retain the permitted input scope in blind runs.

For an existing model run `recover-checkcif --directory OFFICIAL --cif FINAL_CIF --check-only` first. Reuse completed results for the exact CIF. For an interrupted download, remove `--check-only` to recover the reports.

Checkpoint continuation includes automatic report QA and publishing when supported. Use [the mainline/tool continuation contract](references/flow-handoffs.md) to resume the selected model without repeating phasing or uploads.

On concrete twin evidence, use [twin-quick](references/quick-twin.md) before OMIT: bounded PLATON search, then native control vs TWIN/BASF refinement from a detected compatible law. No extra search without evidence; review before adopting the model.


## 连续化学处理 / Continuous chemistry workflow

使用 [chemistry-screen / hydrogen-continue](references/chemistry-handoff.md) 集中比较本轮元素候选，并在有依据的化学图确认后自动重编号、加氢、复核和交付。只把未解决的科学歧义交给 AI；当前推断图不能写成客户已提供的二维式。

Use the linked tools for current-run element contrasts and reviewed-graph H/refinement/report continuation. Inferred chemistry is not an independently supplied 2D prior.
