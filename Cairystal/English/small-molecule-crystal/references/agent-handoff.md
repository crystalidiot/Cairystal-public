# 换AI时真正可以继承的内容

中文版首次交接请读 [开始使用与交接](../START.zh-CN.md)；English customer and agent handoff: [Getting started](../START.en.md). These entries are equivalent; the full technical references below are shared. Do not require this project's chat history.

Skill不是训练后的神经网络权重。它由入口指令、按问题检索的知识文档、可执行Python脚本、合成回归测试组成。模型在运行时读取这些文件；没有读取的聊天经验不会自动传过去。

| 层次 | 已存放的内容 | 接手时的含义 |
|---|---|---|
| 可重复执行 | 输入哈希/配对、原始求解、二维图匹配与有界C/N/O比较、受限加氢、权重检查、元数据补齐、验证、双语表、排版规则及封存 | 需要相同文件版本、依赖和外部程序；不依赖某个AI记住本次原子编号 |
| 按需查阅的经验 | 无序/PART/FVAR、特殊位置、链无序、ADP、非收敛、常见AB及元数据诊断 | 文档提供推理路径，不意味着所有情形已变成自动算法 |
| 必须保留的不确定性 | 新化合物身份、不完整或错误二维图、复杂无序/孪晶/空间群、异常实验处理 | 换AI后能力可能不同；需要实际证据、独立测试或人工审阅 |

`references/skill-detail-map.md` 是已有材料的索引，包含历史案例分支。盲测必须避开这些分支，只读取通用规则及当前产生的证据。不能把“文件很多”“曾经读过”“通过一个简单例题”当成全部掌握或普适正确的证明。本次维护没有重新审计所有旧PDF/PPT资料的逐条知识覆盖率，因此不声称没有遗漏。

## 给另一个agent的最小启动说明

支持范围内优先用 [automatic-dispatch](automatic-dispatch.md) 的 `crystal_autorun.py run` 自动串起下述阶段。正常步骤无需反复要求 agent 读取输出并发下一条命令；停止后只读 `handoff.json` 再按证据介入。补充配置可恢复未尝试的步骤，执行异常或结果不明不会自动重试。需要实际命令执行权限，不依赖 Codex 专有接口。

读当前包的 `SKILL.md`，按 `references/portable-environment.md` 建立本机运行配置，验证软件许可及可执行文件，运行合成测试。仅在新任务目录使用允许的原始数据；明确可能元素和二维式来源。支持的HKL/P4P路线依次执行 `crystal_pipeline.py start`、`match`、`autofinish`；遇到 `needs_review` 读取对应小型诊断包，不读参考答案、不静默改数据。交付官网含结构因子的checkCIF和同源中英文Word，报告未解决的问题。保留所有文件和阶段耗时。

所需能力是本地文件访问、Python与命令行执行、SHELXT/SHELXL/PLATON、Word或LibreOffice渲染以及允许访问IUCr。只有聊天功能而不能执行软件的agent不能完成同一流程。不要照搬本机盘符或依赖路径；重建profile。核心Python依赖包括Gemmi、python-docx、pypdf、pdfplumber；测试所需reportlab与渲染工具另行检查。

跨agent评估应冻结相同skill版本，使用隔离输出和同一许可输入，比较实际产物与失败原因，而不是要求它声称“已经学会”。脚本减少了自由发挥，但不会消除复杂科学判断的能力差异。

## 固定版本运行入口

本机若提供项目根目录的 `Cairystal.current.json` 和 `cairystal.py`，先读取 current 记录，再使用该版本的 SKILL/profile。入口验证固定发布目录的文件哈希；`info` 显示版本，`doctor` 检查功能依赖，`autorun`/`pipeline` 调度对应版本。新任务使用当前发布版；旧任务恢复时仍使用其最初记录的固定版本，不能换代码后伪称原测试延续。

当前镜像目录便于其它 agent 发现；各次发布目录和旧稳定版备份保留。跨电脑仍要建立本机 profile。不要把本机 launcher、已有结果或回归测试通过当成其它 agent 已经验证成功。
