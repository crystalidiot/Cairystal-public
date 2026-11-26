# Cairystal 工具箱

入口只负责选择工具，不重新实现精修、加氢或验证算法。具有本地文件及终端权限的 agent 或人均可调用。同一套参数适用于不同样品，不硬编码某颗晶体的原子坐标、指认或答案。

在 skill 目录中执行；其他工作目录使用 cairystal.py 的绝对路径。路径含空格或中文时加引号。大写路径是占位符，须替换成本机路径。

    python -B cairystal.py list
    python -B cairystal.py list --group validation
    python -B cairystal.py describe complete
    python -B cairystal.py run complete -- --help
    python -B cairystal.py plan complete -- --input CANDIDATE --profile PROFILE.json --review REVIEW.json --output NEW_OUTPUT --data-dir ORIGINAL_DATA

list --json / describe TOOL --json 提供机器可读目录：输入、输出、依赖、文件或联网影响、适用边界及参考资料。目录真源为 assets/toolbox.json。**plan 只显示将执行的 argv，不校验科学输入、不授权、不运行**。run 后须用 -- 分开原工具参数；原样转发，不使用 shell、不增加上传同意、不隐式换 profile、不把工具失败解释为成功。退出码来自实际工具；工具箱自身参数错误为 2。

## 完整任务的最短路线

    python -B cairystal.py run doctor -- --profile PROFILE.json
    python -B cairystal.py run intake-form -- --language zh-CN --output NEW_FORM
    python -B cairystal.py run intake-accept -- --input ANSWERS.json --profile PROFILE.json --output NEW_INTAKE
    python -B cairystal.py run autorun -- run --config NEW_INTAKE/autorun_config.json --output NEW_RUN

正常步骤由已有调度器继续。needs_review、blocked 或非零退出时读取 handoff.json / decision_packet.json 和对应日志，按具体原因选择工具，不重启整条任务来躲避检查。自动初始化当前有 HKL/P4P 范围限制；其他格式用 inspect、setup、stage 及 [原有流程](workflow.md)。原工具参数和配置 schema 没有改变。

## 按任务选择

| 任务 | 工具 |
|---|---|
| 环境、安装、版本 | probe、doctor、profile、verify |
| 输入与参数 | intake-form、intake-accept、inspect、metadata、project-metadata |
| 后台求解、精修、调度 | setup、stage、pipeline、autorun |
| 二维式与氢 | match、hydrogen-plan |
| 氢与反射证据 | donor-audit、reflection-audit |
| 材料方法工具 | water-h-trials、reflection-omit、adp-directions |
| 诊断、无序、占有率、溶剂 | diagnose、occupancy、disorder、trials、squeeze |
| 编号与收尾 | labels、finish、complete |
| 本地及官网验证 | platon、checkcif、recover-checkcif、compare-ab |
| 双语报告及交付 | deliver、check-delivery、viewer |
| 故障与回归 | support、test |

例：只核查占有率、读取参数或比较警告，不重跑整个解析：

    python -B cairystal.py run occupancy -- "CURRENT/model.res"
    python -B cairystal.py run metadata -- "ALLOWED_SAMPLE/model.pcf"
    python -B cairystal.py run compare-ab -- --before BEFORE.ckf --after AFTER.ckf --output NEW_COMPARE

每个工具的 describe 与原生 --help 定义实际输入输出。metadata 读取一个明确授权文件；盲测对 project-metadata 显式指定允许的 --source。工具箱不是文件访问沙箱，不能用自动发现功能越过输入范围。

二维图像不是核实过的化学图。加氢仍要核对价态、质子化和对称位置，精修后再验证。无序生成有证据支持的候选及未改对照，不自动采纳；SQUEEZE 保留针对本模型的用户选择和科学检查。

deliver run 核对配对原生文件，进行官网验证并生成两版 Word，**不是未经验证的 CIF 转 Word**。本地 PLATON 不能替代官网 PDF；上传选项只能表示已有有效授权。独立工具调用不等于完整任务交付。support 只在本地保存反馈，不自动发送。

## SOP 与工具的分工

- SOP 规定顺序、证据、复核条件和交付物。
- 工具负责计算、格式处理和检查，保留已有日志、退出码和产物；各工具的业务输出 schema 目前并不统一。
- AI / 专业人员处理化学、空间群、无序等不确定判断；工具箱不会把疑问自动变成通过。

正常任务只读 SKILL 和选中的工具说明。必要时读 [操作细则](operating-protocol.zh-CN.md) 对应段落；历史案例不作为盲测输入。旧直接脚本入口保留，进行中的任务继续固定旧版本。离线合成测试不代表晶体正确率或不同 agent 的兼容认证。

本地收尾已完成时用 **resume-delivery** 继续官网与 Word，不重跑 complete；再用 **report-qa** 和 deliver finalize 完成复核与客户目录导出。参数和状态见 [续跑与可靠性](workflow-reliability.md)。

新增入口：`initial-review`（初解 C/N/O 初筛）、`route-problem`（按警告/现象查处理工具）、`session`（显式元素替代与精修计划）、`restraint-tension`（最终几何限制冲突）。用 describe 查看输入；见[处理工具索引](problem-tool-library.md)。

`repair-plan` exposes six bounded recipes with an unchanged control, native execution and comparison. See [evidence-repair-tools.md](evidence-repair-tools.md).

特殊位置与溶剂无序：`fragment-orbits` 支持完整分子、共享原子和骑乘氢的一致性检查。 [Details](complete-configurations.md).

## 按情况查阅

- [自动 A/B](automatic-ab-mainline.md)
- [材料工具及配方](material-derived-tools.md)
- [方法来源](learning-method-map.md)
- [无序/PART](disorder-occupancy.md)
- [SQUEEZE](squeeze-workflow.md)
- [分壳、相关性、多起点、限制强度、备用求解](five-tool-enhancements.md)
- [资源适配](native-performance.md)
- [分级筛选](density-disorder-screening.md)
- [对称构型与占有率](symmetry-configurations.md)
- [统一入口、版本与新增自动分支](unified-mainline.md)
- [耗时诊断](speed-diagnostics.md)

- `twin-quick`: [快速孪晶检查与对照精修](quick-twin.md)。
