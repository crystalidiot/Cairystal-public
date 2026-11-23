# 统一入口与自动修复 / Unified entry and automatic repair

所有工具使用 `python -B cairystal.py`。旧 `scripts/toolbox.py` 继续兼容。

```text
python -B cairystal.py version --json
python -B cairystal.py list
python -B cairystal.py describe ab-auto
python -B cairystal.py run ab-auto -- --baseline CURRENT --stem case --validation CURRENT_VALIDATION --profile MACHINE.json --output NEW_RUN
```

`release_info.json` 是安装版本的唯一来源；工具列表、路由、工作台与新交付记录使用同一版本号。`assets/toolbox.json` 只定义工具注册；每个工具必须属于已声明分组，工具数量必须与版本声明一致。版本不一致时报错，不悄悄漏工具。历史方法来源日期不当作当前安装版本。

主线：输入与来源 → 初解/检查 → 完整精修与权重 → 配套本地验证 → 收集 A/B 证据 → 支持的对照试验 → 比较与必要的科学复核 → 最终精修/官网验证/中英文 Word。当前 `finish` 对已通过固定清单 OMIT 接受检查的 919/934 分支自动继续；其它有改善但尚需科学判断的候选返回复核包，不先把旧模型当最终结果上传。

| 条件 | 自动准备与执行 | 仍需判断 |
|---|---|---|
| 213/214，独立全占有原子，无邻近残余密度/短接触等竞争解释 | 局部 ISOR 对照 | 无序、元素指认及最终模型 |
| 234，明确同 PART 的键接原子对 | 分别试 RIGU/SIMU | 限制是否符合化学模型 |
| 241/242，满足配套和化学元素范围条件 | 已提供 C/N/O 内的元素对照 | 化学计量、键型与氢 |
| 420，完整已有 O(H)2，周期邻近 O 与现有模型符合严格筛选 | 当前向量固定＋两个刚体旋转，AFIX 3，保持水内几何 | 氢键受体、质子化/电荷、差值密度；不把几何候选当水身份确认 |
| 420，明确已有 C-O-H | OH 旋转候选 | 取向与氢键网络 |
| 031，配套 EXTI 值与正标准不确定度证实小于 3.33 su | 去掉 EXTI 对照 | 是否应保留消光模型 |
| 936/731/732，现有单条 DAMP | 解除 DAMP 后重查收敛 | 是否存在真实不稳定/无序 |
| 919/934/939，当前配套加权异常反射证据支持 1–20 个点 | 固定 OMIT 对照。919/934 经核验可直接采用工作版，939 单独诊断 | 数据质量原因及低角信息损失；不按降低 R 值自动选为最终模型 |

新水氢规则不会凭孤立 O 添加缺失 H；不支持部分占有、特殊位置、复杂 PART 或模糊 H 归属。接受器只能是筛选得到的候选，执行器再次核对完整几何、对称性和现有限制。C36 一类邻近残余密度的情况会保留为需要科学判断，而不是用限制掩盖。

自动候选不等于自动最终采纳。未知数据保持未知；元数据 A/B 单独统计、仍在官网报告中保留。改变反射集合的对照单列，不与原数据模型按 R 值竞争。脚本内部 AI 调用数为 0 不等于整个任务 Token 为 0，实际 Token 未测就写“未测”。

English: `cairystal.py` is the portable unified CLI and `release_info.json` is the sole installed-release identity. The normal finish route collects current evidence, executes bounded supported comparisons and provides one review packet. New routes include complete-existing-water orientation hypotheses, verified weak-EXTI removal, existing-DAMP release and evidence-backed PLAT939 reflection sensitivity trials. Missing H, chemical identity, protonation and disorder are not silently decided. Fixed-list 919/934 acceptance uses its documented checks; other changed-data trials require review. Preserve original data and all candidates; every selected diagnostic version still needs exact-CIF official checkCIF and bilingual Word. This is a repair regression on prior working models, not unseen blind phasing or proof of chemical correctness.
