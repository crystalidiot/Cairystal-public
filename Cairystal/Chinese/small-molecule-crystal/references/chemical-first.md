# 化学合理性优先，A/B其次

用户于2026-11-23更新了优先级。本规则取代旧的“先消A/B，再考虑模型”偏好。checkCIF仍完整运行；它检查结构报告的一致性与完整性，警告数量不等于化学正确性。[IUCr服务说明](https://checkcif.iucr.org/)

## 主线判断

1. 初解后先核对可能元素、化学连接/价态、键长与构象、H及质子化、电荷与组分、占有率和特殊位置、ADP和差值密度。二维式或参考模型是待与数据核验的先验，不强迫数据符合预期结构。
2. 用本次数据比较元素指认、无序取向和完整组分的备选方案。保留基线、失败路线、限制依据、组成/占有率核算和参数稳定性。无AB也要处理已发现的化学矛盾。
3. 优先采用化学更合理且有衍射支持的模型；在合理性相近的候选中，再考虑AB、收敛和模型复杂度。允许合理模型有剩余AB或稍高的R，但须说明对应问题。
4. 依选定模型重新精修、权重检查、PLATON、官网checkCIF和中英文Word。解释警告不是消除了警告；未解决项在报告中明确保留。

这不是要求客户填写更多表格。常规判断和有依据的试修由助手继续完成；不能仅凭全局R或零AB自动判对。

## 脚本怎样比较

自动试修保留全部诊断，`chemical_priority`分为：`supported`（已记录且与当前模型配对的支持证据）、`not_assessed`、`needs_review`、`contradicted`。没有发现几何问题并不自动等于化学检查通过。排序是复核顺序，不是自动批准结构。

有实际化学复核后，可用已有比较脚本重排，避免重跑SHELXL：

```text
python -B scripts/compare_diagnostic_trials.py --control CONTROL/result.json --results TRIAL/result.json --chemical-reviews REVIEWS.json --output NEW_COMPARISON.json
```

`REVIEWS.json`按试修名称索引。每例包含当前`paired/case.cif`的`model_sha256`、具体`basis`，以及`checks`：`connectivity_and_elements`、`geometry_and_hydrogens`、`composition_charge_occupancy`、`symmetry_and_disorder`、`adps_and_density`、`diffraction_support`。每项为`pass`、`not_applicable`、`uncertain`或`fail`。未知不能填pass；这些是助手的复核记录，不是软件自行证实的结论。

如筛查的短键来自真实受张力结构，须在`addressed_flags`逐项给证据和解释，原警告仍保留。NPD或H/母原子PART-占有率不一致不能靠文字说明自动越过。现有几何限制冲突未解决时，小清单OMIT仍可作为独立对照，但不自动接管最终工作模型。

## 有参考结构时

常规任务可读取用户提供或已允许使用的模型，包括用户给定样品目录内的已有CIF/RES/INS模型，不必因“不是独立解析”反复询问。先判断是同一样品、相似化合物还是仅化学连接参考；核对晶胞/空间群设置、数据对应、完整组分和占有率语义。不同衍射数据必须重新精修。参考坐标、比例、H和限制不天然正确，不能直接搬来消警告。参考的低R/少AB不作采纳依据。

已明确要求盲测、只读指定输入或不看旧模型时，仍遵守该次约定。不要自动搜索隐藏答案。记录借鉴了什么，把“参考模型辅助”与“无参考独立解析”区分；参考对照也不等同于完成正确性评分。

给`finish`或`complete`的既有review JSON可增加：

```json
{
  "chemistry_and_h_reviewed": true,
  "basis": "这里填写本次模型、化学及衍射证据的实际复核依据",
  "model_origin": "reference_assisted",
  "reference_model": {
    "path": "D:/authorized/reference.res",
    "sha256": "填该参考文件实际SHA256",
    "use": "starting_coordinates",
    "comparison_basis": "说明与当前样品的关系、设置转换及哪些内容已经重新核验"
  }
}
```

`use`也可为`chemical_connectivity`或`comparison_only`。脚本先检查盲测/独立模式冲突，再核验参考指纹，将用途写入中英文报告。它只处理来源记录，不自动导入坐标或替你认可参考模型。`basis`等字段必须填写实际证据，不能复制示例当完成证明。
