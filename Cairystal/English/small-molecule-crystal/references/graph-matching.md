# 二维图匹配、元素指认与自动加氢

`scripts/graph_assignment.py` 不调用模型 API，不使用历史原子坐标或预设原子标签。输入是明确的重原子化学图（元素、键级、电荷、氢数）和本次 H-free RES；图片需先变成经确认的结构化图。二维图本身的正确性是外部前提，不能用本脚本证明。

```text
python scripts/crystal_pipeline.py match --run NEW_RUN --source 01_baseline_0 --graph CHEMICAL_GRAPH.json --name 02_graph --max-candidates 6 --add-hydrogens --donor-basis "Protonation specified by the supplied chemical graph"
```

流程：对当前模型做占有率/UNIT/对称检查 → 用周期性距离建立邻接图 → 一一匹配全部重原子 → 枚举 C/N/O 指认类别 → 从同一未加氢模型分别精修 → 检查收敛、ADP、图连接和氢规则 → 输出暂选方案 → 按新标签生成 HFIX → 精修并发现氢键。所有方案、命令、指标、图映射、输入哈希及失败原因保留。`finish` 仍要求科学复核，仍运行权重检查、本地 A/B、IUCr 官网和双语 Word；匹配成功不能跳过这些步骤。

## 边界与审阅门槛

- 仅枚举 C/N/O 互换；其他元素作为固定锚点。所有重原子必须一一匹配；缺原子、溶剂未包含在图中、连接不符则转审阅，不补造原子。
- 目前支持满占有率、一般位置、无无序且无显式立体化学的模型。特殊位置、PART/RESI、孪晶、坐标约束、已有氢、显式手性/双键立体信息等停止自动路线。完整结构而非一份分子的图是输入要求；不猜测 Z′、组成或价态。
- 建图使用 Gemmi 共价半径：C/N/O 使用图中可能类型的最大半径，半径和加 0.25 Å。距边界 ±0.05 Å、过近重叠、自对称成键或多对称像成键均转审阅。该启发式不覆盖所有配位化合物和聚合物。
- 元素、氢数、HFIX 和氢键受体排除规则在各位置都相同的标签排列归为一类；保存排列数。此压缩包括等价 Lewis 共振标签，绝不代表完成手性判定。
- 最多六个类别、20 万搜索节点；搜索截断不选答案。候选均使用同一源模型、同一反射和相同精修设置，无 OMIT、额外限制或占有率调整。
- 暂选需所有候选执行完；候选收敛 max shift/esd ≤0.01、无 NPD/其他门槛问题，图/H规则通过、R1≤0.12、0.5≤GoF≤2。最佳与所有其他候选的 R1 间隔需至少 max(0.003, 最佳 R1 的5%)，反射数相同。低 R 但有异常的竞争方案同样阻止轻率选择。门槛是审阅规则，不是正确率估计。
- 歧义、异常或不支持的情形输出 `needs_review`，由人/AI检查本次数据证据。不要为了通过而放宽门槛或套用旧映射；科学判断需保留理由。

## 产物与复现

运行目录内 `<name>/proposal.json`、`result.json`、每候选 plan、所选 `mapping.json`、`hydrogen_decisions.json`、`hydrogen_plan.json`；原生文件在 `session/stages`。H方向由本次 SHELXL 重新产生；图规定氢数不是旧 H 坐标/AFIX 的复用。公开报告应说明化学先验、脚本候选范围及局限。`test_graph_assignment.py` 使用合成图测试排列、歧义、截断和质量门槛，不包含历史案例坐标。


相同且彼此分离的完整组分可减少重复匹配。程序逐个比较元素、电荷、氢数及键级，并核对候选片段数量。只省去整份等同组分互换编号的排列；仍枚举各片段内部会改变元素、加氢或受体排除的方案。支持不超过 32 个重原子的树形片段和简单单环。记录等价排列数。无序 PART、部分占有及特殊位置沿专门路线处理。

For identical disconnected trees or simple rings (up to 32 heavy sites), Cairystal checks atom attributes, bond orders and the number of compatible connected components before pruning whole-copy permutations. Internal alternatives with different site treatments remain candidates. This optimization applies to separate full-occupancy fragments on general positions.
