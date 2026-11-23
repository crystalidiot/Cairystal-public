# Reviewed solvent SQUEEZE comparison

Use this route when the requested result is a reliable host structure and current diffraction evidence supports severely disordered solvent in a separate accessible region. This is an optional method, not a generic way to remove bad atoms or alerts. Reuse the saved one-time intake choice and existing authorization; do not ask again for each command. If the choice is undecided, continue unaffected work and request a decision only when the branch is actually needed.

## What must be established first

The host must be complete, including appropriate H, numerically stable and chemically reviewed. Resolve its disorder; inspect residual density, low-order completeness and resolution. The automatic branch does not mask required counterions, chemically relevant target fragments, significant anomalous scatterers or solvent disorder coupled to the host. Charge balance and the requested scope must be explicit. Host/solvent attribution, selection of excluded solvent sites and chemical accounting remain evidence-based scientific decisions. The review flags below record a decision; they do not prove it and must never all be set true merely to run a command.

Retain the unmodified explicit-solvent trial and create a separate converged host-only checkpoint by removing only reviewed solvent sites, associated H/constraints/restraints and updating accounting. The helper never deletes atoms automatically. An electron count alone does not identify solvent or its stoichiometry.


## 一次性客户选择与脚本接续

当本次证据已经支持主体模型，且剩余困难确实位于独立溶剂区域时，不必无限尝试溶剂的显式无序模型。完成适用性审阅后主动提供一次 SQUEEZE 选择。客户主要关心主体分子时尤其适合讨论；若目标是完整溶剂组成/化学计量，需先明确能否满足该目标。仅有低 R 或 AB 变少不能证明主体可靠。

在上方 PLAN.json 另加 `host_summary`（当前主体完成情况）和 `solvent_challenge`（哪些溶剂区域难处理及证据）。`review` 和 `evidence` 仍是实际审阅结论；不要为通过程序把未知项全部设 true。

```text
python scripts/squeeze_request.py prepare --plan PLAN.json --intake CURRENT_INTAKE/intake_state.json --output NEW_REQUEST
python scripts/squeeze_request.py respond --request NEW_REQUEST --answer CUSTOMER_ANSWER.json
python scripts/squeeze_request.py execute --request NEW_REQUEST --profile MACHINE_PROFILE.json --output NEW_TRIAL
```

`--intake` 可省略；没有保存的授权时生成问题。prepare 自动检查本次输入配对、反射/原生模型适用范围、数值问题和科学审核项，检查不过时不向客户提供一个尚不能实施的选择。检查通过后的状态：

- 本例问卷已允许 `allow_if_justified`：复用授权，生成计划，不再次问客户。
- 已选 `never`：记录拒绝，继续显式模型路线，不反复推荐。
- `undecided`：生成 `request.json`、`result.json` 和本地 `index.html`，供 agent 一次性提问或客户在下拉框选择。表单默认尚未选择，不把默认值当作同意。三个选项是“同意尝试并保留对照”“不同意”“暂不决定”。

也可把当前客户聊天中的明确回答记录为：

```text
python scripts/squeeze_request.py respond --request NEW_REQUEST --decision allow --basis "本例客户在当前消息中明确同意尝试 SQUEEZE"
```

只能在实际收到回答后执行该命令。网页下载的 JSON 只记录本次选择，不上传结构。未知颜色、尺寸等已问过的信息不混入这个新问题。拒绝或暂缓会被保存；重复导入同一选择不重复执行。模型、证据或已保存问卷改变后不能静默沿用针对旧模型的执行计划；要审查变更。已经覆盖本例的条件授权仍应复用，不因每条命令或无关参数调整重复询问。

execute 调用现有 PLATON→SHELXL→本地 AB 对照流程，保留执行记录，不自动重放已经完成、失败或结果不明的尝试。它不自动采纳处理后模型，不把客户授权当作科学正确性证据。最终仍核对主体几何/ADP、残余密度、空洞体积/电子数、化学计量/电荷和权重；带匹配 FAB 的最终文件继续走官网验证及中英文 Word。SQUEEZE 同意与 IUCr 上传同意是两件不同的事，不能相互代替。

科学依据：SQUEEZE 通过溶剂区电子密度估计对计算结构因子的贡献，并与主体模型共同精修，不是把不喜欢的实测反射简单删除。见本文末的 Spek 2015 原始方法说明。脚本负责可重复检查、提问模板、选择保存、原生计算和记录；主体/溶剂归属、异常结果与计量解释不能仅靠模板保证。

## Execution

`squeeze_workflow.py --plan PLAN.json --profile MACHINE_PROFILE.json --output NEW_DIRECTORY` requires a paired INS/RES/HKL/CIF/FCF/LST checkpoint, ACTA/LIST 4, with embedded SHELX inputs. The plan contains:

```json
{
  "source": "ABSOLUTE_CURRENT_JOB_HOST_CHECKPOINT",
  "stem": "model",
  "squeeze_preference": "allow_if_justified",
  "review": {
    "host_complete_including_H": true,
    "host_disorder_resolved": true,
    "separate_diffuse_solvent_region": true,
    "no_target_or_required_counterion_masked": true,
    "no_host_solvent_coupled_disorder": true,
    "charge_balance_reviewed": true,
    "no_significant_anomalous_scatterers_in_mask": true,
    "low_order_data_and_resolution_reviewed": true,
    "basis": "Specific current-run evidence, solvent-region selection and scientific limitations"
  },
  "evidence": [{"path": "CURRENT_RUN_EVIDENCE.json", "sha256": "ACTUAL_SHA256"}],
  "timeout": 600,
  "cycles": 20
}
```

The helper preserves `before`, calls actual `platon -q model.cif`, verifies generated HKL against the original and generated INS against the host, adds native ABIN/FAB to a new `after` refinement, runs SHELXL, freezes matching files and obtains both local PLATON CIF/FCF checks. It records commands, hashes, timing, native logs, void volume/electrons, and before/after metrics/AB findings. Observed intensities are not silently subtracted, rescaled or omitted. Negative void electron counts are retained as quality flags, never converted to positive values. An engineering calculation or reduced R is not acceptance.

Some Windows PLATON versions finish calculation but keep the virtual terminal process running. The helper checks `NORMAL END of PLATON`, all required output files, a parseable FAB and stable files before terminating only its own completed child. The actual exit code and reason remain recorded. Timeout/incomplete output fails and is not treated as completion.

## Supported boundary and downstream delivery

Initial support is non-twinned HKLF 4 without an index transform and unscaled ABIN. TWIN/BASF, HKLF 5, pre-existing masks, SWAT and parameterized ABIN go to specialist review. Twin SQUEEZE needs the documented LIST 8/deconvolution route; do not run this helper or change settings to imitate support.

Every masked checkpoint needs its matching `.fab`. `run_crystal_stage.py` requires explicit `--fab` with ABIN. `paired_bundle` validates actual and embedded FAB contributions/metadata; missing or mismatched FAB fails. Subsequent weight refinements and frozen delivery packages carry FAB. Do not distribute only RES/HKL for an ABIN model. The CIF supplied to IUCr must embed the matching FAB and SQUEEZE details, in addition to structural/reflection data.

`comparison_complete_requires_review` is not final delivery. Review host geometry/ADP changes, uncertainty, residual density, low-order agreement and solvent accounting against the retained explicit model. `routine_finish` requires `review.solvent_accounting_review` and no unaddressed mask quality flags. Record explicit host versus masked solvent, total/host formula basis, charge, molecular weight, density, F(000), void volume and electrons. The bounded automatic F(000) gate appropriately asks for review. The current ordinary orbit/UNIT audit supports host-based accounting; total-composition changes require a specialized audit, not bypassing it.

Keep full AB diagnosis, final weight checks, exact-file authorized IUCr validation, Chinese/English Word and report QA. Existing `crystal_delivery.py` remains available to deliver a transparently labelled partial result with unresolved alerts after scientific review. Include `squeeze_report_notes.json` or automatically appended `routine_finish` bilingual notes; record limitations rather than inventing solvent identity. Do not upload artificial fixtures to IUCr.

## Sources

- [PLATON HOW TO, SQUEEZE/ABIN/FAB and limitations](https://web.mit.edu/platon_v220117/PLATON_HOW_TO.pdf).
- [Spek, Acta Cryst. C 71 (2015), 9–18](https://journals.iucr.org/c/issues/2015/01/00/ln3172/).
- [PLATON command switches](https://www.platonsoft.nl/platon/pl060000.html).

## 后续传递与实验参数保留

ABIN 模型进入 `crystal_session` 后续精修、准备交付以及 `candidate_trials` 时，都核验并传递外部 FAB 与 CIF 内嵌 FAB。不能只复制 RES/HKL，导致后续精修遗漏掩蔽结构因子。原始 HKL 保持不变。

SQUEEZE 后原生 SHELXL 新生成的 CIF，需从已配对的处理前检查点转录实验参数并记录 `metadata_carry_forward.json`。保留参数的来源及冲突，不用模型精修范围冒充晶胞测定范围。空洞电子数为负或计量/电荷不清仍交科学审阅，不能因命令成功自动采纳。
