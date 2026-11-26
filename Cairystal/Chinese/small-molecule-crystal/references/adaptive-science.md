# 按结构选工具 / Adaptive scientific work

目标是用衍射数据建立可信的化学模型。SHELXT 的元素标签、画出的键、低 R、漂亮椭球或零 A/B 都只是证据的一部分。没有完整二维式，不代表不能继续；无需让客户编造 SMILES。适用范围有限的是某个脚本，不是 SHELXL，也不是这个任务。

## 主线走不通时仍由助手继续

1. 查看当前候选 RES/CIF、LST、差值密度和允许元素，先区分：普通有机片段、配位环境、可能的簇/硼笼、PART/特殊位置以及单独的溶剂区。`model-strategy` 会给出几何筛查和可调用工具，标签是路由提示，不是化合物识别。
2. 普通且适用的片段继续用图匹配和加氢脚本。模板不适用的部位，助手根据当前证据编写派生 INS，调用原生 `stage` 精修；保留基线和有化学意义的备选。不要求为了过程序检查先给整个配位结构指定普通有机单/双键。
3. 比较元素/几何、占有率、ADP、残差、收敛、组成和限制影响后选择工作模型。`complete` 接受实际模型和书面的本次化学/H复核记录，不依赖 graph-matching 的结果；它仍执行原生精修、权重、本地验证和已授权的官网/双语交付。
4. 失败要区分：程序输入/环境错误、该工具不支持、证据不足、数值失败。前两者先换适用工具或修复输入，不能都解释为“用户需要完整结构式”。没有新的假设/证据则保留当前最佳模型与明确待核实点。

```text
python -B cairystal.py run model-strategy -- --directory CURRENT --stem model --elements B C N O Ti H --output NEW_STRATEGY.json
python -B cairystal.py run stage -- --executable SHELXL --ins NEW_CANDIDATE.ins --hkl ORIGINAL.hkl --output NEW_TRIAL --reason "current-data hypothesis"
python -B cairystal.py run complete -- --input SELECTED_CURRENT_TRIAL --profile PROFILE.json --review CURRENT_REVIEW.json --output NEW_FINISH --data-dir ORIGINAL_DATA
```

路径是占位符；从本机 profile 与本次 handoff 取实际路径。只有本例已有官网上传授权才加 `--authorize-iucr-upload`。`CURRENT_REVIEW.json` 记录真实已做的化学及氢复核：`chemistry_and_h_reviewed`、`basis` 及剩余问题；不能为让程序继续而虚填。ABIN 模型携带配对 FAB；对照使用原始反射。此路线不需要关闭一致性检查。

## 将原生候选接回同一任务 / Return a native candidate to the same job

```text
python -B cairystal.py run autorun -- continue-native --run CURRENT_JOB --candidate CURRENT_REVIEWED_MODEL --review CURRENT_REVIEW.json --name native_01
```

这是助手的工具，不是需要客户逐项填写的新问卷。`review` 使用已有的真实化学/H复核记录；已知 model_sha256 必须匹配。可在缺图、图匹配不适用或匹配后的元素/氢方案需要修改时使用。选定候选的 HKL 必须与本任务原始 HKL 一致；OMIT 指令可以在派生 INS 中保留，原 HKL 不变。真实重索引/转换的数据走独立且记录转换的任务，不能混作同一份数据。

原数据没有 P4P 时，唯一 HKL 或以 stem 明确选定的 HKL 也可建立样品绑定，包括中文文件名。这只解决任务身份，不生成晶胞或采集参数。HKL/INS 等输入可依据实际文件准备原生 stage，再从配对的 INS/RES/CIF/HKL/LST/FCF 续接；常规原始求解助手的格式限制不是整项任务的限制。

脚本保留原调度记录及每个分支，把候选快照交给已有 complete，沿用本任务的 profile、原数据交付目录、上传选择、时间/权重预算。不重跑 SHELXT 或旧图匹配。准备中的模型仍直接用 stage；这一步是已做实际复核后的收尾，不能把未知情况假填为通过。

`autorun resume --run CURRENT_JOB` 在有原生分支时继续该分支。已有本例上传授权会复用；没有则保留本地精修/检查结果。官网故障或报告异常的具体续跑入口在 handoff.json 的 native_completion/continuation 中，修复后 resume 核对实际文件；不因页面失败重解结构。已完成旧分支不覆盖，新方案使用新 name。这个入口不会自动证明模型正确，也不会把剩余 AB 隐藏。

The native branch accepts a reviewed same-specimen candidate after an organic helper is unsuitable, including after graph matching already ran. It keeps previous checkpoints and candidates, snapshots the current input, reuses machine profile and actual upload choice, and calls the existing completion workflow. No solve/graph replay or new customer questionnaire. Resume stays on the native branch; official/report problems use their actual checkpoints. Supported chemistry precedes alert counts.

Specimen binding also supports a unique or explicitly stem-selected raw HKL without P4P, including non-ASCII basenames. This does not invent cell/experimental metadata or extend the vendor-specific raw solver's formats. Prepare native input from the actual available files and continue its paired INS/RES/CIF/HKL/LST/FCF bundle.

## 硼笼 / 配位结构

- B/C 簇中的接触数不能直接当成普通碳的价键数；配位 O/N 与金属相连也不能因忽略金属邻居就被判成“孤立水”。多中心键、桥连和配位几何应结合整个片段判断。
- 元素表有 B 但模型没有 B 时，列为值得检查的缺项，不能自动补固定数目的 B。已有多个 B/C 的闭合接触片段只提示可能的笼，不能自动称 C2B10 或给定 closo/nido 类型。
- B/C 指认比较相同数据、权重和模型自由度的局部/组合假设，结合取代位、局部几何、ADP和差值密度；热参数或最小 R 单独不够。保持可疑位点的身份不确定性，必要时比较元素混占模型，不能擅自宣称“已经认出硼笼”。
- 簇顶点的 B–H/C–H、桥氢、金属氢不套普通 CH2/CH3 的自动计数。依据适用的几何和密度准备原生氢模型，检查实际输出与占有率。普通有机外围可继续使用已支持的规则。

## 溶剂与 SQUEEZE

主体已有支持而单独的溶剂区域难以显式建模时，可以并行比较显式溶剂和 SQUEEZE，不用先把所有 A/B 消除。`squeeze prepare` 会复用本例问卷的 `allow_if_justified`，没有该授权时集中问一次；明确拒绝则不运行。不要把别人的截图或聊天里的“直接 SQUEEZE”当作当前样品授权。

先检查孔隙、全差值图、主体/溶剂边界及电荷；“离分子约4 Å有Q峰”本身不是溶剂确认。不能把未识别的笼顶点、配位组分或关键反离子随意掩掉。保留未掩膜模型、原HKL、FAB、孔隙体积/电子数和前后结构指标。电子数通常不能唯一推出溶剂名称或计量数；截图中的69电子或29%体积不是通用参数。采用后仍完成 checkCIF 和报告，披露组成的不确定性。

## English

Treat helper applicability limits as routing decisions, not global scientific failure. Review current data, prepare native INS candidates when graph/H templates cannot represent clusters or coordination, and finish through `complete` using an evidence-based model/H review. No complete organic graph is required for this branch. The agent continues routine work; customer questions are limited to genuinely missing facts, changed scope or missing authorization.

`model-strategy` flags possible B/C contact clusters and coordination environments; it does not identify a compound. Do not apply ordinary carbon valence or water heuristics to those sites. Native B/C/H alternatives require full-fragment, density, displacement and charge evidence. SQUEEZE is an eligible parallel solvent strategy once the host/mask separation is supported, without a zero-AB prerequisite; retain raw reflections and matching FAB, reuse actual case consent and report mask/composition uncertainty. None of these hints bypasses scientific checks or proves the user's pictured case solved.

## 技术依据 / Primary sources

- [SHELXL 原生指令：AFIX、ABIN、PART、SFAC](https://shelx.uni-goettingen.de/shelxl_html.php)
- [PLATON SQUEEZE 方法论文](https://journals.iucr.org/c/issues/2015/01/00/ln3172/)：溶剂可达区域的贡献进入计算结构因子。
- [IUCr 硼笼顶点指认实例](https://journals.iucr.org/e/issues/2014/12/00/pk2536/index.html)：说明 B/C 顶点与可能混占需要专门证据，不提供本项目任何样品的答案。

这些材料支持方法边界。当前模块是几何分流与交接改进，不是训练得到的硼笼识别模型。
