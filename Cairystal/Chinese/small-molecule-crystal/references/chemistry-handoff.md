# 元素比较、加氢与连续交付

初解仍用主线 `pipeline start` / `autorun`。没有外部二维式时，先用本次 H-free 模型生成集中证据，不读取历史模型。

```text
python cairystal.py run chemistry-screen -- --run PIPELINE --source CURRENT_STAGE --name types01 --mode all
```

比较相同源模型、HKL、权重和精修轮数下的未改基线及有界 C/N/O 替换；短键四配位终端 P/S/Cl 基团可以提出氧配体组合假设。候选、键长、Ueq、指标和失败均在一个 `result.json`，排序不等于采用。终端四氧基团暂不做逐 O→C/N 试探；该策略不是独立确认阴离子身份。存在相关多位点变化时由助手提出组合方案。`--mode motifs` 或 `light` 可分别比较，最多 32 个候选，超预算明确停下，不截断后冒充完整比较。所有完整结构仍须 AB 验证。已有氢、PART、部分占有和特殊位置走专用工具。

助手根据本轮证据确认完整重原子图、键级、电荷与质子化，保存 graph 和一一对应 mapping。不知道的化学信息不得以低 R 代替判断。图可以来自客户二维式或本次推断，来源必须如实记录。随后一次调用：

```text
python cairystal.py run hydrogen-continue -- --run PIPELINE --source SELECTED_STAGE --name h01 --graph GRAPH.json --mapping MAPPING.json --graph-origin current_run_inferred --basis "本次几何、元素对照与电荷依据" --finish --execution-mode fast --max-weight-updates 1 --authorize-iucr-upload
```

此命令自动按元素重编号并更新映射 → 检查图/模型 → 按价态生成 HFIX → 原生精修和氢键检查 → 核对实际氢数与 UNIT → 数值和科学一致性检查 → 本地 AB → 已授权官网验证 → 双语 Word → 排版/文件检查 → 客户 Cairystal 文件夹。N–H/O–H 仍需记录依据；水氢/特殊位置不套普通加氢规则。无权限时不加上传开关，保留续接点。

`finish` 与 `deliver` 也统一接入报告 QA 和导出，只有真实告警、内容或排版问题才暂停；不把尚未验证的文件标成完成。脚本为每阶段记录时间，交接时间不称为实测 AI 或 Token 用量。

## English

Use `chemistry-screen` for a bounded batch of current-run H-free element contrasts, retaining an unchanged equal-cycle reference. Local geometry may propose a tetrahedral oxoanion hypothesis; fit ranking never accepts chemical identity. No reference coordinates are read. General-position full-occupancy models only; uncertain chemistry, correlated substitutions, disorder and water require their own evidence.

Once an assistant has reviewed the current graph, charges and donor basis, `hydrogen-continue` normalizes labels, remaps atoms, generates HFIX, refines and checks actual H/UNIT counts. With `--finish` it continues into scientific checks, local AB, authorized IUCr PDF, bilingual Word, exact-file QA and customer export. `--graph-origin` distinguishes independent supplied 2D chemistry from a graph inferred from this diffraction run. Never imply an inferred graph is independent corroboration. Upload authorization is explicit and not created by the tool.
