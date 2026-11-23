# 自动调度：正常连续执行，异常接手

入口为 `scripts/crystal_autorun.py`。它调度已有经过检查的程序，不调用语言模型。首次配置和不确定的科学判断仍由使用者/agent 负责；不能把“脚本 AI 调用为 0”说成整个项目不需要 AI。

## 单次启动

用本机 Python 创建并验证 runtime profile；见 [scripted-pipeline](scripted-pipeline.md)。准备一个独立 JSON 配置（相对路径以配置所在目录为基准）：

```json
{
  "schema": 1,
  "data_dir": "D:/CrystalData/new_sample",
  "profile": "D:/CrystalRuntime/profile.json",
  "elements": ["C", "H", "N", "O", "Cl"],
  "specimen": "D:/CrystalData/specimen.json",
  "graph": "D:/CrystalData/chemical_graph.json",
  "donor_basis": "用户提供二维键连图中的形式电荷及氢数；由新模型匹配和精修复核",
  "deliver": true,
  "authorize_iucr_upload": false,
  "prior_conversation_exposure": false,
  "max_candidates": 6,
  "max_weight_updates": 4,
  "timeout": 180
}
```

元素、实验信息、二维图必须是本例事实/显式假设，不能照抄示例的元素或质子化状态。未知外观可省略 `specimen`。无二维图可省略 `graph`；脚本仍先求解，之后明确停在化学判断处。使用已有且覆盖本数据的上传授权时直接记录 `authorize_iucr_upload:true`，无需再次询问。默认 false 不构成授权。`timeout` 是交付阶段支持的单项本地/网络操作超时，不是整例时间预算；求解及匹配沿用已有程序内部边界。

```text
python scripts/crystal_autorun.py run --config JOB.json --output NEW_RUN
python scripts/crystal_autorun.py status --run NEW_RUN
```

`NEW_RUN` 必须不存在，并在原始输入目录之外。调度顺序：

1. `start`：环境与输入检查、SHELXT 新求解、SHELXL 基线精修。
2. `match`：完整二维键连图匹配、限定 C/N/O 指认对照、自动加氢与后续精修。
3. `autofinish`：限定科学规则、权重更新、实验参数/模型一致性检查、本地 PLATON、官网 checkCIF、中英文 Word、实测排版检查和封存。

正常运行不用 agent 每阶段读输出、决定“继续”再发一条命令。保留所有中间候选、参数、完整日志、输入与脚本哈希。官网报告只交付 `IUCr_checkCIF.pdf`；Word 中英文各一份。生成报告不代表结构正确。

## 哪些情况交回判断

- 自动路线目前支持原始 HKL/P4P、已有完整化学图的常规范围，**不等于所有晶体都可自动解决**。
- 初始空间群/模型有多个候选：不按最低 R 自动选择。
- 缺失/不完整二维图、图匹配歧义、质子化不明、无序、特殊位置、孪晶、超出规则的元素/结构。
- 不收敛、异常 ADP/差值密度、权重不稳定、局部或官网 A/B、报告检查失败。
- 软件执行失败、输入或脚本变化、未完成的上次操作、缺少上传授权。

状态 `needs_attention` 时，先读 **`handoff.json`**：类别、具体原因、底层失败、规则判断、A/B、最后命令和证据路径。只再读其中所指的当前运行记录及相关知识，不重复读全套日志。入口不会自己启动其他 AI，也不会伪造已人工查看页面。

## 可恢复范围与防重复

```text
python scripts/crystal_autorun.py resume --run NEW_RUN --graph GRAPH.json --donor-basis "本例质子化依据"
python scripts/crystal_autorun.py resume --run NEW_RUN --source INITIAL_STAGE --basis "本次空间群证据"
python scripts/crystal_autorun.py resume --run NEW_RUN --authorize-iucr-upload
```

仅可在匹配开始前补充图/氢依据/初始候选选择，授权也可补记；每次写入 interventions。不得覆盖已冻结图、修改原始输入或替换旧模型。显式选择空间群不绕过下游科学规则：现有限定自动验收仍可能拒绝多个初始候选。

已完成步骤不重复运行；完成后 resume 为只核验的空操作。失败或结果不明的步骤不自动重试，尤其不重放可能已经上传的请求。并发锁/遗留锁不自动删除。确认原因后保留失败目录，用新目录重新运行；或由 agent 使用已有 `crystal_pipeline.py step/finish/finalize` 做有依据的人工分支。外部修改后的模型不会被调度器静默接纳，原 autorun 保持异常记录。

`deliver:false` 只得到 `local_ready`，不是官网与 Word 交付完成。配置/命令错误返回 1，需要接手返回 2，完成/本地准备完成返回 0；仍须读取结构化状态区别语义。

## 证据和边界

`autorun.json` 保存运行状态、快照、命令、耗时、干预记录；`result.json` 是摘要；`index.html` 可打开查看。`pipeline/` 保留完整计算和交付内容。输入快照及原路径均核验；当前运行文件在恢复时核验，拒绝链接路径和静默改动。

原始程序仍执行所有准确性/A-B/官网验证门槛。`review_mode` 必须从科学规则传入后续精修检查，不能在调度边界丢掉。嵌入结构因子的 CIF 重写应先完成，再加 Cairystal 注释、计算哈希、做本地和官网验证，确保复用缓存验证的确是同一文件。

耗时按实际动作记录。精确 Token 消耗及节省值保持 null；程序没有聊天计费遥测。回归测试覆盖调度行为，不证明未知晶体的科学正确性或其他 agent 的表现。

## 延后上传时继续本地工作

上传选项尚未决定时，先完成科学检查、权重和本地验证，再停在网络提交前。已经准备好的 `routine_finish` 检查点封存配置、原始文件审计、审核说明、最终文件和代码版本；后续 `resume --authorize-iucr-upload` 只调用 `crystal_pipeline.py deliver`，不重复求解、加氢或精修。改变文件/代码后不能继续沿用旧封存。已失败或结果不明的提交也不会因 resume 被重放。

如果官网已返回报告链接但下载中断，用 `iucr_validation.py recover --directory OFFICIAL_DIR` 取回既有报告；它核验已提交 CIF 哈希，只 GET 保存的官方链接，不重新 POST。没有已确认的响应时会停止。恢复报告文件不自动等于整套 Word/排版交付已完成；继续记录未完成环节。

难处理溶剂的接手包提供 `solvent_branch_guidance`，指向 `squeeze_request.py`。它仅是路由提示，不把任意 AB 或无序自动分类成可 SQUEEZE。确认主体/溶剂适用性后，由 prepare 生成具体客户选项并复用问卷中的授权；正常选择记录与原生计算由脚本接续。详见 [SQUEEZE](squeeze-workflow.md)。
