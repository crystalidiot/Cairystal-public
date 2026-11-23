# 水氢与反射证据工具 / Donor and reflection evidence tools

这是诊断工具，不改原始数据，不选择最终模型。`ab-auto` 看到 306/417/420/430 时自动运行 donor-audit；918/919/934/939 时运行 reflection-audit。结果放在 `evidence/`，同一工具只运行一次；失败记录原因，其他诊断继续。正常无关步骤不额外运行。

These read-only tools attach evidence to the A/B review packet. They neither modify data nor adopt a model. Relevant alerts trigger one invocation per tool; errors remain visible without suppressing other diagnostics.

## donor-audit

    python -B scripts/toolbox.py run donor-audit -- --directory PAIRED --stem case --output NEW_donors.json

读取同轮 CIF/RES。按度量和周期对称关系枚举距离范围内的所有邻居，含自由精修的 H，不再仅依赖紧邻母原子的 AFIX 记录。检查 PART 相容性；H 有多个几何母原子候选时不强行分配。输出 D–H、H···A、D···A 和角度，记录短接触，以及 RES 保存的邻近 Q 峰。所有潜在受体均未确认化学身份；几何筛选阈值不是 PLATON 全套氢键标准。

Reads a matched CIF/RES and enumerates periodic neighbours using reciprocal-metric bounds. Free H atoms are included. Ambiguous parentage is reported, not silently resolved. Distances, angles, short-contact screens and saved Q peaks are evidence only, not confirmed hydrogen bonds or a fresh Fourier map.

孤立氧可能是水，也可能是其它含氧组分。与碳成短键的氧不会仅因附近有金属或 O···O 接触就当水加氢；有配位金属不自动排除水的可能性。无法区分水、羟基或其它组分时交科学复核。已有简单 C–O–H 可调用 `repair-plan` 的 `oh_rotate` 或 `h_freeze` 做独立对照；AFIX 3 不寻找正确方向。已有普通位置全占有水的两颗 H 可用 water-h-trials 做有界对照；任意水氢/自动生成水氢仍未实现。

An isolated O is only a water hypothesis. A short covalent C–O contact prevents this water screen; metal coordination alone does not. Existing simple C–O–H can use `repair-plan oh_rotate/h_freeze`; AFIX 3 itself does not locate H. Existing general-site full-occupancy water H can use bounded water-h-trials; arbitrary H creation/reorientation remains unsupported.

## reflection-audit

    python -B scripts/toolbox.py run reflection-audit -- --directory PAIRED --stem case --output NEW_reflections.json

先核对配对 INS/RES/HKL/CIF/LST 与 LIST 4 FCF。读取 **CIF 中本轮实际权重公式**，不误用 RES 末尾建议的下一轮 WGHT。支持标准 `w=1/[sigma²(Fo²)+(aP)²+bP]`，负 Fo² 在计算 P 时取零。分别列出 `(Fo²−Fc²)/sigma(Fo²)` 和 `(Fo²−Fc²)/sigmaW`，sigmaW 为 `sqrt(1/w)`。计算 hkl 的 d 和 θ，标出低角负偏差。扩展权重、未明强度比例、孪晶或溶剂修正情形，不猜 sigmaW，填 null 并说明原因。由舍入后的 FCF 重算的临界值须和原生结果对照。

Checks the same-run bundle, then reconstructs standard weights from the actual CIF formula, not a suggested next-cycle WGHT. Reports measured-sigma and sigmaW deviations separately, with resolution and theta. Unsupported formulas, intensity scaling, twins or solvent corrections leave weighted metrics null. Rounded FCF values may differ near a native threshold.

“≤20 个点”只形成一个小规模候选列表；不是过曝证明。原 HKL 不动。FCF 被标记点数占比 **不等于完整度损失**。若做 OMIT 对照，必须另存、记录反射/原因，再由精修与验证重新计算完整度、R/GoF、残差、几何和 A/B；不能用删除后低 R 单独选模型。

A small list (up to 20) is not proof of overexposure. No data are omitted. Flagged-row fraction is not theoretical completeness loss. A separate OMIT comparison must document exclusions and recompute refinement, completeness and validation.

## 来源与改写 / Sources and interpretation

- 用户提供《单晶解析相关知识.pptx》258、261–262 页：HFIX/AFIX、转动氢收敛与羟基距离；305–306 页：反射处理。未照搬按角度截断改善 R 的做法。
- 用户提供《Checkcif所有检测内容汇总及解释案例.pdf》261 页 PLAT306、314 页 PLAT420、409 页 PLAT919、418 页 PLAT934。只提炼通用检查规则，不打包文献个案、图片或参考坐标。
- [IUCr PLAT934](https://journals.iucr.org/services/cif/checking/PLAT934.html)：sigmaW 与异常反射调查。
- [SHELXL WGHT/AFIX 官方说明](https://shelx.uni-goettingen.de/shelxl_html.php)：标准加权公式、建议下一轮权重与本轮权重的区别、骑乘模型。

原资料哈希与本次阅读页码保留在本次维护记录；执行规则与课件口头简写有差异时，以明确参数定义和本次证据为准。Teaching material has been paraphrased into bounded checks, not treated as an automatic scientific answer.
