# 快速孪晶分支 / Quick twin branch

当前入口：`python -B cairystal.py run twin-quick -- --directory PAIRED --stem model --profile MACHINE.json --output NEW_DIR --reason "本次孪晶迹象与依据"`。
主线 `routine_finish → ab-auto` 已自动接入，不需重复询问客户。仅使用本例配对的模型/反射。

1. **触发**：明确的 PLATON 孪晶/绝对结构线索（含相关 C/G），或 PLAT934/939 下至少3个 Fo² > 2Fc² 且 (Fo²−Fc²)/σW >10 的正偏差点。仅 R 高、GoF 高或负偏差并不触发。助手发现其它具体证据可传 `--reason`。阈值是计算分流规则，不是孪晶诊断。
2. **快速检查**：`platon -T case.cif`，同目录携带配对 LIST4 FCF。默认20秒、`--seconds`可指定1–120秒，仅限制搜索时间。读取原生 `.lis` 中完整的三行 h2=M*h1 矩阵、重叠数、BASF、DEL-R。完整候选稳定0.5秒即可终止本次自启进程，不等待图形窗口退出，不声称搜索穷尽。
3. **自动试修**：全重叠、非现有空间群操作、与晶胞度量相容、整数且 M²=I 的双组分 HKLF4 候选，在新 INS 中加入 TWIN 和 PLATON 估计值起始的 BASF。仅改这两条，保留相同反射/权重/空间群/原子起点，自动跑未加孪晶和孪晶各20轮及本地PLATON。
4. **比较再选**：输出 BASF及其末轮标准不确定度、R1/wR2/GoF、收敛、ADP、密度与完整AB。由助手依据化学及衍射证据选模型；显著性不足/异常人口不静默截断。此工具没有自动批准最终模型。
5. **继续交付**：采用新模型后用其精确最终CIF走现有IUCr官网验证和中英文Word。快速检测产生的 `.chk` 空文件/临时文件不是验证报告。未获官方PDF不得声称官网完成。

**边界**：已有TWIN/BASF不叠加。部分重叠、非整数矩阵、HKLF5、多组分、ABIN/SWAT或复杂批次转专门处理；不把HKLF5改标成4。搜索失败/超时/格式无法识别不算阴性；保留具体日志与模型，助手直接诊断，不重新问客户是否继续。发现孪晶趋势先暂缓OMIT，避免先删掉识别依据。无信号正常继续，没有额外的原生运行。

Windows调用统一使用本机路径分隔符。该机PLATON使用正斜线可执行文件路径时出现“No Filename Extension”；已用`Path.resolve()`规范化。图形启动请求隐藏，但不保证所有版本的原生窗口都隐藏。

## English

`twin-quick` is integrated before outlier omission in `routine_finish → ab-auto`. No new customer permission is requested for local comparisons. Trigger only on current evidence; preserve all input and unrelated controls. Search defaults to20s, stops on a settled complete native matrix block, and is explicitly non-exhaustive. One compatible full-overlap integer two-domain law is inserted as TWIN/BASF in a new INS and refined against a same-data untwinned control (20 cycles each), with native local validation. Report BASF and its s.u., metrics, density, ADPs, convergence and A/B. Model choice still requires chemical/diffraction review. Continue the existing official IUCr PDF and bilingual Word route for the selected final CIF. Existing twin/batch/mask controls and HKLF5/partial-overlap cases are not silently converted. Timeout, failure or unknown native text is never a negative twin diagnosis.

## Sources

- [PLATON TwinRotMat](https://www.platonsoft.nl/platon/pl000417.html): current-data intensity analysis, matrix estimates, full overlap vs HKLF5. Checked2026-11-24.
- [PLATON shortcuts](https://www.platonsoft.nl/platon/pl060000.html): command modes.
- [SHELXL instructions](https://shelx.uni-goettingen.de/shelxl_html.php): TWIN/BASF/HKLF/LIST meanings.

Engineering validation uses explicitly simulated data; it is not a blind solution of a real twinned crystal.
