# One mainline with evidence-driven A/B routing / 一条主线与 A/B 自动分流

The executable defaults live in `assets/ab_policy.json`, not in a paragraph that an agent must reinterpret. `ab-auto` consumes an exact paired INS/RES/HKL/CIF/FCF/LST bundle and the matching, hashed local PLATON validation directory. It writes an independent baseline, diagnostics, explicit hypotheses, previews, one contemporaneous control, native logs and a ranked comparison. It never edits source inputs or performs IUCr uploads.

`routine_finish.py` now calls this route when its local check has A/B findings. Thus the normal `autofinish` route prepares/runs applicable hypotheses before returning its specific unresolved evidence to the agent. General chemistry/disorder hypotheses remain review candidates. The verified 919/934 fixed-list OMIT branch can adopt a working model using its explicit stability, reflection-set and validation checks; it remains excluded from same-data R ranking. Weight review already occurs before this branch; early chemistry or convergence gates may stop before reaching it. A selected hypothesis must pass the applicable model checks, refinement, paired validation and delivery. Selecting an old result while citing new trial metrics is prohibited.

## 自动执行边界

211–216 另自动附加 `adp-directions` 的长轴/残余峰证据。缺少可选 NumPy 时仅记录该工具不可用，不阻断其它诊断。已有水 H 的方向候选通过 `water-h-trials` 调用，需先给出水与受体的化学依据，不从 420 编号自动猜受体。

在候选生成前，相关 A/B 自动调用[证据工具](donor-reflection-tools.md)：306/417/420/430 → `donor-audit`；918/919/934/939 → `reflection-audit`。结果写入 `evidence/` 并附到 finding；每工具每轮只调用一次。不支持的权重留 null，工具失败保留原因，不把失败当零警告。这一步只收集证据；下表仍定义实际可执行的模型修改。

Before candidate preparation, relevant A/B routes attach read-only donor/reflection evidence. These tools do not add H, omit reflections or adopt a model; unsupported values remain null and failures remain explicit.

| 当前证据 | 自动候选 | 不满足时 |
|---|---|---|
| 213/214 明确指向一个各向异性原子；无部分占有、近旁明显差值峰或严重几何/指认疑点 | 一个局部 ISOR 对照 | 优先查无序/指认；不会全分子强行 ISOR |
| 234 明确原子对，同 PART/RESI，已聚拢的几何成键候选 | 分别比较 RIGU 和 SIMU | 先解决配对、化学或无序问题 |
| 241/242 单个 C/N/O 位点，原 SFAC 有候选元素，无附属骑乘氢冲突 | 分别比较原 SFAC 中的 C/N/O 方案 | 不引入未知元素、不套用旧加氢 |
| 420 明确现有简单 C–O–H，唯一 C 锚点、全占有普通位置 | 现有 H 的有限角度转动 + AFIX 3 | 水、N–H、特殊位置另行复核，不凭警告补 H |
| 080/SHFSU01，最后一轮 shift/esd 明确定位到可处理的骑乘 H | 当前 H 向量固定为 AFIX 3 | 不盲目固定所有重原子 |
| 919/934，当前权重确认 1–20 个异常反射 | 固定清单对照。检查通过即采用 OMIT 工作版继续交付 | 普通 HKLF 4。保留原 HKL。已有逐点 OMIT 时停止自动选点 |
| 参数缺失或其他警告 | 自动返回对应 tool、依据及缺失条件 | 不捏造参数；不因异常反射警告编号直接删点 |

工作版检查精修实际使用的反射集合、权重、模型稳定性和本地警告。排除数最多占原独立反射的 0.5%，两项 CIF 完整度各最多下降 0.5 个百分点。已有局部 DFIX/DANG 冲突会继续报告。可用作业设置 `allow_automatic_reflection_omission=false` 仅运行对照。

For ordinary HKLF 4 data the finishing pipeline carries a verified fixed-list OMIT working model into reporting. It checks the actual fitted indices, convergence, heavy-atom shifts, occupancies, coverage and local alerts. The CIF and bilingual methods list the indices and signed standardized residuals. Preserve the all-data model and original HKL. Respect a job request to retain all reflections.

Rules are hypotheses, not diagnoses. PLAT214 can indicate unresolved disorder; PLAT234 can reflect atom-type or data/model errors; PLAT242 also has false positives; not every PLAT420 is a misplaced H. Sources: [IUCr 214](https://journals.iucr.org/services/cif/checking/PLAT214.html), [234](https://journals.iucr.org/services/cif/checking/PLAT234.html), [242](https://journals.iucr.org/services/cif/checking/PLAT242.html), [420](https://journals.iucr.org/services/cif/checking/PLAT420.html) (checked 2026-11-06).

## 排序与停止

优先 A 数，再 B 数；只在对照可比、源文件未变且比较筛查无恶化标记的候选中推荐。几何、收敛、占有率、NPD、差值密度等不合格的“零 AB”候选不能排到合格候选前。推荐结果仍需化学/密度复核，不等于结构正确。未知指标保持 null。共享一份不改模型的继续精修对照，不为每条警告重复跑相同对照。

默认一次最多 8 个假设、每次 20 轮；不是任意晶体的固定时间限制。达到本轮候选预算、无支持改善、未支持警告或证据不明时保留记录并交给 agent。不会无止境自动加限制。实验参数警告与模型/数据警告分开显示但不隐去。只有精确模型与反射配对、当前验证文件哈希一致才会开始；共同对照失败后停止剩余比较。

## CLI / configuration

```text
python -B scripts/toolbox.py run ab-auto -- --baseline CURRENT_BUNDLE --stem model --validation MATCHING_LOCAL_VALIDATION --profile MACHINE.json --output NEW_OUTPUT
```

Add `--plan-only` for no native execution. `--policy EXTERNAL.json` accepts only `automatic_candidates`, `automatic_reflection_trials`, `allow_automatic_reflection_omission`, `max_hypotheses`, `cycles`, `adp_sigma`, `adp_terminal_sigma`, `oh_angles`, within enforced ranges. It accepts no arbitrary executable command, model-acceptance bypass or upload permission. In a finish config use `ab_policy` for that external file, or `automatic_ab_trials: false` to prepare only. All original policy values and source hashes remain recorded with the job.

The local console's `/automation` page shows this same machine-readable policy and can export a small task-specific parameter JSON. It does not modify installed skill code or silently apply a policy to a running job. An agent can attach the saved policy to a new job. Update methodology and tests in new releases; freeze ongoing benchmarks.

The autorun config now accepts `ab_policy` (path to the external overrides); it freezes and hashes that file with the job, and forwards it to `crystal_pipeline.py autofinish --ab-policy`. Both `finish` and `autofinish` accept this option. A supported improved candidate that has no implemented automatic acceptance rule pauses before uploading the older baseline, even if diagnostic reports with unresolved alerts were otherwise requested. Recommendations and pending alerts propagate to the coordinator handoff.

## CIF and quiet execution

`cif-format` checks the CIF1.1 submission boundary using Gemmi, case-insensitive duplicate tags, missing scalar values, loop width, block selection, quotes/semicolon syntax, ASCII and standard lengths. Optional model checks cover cell and atom-loop basics. Unknown `?` and not-applicable `.` remain distinct; source bytes are unchanged. Syntax checks do not replace full dictionary checks, reflection pairing, PLATON or IUCr. Read/write structural values through Gemmi; do not repair an entire CIF with regex.

The check runs after supported narrative normalization in routine finish, before local validation, and before any official web fetch/upload. It does not silently convert CIF2 or select the first of multiple blocks. [IUCr CIF1.1 syntax](https://www.iucr.org/what-we-do/digital-standards/cif/cif1/file-syntax), [Gemmi parser](https://gemmi.readthedocs.io/en/latest/cif.html).

Windows native startup requests both CREATE_NO_WINDOW and STARTF_USESHOWWINDOW/SW_HIDE. PLATON visibility is sampled only for the job's own process. No global window suppression, closing of unrelated apps or security setting changes. Software can override startup visibility or create another process; no absolute no-popup guarantee. [Python subprocess](https://docs.python.org/3/library/subprocess.html), [Microsoft STARTUPINFO](https://learn.microsoft.com/en-us/windows/win32/api/processthreadsapi/ns-processthreadsapi-startupinfow).


Updated automatic branches and constraints are documented in [the unified mainline contract](unified-mainline.md). Changed-data sensitivity trials pause for review unless the implemented fixed-list 919/934 acceptance rule passes. Zero alerts alone never satisfy that rule. See [tool continuation](flow-handoffs.md).

## Chemical-first comparison

The current objective is chemical/diffraction support first, A/B second. `comparison.json` exposes `chemical_priority` as supported, not_assessed, needs_review or contradicted; absence of a flag is not a chemical pass. Specific post-refinement reviews may be supplied through `compare_diagnostic_trials.py --chemical-reviews`; each is bound to the actual paired CIF. A supported model with more A/B can be recommended for scientific review, with all numerical flags retained. See [the evidence format](chemical-first.en.md).

Small fixed-list OMIT trials remain available. Automatic adoption no longer carries unresolved pre-existing geometry/restraint conflicts forward just because they did not worsen. Resolve or interpret the model concern first; retain both models and the full-data record. An explicitly reviewed manual choice remains a separate scientific decision.
