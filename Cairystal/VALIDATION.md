# 验证范围 / Validation scope

本次是入口、版本与文档结构整理。中英文科学脚本均与本次封存源逐字节一致；求解、精修、官网及报表生成算法保留。

每种语言 1,263 项离线测试通过，包含新增 8 项入口/模式/版本/路径及错误传播测试。原始测试中 5 项本机 HTTP 测试受沙箱 WinError 10013 限制，获得回环权限后逐项补测通过，保留初始失败记录。这是软件测试数，不是晶体数。

另从原始数据重新执行一个以前使用过的简单晶体：SHELXT、元素候选对照、新建化学图及加氢、SHELXL 权重精修、本地 PLATON、同一份新 CIF 的 IUCr 官网 PDF、两种 Word 和自动交付。R1=0.0481，wR2=0.1300，GoF=1.087，官网0A/0B/3C/10G。无旧坐标或旧加氢方案输入；已有对话背景，不称完全独立盲测。保留原 HKL 与各候选。两份 Word 各6页、官网PDF3页随后查看渲染预览。

开始到自动交付 204.07 秒；开发、回归及随后人工查看页面不计入。不能把这一例推断为复杂结构准确率或受控提速比例，无真实 Token 计数。

The public package is checked by source hashes, archive round-trip, extracted CLI tests, dependency/license and content scans. Original experimental data, models, official reports and Word documents are retained locally, not published. WorkBuddy/Feishu cross-host end-to-end execution remains unverified. Chemistry and present diffraction evidence precede alert counts.
