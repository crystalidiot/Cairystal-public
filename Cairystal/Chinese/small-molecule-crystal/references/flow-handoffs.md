# 主线与工具衔接 / Mainline and tool continuation

正常路线：输入核对 → SHELXT/有依据的备用求解 → 初解检查与元素/氢 → 精修和权重 → 本地 A/B → 支持的工具对照 → 选定版本 → IUCr → 中英文 Word → 自动报告检查 → 数据目录/Cairystal。

`autorun` 负责已有证据明确的连续步骤。`ab-auto` 准备和运行诊断对照：只有已实现的固定清单 OMIT 接受规则会自动选入工作模型；元素替换、H 方向和一般无序候选仍保留科学复核。未实现的自动选择不能用“自信”替代证据。

工具返回后：

| 当前结果 | 后续动作 | 是否需要 AI 判断 |
|---|---|---|
| 919/934 固定清单对照通过接受检查 | finish 使用新 CIF/FCF 重验，继续交付；摘要读取新目录 | 否 |
| 候选几何、占有率、H 或元素仍有歧义 | handoff 给出具体模型、诊断、下一工具 | 是，依据本例证据 |
| ready_for_official_delivery，授权已具备 | resume-delivery 续接现有选定模型 | 否 |
| 官网和两份 Word 已生成、自动 QA 通过 | 续接工具自动 finalize、打包、发布及提示客户目录 | 否 |
| 官网回执已有，下载失败 | deliver continue/recover-checkcif 核对同一 CIF 指纹后续取 | 不重新求解；结果不明的提交不自动重发 |
| 自动 QA 有内容、排版或官网 A/B 异常 | 保留文件和具体 finding，继续对应复核 | 需要处理异常，不能标记全部完成 |

```text
python -B cairystal.py run resume-delivery -- --run FINISH_DIRECTORY --data-dir ORIGINAL_DATA_DIRECTORY --authorize-iucr-upload
```

新任务通过 pipeline 或 complete 生成的封存配置会保存原始客户数据目录。历史封存点没有该字段时，给 `--data-dir`；不把中间模型目录猜作客户目录。已生成报告的续接检查不重发 CIF，也不重新精修。任务固定代码版本和样品 HKL/CIF 指纹；旧任务用原版本完成。

English: A ready checkpoint continues from the exact selected model. The standalone `resume-delivery` CLI now runs the same exact-file automated report checks and publishes to the recorded original specimen directory (or explicit `--data-dir`) when they pass. Generated reports can be checked again without another upload. QA failures remain specific review checkpoints. The coordinator summary follows the selected OMIT CIF/FCF rather than the all-data baseline. Automatic publication is not chemical correctness certification or manual visual inspection.
