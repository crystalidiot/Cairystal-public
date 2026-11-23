# 资料转成的三个工具 / Three material-derived tools

本页描述可执行范围。两种试验都保留同起点对照和原 HKL，不自动选择最终结构。主线精修、本地 A/B、确切最终 CIF 的官网 PDF 与双语 Word 交付要求不变。新工具不等于每种晶体均可自动解决。

Both trial tools preserve an unchanged control and original measured HKL, and never adopt a final model. Refinement, local A/B checks, official validation of the exact final CIF and bilingual Word delivery remain mandatory for a completed structure.

## 1. water-h-trials：已有水氢方向与 AFIX 3

依据课件 229、260–265 页与 checkCIF 汇编 261、314–315 页。先确认 O 是水、已有两颗 H、候选受体的化学角色，再给出本次模型中的受体和对称像。仅支持全占有、PART 0、普通位置、同一 O 后紧接的两个自由或 AFIX 3 H。不会凭“孤立氧”创造两个 H。

旋转整个 H–O–H 构型，保持 O–H 长度和夹角，坐标以笛卡尔度量计算。比较：不改模型继续精修、固定现有向量、两种受体对应方向。AFIX 3 保持所选向量随母原子移动，保留 H 数、占有率及 U；移除并记录本水内部已冗余的 DFIX/DANG。跨分子的 H 限制、特殊位置、部分占有、共线或不合适的受体方向会拒绝执行，交其它路线处理。

Uses PPT 229/260–265 and checkCIF compilation 261/314–315. Requires an identified water and two existing H, plus justified acceptor images. Applies a proper rigid Cartesian rotation, preserving O–H lengths and H–O–H angle. Compares unchanged refinement, AFIX 3 at current vectors and two directional hypotheses. Only redundant internal DFIX/DANG are removed and recorded. Partial/special-site water or external constraints are not silently rewritten.

```json
{
  "recipe": "water_orient",
  "parameters": {
    "parent": "O1", "hydrogens": ["H1", "H2"],
    "acceptors": [
      {"atom": "O2", "symmetry": "x,y,z", "translation": [0,0,0]},
      {"atom": "O3", "symmetry": "x,y,z", "translation": [0,0,0]}
    ],
    "basis": "Replace with current water identity and acceptor-chemistry evidence"
  },
  "reason": "Compare existing water-H directions",
  "evidence": ["Replace with current model, density and contact evidence"],
  "cycles": 20
}
```

标签与坐标设置仅为格式示例，不能原样套用。These labels/settings illustrate schema only.

    python -B scripts/toolbox.py run water-h-trials -- prepare --baseline PAIRED --request WATER.json --profile MACHINE.json --output NEW_TRIALS
    python -B scripts/toolbox.py run water-h-trials -- run --plan NEW_TRIALS/plan.json

方向更像氢键但残差/几何/警告变差的方案不采纳。结果中的 `hydrogen_geometry`、精修指标、差值密度和警告要一起比较。受体是否质子化或可接受氢键仍需化学判断。

A plausible contact direction is insufficient if residual density, geometry or validation worsens. Review `hydrogen_geometry`, refinement statistics, density and alerts together; acceptor chemistry remains a scientific decision.

## 2. reflection-omit：固定反射列表的敏感性对照

依据课件 305–306 页、汇编 409/418 页和 SHELXL OMIT 定义。由 `reflection-audit` 确认实际权重下的异常，不把普通 sigma 当 sigmaW。仅接受 1–20 个当前有效、未剔除的 >10 sigmaW 点，普通 HKLF 4；孪晶、掩膜、消光修正等复杂因素进入专门路线。

在新的 INS 添加精确的 `OMIT h k l`，原始 HKL 字节不变。不截掉整个高角区，不根据精修后新残差循环挑点。比较前后精修使用的反射数、采集完整度、R/GoF、残差和 A/B。**采集完整度可以不变；它不等于精修纳入完整度。** 不同拟合数据集合不能单凭 R 降低判胜。

Uses PPT 305–306, compilation 409/418 and the SHELXL OMIT definition. Only an explicit fixed set of 1–20 active >10 sigmaW outliers is supported. Writes OMIT cards into a new INS, never changes raw HKL. Does not truncate resolution or repeatedly select new outliers. Reports native used-reflection counts, measured completeness and model metrics; measured completeness can remain unchanged after exclusion from refinement. R values with different fitted sets are not directly ranked.

```json
{
  "recipe": "reflection_omit",
  "parameters": {"hkls": [[1,2,3]], "basis": "Replace with current weighted outlier and investigation evidence"},
  "reason": "Fixed-list sensitivity comparison",
  "evidence": ["Replace with current evidence; not an assumed overexposure diagnosis"],
  "cycles": 20
}
```

    python -B scripts/toolbox.py run reflection-omit -- prepare --baseline PAIRED --request OMIT.json --profile MACHINE.json --output NEW_TRIALS
    python -B scripts/toolbox.py run reflection-omit -- run --plan NEW_TRIALS/plan.json

主线 A/B 919/934 符合条件时自动准备/运行该对照；`automatic_reflection_trials: false` 可关闭试验。旧 `allow_automatic_reflection_omission: false` 仍表示不得自动把剔除方案采纳进最终结构。不超过 20 个并不能证明采集错误；失败与不支持的原因会保留。

Eligible A/B 919/934 routes can prepare/run this comparison; `automatic_reflection_trials: false` disables it. Automatic adoption of omitted data into the final model remains prohibited. A small outlier count does not establish an experimental error.

## 3. adp-directions：长椭球是否指向差值峰

依据课件 246–248 页、汇编 203/209/212/218 页。将 CIF Uij 按晶胞度量转为笛卡尔张量，计算主轴，再量化保存 Q 峰与长轴的夹角、平行和垂直距离。适用于 211–216 等热参数问题的前置排查：决定是否应先检查无序或原子指认，而不是直接加 ISOR。

NPD 或最大两特征值近简并时不报告可靠的唯一长轴。当前筛选使用峰高 0.35 e/Å³、夹角 30°、主轴特征值分离 1.15；这些只是找线索的阈值。Q 列表不代表完整差值图；长轴对准峰不证明该峰是另一位置的原子，也不提供占有率。

Uses PPT 246–248 and compilation 203/209/212/218. Compares Cartesian ADP axes with saved Q peaks, including periodic images. NPD/degenerate tensors do not yield a reliable unique axis. Screening thresholds are clues, not correctness criteria; saved Q lists are incomplete map samples and do not assign atoms/occupancies. Relevant A/B 211–216 routes attach this evidence automatically.

    python -B scripts/toolbox.py run adp-directions -- --directory PAIRED --stem case --atoms C36 --output NEW_AXES.json

## 资料核对与后续交付

源文件名、SHA256 与阅读页码见 `assets/material-tool-sources.json`。只打包改写后的通用规则，没有原课件图片、论文案例或参考坐标。SIMU 是相似限制、EADP 才是相等约束；ISOR 是趋于各向同性的限制，不等于直接改成各向同性精修。

Source hashes/pages are recorded in the asset. No original slide illustrations, case answers or reference coordinates are bundled. SIMU restrains similarity; EADP constrains equality. ISOR is a restraint towards isotropy, not conversion to isotropic refinement.

官方定义：[SHELXL AFIX / OMIT / LIST / WGHT](https://shelx.uni-goettingen.de/shelxl_html.php)、[IUCr PLAT214](https://journals.iucr.org/services/cif/checking/PLAT214.html)、[PLAT934](https://journals.iucr.org/services/cif/checking/PLAT934.html)。选定候选后仍返回完整精修、本地验证和已授权官网验证，最终四份文件进入原始数据目录/Cairystal。工具对照不自动成为客户最终交付。
