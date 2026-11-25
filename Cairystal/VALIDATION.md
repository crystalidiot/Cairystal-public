# 验证范围 / Validation scope

本版科学脚本与 chemistry_handoff_20261125_01 封存源逐字节一致。上游本次相关回归 97 项和交付续接检查 1 项通过。发布目录另行执行离线回归、双语入口和 ZIP 完整性检查，结果见仓库 docs/validation.json。

上游单个简单晶体独立重解析的记录为 219.19 秒，历史对照为 500.95 秒；两次并非随机、重复对照试验。该次包括新 CIF 的官网 PDF 和中英文 Word，记录官方 0A/0B。这些数据不是复杂结构准确率，不保证其他机器或样品获得相同速度。没有真实 Token 计量。本次发行同步不重复解析样品或上传 IUCr。

Upstream evidence includes 98 relevant checks and one simple-case workflow timing. Distribution checks are software tests, not solved-crystal counts, scientific accuracy estimates or independent cross-agent certification. Complex organic disorder and layered perovskite modelling remain limitations. Low R, convergence and zero AB alone do not prove correctness. WorkBuddy and Feishu end-to-end execution remains unverified.

本次发布目录实测 / Distribution tests: Chinese: 1255 tests, 0 failures, 0 errors, 0 skipped, English: 1255 tests, 0 failures, 0 errors, 0 skipped.
