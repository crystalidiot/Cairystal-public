# 异常才转审阅的报告与科学说明

适用于已有明确二维化学图、新模型匹配无歧义的常规路线。自动流程不等于自动确认化学身份；输出状态区分规则通过、需要审阅和执行失败。

```text
python scripts/crystal_pipeline.py autofinish --run NEW_RUN --source CURRENT_GRAPH_H_STAGE --deliver --authorize-iucr-upload --baseline-seconds OPTIONAL_PREVIOUS_TIME
```

`CURRENT_GRAPH_H_STAGE` 必须取本次 `match` 输出的 `hydrogen_stage`。不手写原子映射，不读取旧案例。上传仍需已有授权。自动路线被挡住时，查看 compact JSON 指向的规则记录及具体异常，不重新阅读全文库。

## 常见科学说明

`scientific_report_rules.py` 检查本次源模型：明确的 C/N/O/F/Cl 图、完整电荷平衡、一个原生空间群候选且有反心、一般位置及满占有率、图连接与元素一致、逐母原子氢数一致、H与母原子距离及过短接触、常规键长、收敛、NPD、局部ADP和残余密度。范围外元素、无序、特殊位置、孪晶、额外限制/OMIT等转审阅；不把正常数值当作科学正确证明。具体阈值和每个发现保存在 `scientific_rules.json`。

从二维图生成组分式、形式电荷及供氢接触注释规则；中心氧合卤素、带正电N不自动作为氢键受体。游离卤离子不会被该规则删除。仅处理报告接触注释，不能据此挪动原子或剔除反射。

`report_method_templates.py` 根据最终RES/CIF记录生成中英文方法与限制：实际AFIX及Uiso、权重更新、实验参数来源、已知吸收处理参数及透射率、化学先验来源、未独立确认的身份、几何接触的解释边界。完整原文单独保存。未知科学原因不能靠套话填写；新异常保留原文并交审阅。已知未解决的实验局限必须披露，不能因为模板生成成功而标成已解决。

## 排版与官网检查

`report_autoqa.py` 使用渲染后PDF的字形坐标、页面和图片边界、表格线，以及DOCX原文，检查：空页、越界、明显文字重叠、未映射字形、表格线穿过文字、渲染后原文字符缺失、页数与图片哈希、两种语言数值表一致。另核对官网PDF的结构因子确认、全部A/B计数、对应CIF哈希与交付文件哈希。

`automatic_qa.json` 列出每页结果和异常预览路径。没有异常才允许自动封存；A/B不清零、缺页、内容缺失或文件变化都会阻止自动交付。保留官网C/G，不自动删除它们。

字体的字形排版边界不等于实际墨迹。上标数字后紧跟低位标点时，允许有限的排版边界伸出：两者起点需充分分离且重叠不超过较窄字形宽度的75%；近重合或更大重叠仍报错。该规则有单独正反测试，不放宽普通文字的重叠门槛。

本路径如实记录 `visual_review_performed:false` 与 `review_mode:automated_rules`，不会填“人工逐页看过”。它不检查所有审美问题、结构图标签的化学含义或图像内全部细微重叠。使用者要求真实逐页人工/AI检查时，继续原来的 `finish` → 实际查看 → `finalize --reviewed-*` 路线。异常页才需要额外查看的策略来自当前用户要求。

## 测量与可移植性

所有规则、渲染、官网请求及封存分开计时。自动路线无需AI模型API；外层agent仍有读请求、启动和交付成本。记录发生的异常审阅及其等待区间，不能把命令间隔全部称作AI思考时间。前次没有独立AI时间戳时，只能比较“动作间隔”这一粗略指标，不能声称精确节省多少AI秒数或Token。

依赖新增 `pdfplumber`；合成PDF测试另用 `reportlab`。缺少依赖应在网络提交前报错，不绕过检查。规则由文件和测试携带，换agent应执行同样命令和门槛；复杂科学判断的跨agent一致性需另行盲测。

CIF data names are case-insensitive. Existing parameters missing from tables or carry-forward guard failures require [CIF 标签大小写检查 / case checks](cif-tag-case.md); retain scientific values and the protected-token guard.
