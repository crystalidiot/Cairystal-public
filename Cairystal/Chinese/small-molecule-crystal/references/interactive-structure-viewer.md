# 交互结构查看器

在最终结构报告交付时使用。由当前 CIF、同版本 RES 和已保存的验证计数生成离线网页，不依赖 Olex2、网络/CDN 或 AI。仅需要原有 Gemmi 环境。网页拖动/缩放不会重新精修，也不会改变原始文件。

## 正常自动流程

`crystal_delivery.run` 在最终 CIF、官网 PDF 和双语 Word 完整性检查后生成 `delivery/structure_viewer.html`、`delivery/structure_viewer.json`，纳入交付哈希与 ZIP。核心四件交付仍然必需，查看器不能替代它们。

`crystal_delivery.finalize` 完成封存后默认请求系统浏览器打开该网页，结果写入本次运行的 `viewer_open.json`。这也覆盖通过 `complete_candidate`、`routine_finish`、`crystal_pipeline`、`crystal_autorun` 调用的正常交付流程。浏览器返回成功只表示已请求打开，不宣称用户已看到页面。不能弹窗的宿主应由 agent 使用支持的文件/浏览器打开工具展示返回的 HTML，或提供可点击链接。避免重复打开已经请求打开的同一个页面。

批量或无界面测试可以显式设置 `CAIRYSTAL_NO_OPEN=1`；直接 delivery 命令也可用 `--no-open-viewer`。仅禁止自动弹窗，仍生成网页。查看器失败会记录原因，不能把这个附加显示问题改写为晶体精修失败，也不能删除已经通过核对的四件交付。最终答复应说明显示失败和修复入口。

## 独立生成（已有模型、另建输出）

```text
python scripts/structure_viewer.py --cif CURRENT.cif --res CURRENT.res --output NEW_VIEW --open
```

同一输出不覆盖。脚本记录输入哈希并复核输入未改。无 RES 时允许按 CIF 的 disorder_group / disorder_assembly 显示，但必须注明 PART 不可直接恢复；未分组位点不能假装已确认 PART 0。

## 显示规则与科学边界

- 读取 CIF 的元素、分数坐标、晶胞、明确对称操作与真实占有率。对称副本不增加独立原子数，不把 SHELX SOF 编码直接显示成占有率。
- 有 RES 时，按标签、元素、晶胞、周期同位置唯一匹配 PART。不能唯一匹配时停止生成并报告；不借用旧模型坐标或分组。主交付流程仍执行完整 `paired_bundle` 检查。
- 用对称操作和整数晶格位移组装连通片段，不做坐标优化、键长拉伸、改变组成或丢弃原子。遇到周期连接网络，显示明确标记的有限片段；不将配位聚合物声称为独立完整分子。展开大小有界，超限报告需要局部视图。
- 连线仅用共价半径与距离筛选，不是键级识别，不显示推定氢键。PART 0 可连接各组，不同非零 PART 不连线；负 PART 不自动补对称键。BIND/FREE/CONN 的额外连接指令不在此轻量查看器中重演，要保留提示。
- 元素图例采用固定颜色；还可切换为 PART/无序组着色。每组可开关，默认保留全部组用于比较；开关是显示过滤，不是新增可同时存在的化学构型。氢可显示/隐藏；原子点击信息含标签、元素、PART/组、CIF 占有率与对称来源。
- 球棍图不是 ADP 热椭球图；零 A/B、外观完整和图形美观都不等于结构正确。失败/假设模型的独立展示应在 `status` 明确标记，不能标成已解成功。
- HTML 嵌入 JSON 并转义脚本边界，动态文字用 textContent。页面无外部脚本、网络连接、遥测或坐标上传。
