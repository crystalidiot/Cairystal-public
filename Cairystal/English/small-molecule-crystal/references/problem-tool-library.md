# 按问题调用工具：把已整理知识接到主线上

工作台的“处理工具索引”和命令行从同一份 `assets/console/workflow-data.json` 读取规则，避免界面说一套、agent 使用另一套。检索只给处理路线，不执行修改或授予上传权限。

    python -B scripts/toolbox.py run route-problem -- --alerts 242_ALERT_2_B 420_ALERT_2_B
    python -B scripts/toolbox.py run route-problem -- --query 无序
    python -B scripts/toolbox.py run route-problem -- --list --json

每条规则明确：触发现象/警告、已知证据与待验证原因、调用工具、对照和验收、返回主线的位置、尚未实现的自动部分。未匹配警告保留为未识别，不能视为无问题。警告按三位代码检索，不因 A/B/C 级别改变而漏掉。

## 知识来源和适用边界

本次整合既有 AB 行动手册、无序/占有率、轻原子与密度、ADP 方案、短键与限制冲突、收敛、权重、特殊位置、实验参数、SQUEEZE、对称/孪晶分流、LYH 通用经验及交付配套规则。索引不含样品身份、参考坐标或历史比例。专题里的通用知识可以读；盲测不得追读链接的历史案例产物或答案。

覆盖：初解 C/N/O 与骨架完整性；氢/水/羟基方向；短键；NPD/椭球形状/Ueq；CF3/叔丁基/烷基链/溶剂无序；PART/FVAR/特殊位置；SQUEEZE；不收敛；小数量异常反射对照；权重与两类 GoF；温度和实验参数；绝对构型字段；有证据的对称/孪晶与整体误差；CIF/FCF 配套和最终报告。

## 执行工具和科学决定分开

- `initial-review`：本次新增的只读候选初筛；已经接入初解基线后。
- `route-problem`：本次新增的问题索引工具；不冒称自动修复。
- `session`：将已有 `crystal_session.py` 的显式元素/氢/精修方案暴露到 toolbox，尤其可做 C/N/O 替代对照。
- `restraint-tension`：将已有最终 LST 限制冲突检查暴露到 toolbox。
- `match/hydrogen-plan/disorder/trials/occupancy/finish` 等原有工具复用；范围、证据与停止条件保留。

SHELXT→SHELXD 对有依据的搜索假设已接入自动备用调度，见 [五项增强](five-tool-enhancements.md)；峰模型还需元素/占有率核对。对已有 OH 的完整方向搜索、水氢自动定位、任意未知化学的自动定案仍未实现。不把知识卡数量当作已自动修复的功能数量。运行修改后仍须精修、AB 复查及按授权完成官网 PDF 和双语 Word。

本版新增 `repair-plan` 执行六类局部对照；已有简单OH可按明确角度旋转，现有H组可保留氢数改AFIX3。见[用法](evidence-repair-tools.md)。route-problem 还提供汇编中的501个PLAT编号页码/官网链接索引；未有处理路线的仍标记未实现，不能当作自动修复。
