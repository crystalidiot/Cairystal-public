# Cairystal 0.3.5-preview — completed-delivery state synchronization

2026-11-26 · Engine delivery_state_sync_20261126_01

- 修复独立加氢/交付完成后顶层仍停在 chemical_graph_required 的问题。子流程结束主动同步，status/resume 也能恢复遗漏。
- 核验同任务原始 HKL、正式交付记录、最终 CIF 对应的 IUCr PDF、两种 Word 及客户导出哈希；缺失或修改的文件不会被标为交付完成。
- `autorun sync-delivery` 可修复旧版已交付任务，保留原计算版本、旧状态与旧交接记录。重复续跑不重新求解、精修、上传或生成报表。
- 同步纳入此前测试版的原生候选续接和结构类别工具分流；化学合理性优先，工具箱并非原生程序调用的限制清单。
- 保留 v0.3.4-preview 与已有发布、学术许可 1.1 和第三方声明。

This is a workflow/state fix, not a change to SHELX numerical algorithms. The current update replays completion of a real previously delivered package; no new crystal was solved or uploaded for this state-repair validation. The CIF, official PDF, bilingual Word and full child records remained byte-identical. Completion does not establish structural correctness. See VALIDATION.md for measured checks and limits.


---

# Cairystal 0.3.4-preview — unified entry and workflow

2026-11-26 · Engine unified_entry_20261126_01

- 统一 `cairystal.py` 入口；`version --json` 返回真实版本、目录和 Python。旧脚本命令兼容，本机快速入口复用同一实现。
- `workflow` 与可选工作台读取同一份七步路线，66 个工具、55 个问题分支保留；`describe` 显示工具的主线位置。
- 合并中英文 SOP、移除过时版本说明。中文技能首页由 4,922 字符降至 2,161 字符。专门的科学知识和旧版本保留。
- 科学计算、精修、官网验证和报表算法没有改写。默认标准模式；fast 为显式选项，已有任务仍用固定原版本。

Both language editions passed 1,263 offline tests each (five localhost checks required an allowed-loopback retry). A fresh raw-input solve/refinement completed official checkCIF and both Word reports, recording R1 0.0481 and official 0A/0B/3C/10G. Automatic delivery took 204.07 seconds; subsequent manual page inspection and development are excluded. This is one previously used simple case, not independent structural-accuracy evidence or a controlled speed benchmark. No experimental data or models are distributed.

Existing Releases and history remain available. Academic licence 1.1 and third-party notices are unchanged.
