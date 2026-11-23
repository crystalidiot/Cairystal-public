# Cairystal

本项目当前优先级（2026-11-23）：化学合理性与本次衍射支持优先，A/B其次。参考模型可在允许范围内使用并记录来源；盲测禁读答案的约定不变。见[化学优先](chemical-first.md)。

中文版本，默认用中文与客户交流。英文入口为 [SKILL.en.md](../SKILL.en.md)；两版共用相同计算代码，均须生成中英文 Word。语言范围见 [语言选择](language-selection.md)，新电脑或新 agent 先读 [开始使用与交接](../START.zh-CN.md)。

常规工作由脚本完成，不确定的科学判断交给 agent 或专业人员。只读当前问题所需的参考资料，不一次加载所有手册或历史案例。脚本执行完成、精修收敛、低 R 或零 A/B 都不能证明结构正确。

## 输入与必须保留的约束

- 通过 [一次收集信息](one-time-intake.md)，优先使用 `intake_once.py form --language zh-CN`，集中询问所有缺失信息：可能元素（含溶剂、反离子）、化学背景/二维式、颜色/形状/三个尺寸和处理偏好。提供颜色、形状选项及示例“绿色、块状、0.050 × 0.051 × 0.052 mm”，但示例不能自动填成实测值。复用本颗晶体已知事实和授权；可选信息未知就保存未知，不分多轮追问。只有新出现的关键冲突才集中补问。未确认默认值仅保留在标明的草稿中，不写入实测 CIF 字段。
- 原始文件及哈希保持不变，在新目录运行，保留失败候选及模型/数据变更依据。元素清单不是原子数或分子式；记录 SFAC 顺序、空间群及设置、组成假设和数据处理来源。
- 遵守当前任务的盲测输入范围，不能读旧坐标、参考身份、文献反查或历史案例答案。披露对话中已有的信息接触，只用允许的本次证据，案例之间不得借用模型。
- 优先后台运行 SHELX/PLATON，不常规打开 Olex2。交付前聚拢片段，通常使用 LIST 4，保留 PART/FVAR、特殊位置和占有率核算。按 [常规孪晶分流](routine-twin-routing.md) 处理：无具体孪晶信号时不额外搜索；支持的 HKLF 4 双组分孪晶自动核对文件，BASF 批次尺度不误判为孪晶。HKLF 5 等未支持格式、同位素处理、复杂化学或元素指认歧义须明确复核。
- 实验参数不能用模型派生值替代：晶胞测定反射数/theta 与精修反射数/theta 不同。CIF 温度单位为 K，TEMP 为摄氏度；无来源且无明确授权假设时保持未知，不能把用户提供的衍射温度无条件替代晶胞测定温度。用户已约定缺省室温时，遵循 [室温假设规则](user-temperature-default.md)，先核查允许的原始记录和冲突，再按约定填写并在 CIF/报告披露假设来源，不伪称实测。
- 明确提供的匿名实验参数侧文件走 [七字段导入](anonymous-experimental-sidecars.md)，验证案例与输入哈希，保留两种温度字段，沿用来源账本、TEMP 同步和重新精修检查。仅含元数据的 CIF 不是结构，不能作为最终 CIF 交付。
- 面向无晶体学基础的客户，用清楚的中文说明当前阶段、未解决问题、由谁处理和已生成哪些文件，技术日志单独保留。软件或科学判断由 agent 诊断，不要求客户编造空间群、限制指令或 SMILES。见 [新手可靠性](beginner-reliability.md)。

## 常规执行

1. 读取固定版本及本机 profile；如果 profile 明确提供 `project_preferences`，先核对其哈希并读取适用本项目的用户约定，保留本次使用记录。用 `runtime_capabilities.py --profile PROFILE.json` 按功能检查依赖；新电脑按 [环境说明](portable-environment.md) 建配置。`probe_environment.py` 检查程序位置，但文件存在不等于能运行，不能照抄其他电脑的绝对路径。
2. 使用 `intake_once.py accept` 接收一次性问卷，生成固定记录、已确认样品信息及 autorun 配置。常规任务执行 `crystal_autorun.py run --config JOB.json --output NEW_RUN`，串联新解析、二维图/氢匹配、本地收尾和已授权交付。不编造化学信息，不单凭 R 选择空间群。
3. 当前脚本化初始化支持原始 HKL/P4P。先遵循 [P4P 方言与原生输入检查](p4p-native-input.md)：Rigaku/SAINT 温度来源、可选 SAINGL、六方 Laue 操作和 SHELX 输入预检；不能根据数值大小猜温度单位。其他允许格式用 [workflow](workflow.md)、`inspect_case.py`、`setup_job.py`、`run_crystal_stage.py`，不静默编造前提。详细命令见 [脚本流程](scripted-pipeline.md)、[自动调度](automatic-dispatch.md)。
4. 有完整二维化学图时用 `crystal_pipeline.py match` 和 [图匹配](graph-matching.md)，按 [氢与报告规则](hydrogen-and-report-rules.md) 生成加氢计划。电荷、质子化、原子匹配或无序不确定则返回复核包。几何加氢仍需精修、接触/差值密度及 AB 检查，不能套用旧加氢方案。
5. 支持范围内用 `autofinish`；其他情况提供有依据的科学复核给 `finish` / `routine_finish.py`。均保留权重稳定性、文件配对、占有率、[一致性](routine-consistency-checks.md) 和本地 PLATON 检查；不覆盖同名试验，使用 `compare_ab_alerts.py` 保留新增/消失/未变的具体 A/B 警告。
   最终验证及报告之前执行 [按元素编号](final-atom-numbering.md)，保持原生原子行顺序、PART/AFIX 和所有原子引用，保留旧新编号映射。命名歧义不能猜；CIF 原子/各向异性行和两版 Word 使用一致的元素及数字顺序。改名后重新生成原生输出及验证。
6. 上传授权只约束联网阶段，不阻断本地精修。授权未决定时先本地收尾，取得或复用当前数据授权后从封存检查点恢复，不再重复解析。模型、说明、配置或代码改变即失效旧 ready 检查点。提交结果不明时不重复 POST；`iucr_validation.py recover --directory OFFICIAL_DIR` 只取已生成 URL，并核对其与固定上传 CIF 的对应。
7. CIF 和 SHELXL 成功只是中间状态。手工准备的本次候选经化学/氢复核后走 `complete_candidate.py`（项目入口 `complete`），串联保留对照的继续精修、权重、AB、已授权官网验证和两版 Word。依 [完整交付](delivery-completion.md) 执行 `delivery_contract.py` 后才能称文件交付完整。本地用 `platon_check.py` / `platon-check` 等报告写完并记录实际规则版本。现代 PLATON 可内置规则，缺少外部 check.def、初始空报告或命令返回都不足以证明缺规则；只记录真实原生错误，见 [PLATON/PDF 可靠性](platon-and-pdf-reliability.md)。本地工具不可用不自动阻止已授权官网验证。未解决 AB 的结果可作为临时诊断报告，但不能称科学上已接受。
8. 最终客户副本放在 **`<原始样品数据目录>/Cairystal`**。收尾脚本复制已检查的确切文件、验证哈希，返回 `customer_notice` 及四个 `customer_delivery.files` 路径。重复运行在 Cairystal 内新建日期子目录，保留旧结果。中间候选使用 `complete --data-dir ORIGINAL_DATA_FOLDER`，不能从临时精修目录猜客户位置。结束时明确告知返回的保存路径；只读输入范围或恢复见 [客户交付](customer-delivery.md)。

完整解析/精修任务最后必须分别提供 **四个可点击文件链接：最终 CIF、IUCr_checkCIF.pdf、中文晶体学 Word、英文晶体学 Word**。PDF 对应确切最终 CIF，两版 Word 来自同一模型。文件夹、网页、ZIP 或 Markdown 不能替代四个直接链接；缺项必须说明原因，标记交付未完成，不能伪造。保留配对的原生文件和独立完整审计日志。报告渲染 PDF 只作内部 QA，不作为额外晶体学表 PDF 交付。

`autofinish` 可以通过 [自动排版与科学说明检查](automatic-report-review.md) 封存，但必须写明未实际目视检查；手动封存的逐页复核标志必须有真实检查依据。中文报告不能堆英文日志。报告完成后脚本生成并封存离线 [交互结构界面](interactive-structure-viewer.md)，含元素颜色/图注、PART 筛选、原子信息及有边界的对称聚拢；默认请求打开浏览器，尊重 headless/批量选择，不重复开页。HTML 为补充，提供链接但不替代四份主文件；界面故障独立记录，不掩盖有效报告，也不代表科学成功或失败。

## 按问题加载知识和脚本

| 情况 | 使用路径 |
|---|---|
| 实验参数缺失、B196/TEMP | [参数预检](experimental-metadata-preflight.md)、[来源账本/同步](metadata-and-disorder-comparison.md)、[温度同步](temperature-synchronization.md)。按 [项目侧文件检查](project-metadata-companions.md) 核查允许的同名 metacif/phil/PCF/cif_od/P4P/日志，保留来源行号、温度/设备级别及 HKL 配对冲突，TEMP 变化后重新原生精修。 |
| A/B、不收敛和系统误差 | [AB 处理](ab-alert-action-playbook.md)、[不收敛](nonconvergence.md)、[系统误差诊断](systematic-error-diagnostics.md)。先定位具体原因再做限制、坐标/氢修改、权重或有证据的 OMIT 对照。 |
| 无序、占有率、ADP 或短键 | [无序与占有率](disorder-occupancy.md)、[ADP 选择](adp-model-selection.md)、[短键诊断](short-bond-disorder-diagnosis.md)、[限制与核算](restraint-and-accounting-audit.md)。用本次原子诊断包和 [有界试验](atom-diagnostics-and-trials.md)，同时比较几何、ADP、差值密度、不确定性、约束和模型复杂度，不能只数警告。 |
| CF3、叔丁基、短烷基链及常见溶剂无序 | [常见无序脚本](common-disorder-automation.md)。收尾复核自动附只读筛查；`common_disorder.py prepare` 生成当前密度支持、哈希固定的 ISO/ANI 对照，`run` 运行未改对照、候选 SHELXL/本地 PLATON。已有氢跟随母原子、PART 和占有率。特殊/部分占有率、无足够密度或不支持化学需复核，不自动替换最终模型。链共享枢轴候选目前还需核心轨道重合门禁的专门审阅。 |
| 主体可靠而弥散溶剂困难 | [SQUEEZE](squeeze-workflow.md)：`squeeze_request.py prepare` 生成一个针对本模型的客户选择或复用已保存选择，`respond` 记录，`execute` 在无 LLM 调用情况下运行保留对照的方案。须有主体/溶剂归属及电荷/组成复核，不能自动删原子。目前原生分支支持非孪晶 HKLF 4 与未缩放 ABIN；每次精修/导出携带匹配 FAB，仍须元数据、AB、已授权官网及双语 Word。 |
| 化学、氢或验证对应不确定 | [化学与密度](chemical-model-and-density.md)、[验证证据](validation-evidence.md)。未知保持未知，脚本不制造科学接受结论。 |
| 本地图像识别和知识检索 | [本地图像 v2](local-image-v2.md)、[案例分流](case-learning.md)。可选实验功能，披露模型可用性和训练重叠；不能删同位素标记或在盲测中读受保护历史案例。 |

先读紧凑的 `handoff.json` / `decision_packet.json`，再读其引用证据；提问前复用 intake。科学结论保留为有依据的假设，新生成 CIF 不自动等于已接受。

## 署名、跨电脑、更新和反馈

Word 大小写、斜体、上下标、版本回退及故障反馈见 [更新与支持](updates-and-support.md)。科学排版不改变原子标签/CIF 数据。`support_report.py` 保存本地解释和最小反馈 ZIP，不自动发邮件、上传或把晶体文件放进反馈包。失败时给客户确切诊断路径。`assets/support_contact.json` 统一配置报表末尾邮箱和微信；切换新版时，旧任务仍使用原固定版本。

两版 Word 使用小字号 Cairystal 辅助说明；派生 CIF 在哈希/验证前添加 ASCII 注释 `# Structure solution and refinement assisted by Cairystal.`。保留真正的 SHELX/PLATON 来源和 IUCr 原始 PDF；这不是作者资格或官方背书。见 [署名与来源](credit-and-provenance.md)。

交接时读 [agent 交接](agent-handoff.md) 及 [开始使用](../START.zh-CN.md)。文档知识、已执行代码和科学验证范围不同；这不是神经网络重新训练，不保证不同 agent 能力相同。[知识索引](skill-detail-map.md) 中历史案例只是可选学习材料，盲测排除。源码发布和安装包保留 [第三方声明](../THIRD_PARTY_NOTICES.md)、`licenses/`，依 [再分发说明](redistribution-licenses.md) 处理；Gemmi 的版本声明不能替代其他依赖的许可核对。

## 原生诊断与 CIF 读取检查

正负 PART、BIND、拆分或移动母原子后的氢，按 [原生限制与氢几何核查](part-hydrogen-native-audit.md) 处理；通用连接筛查有适用边界，警告减少不能证明溶剂几何正确。CIF 已有参数但报表显示未提供、或参数继承误报时，见 [CIF 标签大小写](cif-tag-case.md)。

## Two-question initial intake

先检查获准读取、属于当前样品的实验文件，并复用已有回答；只有两类信息都缺失时才同时提问：（1）颜色、形状和三维尺寸（mm），给出标准格式与未知选项；（2）所有可能元素（含溶剂/反离子）和可选二维结构图片。文件中已有的信息直接沿用并记录来源，不再询问或要求重复确认。部分缺失只问缺项；记录冲突只核实冲突项。通过 `intake-form --metadata-ledger` 生成对应提问清单，详见 one-time-intake.md。图片不是已验证化学图；上传授权另行记录并复用，不以沉默表示同意。
