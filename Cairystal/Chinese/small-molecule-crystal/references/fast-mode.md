# 快速模型模式 / Fast working-model mode

用于“先尽快看清是什么结构、主体是否合理”的任务。这是单独的选择，严格版及已开始的任务不切换。

## 用户如何使用

告诉助手：**“用 Cairystal 快速版解析这个目录，先给我可查看的模型。”**
同一原始输入仍先复用已有外观/元素信息，缺失时一次问清；不为每次试修反复征求许可。原始文件保持不变。

主线：原始数据 → SHELXT → 本次初解的元素/键连核对 → 常规精修与加氢 → 一轮权重更新 → 一次本地 PLATON → **先提供快速模型路径和未解决问题** → 已授权的官网 checkCIF 与中英文 Word。

## 与严格版有什么不同

| 环节 | 标准模式（代码默认） | 快速模式（本副本的推荐入口） |
|---|---|---|
| 二维图匹配候选预算 | 最多 6 | 最多 2；歧义仍要判断，不能只按 R 选 |
| 建议权重更新 | 最多 4 次 | 最多 1 次；剩余差异记录，不为此独立停住 |
| 权重试修后同参数续跑 | 最多 2 次 | 0 次；不收敛严重则交给异常处理 |
| 最大 shift/s.u. | 常规检查 0.01 | 临时模型可至 0.1，数值照实保留 |
| AB 警告 | 可触发自动工具对照 | 检查、列出和分类，但不自动展开逐项试修 |
| C/G 与完善细节 | 按问题需要处理 | 不单独为其反复试修；明显模型问题仍处理 |
| 官网及报表 | 保留 | 保留；本地模型先出，不等待远程服务器 |

0.1 是本项目的临时模型停止规则，不是 IUCr 的发表标准，也不证明近似正确。化学/键连检查未通过，不能因为数值低而标为“较准确”。

## 助手怎么执行

使用本副本 `cairystal.py run fast -- --config CONFIG.json --output NEW_RUN`。它调用与标准版相同的原生软件入口，显式传入 `--execution-mode fast`，不复制旧模型。现有 autorun 配置也可以加 `"execution_mode": "fast"`。配置仍需要 `data_dir`、`profile`、`elements`，有经核对的二维图时提供 `graph`。`deliver` 默认 true；上传权限沿用该样品已有授权，快速模式不会产生上传授权。

没有二维图或遇到复杂模型时，自动流程会交给助手一次科学判断。助手先读紧凑候选摘要，处理会改变主体身份/骨架/空间群/主要占有率的问题。有明确证据才做一轮针对性对照；必要时调用现有无序/孪晶工具，不自动穷举许多低占有率溶剂方案。预算不足或主体仍不可靠就保存真实产物并说明“部分模型”，不伪称成功。快速预算是节约试探的默认值，不是阻止用户继续处理的限制。

元素、键连、氢数、明显短接触、占有率、NPD、奇异矩阵、模型与结构因子配对、原始输入哈希仍检查；不靠缩小误差、虚构尺寸、删反射或加限制来制造通过。特殊位置/无序/重原子等不在自动化学规则覆盖范围时，助手判断后可用 `pipeline finish --execution-mode fast --review REVIEW.json ...` 继续，同样保留依据。

`fast_preview.json` 是先出模型的回执，包含 CIF/RES/HKL/FCF 路径与哈希、实际指标、所有本地警告、权重状态及本地耗时。它不代表官网/Word已完成。官网请求失败时从现有回执/检查点继续，不重新解结构。最终四件套仍按项目约定放到目标数据目录的 `Cairystal` 新运行子目录；报告注明快速候选及未解决问题，不称发表定稿。

需要精修定稿时，从该次新模型继续严格检查，另建阶段；无需重跑初解。切换版本后不要强行恢复旧版本固定的脚本检查点。

## Evidence and limitations (English)

Fast mode limits graph candidates to 2 and suggested-weight updates to 1, disables unchanged weight continuations and automatic AB repair trials, and permits measured max shift/s.u. up to 0.1 only for a provisional model with zero reported NPD atoms. All other execution/control, pairing and chemistry checks remain. The standard defaults remain available and the previous release is unchanged.

Use `cairystal.py run fast -- --config CONFIG.json --output NEW_RUN`, or set `execution_mode` to `fast` in an autorun configuration. Obtain a chemically supported initial model; ambiguous identity, graph matching, symmetry or major disorder still needs the agent. Read compact evidence once and try a targeted alternative only with evidence. Do not stop at a routine handoff if the agent can resolve it within scope.

Local preview precedes remote validation and reporting. Existing upload authorization is reused without being inferred or expanded. Official PDF and bilingual Word are still generated when delivery was requested and authorized; all unresolved findings and provisional status remain visible. Accuracy and overall speed are not guaranteed by a budget or a low R factor. Benchmarks on a synthetic finishing fixture do not measure fresh-solution accuracy or complete customer wall time.
