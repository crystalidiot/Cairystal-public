# 从处理经验到可执行修复对照

`repair-plan` 是局部对照工具，不是按警告编号自动修改结构。先用 `route-problem` 和 `diagnose` 找原因，再提交本例的原子、假设和证据。无需重走初解主线，不读取历史案例坐标。

## 一次完整调用

在 skill 根目录执行，替换占位路径。原目录至少要有同一轮的 INS、RES、HKL、CIF、LIST 4 FCF、LST。它们须通过配对与执行检查；缺文件或占有率账目不一致先解决，不能用旧文件凑齐。

```powershell
python -B scripts/toolbox.py run repair-plan -- list
python -B scripts/toolbox.py run repair-plan -- prepare --baseline CURRENT --stem model --request REQUEST.json --profile PROFILE.json --output NEW_COMPARE
python -B scripts/toolbox.py run repair-plan -- run --plan NEW_COMPARE/plan.json
```

prepare 产生冻结基线、修改预览、诊断与计划；不启动精修。run 核对基线/实现/软件哈希和方案定义，调用 SHELXL 和本地 PLATON。每个候选从同一基线开始，另跑未修改对照，逐个保存成功或失败。原 HKL、WGHT、晶胞、空间群、TEMP、OMIT、孪晶控制和 ABIN 都保持原样。它不上传、不默认接受方案。

## 配方

所有请求都有 `recipe`、`parameters`、`reason`、`evidence`，可选 `cycles`（1–100，默认20）。evidence 必须指向本例观察；填写字符串不是工具已独立验证该事实。

| 配方 | parameters 示例 | 适用与边界 |
|---|---|---|
| element_scan | `{"atom":"N1","elements":["C","N","O"]}` | 单位点 C/N/O 替代；候选必须在输入 SFAC 中。更新模型 UNIT，不把它当已确认分子式。已有骑乘 H 的母原子拒绝这一简化路线。 |
| adp_local | `{"atoms":["C1","C2"],"methods":["RIGU","DELU","SIMU","ISOR","ISO"]}` | 每种方案单独精修，显式局部 ANI 非氢原子；不默认对全分子加限制。可指定 sigma、terminal_sigma、SIMU cutoff；默认0.04/0.08/1.7 Å只是宽松试验起点，非通用最优值。 |
| geometry_local | `{"restraint":"DFIX","atoms":["C1","C2"],"target":1.50,"sigma":0.02,"basis":"本例已核对的键型和距离依据"}` | DFIX/DANG 一对原子；SADI 多对、FLAT 至少4原子，不需要 target。示例距离不能照搬到所有 C–C 键；支持0.005–0.2的试验 sigma，强限制需另行科学复核。 |
| h_freeze | `{"parent":"C5"}` | 已有相邻显式骑乘氢组改 AFIX 3，氢数、SOF、U设置保留；不把甲基改成亚甲基，不理想化错误方向。 |
| oh_rotate | `{"parent":"O1","anchor":"C1","angles":[0,180]}` | 已有简单 C–O–H，完整占有率 PART 0；围绕 C–O 转动并保留当前 O–H 长度和 C–O–H 角，用 AFIX 3 做对照。给定1–8个角度；不是自动搜出正确水氢或氢键受体。 |
| omit_map | `{"atoms":["O1"]}` | 局部移除原子贡献的零周期差值图诊断；相关骑乘 H 同时移除。LIST 6、L.S. 0，无 ACTA。不是反射 OMIT，也不是收敛模型。 |

请求范例：

```json
{
  "recipe": "h_freeze",
  "parameters": {"parent": "C5"},
  "cycles": 20,
  "reason": "本次最终 LST 显示该甲基的转角持续振荡，检查固定方向对照",
  "evidence": ["本次 model.lst 的参数与 shift 记录", "已核对 C5 后有三颗同 PART、同占有率的氢"]
}
```

这些示例原子名仅为占位，不是某颗晶体的方案。几何与ADP列表拒绝通配符、跨PART/RESI及未知原子。现有氢编辑会检查AFIX计数、母原子、占有率、显式限制和格式；特殊位置、部分占有率OH、游离水、跨残基和依赖母原子需专门路线。

## 如何选结果

先看自动生成、逐例更新的 `trials/comparison.html`；完整指标在 `trials/comparison.json`，再打开候选原生文件和密度证据：

- 未改对照与候选的 R1、wR2、GoF、最大 shift/esd、NPD、参数数、限制数、差值极值；缺失指标保留 null。
- 完整 A/B 条目变化，几何偏离、占有率和限制冲突；失败和 map-only 的 AB 不能记成0。
- 氢方向试验附前后 D–H、潜在 H···A / D···A 与角度、对称关系和极短接触。N/O/F/Cl 近邻只是潜在受体，质子化需核对；这里不声称读取了完整差值密度图。

工具只输出候选证据与风险标记。AFIX 3、ISOR 或 DFIX 后警告减少，不能证明方向、类型或无序正确。确认后才返回主线的 `complete` / `resume-delivery`，完成权重、配套核对、本地 AB、已有授权下的 IUCr 官网 PDF 和中英文 Word。本地候选对照不能冒充官网最终验证。

来源与需要纠正的经验见[学习资料方法映射](learning-method-map.md)；本实现的离线及原生合成测试不代表真实晶体成功率。

## 中断后继续

新版对照会逐分支保存校验点。输入、程序、实现和已完成产物全部一致时，可在新目录复用已完成分支，只运行剩余部分：

```powershell
python -B scripts/toolbox.py run repair-plan -- resume --plan OLD_COMPARE/plan.json --output NEW_CONTINUATION
```

旧目录保留；正在运行的任务不能同时续跑。失败分支默认不重试，先查日志。问题确已解决且仍在同一固定环境时，可显式加 `--retry-failed`，同分支最多追加一次失败重试；代码或软件变了则重新 prepare，不能混用旧结果。旧版没有校验点的运行不自动复用。未改对照失败时停止其余分支，保留“未运行”状态。

新简表区分本次执行、已核验复用、未运行和失败；分别列出实验信息类及其余 A/B、具体警告、R1/wR2/GoF、残余密度、完整记录链接。`trial-summary --directory TRIALS --output NEW.html` 可单独导出简表。续跑耗时只计本次工作，不把旧分支耗时当成新执行。

English: `repair-plan resume --plan OLD/plan.json --output NEW` reuses hash-verified completed trial artifacts and runs pending trials in a new directory. A running job, changed inputs/code/software/artifacts or an uncheckpointed legacy run cannot be reused. Failed trials need an explicit `--retry-failed`, bounded to one repeat. A failed unchanged control stops dependent candidates. `trials/comparison.html` lists every planned branch with specific A/B alerts; missing validation remains unknown. This local report does not replace final authorised IUCr PDF and bilingual Word delivery.
