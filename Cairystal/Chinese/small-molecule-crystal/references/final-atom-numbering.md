# 最终原子编号

`routine_finish.py`（包括 autorun、finish、autofinish 和 complete 的收尾入口）在权重收尾及最终验证前调用 `atom_labels.py`，保存旧/新标签、元素、PART、氢母原子和文件哈希。原模型不覆盖。标签改变时运行一次本地 SHELXL 全矩阵续算，继续检查收敛、NPD、坐标/ADP/占有率变化及 HKL 哈希；不通过就保留候选并交回复核。随后正常检查权重、AB、官网验证及双语 Word，不复用改名前的官网报告。

每种非氢元素从 1 依次编号，如 C1、C2、N1、O1、CL1。序号按原生位点出现顺序确定，保持可复现；不宣称是 IUPAC 化学编号。无序位点保留 PART，不改变占有率。仅当原标签已明确具有相同元素/数字主干、不同后缀且位于不同 PART 时，保留对应关系，如 C34A/C34B → C1A/C1B。不能据距离自行推定两个无序位点对应。

氢依据现有 AFIX 母原子并核对距离，或唯一的同一书写分子图像内键距候选，关联母原子数字。多个氢或 C1/N1 等同号母原子用字母后缀消除重名；对应表明确记录实际母原子与 PART，H 后缀不单独代表 PART。母原子不明确时停止自动改名，不猜测质子化或移动氢。

**原生 SHELX 行顺序不改。** AFIX 的母原子、SAME 的隐式目标及 `>`/`<` 范围可能依赖行顺序。仅同步支持指令的原子引用，包括 DFIX、SADI、SIMU、RIGU、EADP、EXYZ、HFIX、HTAB 等，保留 `_$n` 对称后缀、数值、SFAC 顺序和全部物理参数。RTAB 的表名及 `$元素` 选择器不是原子标签。非零 CHIV 的符号依赖邻居字母序，不自动处理。

CIF 的原子与各向异性参数循环按 C、其它非氢元素字母序、H 排列，每种元素内自然数字序；移动的是完整行，不改数值、标准不确定度和其它循环。原生文件保持原顺序。两版 Word 从同一最终 CIF 读取，沿用相同标签和顺序。直接 `crystal_delivery.py` 入口也检查编号；待编号模型应先走 `complete`，不得只改 Word 或已验证的 CIF。

此前自由文字中的 `C9 H12` 可能是分子式而非原子标签，不能盲目替换。保留既有文字记录，并明确其采用原编号；随交付保存 `atom_label_map.json`。最终表格和重新计算的几何/警告使用新编号。原始日志保持原样。

当前自动范围：简单元素列表 SFAC、唯一标签、常规 PART/AFIX、明确 H 母原子和四字符原生标签。不自动处理 RESI 范围/通配符、外部 include、FRAG、MOVE、同位素、非零 CHIV 或超长标签；输出明确复核原因。此限制不是解析失败，也不能跳过验证后宣称交付完成。旧版运行和已出报告保持冻结。

手动检查本次模型并生成独立输入：

```text
python scripts/atom_labels.py --res CURRENT/model.res --output NEW_NUMBERING_FOLDER
```

这只生成 INS/对应表，尚未精修或验证；完整任务仍走 `complete`/`routine_finish`。

语法依据：[SHELXL 官方指令](https://shelx.uni-goettingen.de/shelxl_html.php) 的 AFIX、SAME、RESI、EQIV 和 CHIV 定义。
