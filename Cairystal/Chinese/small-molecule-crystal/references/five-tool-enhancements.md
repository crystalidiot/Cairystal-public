# 五项增强 / Five workflow enhancements

These tools operate on explicitly selected current inputs. No historical answer lookup, AI API, reflection deletion or upload is performed. Trial models return to the normal refinement, A/B, official IUCr PDF and bilingual Word delivery workflow after review.

## 1. 分辨率分组 / Resolution shells

`toolbox.py run resolution-shells -- --directory CURRENT --stem case --bins 6 --output NEW.json`

按 1/d² 等宽分组，从低角到高角报告实际 FCF 的信噪比、负强度比例、R1、加权偏差和已排除记录。空组为 null。完整度和 Rint 不从已合并 FCF 虚构；需要另外的实测反射/积分记录。相关 A/B 自动证据收集会调用。不会自动建议或应用截断。

Equal-width 1/d² bins summarize available paired LIST 4 reflections. Excluded rows are counted separately. Missing completeness/Rint remain null. Weak high-angle signals do not establish a cutoff or exposure error.

## 2. 参数相关性 / Parameter correlations

`toolbox.py run parameter-correlations -- --directory CURRENT --stem case --output NEW.json`

读取 LST 最后一段相关性输出的**全部列**，保留正负号，列出参数和可识别的原子/PART/RESI。只有部分相关性被打印，不冒充完整协方差矩阵；重名和未识别参数不猜。已有收敛续算检查复用此解析器，避免漏掉第二、第三列的高相关。它不会自行固定坐标。

Every printed column in the last correlation section is parsed; unknown or malformed sections remain visible. Printed correlations are diagnostic evidence, not an instruction to fix atoms.

## 3. 已有无序的多起点 / Population stability

先用 `population-stability --directory CURRENT --fvar-index 2 --output NEW.json` 检查适用性，再通过 `repair-plan prepare/run` 执行：

```json
{"recipe":"occupancy_stability","parameters":{"fvar_index":2,"starts":[0.2,0.5,0.8],"basis":"Replace with evidence for this existing two-position model"},"reason":"Test starting-population dependence","evidence":["Current model and density evidence"],"cycles":30}
```

保留不改起点的对照；其余分支只改初始 FVAR。支持一般位置、两组元素数相同、互补 SOF、仅控制占有率的变量。特殊位置、同变量还控制坐标/ADP、SUMP 耦合等返回不支持。比较最终占有率、同标签坐标 RMSD、收敛、残差与 A/B；0.02 占有率差及 0.1 Å RMSD 只是明确记录的筛查阈值。交换组分、边界占有率、任一失败均需复核。

This tests an existing hypothesis, not whether disorder exists. Supported groups use one SOF-only complementary FVAR on full general sites. Do not interpret stability as chemical correctness. Keep every initial and final model.

## 4. 限制强度 / Restraint strength

`restraint-strength --directory CURRENT --instruction "DFIX 1.4 .02 C1 O1" --output NEW.json` 检查指定的已有指令。实际比较请求：

```json
{"recipe":"restraint_strength","parameters":{"instruction":"DFIX 1.4 .02 C1 O1","factors":[0.5,2],"basis":"Replace with the chemical basis for this existing restraint"},"reason":"Test sensitivity to restraint strength","evidence":["Current model and justified target geometry"],"cycles":30}
```

将明确写出的 sigma 分别乘以 0.5 和 2，连同原值对照；小 sigma 较强，大 sigma 较松。支持显式 DFIX/DANG/SADI/FLAT/RIGU/DELU/ISOR/SIMU 的一条局部指令。目标键长、SIMU 距离截断、原子列表、HKL 和 WGHT 不改。不支持通配符、对称选择器、重复同指令或隐式默认 sigma。记录实际距离/Ueq 和完整对照指标；不逐轮收紧直到警告消失，也不自动选“最强”的方案。

Vary only explicit restraint sigmas in a bounded stronger/control/weaker comparison. Measured/refined standard uncertainties are different quantities and are not overwritten.

## 5. 求解自动接替 / Solver fallback

独立入口：

```text
python -B scripts/toolbox.py run solve-cascade -- --ins SEARCH.ins --hkl DATA.hkl --shelxt SHELXT.exe --shelxd SHELXD.exe --config SEARCH.json --output NEW_RUN
```

SEARCH.ins 必须不含原子坐标，只提供晶胞、波长、SFAC 和搜索用 UNIT 等。SHELXT 成功产生可检查候选则不启动 SHELXD；无候选/超时可切换。安装、语法或原生异常不反复重试。所有阶段在新目录、原始 HKL 不改。

可供 `autorun` 配置的 `solver_fallback` 文件，或 `pipeline start --solver-fallback SEARCH.json`：

```json
{"timeout_seconds":600,"primary_timeout_seconds":600,"hypotheses":[{"space_group":"P 1","find":20,"ntry":30,"basis":"Replace with this dataset's symmetry and search-count evidence"}]}
```

数字和空间群仅展示格式，不是默认答案。一个计划最多六个假设，每个 NTRY 明确有限；进程 watchdog 可配置。缺省只对原始三斜 P 类型种子提出 P1/P-1 搜索假设，FIND 从搜索 UNIT 粗估并明确标注；不是分子式或实验确认原子数。其他情况须提供有依据的空间群/FIND 假设，否则如实记输入不足。不能由“晶胞是单斜/正交”等度量直接确定空间群。

主线已接入：`autorun → pipeline → session` 的初解失败会走此分支；新建 profile 在软件目录存在 SHELXD 时记录其哈希。旧 profile 可查同一 SHELXT 目录的 shelxd.exe，实际路径/哈希写入本次记录。不会下载、激活或更改授权。

**SHELXD 的峰模型并非完成的化学模型。**其散射类型和 SOF 字段可能只是搜索设置/峰排序；必须核对元素与物理占有率后再精修。主线在此返回带路径的 `solver_handoff`，让 AI/有依据的图匹配接手，不能直接作为最终 CIF。实际求解软件的记录不再一律写成 SHELXT。

The native fallback is automatic for supported, justified inputs; chemical atom assignment is a separate checkpoint. An installation failure or unknown search symmetry is not a failed crystal solution. Preserve timestamps, commands, outputs and failed hypotheses. Successful CIF generation, low R or zero A/B does not establish structural correctness.

Technical references: [SHELXL instructions](https://shelx.uni-goettingen.de/shelxl_html.php), [SHELXD instructions distributed by RWTH](https://www.ac.rwth-aachen.de/extern/AKS/shelxde.pdf), [Olex2 structure-solution documentation](https://www.olexsys.org/olex2/docs/tasks/tasks/structure-solution/). Native test logs record the actual installed versions. No source manual or figures are bundled here.
