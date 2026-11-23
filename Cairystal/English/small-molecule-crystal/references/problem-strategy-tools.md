# 问题—策略—工具 / Problems, strategies and tools

本页来自对《Checkcif所有检测内容汇总及解释案例.pdf》（DJ_Tokyo，2021-05-06）通用解释和处理策略的重新整理。来源 SHA256、页码与工具映射见 `assets/problem-strategies.json`。没有把文献案例的坐标、图片或作者答复当成当前晶体答案。适用条件以当前数据和官方定义为准。

The 25 strategy families are a many-to-many problem index. They reuse existing tools and add three executable audits plus three explicit comparison recipes. A route match is not a diagnosis; an implemented diagnostic is not an implemented automatic repair. Local PDF text/images are not included in the skill.

## 查路线 / Find a route

```text
python -B scripts/toolbox.py run route-problem -- --alerts PLAT088 711_ALERT_1_B SHFSU01 --json
python -B scripts/toolbox.py run repair-plan -- list
```

支持 PLAT 编号、完整警告及 SHFSU01、REFNR01、WEIGH01 等字母开头的检查项。一个问题可能有多个原因；一个策略可处理多种问题。原有自动 A/B 证据收集会附上新诊断，每轮每工具一次。未知原因、失败及缺失指标保留，不当成零警告。

## 新增可执行诊断 / New executable audits

| Tool | 输入与输出 / Input and output | 边界 / Boundary |
|---|---|---|
| `parameter-budget` | 当前 CIF/RES → 实际数据/参数数、H 的自由或 AFIX 状态、可检查的自由度；对应 088/089/090/904/REFNR01 | 不把限制数当新反射；非心结构的 Laue 比与原生精修比不混淆；不凭空计参数 |
| `geometry-audit` | 当前 CIF → 标签一致性及按明确对称码重算的键长、角度、扭角和氢键；对应多种 711–758 问题 | `?` 不当 `.`；不自动取最近像掩盖错误对称码；无协方差矩阵不改 s.u. |
| `refinement-controls` | 当前 CIF/RES → EXTI 显著性、DAMP/其他控制的证据及可试方案 | 只有来源明确的尺寸/误差修正可走 metadata；不会任意改 SIZE/ZERR |

```text
python -B scripts/toolbox.py run parameter-budget -- --directory CURRENT --stem case --output NEW_budget.json
python -B scripts/toolbox.py run geometry-audit -- --directory CURRENT --stem case --output NEW_geometry.json
python -B scripts/toolbox.py run refinement-controls -- --directory CURRENT --stem case --output NEW_controls.json
```

## 三个对照配方 / Three comparison recipes

共用 `repair-plan prepare/run`，复用同起点未修改对照、原 HKL、SHELXL、PLATON 与比较日志。不能自动采纳最终模型。All recipes are isolated, evidence-backed trials using the existing native runner, with unchanged raw HKL and an unchanged contemporary control.

- `remove_extinction`：当前 CIF 与 RES 的 EXTI 一致且有有效 s.u.，显著性低于 3.33 时比较移除；未知误差不能当不显著。/ Compare removal of a demonstrably insignificant EXTI.
- `release_damping`：仅移除一个 DAMP，其余模型不变；比较真正收敛与最终几何/协方差表现。/ Compare undamped final refinement and recheck convergence.
- `resolution_window`：明确指定高角界限 `d_min_A`，新增 SHEL，对比完整起点数据。记录超出窗口的实测记录、信噪比、最终反射数、完整度、R/GoF、残差与 A/B；未知项为 null。实测记录比例不是独立反射完整度损失。不同拟合集不能按低 R/零 AB 排序。/ Explicit resolution sensitivity comparison; report information loss, never claim improved correctness from lower R on fewer data.

请求示例（理由和证据必须换成当前实验的实际依据）：

```json
{
  "recipe": "resolution_window",
  "parameters": {"d_min_A": 0.84, "basis": "Current high-angle shell evidence and explicit sensitivity question"},
  "reason": "Compare full data and this resolution window",
  "evidence": ["Path or identifier of the current shell/processing analysis"],
  "cycles": 20
}
```

0.84 仅为参数格式示例，不是默认截断值。`remove_extinction` 和 `release_damping` 的 parameters 只需要 `basis`。已有 SHEL、复杂孪晶/掩膜、参数子块、特殊控制等需专门路线；不叠加截断或隐藏原数据。

```text
python -B scripts/toolbox.py run repair-plan -- prepare --baseline PAIRED --stem case --request REQUEST.json --profile MACHINE.json --output NEW_TRIAL
python -B scripts/toolbox.py run repair-plan -- run --plan NEW_TRIAL/plan.json
```

## 本次纠正的规则 / Corrected interpretations

1. PLAT088 是有心结构的数据/参数比问题；PLAT080 和 SHFSU01 才属于位移/误差收敛问题。089/090 的 Zmax 是最大原子序数，不是晶胞分子数。
2. 101–103 关注特殊位置坐标精度，不能泛化为“改占有率小数”。
3. 711–718 主要检查几何表中的标签能否在坐标表中找到；Cu01/H0A 不能仅凭格式认定错误。
4. ISOR 为趋于各向同性的限制，不是转 ISO；SIMU 为相似限制，不是 EADP 相等约束；DELU/SIMU 的两个 sigma 无必须成倍数的通则。
5. 甲基与羟基的 AFIX 不可混用；不把资料中“甲基一律 147”作为自动规则。
6. 把实际未知改成 `?`、按明确单位转换、纠正有原始证据的误录可以做；随意缩小误差/尺寸、不上传 FCF、删不利几何行不能冒充真实修复。高角截断可以作为上述独立敏感性试验，必须披露。

Current official definitions checked: [PLAT088](https://journals.iucr.org/services/cif/checking/PLAT088.html), [PLAT089](https://journals.iucr.org/services/cif/checking/PLAT089.html), [PLAT090](https://journals.iucr.org/services/cif/checking/PLAT090.html), [PLAT031](https://journals.iucr.org/services/cif/checking/PLAT031.html), [PLAT711](https://journals.iucr.org/services/cif/checking/PLAT711.html), [PLAT380](https://journals.iucr.org/services/cif/checking/PLAT380.html), [SHELXL instructions](https://shelx.uni-goettingen.de/shelxl_html.php). Source PDF pages for further review: 100,145–149,157,202–234,270,298,343–358,422,519. Official pages unavailable during retrieval are not labelled verified online.

选择修改后仍回到主线：精修/权重 → 本地 A/B → 授权上传的确切最终 CIF 官网 PDF → 中英文 Word → 四份最终文件的交付检查。此次工具试验本身不代替这个最终交付过程。

## “误差”要分清两类 / Distinguish restraint sigmas from measured s.u.

- DFIX、SIMU、RIGU 等限制的 sigma 决定限制强弱；可按化学依据和数据支持调整，在单独候选中记录数值，比较限制张力、几何、ADP、残差和 A/B。现有 `geometry_local` / `adp_local` 配方支持显式 sigma，不做逐轮收紧直至零警告的搜索。
- 晶胞、坐标、键长等报告中的标准不确定度须来自实际处理或精修；有录入/单位错误可据原记录纠正，重算后可变小，但不能为了让检查通过手改成更小的数字。
- 晶体尺寸可据实测重新核对和修正；未知时保留未知。假设尺寸影响的计算不能作为实际尺寸填入最终 CIF。

Restraint sigmas are modelling choices that may be compared with chemical evidence. Experimental/refinement standard uncertainties and measured dimensions require traceable observations or recalculation. A resolution cutoff is an explicit, separately reported sensitivity trial, with the full-data control preserved.
