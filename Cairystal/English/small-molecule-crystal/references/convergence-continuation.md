# 收敛趋势与有限续算 / Convergence trend and bounded continuation

先定位 LST 中每轮最大 shift/esd 的具体参数。新加水氢附近并不一定是慢参数；本次实际定位到另一颗水氢的 z 坐标。比较原始符号和幅度，不能仅看最后一个绝对值。

`convergence-trend --directory NATIVE --stem model --output NEW.json` 只读同轮 INS/LST 与数值门禁，输出原因和建议，不自动改变模型。主线权重更新现在会调用同一判断。仅当：

- 唯一待审原因是 shift/esd 未达 0.01；执行完整、无其他失败、NPD=0；
- 最后四轮为同一个参数、同一符号，绝对值逐轮下降，末值不超过首值的 80%，并处于 (0.01, 0.2]；
- 最后一轮数值与门禁一致，没有 BLOC/XNPD/DAMP/CGLS；已打印的相关系数没有达到 0.9；

才允许按原权重、原模型、原 HKL 再算 20 轮。每次权重试验至多追加两次；每次保存趋势 JSON、新 INS/RES/LST 和命令。续算后仍执行原来的位移、占有率、ADP、反射数、R1 和收敛核查。阈值是保守的工程筛选，非晶体学定理；不符合时交诊断，不降低验收标准。未打印相关系数记 null，不伪称为零。

**水氢方向的独立检查不能省。** AFIX 3 会使 H 随母原子骑乘；氢键方向看起来合理、420 B 消失并不证明方向正确。对照局部密度和释放约束的试验。如果新方向的密度更弱、释放方向后回到旧位置，就保留新方案供检查，不能自动采纳。两套不同重原子起点的 H-omit 图可帮助检查模型依赖，但仍有相位偏倚；不等于无偏实验真值。这里省略的是诊断图中的 H 原子，**没有 OMIT 衍射点**。

本次实际验证：10 轮后最大 shift/esd=0.029 的候选不改变模型续算后达到 0.001；权重更新后的 12 轮也曾停在 0.022，新流程自动续算并通过原门禁。骑乘改向方案却未通过密度/释放约束对照，故保留 420 B 的更受数据支持的候选用于最终报告。该案例证明流程能区分“循环不足”和“方向证据不足”，不证明所有水氢可以自动修好。真实报告按其最终官网结果列警告，不把本地计数冒充官网计数。

## English

Locate the actual shifting parameter, including sign and magnitude over successive cycles. The newly modified water is not necessarily responsible. The read-only `convergence-trend` tool and the finishing weight loop use the same conservative screen: the sole review reason is max shift/esd >0.01, native execution is complete with no other failures and NPD=0, and the final four signed maxima refer to the same parameter and decrease monotonically by at least 20% overall, ending in (0.01,0.2]. INS controls BLOC/XNPD/DAMP/CGLS or reported correlations >=0.9 block this shortcut. The final LST value must match the gate. Missing correlation evidence remains null.

Eligible trials retain the same weights, parameterization and measured HKL and receive 20 additional cycles, at most twice per weight trial. All native files and trend decisions are saved. The full original model-movement/occupancy/ADP/reflection/R1/convergence checks still apply; this is not chemical acceptance or a relaxed convergence threshold.

AFIX 3 water orientations require separate density and chemistry review. In the actual test, the rotated candidate converged but had weaker H-omit density, and restoring distance-restrained positional refinement returned to the original direction. Therefore the warning-clearing orientation was rejected. H-omit maps remain phase/model biased and do not omit reflections. A remaining donor-without-acceptor alert must be disclosed when no supported repair is available. The successful transferable method is evidence-based continuation, not automatic water-H direction assignment.

Syntax reference: [SHELXL instructions](https://shelx.uni-goettingen.de/shelxl_html.php). Generic nonconvergence guidance: [nonconvergence.md](nonconvergence.md).

## 同步保留未知实验值 / Preserve unknown experiment metadata

SHELXL 未给 TEMP 时可能在新 CIF 写出 293 K。续算不是新的实验测量：已知同样品值继续沿用，温度、外观与尺寸的温度、外观与尺寸的明确未知 ? 或不适用 . 不得被新原生默认值覆盖。来源没有温度时恢复为 ?；不给未知温度写 TEMP 20。修正后的确切 CIF 重新做本地及官网验证，中英文表也重新生成；因此元数据警告可能增加，必须如实显示。

When TEMP is absent, native CIF output may contain a default 293 K. Continuation supplies no new experimental evidence. Preserve source unknown/not-applicable temperature, appearance and size scalars; absent source temperatures remain unknown. Known transmission factors continue to follow their existing source policy. Do not invent TEMP 20. Revalidate the corrected exact CIF and regenerate both reports; increased metadata alerts are reported honestly.
