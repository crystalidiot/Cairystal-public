# 按样品续跑 / Resume the requested specimen

任务记录可带 `case_id`。续接另一聊天的任务或回答“最新结构”时，从本次请求取样品的 HKL 和运行目录。以交付结果中记录的精确 CIF、PDF 指纹核对链接。授权由实际提交数据的会话按本次样品和目的地核对。多例可一次列出待上传的样品和范围，历史授权与同名文件仅作线索。

先在同版本 autorun 的 `status`、`resume` 或 `review` 后加 `--expected-hkl 原始反射文件`。手工完成精修后遇到官网中断，可从包含 `result.json`、`frozen/` 和 `official/` 的交付目录执行：

    python cairystal.py run deliver -- continue --run DELIVERY_RUN --cif SELECTED_CIF --expected-hkl MATCHING_HKL --inspect-only

返回 `reuse_verified_report` 时使用同一 CIF 的报告。返回 `download_existing_reports` 时只取已有回执的报告。返回 `submit_only_with_authorization` 且实际有本例直接上传授权时，才可加上传参数。对未确定是否已上传的旧记录，保留原尝试并核对回执。

    python cairystal.py run deliver -- continue --run DELIVERY_RUN --cif SELECTED_CIF --expected-hkl MATCHING_HKL --profile PROFILE --output NEW_DELIVERY

首次发送确需授权时，在上式末尾加 `--authorize-iucr-upload`。使用完成精修的同一版 skill。新目录接着生成双语 Word，按原流程做 report-qa 和 finalize。原始 HKL 经有记录的重定标或变换后，交付续跑使用与选定模型配套的那一版 HKL，先核对其与原始数据的来源关系。

对有明确 disorder group 的分子，脚本在已报告的键连中筛查 CF₃ 的过短 C–F 和两个饱和碳之间的过短 C–C。后者用当前配套 RES 的骑乘氢类型识别。输出列出实际坐标算出的键长和对应组分，可结合差值密度、键长不确定度与对照模型决定是否保留。阈值用于提请复核；缺少分组、键表或可靠杂化依据时看覆盖状态。

## English

Carry the requested case ID, source reflections and selected CIF across chats. Use `--expected-hkl` on autorun status, resume and review. For a delivery checkpoint, the inspection command above checks both file hashes offline. A known receipt allows report downloads only. A verified complete receipt supplies the report cache. A positively recorded pre-submission stop requires valid specimen-specific consent before the first POST. An uncertain submission remains for receipt review. With the pinned release, the second command resumes into a new directory, builds bilingual Word files and leaves normal QA and customer export available. Use the matched reflection version for a documented derivative.

During disorder screening and before reporting, the code calculates short CF₃ C–F and riding-H-supported saturated C–C bonds from coordinates using explicit CIF bond connectivity and disorder groups. Inspect the covered bonds, group labels, residual density and uncertainty before choosing a model. Where a chemical class cannot be established, the tool records its limited coverage.

同任务续跑会自动尝试上一交付目录的报表页面复用；内容或渲染环境变化时重新导出。任何复用仍须重新执行 report-qa / finalize，不跨任务搜索。See [render reuse conditions](usage-and-cost.en.md).
