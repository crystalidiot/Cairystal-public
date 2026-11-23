# Explicit room-temperature convention / 用户明确采用室温的约定

## 中文

这是**用户授权的工作假设**，不是缺失实验记录的推断算法。适用于用户已明确约定“相似情况下，原始记录没有温度时按室温 293 K 处理”的项目。普通客户未作此约定时仍保存温度未知，不能因为缺少记录就断定室温，更不能根据程序默认值认定实测温度。

先读本机 profile 中明确提供的 `project_preferences` 路径，并核对其 `sha256`。这份配置供 agent 读取；现有 Python pipeline 不会自动读取它或无条件注入数值。配置必须包含启用状态、适用项目、温度值和用户授权来源。复制本次采用的约定和哈希到独立任务记录；既有固定版本任务仍使用原版本。示例模板见 [配置模板](../assets/temperature_default_policy.example.json)，默认关闭。

每颗样品执行：

1. 检查盲测范围内允许读取的同次实验原始文件及用户记录，保存文件哈希、检查字段/位置和未找到温度的结论。CIF_OD、PCF、P4P 和还原日志的实际内容优先；不得扩大访问范围寻找答案。解析失败、文件未能访问或尚未检查，不能写成“已检查且无温度”。不要求读取任务范围外的所有可能文件。
2. 任一明确实验温度优先于缺省约定。已有原生 TEMP、非未知温度字段、低温/变温线索、冲突的用户说明或未解决的解析异常，都需先核对来源，不用 293 K 覆盖。低温设备名称本身不是低温实测值，但若无法确定实验条件，应保留疑问。
3. 仅在检查范围已明确、相关可读记录无温度且无冲突时，复用当前项目已授权的室温假设，**293 K → SHELXL `TEMP 19.85`（℃）**。不是 293.15 K / TEMP 20，也不是 293(2) K；不得添加未经提供的不确定度。
4. 保留原始文件和未修改候选，在新的阶段同步 TEMP。需要重新原生精修、温度敏感氢几何检查、RES/FCF/CIF 配对、AB 检查、已授权官网验证及两版 Word。不能只编辑 CIF 数字或复用修改前的 FCF/PDF。温度约定不包含上传授权。
5. 在独立 `temperature_assumption.json` 记录 `basis_kind: user_authorized_assumption`、`measured: false`、采用值、项目约定及授权来源、原始输入/已检查文件哈希、排除冲突的依据和所改阶段。不要伪装成仪器导出的 CIF_OD，也不要把这一假设当作“已确认的实测值”输入 `confirmed_json` 来源账本或 `temperature_consistency.py --source` 的实测来源路径。
6. 从正常精修输出准备正式验证 CIF 时，在 `_publ_section_exptl_refinement` 的现有说明后追加来源说明，并在两版 Word 中保留等义说明。保持已有方法描述，用标准 CIF 解析器安全写入，不用替换整个字段覆盖其他重要内容。若已有通用模板宣称“所有参数均来自实测”，须修正其不适用部分；不能只在内部日志披露假设而对外遗漏。

中文说明模板：

> 原始实验记录未提供采集温度。本次按用户约定采用室温 293 K；该值为工作假设，未核实为仪器实测温度，未提供测量不确定度。SHELXL 使用 TEMP 19.85 ℃。

英文 CIF/Word 说明模板：

> The collection temperature was not recorded in the available original experimental records. A room-temperature value of 293 K was adopted by explicit user convention. It is an assumption, not a verified instrument measurement; no measurement uncertainty was supplied. SHELXL TEMP was set to 19.85 degrees Celsius.

默认只涉及衍射采集温度 `_diffrn_ambient_temperature`；不把它自动称作另一次独立晶胞测定的实测温度。若 SHELXL 从 TEMP 派生 `_cell_measurement_temperature`，注明它来自同一假设而不是第二次测量。若用户另有明确、无冲突的同温条件信息，可记录适用范围再处理晶胞温度；不同温度始终分别保留。

未提供不确定度就不造 `(2)`。当更可靠的原始记录出现，更新来源并重新执行受影响的精修和交付，不静默覆盖已封存结果。警告减少只说明字段/一致性问题可能解决，不证明温度被测过或结构正确。假设仍是报告中的一项局限。

## English

This is an **explicit user-authorized working assumption**, not an inference that missing records establish room-temperature measurement. It applies only to a project whose user has chosen 293 K for comparable cases with missing original temperature records. Other customers retain unknown temperature unless they explicitly adopt a convention.

Read an explicitly supplied `project_preferences` path in the machine profile and verify its SHA256. This is agent-facing configuration: the existing Python pipeline does not automatically load it or inject a temperature. Record the enabled policy, project scope, value, authorization evidence and policy hash in the new job. The [portable example](../assets/temperature_default_policy.example.json) is disabled. Existing jobs retain their fixed code/version.

Before applying it, inspect only permitted same-experiment original files/user records and retain hashes, field locators and the missing-value finding. An unreadable, unparsed or uninspected file is not evidence that temperature is absent. Respect strict blind-input boundaries. Recorded temperatures take priority. Existing TEMP, numeric temperature fields, low/variable-temperature indications or unresolved conflicts require source review rather than replacement with 293 K.

If the declared source check is complete, relevant accessible records lack temperature and no conflict remains, reuse the authorized convention: **293 K corresponds to TEMP 19.85 °C**, without an invented standard uncertainty. Preserve the baseline, run a new native refinement, inspect temperature-sensitive H geometry, regenerate paired RES/FCF/CIF, recheck A/B, and obtain authorized official validation and both Word reports. The convention itself does not grant upload permission.

Keep `temperature_assumption.json` with `basis_kind: user_authorized_assumption`, `measured: false`, the adopted value, authorization, input/source hashes, conflict review and affected stage. Do not fabricate an instrument sidecar or feed the assumption into a measured-source importer as a confirmed measurement. Append the English disclosure above to existing CIF refinement-method text before validation and carry equivalent Chinese/English report notes. Preserve other method statements and remove any incompatible claim that every parameter was measured. An internal log alone is insufficient disclosure.

The default scope is diffraction collection temperature. A cell-measurement temperature emitted by SHELXL from TEMP must be identified as derived from the same assumption, not an independent measurement. Separate source-supported temperatures remain separate. Later experimental evidence supersedes the assumption through a new preserved run. Fewer alerts do not establish a measured temperature or correct structure.
