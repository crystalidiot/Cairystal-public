# 常规孪晶分流 / Routine twin routing

用户希望普通结构不要因为猜测存在孪晶而不断追加检查。常规精修、配套结构因子和 PLATON 检查完成后，没有孪晶提示、没有已启用的孪晶模型、也没有其它具体异常证据，就按普通模型继续；不另开 TwinRotMat、穷举孪晶律或要求客户证明“没有孪晶”。将结论写为“本次常规检查未提示需额外孪晶处理”，不写“已证明无孪晶”。缺失或失败的 PLATON 检查不能当作阴性结果。

For routine tasks, do not launch additional twin-law searches without a concrete signal. Reuse completed validation. An active twin model, relevant diagnostic, split reflections or otherwise unexplained model/data inconsistency may justify a focused review. Stop after resolving the actual issue; do not turn a possibility into an endless checklist. Ordinary convergence, chemical consistency, AB review, official checkCIF and bilingual Word delivery remain required.

## What the delivery checker now does

`crystal_runtime.paired_bundle` calls `twin_delivery.classify`. It distinguishes:

| Actual model | Action |
|---|---|
| HKLF 4 without TWIN/BASF | Ordinary pairing and delivery; no new twin search. |
| HKLF 4, BASF but no TWIN | Treat BASF as batch scales, not twin fractions. Positive scales can exceed 1; batch 0/1 use the overall scale. Check recorded batches against the available scales. |
| HKLF 4, one supported two-domain TWIN and one BASF | Continue automatic pairing using native LIST 4 output; preserve TWIN/BASF. Supports the default inversion matrix or an integer non-identity matrix whose square is identity, with two components. This is a file-format support boundary, not proof the selected twin law is physically correct. |
| HKLF 5, other domain counts/matrices, combined twin and multiple batch scaling | Keep the explicit unsupported-format explanation. Retain the model/data for a dedicated route; do not delete TWIN/BASF or relabel reflections to bypass the limitation. |

The old unconditional rejection on either TWIN or BASF is removed for supported cases. Automatic pairing still compares embedded native instructions and HKL, CIF/RES coordinates/ADPs/occupancy, symmetry, LIST 4 format, reflection counts, embedded Fo/Fc, final native statistics and unchanged hashes. Passing pairing does not override convergence, chemical, occupancy or validation findings. A supported existing twin need not be rediscovered by PLATON to remain in the model.

`routine_finish` records `twin_handling` and `twin_review_policy`. Relevant PLATON findings are review evidence, not proof of a new twin law. PLAT931 can describe already-modelled twinning; check its context rather than adding another TWIN instruction. An out-of-range refined inversion parameter retains its review context and uncertainty; never silently turn it into a batch scale or clip it to zero.

## Why “PLATON did not flag it” is not absolute exclusion

The IUCr describes TwinRotMat as using unusually strong observed-versus-calculated reflections; removing such reflections can impair detection. Thus, absence of a flag guides routine workload, but cannot erase direct evidence or an already applied model. See [Spek, checkCIF validation ALERTS (2020), section 3.3](https://journals.iucr.org/e/issues/2020/01/00/su5533/index.html).

SHELXL documents the different BASF meanings for batch scaling and twin fractions. Validation uses the native LIST 4 Fo/Fc listing; LIST 8 detwinned data are not a substitute for checking missed twinning. See [SHELXL BASF/HKLF/LIST instructions](https://shelx.uni-goettingen.de/shelxl_html.php) and [IUCr PLAT766](https://journals.iucr.org/services/cif/checking/PLAT766.html). Checked 2026-11-03.

## Test boundary

Offline regressions cover routing and format rejection. Native SHELXL 2018/3 experiments use fictional HKL generated from a synthetic model, not customer data. Ordinary, batch-scale, inversion and non-inversion two-domain outputs all pass file pairing; altered BASF/HKL, missing FCF, LIST 8 and HKLF 5 controls remain rejected. This establishes the tested file-handling path, not successful solution of real twinned crystals or a new IUCr validation result. SQUEEZE/twin combinations and the narrow automatic chemical-review scope are not expanded by this change.
