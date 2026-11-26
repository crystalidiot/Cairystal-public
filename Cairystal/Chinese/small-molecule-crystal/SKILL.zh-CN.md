---
name: small-molecule-crystal
description: Cairystal 小分子单晶解析工具箱：调用本机 SHELX/PLATON，完成解析精修、A/B 诊断、IUCr 官网 checkCIF 和中英文 Word；常规步骤脚本执行，科学歧义交 AI/专业人员。
---

# Cairystal

给定数据路径后，在独立目录调用本机程序，保留输入和对照，交付可核验的模型与报告。[English](SKILL.en.md)

**化学合理性与本次衍射证据第一，A/B 第二。** 零 A/B、低 R 或收敛本身不能确认结构。[化学判断](references/chemical-first.md)

在本次任务授权与环境权限内，工具箱不是只能调用这些命令的白名单。脚本不适用时，可直接调用原生 SHELX/PLATON，或编写本次辅助脚本；保留证据与对照，无须先修改 skill。复核后的原生候选用 `autorun continue-native` 接回当前任务，跳过已做过的求解和图匹配，见[原生续接](references/adaptive-science.md)。

## 统一入口

在本 skill 目录运行 `python -B cairystal.py version --json`，记录实际版本和路径。版本唯一来源是 `release_info.json`；已有任务用创建它的固定版本续跑。新电脑先看 [安装](START.zh-CN.md)。

```text
python -B cairystal.py workflow
python -B cairystal.py list
python -B cairystal.py describe TOOL --json
python -B cairystal.py run TOOL -- --help
```

默认 `autorun` 主线；用户要求快速工作模型时用 `fast`，见[模式差异](references/fast-mode.md)。快速版缩短试修预算，保留化学、占有率、A/B、官网及报告检查，不等于降低事实要求。


## 按结构选路线

普通有机图是便利工具，不是解析的前提。硼笼/簇、金属配位、无序或未知组成超出某个脚本时，助手继续查看本次模型和密度，使用原生 `stage` 比较派生 INS，再以 `complete` 接回精修、官网和报表。不要为了套模板改错化学，也不要因缺图反复问客户。`model-strategy` 提供适用范围提示；见[原生建模与溶剂分支](references/adaptive-science.md)。

## 一条主线

1. **输入与缺项。** 固定 profile、读取范围、新工作目录与原 HKL 哈希。先读取同样品 PCF/cif_od 等实验记录，仅集中询问剩余两类信息：颜色/形状/三维尺寸（例：绿色，块状，0.050 × 0.051 × 0.052 mm）；所有可能元素，含溶剂和反离子，可附二维式。未知留空，不能把示例当实测值。元素种类不代表原子数。[输入与问卷](references/one-time-intake.md)
2. **初解与元素。** SHELXT → 初解筛查 → 元素、连接、占有率复核。需要时比较有依据的 SHELXD 假设。`chemistry-screen` 做本轮 C/N/O 等有限对照；不因低 R 自动接受身份。[输入分流与求解](references/mainline-and-exceptions.md)
3. **加氢与精修。** 适用时：已核实化学图 → `hydrogen-continue` → SHELXL/权重 → H 数、UNIT、几何和热参数复核。不适用时直接准备有依据的原生氢/无序模型。当前推断图如实标记，不能说成客户提供的二维式。[连续化学处理](references/chemistry-handoff.md)
4. **本地验证与工具对照。** `route-problem` 找策略，`ab-auto` 执行已支持的对照。模型变化回到精修及验证；化学/无序歧义读本次密度与候选，不停在一句“需要 AI”。具体分支见[共同路线图](references/flow-handoffs.md)。
5. **官网与交付。** 固定最终 CIF/结构因子，执行已授权的 IUCr 验证；同一 CIF 已有回执则续取，不重新求解。生成中英文 Word、自动 QA、核对四份文件，保存到客户数据目录的 `Cairystal` 子文件夹，并在最终回复给出位置和剩余问题。[完成与恢复](references/delivery-completion.md)

## 共同判断规则

- 有依据的参考模型可按授权使用，盲测则不读答案；每种模型仍须与本次数据核验。
- 常规备选求解、元素/氢/权重与有证据的无序试修由助手在新目录继续，不重复询问已有事实或授权。只有必须由客户提供的事实、目标变化、尚未具备的上传/SQUEEZE 授权才询问；“不清楚”后继续可完成的工作。
- 孪晶迹象先做有界 `twin-quick` 对照；919/934 按固定清单和接受规则做 OMIT 对照，保留原数据与完整记录；SQUEEZE 保留本例授权和贡献说明。[自动 A/B 分支](references/automatic-ab-mainline.md)
- `handoff.json` 的下一步属于助手时，继续执行。科学不确定保留部分模型与证据；网络/报告故障从交付断点恢复，不重解。最终缺少 CIF、IUCr PDF 或任一语言 Word，须明确未完成。

## 按需工具

`describe` 给出输入、输出、依赖、副作用、适用边界和主线位置；原程序退出码和日志保持不变。[工具索引](references/toolbox.md)只在需要时查阅，无须每次加载全部知识。

按样品续跑使用 `--expected-hkl` 和选定 CIF 指纹：[续跑](references/case-resume.md)。自动修复能力以实现和本次日志为准；路线图不是已经执行修复的证据。

交付完成会自动同步顶层任务；旧任务恢复见[交付状态同步](references/delivery-state-sync.md)。
