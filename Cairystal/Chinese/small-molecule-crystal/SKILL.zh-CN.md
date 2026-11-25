---
name: small-molecule-crystal
description: Cairystal 小分子单晶解析工具箱：调用本机 SHELX/PLATON，完成解析精修、A/B 诊断、IUCr 官网 checkCIF 和中英文 Word；常规步骤脚本执行，科学歧义再交 AI/专业人员。
---

<!-- fast_model_20261125_01 -->
## 快速版入口 / Fast edition

本副本用于尽快获得可查看的合理候选模型，默认用工具 `fast`（显式 execution_mode=fast）；先阅读 [快速模式](references/fast-mode.md)。减少试探轮数、先出模型，保留本地AB检查及已授权的官网/中英文Word。快速模式不要求AB清零，报告标为临时模型；明确的化学、占有率或数据配对错误仍需解决。下文通用主线与快速模式冲突时，以快速模式的试修预算和停止规则为准；未变化的科学/权限规则继续适用。

This opt-in copy uses the `fast` tool by default. Read [Fast mode](references/fast-mode.md). Bound trial budgets and publish a provisional local model before authorized official reports. Do not chase zero AB automatically; retain chemistry, occupancy and data-pairing checks. Fast-mode budgets take precedence over the general workflow below. The previous standard release stays unchanged.


# Cairystal 小分子单晶解析

客户给出路径即可开始。由助手操作本机程序、记录证据并说明结果。用户可直接说“帮我解这颗晶体”“看一下这两条警告”或“模型已经有了，接着出报告”。[English](SKILL.en.md)

**模型选择顺序：化学合理性与本次衍射证据第一，checkCIF 的 A/B 警告第二。** 先核对元素、键连/价态、H与电荷、组成、占有率/特殊位置、几何及密度支持，再在同等合理的模型之间比较警告。不能因为少了警告就采用化学上更差的模型；合理且有证据的模型可保留无法消除的警告并说明。已提供或允许使用的结构模型可作参考，核验与本样品的关系并记录继承内容；明确要求盲测或不读旧模型时继续遵守该范围。见[化学优先与参考模型](references/chemical-first.md)。

### 哪些事由助手决定

求解或精修返回 `needs_attention` 时，先读 `handoff.json` 的 `next_step`。若 `owner=assistant`，在本轮执行下一步。缺少二维式时，先读本例初解模型、差值峰、几何和热参数。常规加氢、权重调整、备用求解和有证据的无序试修，在独立目录保留对照并直接比较。对特殊位置阳离子，核对完整取向的对称关系、共享原子、占有率及化学组成，再比较未分裂和分裂模型。证据仍有歧义时交付已确定的部分并标明待核实处。

同一样品的记录和用户已给的事实优先。只向客户询问会改变判断且只能由客户补充的事实、会改变工作目标的选择，或缺少的对外上传及 SQUEEZE 授权。同批可问的项目一次列出，用户答“不清楚”后继续其余工作。此前已授权的操作在原范围内续接。用户指定盲测、要求先看结果或暂停时，按该约定执行。

P4P 缺 BRAVAIS 时，入口根据晶胞和本例 HKLF 4 等价反射提出初解搜索对称性。若格心或劳厄对称性仍有歧义，由助手用本例数据比较候选并记录依据。

跨聊天或中断续跑时带上当前样品编号和原始 HKL。用 `--expected-hkl` 核对任务，按选定 CIF 的指纹取回官网结果并回复该样品的链接。[按样品续跑](references/case-resume.md)。无序试修出现短键时先比较两种取向及未分裂模型，再选最终方案。

PLAT919/934 出现时，走[固定清单 OMIT 分支](references/automatic-ab-mainline.md)。1–20 个核实的异常反射直接试修，检查通过就用 OMIT 工作版继续。两个版本均保留，CIF 与中英文报告记录每个排除点。

## 一条主线

1. **确定输入。** 固定版本、本机 profile、允许读取的文件及新工作目录。保留原始 HKL 和指纹。盲测只读约定输入，起始 INS 应先确认允许使用。HKL＋P4P 可走 autorun，只有 HKL＋INS 时按 [输入分流](references/mainline-and-exceptions.md) 检查与准备。新电脑先看[安装交接](START.zh-CN.md)。
2. **一次补齐缺项。** 先查同样品的实验记录。需要时集中询问两类信息：颜色、外形、三维尺寸（例如绿色，块状，0.050 × 0.051 × 0.052 mm）；可能元素，包括溶剂和反离子，也可附二维式。已知信息注明来源，未知留空，冲突只核实相关字段。元素清单不代表计量比。[表单与授权](references/one-time-intake.md)
3. **初解、精修。** 用 SHELXT 初解，核对空间群、C/N/O 指认、几何与占有率。失败时按证据尝试 SHELXD。通过 SHELXL 比较候选、加氢和权重。缺少二维图、无序或特殊位置存在歧义时保留模型，交给科学复核。[工具与诊断索引](references/toolbox.md)
4. **处理警告。** 优先核查 A、B，使用本次密度、连接、热参数和反射证据决定试修。保留修改前后版本。SQUEEZE 需要主体可靠及本例明确授权。异常反射剔除须保留原 HKL、具体依据与对照结果。[按问题找工具](references/problem-strategy-tools.md)
5. **交付或续接。** 用最终 CIF 和结构因子验证，通常 LIST 4。对同一 CIF 的官网提交使用本例授权。已有回执先恢复下载，再生成中英文 Word、检查排版和文件指纹。最终给出数据目录 Cairystal 子文件夹里的 CIF、IUCr PDF、两份 Word 的链接和剩余问题。未完成的阶段如实说明。零 A/B 或低 R 单独不足以确认结构。[交付与恢复](references/delivery-completion.md)

采集文件声明原始正交晶格（Orthorhombic P）时，autorun 按三个二重旋转分别比较实测等价反射。三个检验均支持 mmm 才启动 SHELXT。过度合并、实测信号不足或强度矛盾时，查看 pipeline.json 的 laue_review；有证据时再提供经核实的 INS。搜索假设与最终空间群分别记录。初解需要化学判断时，handoff.json 的 first_models 列出各候选的 RES、指标和逐原子复核入口。

已给完整二维结构时，只有图上的 N–H/O–H 需要提供质子化依据。普通 C–H 按图匹配后加氢，并核对 SHELXL 实际生成的氢数与 UNIT。图中无氢时沿用已精修的重原子模型进入复核。详见[图匹配与加氢](references/graph-matching.md)。


每轮集中比较候选，先核对完整片段几何，再固定模型、验证并生成报告；只重做变化影响的部分。现有工具优先，未变页面按指纹复用，科学与交付检查保留。见[减少重复工作](references/usage-and-cost.md)。

初解后的 `decision_queue` 给出逐原子证据和工具入口；可运行有界 C/N/O 对照。autorun 记录停顿原因，常见无序保留分级入选/暂缓依据。见[初解决策与停顿诊断](references/decision-flow.md)。

## 助手入口

在 skill 目录用 `python -B cairystal.py guide` 查看常见任务，`describe 工具名` 查看参数，`run 工具名 -- --help` 查看程序帮助。工作台可选。已有任务用创建它的版本续跑。

助手在有同样品 PCF、cif_od 等实验记录时，用 `metadata` 查看字段，用 `metadata-ledger` 建立配对记录，将 `--metadata-ledger` 传给 `intake-form`。用 `initial-review` 核对初解，用 `ab-auto` 比较有证据的本地试修。交付前用 `check-delivery` 核对四份文件。按当前步骤查阅参考资料。

- 处理新样品：`run autorun -- run --config JOB.json --output NEW_RUN`。配置由助手依实际资料准备。
- 粘贴官网警告：`run route-problem -- --alert-text "PLAT306_ALERT_2_B ..." --json`。保留未匹配编号。
- 维护者提出改动：用[中文需求与验收模板](references/owner-guide.zh-CN.md)给出一个正例、一个反例。[详细操作规范](references/operating-protocol.zh-CN.md)

已明确配对的 PCF 或 cif_od 可直接交给 `intake-form --hkl A.hkl --paired-record A.pcf --pairing-basis "配对记录依据" --output NEW_FORM`。仅文件名相同的记录先核实。限制读取范围的盲测仍按指定输入运行。

补报告先用 `recover-checkcif --directory OFFICIAL --cif FINAL_CIF --check-only` 做本地核对。指纹一致且回执完整时复用官网结果；下载中断时，用同一命令去掉 `--check-only` 续取报告。

从本地封存点续接时，常规报告检查通过后自动完成打包和客户目录交付。遇到工具返回时按[主线与工具衔接](references/flow-handoffs.md)继续，核对选定版本，不重复求解或提交。

孪晶迹象出现时，主线先走 [twin-quick](references/quick-twin.md)：有界 PLATON 检查，检出可用法则后自动在新 INS 加 TWIN/BASF 并作原生精修对照；取得模型比较再决定采用。该检查先于 OMIT，无迹象不额外运行。


## 连续化学处理 / Continuous chemistry workflow

使用 [chemistry-screen / hydrogen-continue](references/chemistry-handoff.md) 集中比较本轮元素候选，并在有依据的化学图确认后自动重编号、加氢、复核和交付。只把未解决的科学歧义交给 AI；当前推断图不能写成客户已提供的二维式。

Use the linked tools for current-run element contrasts and reviewed-graph H/refinement/report continuation. Inferred chemistry is not an independently supplied 2D prior.
