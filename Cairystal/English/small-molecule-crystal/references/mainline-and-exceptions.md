# 主线走通，异常才分流

主线及工具位置见[共同路线图](flow-handoffs.md)，或运行 `python -B cairystal.py workflow`。本页仅补充输入分流和求解例外。

任何异常分支都必须说明：**触发原因 → 对应工具 → 可核验结果 → 返回主线位置 → 无效后的停止条件**。修改模型后回到精修和验证；网络或报告故障从相应交付断点恢复，不重解结构。不能把“有说明文档”当成“自动调度已实现”。

现有代码核对：
- crystal_session.start 正常调用 SHELXT；无可用候选且不是输入/环境故障时，autorun 自动运行有依据的 SHELXD 搜索假设。缺少假设或软件则明确交接，SHELXD 峰模型返回元素/占有率核对，详见 [五项增强](five-tool-enhancements.md)。
- autorun.drive 在缺少已审核化学图/供氢依据时会停下；当前不是仅凭元素就能全自动推断化学的通用程序。
- hydrogen-plan 主要从明确化学图生成初次加氢计划，拒绝直接重复处理已有 H；新增 repair-plan 支持已有简单 OH 的有限转动对照及 AFIX 3；已有普通位置全占有水的两颗 H 可用 water-h-trials 建方向对照；新建水氢/任意供体重定向尚未实现。
- routine_finish 的常规精修/权重、本地验证、官网提交/取回和双语报告工具已存在。异常修复方案的选择仍有 agent 介入。

两个关键异常分支：
1. SHELXT 无可用候选：先排输入/环境错误 → 明确本次空间群与组成搜索假设 → 在独立目录准备/运行 SHELXD → 用骨架、元素/几何和精修表现评估 → 返回元素与氢步骤。候选取舍不单凭 R；无新证据不反复重跑。
2. PLAT420：核对 OH 化学身份 → 搜索含对称邻居的受体和差值密度 → 给已有 H 建方向候选 → 必要时 AFIX 3 保持选定方向 → 精修/接触/密度/A/B 对照 → 返回 SHELXL 和本地验证。不是把每个无受体警告都强行靠近最近原子；AFIX 3 自身不生成正确 H 位置。

完整、人可读与机器可读共用的路线定义在 assets/console/workflow-data.json。本页说明路线；repair-plan 是另行调用的可执行局部修复工具，见[用法](evidence-repair-tools.md)。用户能从本机首页选择例子查看；实际任务、参数和模型在 /workspace。

技术依据：
- https://journals.iucr.org/services/cif/checking/PLAT420.html
- https://shelx.uni-goettingen.de/shelxl_html.php （AFIX：m=0、n=3）

后续先补可复现的异常分流与验收，再优化速度/界面。每条新分支需要实际对照案例、保留原模型，且复核成功才恢复主线；有限配方已经实测，未支持的特殊情况继续保留复核。
