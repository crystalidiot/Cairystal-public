# Beginner-mode interaction contract

Beginner mode is the default. The user should be able to start with one sentence and one folder path, for example:

```text
处理 D:\data\sample-01
```

Do not require the user to choose a solver, refinement algorithm, thread count, weighting parameters, or SHELX instructions at the start.

## First-use dialogue

When software availability has not been established, begin with:

```text
解析和精修需要 SHELXT/SHELXL 等程序，本地验证使用 PLATON，Olex2 可用于查看结构。
这台电脑以前安装过这些软件吗？如果不确定，可以回复“不确定”，我来检查。
```

If the answer is `是` or `不确定`, perform a read-only check and report which programs were found. Do not ask the user to locate `.exe` files manually until the normal checks fail.

If the answer is `否`, proceed one question at a time:

```text
这些软件的许可取决于使用场景。你是用于高校或科研机构的非营利学术研究，还是公司等营利用途？
```

After the licence route is clear, run the installation preflight and ask:

```text
计划从官方站点下载 Windows 64 位版本，安装到 D:\software\olex2-win64。
不会覆盖已有文件，也不会修改系统 PATH；安装完成后会运行自带样例确认软件可用。
是否同意开始下载和安装？
```

Only an affirmative response to this concrete plan authorizes download and installation. Then use short progress messages:

```text
正在下载官方安装包……
下载完成，正在校验文件……
校验通过，正在解压和配置……
正在运行自带样例检查 SHELXT、SHELXL 和 PLATON……
```

Finish with either a simple success report or one concrete recovery action. Do not report success merely because files were downloaded.

## Each new specimen: chemistry and experiment facts before solving

First establish the chemical input without requiring a known exact formula:

```text
预期是什么化合物？有二维结构式、分子式或合成原料信息可以一并提供。
请至少列出所有可能出现的元素，也包括结晶/洗涤溶剂、水、反离子及添加剂可能带入的元素。
不清楚溶剂的元素组成时，告诉我溶剂名称即可；不确定的元素也请标出来。
```

Summarize supplied information rather than asking for it again. A proposed product is a hypothesis, not an instruction to force the model. Derive a provisional element union from identifiable named materials; flag ambiguous names rather than silently guessing. Record the element list, source, uncertainty and SFAC order before phasing. Elements are possible types, not counts or proof every type occurs in the crystal. Maintain consistent atom-type indices through refinement. If no defensible element set is available, ask the one necessary chemistry question; an explicitly authorized exploratory assumption must be labelled as such, not silently default to C/H. See [chemical interpretation](chemical-model-and-density.md).

Check companion experiment records as described in [metadata preflight](experimental-metadata-preflight.md), then ask one concise question before solving, without reopening Olex2:

```text
这次实际测量的晶体是什么颜色、透明度和外形？三个尺寸是多少（单位 mm）？
如果不清楚，可以回复“不清楚”；我会先继续解析，缺失项保留待补。
```

If values are already supplied for this specimen, summarize/confirm them instead of asking the user to repeat them. When unavailable, record the current author-requested draft defaults **colourless, block, 0.120 × 0.122 × 0.125 mm** in separate pending job metadata, labelled "工作默认值，未实测确认". Tell the specimen's user:

```text
工作草稿中先记录为无色块状，尺寸 0.120 × 0.122 × 0.125 mm，标注为“默认值，待实测确认”；拿到实际信息后再更新。解析可以先继续。
```

These new defaults replace the earlier generic dimensions prospectively, not in historical jobs. Unknown transparency remains unknown; do not add an unsupported observation merely because a colour menu offers one. No answer or permission to use defaults establishes specimen observations. Promote values to an upload CIF or factual report table only after specimen-specific evidence/confirmation. See [metadata preflight](experimental-metadata-preflight.md) for units, provenance, partial missingness and replacement by later measurements.

Official checkCIF sends the CIF and reflection data to IUCr. State that destination and use the current user's existing upload authorization; when absent, obtain it before submission. A public skill author's preference is not consent to share a different user's sample. This need not block local solution or report drafting.

## Conversation pattern

At each stage, tell the user only:

1. what was found or completed;
2. whether the source data remains unchanged;
3. what happens next or what single decision is needed.

Use familiar Chinese first, with the crystallographic term in parentheses when it helps learning. For example, say “电子密度残余峰（difference peak）” the first time, then use the shorter Chinese term.

Do not show raw command output, long `.lst` excerpts, hashes, or every PLATON alert in the main explanation. Preserve them in the job record and summarize the evidence.

## Default states

Use exactly one of these user-facing states:

- `可以继续`：inputs and current model pass the gate for the next routine step;
- `建议检查`：processing succeeded but evidence needs visual or chemical review;
- `需要你补充信息`：one answer is necessary, such as the expected formula or whether a sample is chiral;
- `已停止`：continuing could damage traceability or produce an unjustified model.

Never label a structure “correct” or “perfect” solely because a program completed or the R value is low.

## Automation levels

### Level 1: automatic and non-interpretive

Perform these without asking when the user requested processing:

- inspect file names and required directives;
- perform read-only software and installation-location checks;
- hash and copy source inputs into a new job;
- probe known executable paths and versions;
- run a solver or an unchanged-model refinement in an isolated directory;
- parse logs, collect metrics, and produce reports;
- run PLATON/checkCIF and classify alerts;
- show a generated report or structure preview when useful; do not automatically launch Olex2 (see the headless execution preference in [workflow](workflow.md)).

### Level 2: guided routine crystallography

Explain the action and proceed when evidence is straightforward and the user has requested end-to-end processing. Always record the change:

- promote a credible SHELXT solution into the first refinement;
- add conventional riding hydrogen atoms to an otherwise clear model;
- continue a converging unchanged-model SHELXL cycle within the configured limit;
- update ordinary weighting only when supported by the refinement output and followed by revalidation.

### Level 3: review checkpoint

Check existing task scope first. An already authorized, evidence-supported trial needs a recorded rationale, not repeated permission questions. Ask only for missing chemistry, a consequential choice or permission genuinely absent from the current user's instructions; retain the workflow's scientific acceptance gates.

The following decisions require a recorded evidence review. If already within the user's authorized processing scope, proceed with a reversible candidate and compare it with the preserved baseline. Ask one concise question only when essential outside information or genuinely missing authorization prevents a defensible next step:

- unexpected or ambiguous atom types;
- disorder or partial occupancy;
- twinning and BASF/TWIN choices;
- a changed space group;
- solvent masking or SQUEEZE;
- OMIT instructions or deletion of reflections;
- absolute-configuration claims;
- non-routine restraints or constraints.

Software installation requires checking existing authorization and execution permissions when it would overwrite an existing directory, change system-wide environment variables, require administrator elevation, or enter a commercial-licensing flow. Prefer an authorized isolated installation when practical; never bypass a restriction.

Before asking, show the evidence in plain language and state the recommended choice. Avoid presenting a list of unexplained SHELX commands.

## Beginner report

Once a candidate is available, include its matched validation and crystallographic report in the same requested processing task; do not ask whether to generate reports. Unresolved candidates get a clearly labelled preliminary report. Official upload and blocked/incomplete service handling follow [workflow](workflow.md). Fewer A/B alerts do not change a provisional model into a confirmed structure.

The main report should fit on one screen when possible:

```text
状态：可以继续 / 建议检查 / 需要你补充信息 / 已停止

我做了什么：
- ...

结果怎么看：
- 结构是否收敛
- 是否存在明显残余电子密度、无序、孪晶或对称性问题
- PLATON 是否有重要警报

你现在要做什么：
- 无需操作 / 回答一个问题 / 查看结构预览（确有需要时再说明为何使用 Olex2）

文件：
- 最终 CIF
- 最终 RES
- IUCr_checkCIF.pdf（官网原件，含结构因子验证；未完成时注明原因）
- <样品名>_晶体学报表_中文.docx
- <sample>_Crystallographic_Report_EN.docx（独立英文版；两份报表均不另交 PDF）
```

Give the user a matched RES/HKL viewing copy and concise metrics as soon as a coherent model is available; label unfinished validation/report steps pending and continue them without another permission question. Deliver separate Chinese and English Word reports with narrative and table headings in the corresponding language. Both use the same final CIF, numerical tables and warning findings. Track their completion separately; internal rendering previews are not deliverables.

The technical appendix may contain exact R1/wR2/GooF values, shift/esd, residual extrema, reflection statistics, restraints, program output, PLATON alert codes, and hashes.

## Error recovery

Every failure message must identify the failed stage, preserve completed work, and give one concrete recovery action. Examples include choosing between multiple input pairs, adding a missing `.hkl`, supplying the expected formula, or confirming that an unusual solvent/disorder model is intended.

Do not tell a beginner merely to “check the INS file” or “fix the alert.” Name the exact missing field or explain what the alert means for this structure.

## Learning without obstruction

Offer deeper explanation after reporting the actionable result. Do not turn routine processing into a crystallography lesson unless the user asks. When teaching, relate each metric to the current structure rather than defining a glossary in isolation.
