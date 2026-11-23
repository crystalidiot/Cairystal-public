# 更新、排版与问题反馈

## 报表排版

`report_typography.py` 是展示层，不修改 CIF、元素指认、原子编号或模型数值。中文报告用中文说明，英文标题采用 sentence case；Cairystal、IUCr、checkCIF、SHELXL 等名称保持原大小写。

- 标量 a、b、c、x、y、z、V、Z 与希腊变量斜体；单位 Å、K、mm、g 和元素符号用正体。
- R₁、wR₂ 的字母斜体、数字下标；R 的 int 描述性下标正体。U 的 eq、iso、ani 描述性下标正体；Uᵢⱼ 的变量指标斜体，U₁₁ 等数字下标正体。
- F(000) 中 F 斜体、括号数字正体。化学式的明确元素计数下标；不把电荷、系数或原子编号猜成计数。
- Hermann–Mauguin 空间群先由 Gemmi 验证，再格式化字母、螺旋轴下标和负轴上划线；保留设置，不擅自换空间群。未知记法原样显示并在构建记录中标记。
- C34B、CL1 等原子标签必须按 CIF 原样保留，不能因美化改名。坐标、占有率、标准不确定度和张量数值原样保留。

排版规则参考 [IUCr 作者说明](https://journals.iucr.org/c/services/notesforauthors.html) 和 [IUCr 对称性说明](https://www.iucr.org/what-we-do/education/pamphlets/symmetry)。具体期刊模板仍可另行要求。双语表格数值一致性、文件配对、渲染和原有 AB/官网门禁继续执行。不能因为只改了字体就跳过渲染。

## 版本更新

采用完整版本目录与固定入口：每次在新目录开发并保留旧稳定版；验证通过后才切换 `Cairystal.current.json`。已有任务继续用它创建时的 skill 和 profile，不自动切换或用新代码恢复旧检查点。

建议发布顺序：修复问题并记录复现条件 → 针对性回归 → 报表实际渲染 → 必要时真实晶体端到端测试 → 清单哈希/版本记录 → GitHub Release 源码 ZIP 与 SHA256 → 客户在新目录安装、自检并切换入口。实验功能保留为预览版；不要直接覆盖稳定目录或客户晶体数据。

每个发布包应包含版本号、变更说明、适用环境、迁移注意事项、测试范围和已知限制。源文件哈希验证完整性，不等于签名或可信来源认证。无明确仓库地址时不臆造自动更新 URL，也不静默下载执行代码。本机 profile 与第三方软件授权由每台电脑独立配置，不随公开源码泄露。

安装后可运行 `python small-molecule-crystal/scripts/verify_release.py --skill small-molecule-crystal --manifest release_manifest.json`，检查缺失、篡改和未列入清单的文件；脚本不联网、不激活版本、不修改客户任务。

回退：先确认没有需要混用代码的运行中任务；保存当前入口记录，将入口指回保留且哈希核验通过的旧版本及其对应 profile。不得改写旧运行记录；新版已开始的任务保留或在旧版另建目录重跑。规范镜像 `small-molecule-crystal` 同步前须核对旧清单；遇到他人修改停止覆盖并保留差异。

## 失败与报错

`support_report.py` 将当前运行的异常保存为 `support/<事件编号>/`。自动接入 autorun 接手、pipeline 失败及 complete 阶段；亦可显式调用：

```text
python scripts/support_report.py --run CURRENT_RUN --category scientific_decision --stage finish --reason "当前模型有未解决的无序与非正定原子"
```

`说明.html` 给客户中文下一步；`incident.json` 是本地详细记录，区分观察到的错误和未知根因；`Cairystal_feedback.zip` 仅含版本、事件分类等最小信息。科学未解决、缺关键输入、文件变更、报告待检查和程序错误分别编号；不把可疑根因写成已确认原因。既有模型、日志与原始数据不删除；报错不绕过精修、AB、官网验证或双语报告。

反馈包默认不含 CIF/HKL/RES、路径、原始报错、traceback、日志或环境变量，也不自动发送。用户检查后自行邮件/微信反馈；需要更完整数据时另行说明精确范围。局部记录本身可能含路径及报错中的敏感信息，不应直接当公开附件。解析参数阶段或尚未建立有效运行目录的异常仍显示在命令行，不创建或遍历任意输入目录；诊断模块写入失败也不掩盖原错误。

## 联系信息

唯一配置：`assets/support_contact.json`。报表末尾和问题反馈说明自动读取，保持一致。

邮箱：caizhuoerr@qq.com  
微信：crystal-idiot
