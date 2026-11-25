# 0.3.3-preview — 2026-11-25

Engine: chemistry_handoff_20261125_01. Previous public release: 0.3.2-preview.

- 元素判断：用本轮数据集中比较元素候选，保留等条件基线与比较记录；不会自动宣称化学身份已被证实。
- 加氢续接：化学图及质子化依据复核后，自动映射短原子标签、生成 HFIX、精修并核对氢数及 UNIT。
- 交付衔接：人工或自动处理路线共用最终 CIF 对应的报告 QA、官网回执恢复和客户目录导出。
- 快速模式：减少试探轮数，先交付注明限制的工作模型；标准模式保留。最新版 skill 默认 fast，调用时显式记录执行模式。
- 快速孪晶检查：有迹象时作有界 PLATON 检查，取得可用法则后保留 TWIN/BASF 对照，按证据选择。
- 现有 66 个工具继续保留。化学合理性和本次衍射证据优先于警告数量。无序/复杂钙钛矿的可靠完整建模仍需进一步验证。

The update adds batched current-run element contrasts, reviewed-graph hydrogen continuation, exact-file report QA/export continuation, fast-mode budgets and bounded twin trials. It does not guarantee unattended solving of complex disorder. Scientific source files match the sealed upstream version; only distribution metadata/documentation is adapted.

Existing 0.3.2-preview history and Release assets remain available. The academic licence and third-party licences are unchanged. No experimental data, private models, teaching files, machine profile or scientific executable is distributed.
