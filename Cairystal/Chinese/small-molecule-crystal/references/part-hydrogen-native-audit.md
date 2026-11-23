# 无序连接与氢几何的原生核查 / Native connectivity and H geometry

用于拆分原子后限制似乎不起作用、正负 PART 混用、氢随母原子移动后几何异常，或目标警告消失但模型仍不合理。本文是通用检查方法，不含历史样本坐标、组成或占有率答案。

1. **先查实际执行的限制。** INS 中有 DFIX/DANG/SADI 不能证明所有目标原子对生效。对照最终原生 LST 的限制类别/数量、实际原子对、目标及偏差。数量相符也不能代替原子对核查。
2. **PART 连接要符合真实共存关系。** 非零 PART 会影响连接表；负 PART 还影响对称生成连接。必要时可依据化学及对称关系考虑 `BIND part1 part2`，保留未改对照并核查原生结果。不要给全部正负 PART 自动加 BIND，也不能把互斥构象连接成同一分子。PART 编号形式的 BIND 与指定原子形式的 BIND 不应当作完全等价。背景见 [Sheldrick 2015, §7](https://journals.iucr.org/c/issues/2015/01/00/fa3356/index.html)。
3. **现有脚本的边界。** `structure_diagnostics.py` 的通用几何筛查不完整复现所有 BIND/PART 自定义连接。含这些控制时，其 alternative/negative-PART 分类是待核对提示，不能独立证明一对原子不存在真实连接。以原生连接表和化学复核补充；本维护版没有新增完整连接解释器。
4. **检查氢的方向，不能只看键长。** AFIX 3 的 riding 处理不能证明任意旧 H 坐标已经成为理想几何。拆分/移动母原子、改变重原子方向后，核查 H 数量、所属母原子、X–H、邻接重原子–母原子–H 和 H–母原子–H 角、占有率/PART、Uiso 比例及共存接触。对有证据的甲基可比较重新构建的非旋转理想化 riding 组；旋转模型不稳定时不能直接视为成功。AFIX 类型、键长及 Uiso 因子仍按实际组分/温度选择，不能把一个案例的数值设为所有客户的默认。几何构造的氢应明确披露为计算位置。
5. **特殊位置重新核算。** 移离镜面等特殊位置、产生对称伴位后，同时核对 SHELX SOF、CIF 占有率、自由变量互补关系、轨道重数及每晶胞组成。CIF 某位点占有率不一定等于完整无序组分比例。氢与母原子一同核算，禁止按原子行数直接累加。
6. **成对比较才能归因。** 比较 SIMU 有/无的候选时，其他模型参数、反射、权重及循环条件要相当；观察实际 LST、几何、ADP、收敛、差值密度、复杂度与全部警告。如果没有独立改善，不能把警告减少归功于 SIMU。拆分后 ADP 警告消失而分子几何仍明显违反已知化学，必须保留“待复核”，不能自动接受。

更多依据及占有率公式见 [限制与核算](restraint-and-accounting-audit.md)、[无序与占有率](disorder-occupancy.md)、[氢处理](hydrogen-and-report-rules.md)。原生模型改变后仍需精修、权重/AB 检查、在已有授权范围内的官网验证及同源双语 Word。

## English operational checklist

- Audit actual native LST restraint pairs, targets, residuals and counts, not only instruction lines. Matching counts are insufficient evidence of correct atom selection.
- Review coexistence and symmetry before altering PART connectivity. A justified PART-number BIND trial must retain its baseline; never connect mutually exclusive conformers automatically. The current generic diagnostics do not fully implement custom BIND connectivity, so their classifications need native and chemical review.
- After splitting or moving a parent, check H count/parent assignment, lengths, both heavy-neighbor–parent–H and H–parent–H angles, occupancy/PART inheritance, Uiso factors and coexistence contacts. AFIX 3 does not certify ideal starting geometry. Rebuilt riding positions are a geometrical hypothesis, not evidence that H was observed. Model/temperature-specific choices still apply.
- Recalculate site populations and symmetry orbits when moving off a special position. Distinguish SHELX SOF, CIF site occupancy and component abundance; preserve unit-cell accounting including H.
- Use matched restraint controls to attribute effects. Convergence or disappearance of an ADP alert does not validate a chemically distorted solvent molecule. Retain provisional status until the remaining evidence is adequate. No automatic repair or scientific acceptance is introduced by this guidance.
