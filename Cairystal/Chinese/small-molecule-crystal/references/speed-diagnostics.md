# 耗时诊断 / Speed diagnostics

`python -B cairystal.py run performance -- --run DELIVERY_RUN --output NEW_TIMING.json`

只读取明确指定的交付运行目录，不扫描样本库或参考答案。常规 `deliver` 已自动把耗时排序写入 `performance.json`；`performance` 还读取该运行中的官网、渲染和自动复核明细。旧任务继续用固定的旧版本；仅查看耗时不需重解。

## 先找瓶颈，再调整

- **官网慢**：`official/submission.json` 区分 `form_get`、`submission_post_and_server` 与各次 PDF/FCF GET。POST 包含网络传输和服务端处理，不能宣称测得纯服务器耗时。冻结最终 CIF 后提交；下载失败使用 `recover-checkcif`，不重复 POST；只有严格匹配 CIF 哈希和验证选项的官网结果才可复用。
- **报表慢**：`qa/render_manifest.json` 分开记录 Word/LibreOffice PDF 导出与两种语言逐页 PNG 生成；`automatic_qa.json` 记录复核总时间和两种语言分别耗时。保留每页、原分辨率和所有检查。
- **精修慢**：查看收敛趋势、数据/参数规模与候选数量。继续使用本机 CPU/可用内存适配；若做核数对照，每组使用相同 INS/HKL、轮数、权重和限制，顺序运行并多次测量。线程浮点规约可能有末位差异，不能保证 RES 按字节一致。`-b` 是矩阵参数容量，不是 MB；不盲目加大。
- **AI 等待多**：常规步骤用 `autorun` 连续运行；只对新科学歧义请求判断。先收集已有实验参数与可用二维式，避免无依据的重复尝试。不能仅因警告减少就自动认定模型正确。

新版报表边框检查按 x 坐标建立页内索引，仅排除数学上不可能相交的边框；不改变 1.5 pt/1 pt 边界、检查条目或报警顺序。每页结束释放 PDF 布局缓存，不保存所有页对象到最后。依赖仍是原有 pdfplumber；未增加新模型或服务。

## 计时的边界

父阶段和明细不能相加重复计数。报表自动复核通常发生在旧交付计时区间之外，单列显示。旧记录没有细分信息时为 `null`。没有真实 Token 计数就保持 `null`，不把脚本时间或 AI 调用次数换算成节省 Token。性能测试不替代结构正确性、A/B、官网 PDF 或中英文 Word 的交付检查。

## English

Run the command above on an explicit delivery-run directory. It never searches a dataset or reference models. Delivery writes `performance.json` automatically; the tool adds nested official/render details and separately measured report QA. Missing historical fields remain null.

Optimize the measured bottleneck. Keep frozen-CIF exact-hash validation and recover known report downloads without another POST. Retain both Word languages, every rendered page and QA. For native thread benchmarks, preserve INS/HKL, cycles, weighting and restraints; run sequential repeated comparisons on the target machine. More threads or matrix capacity are not universally faster; floating-point reductions may differ in the last printed digits.

The indexed border check uses the same strict geometry predicate and issue order. Page-local layout caches are released after inspection. No chemistry, tolerance, reflection, refinement or acceptance setting changes. Nested timings are not additive to their parents; a partial-stage speedup is not an end-to-end speedup or measured token saving.

## 结构解析时的等价编号 / Equivalent labels during structure determination

二维匹配只对连接到同一母原子、元素、键级、形式电荷与加氢规则均相同的末端原子按编号排序搜索。完整编号数包含等价排列的数学重数。不同的元素和氢位候选仍逐个精修；手性、特殊位置、部分占有和无序按原有规则分流。每个原生阶段核验工作 HKL 的 SHA-256，同一路径和内容完全一致时可以沿用进程内上一份格式检查结果。可在阶段 attempt.json 查看 hkl_format_reused，在 proposal.json 查看 search_nodes、complete_label_mappings 和 assignment_classes。

For terminal sites sharing a parent, element, bond order, formal charge and hydrogen treatment, the matcher searches canonical label order and counts the full permutation multiplicity. Distinct chemical candidates still undergo separate refinement. The same-process HKL format check can be reused for the same source path and digest only after the staged copy passes its own content check.
