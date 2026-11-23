# 本地检索及二维式识别 实验功能

稳定版仍位于项目原目录，本实验版独立保存。没有训练或微调神经网络。MolScribe 是作者预训练的局部图识别模型，本地检索是无需神经网络的 BM25；不连接语言模型 API。

## 检索

用 `local_knowledge.py build --skill SKILL_FOLDER --output NEW_INDEX.json` 建立固定的 12 篇通用文档索引。用 `search --index INDEX --query "PLAT080 不收敛"` 返回带行号、SHA256 的前三条证据。原文更改必须重建索引。不会检索历史案例、坐标、身份映射或互联网，不会沿文档链接打开旧答案。设置 CAIRYSTAL_KNOWLEDGE_INDEX 后，autorun 异常包会自动附上相关摘录；摘录只是诊断材料，不自动授权修改结构。

## 识别

用专用 MolScribe Python 执行 `molscribe_local.py --manifest images.json --checkpoint MODEL.pth --output NEW_PREDICTIONS --device cuda`。清单只有 schema、checkpoint_sha256、cases；每例只有 case_id、image、image_sha256、elements。元素必须来自使用者提供的可能元素，不能由识别结果反过来充当确认依据。支持本地中文路径。先固定作者模型哈希，再以受限可信文件加载。绝不加载来源不明的 Pickle/PyTorch 权重。

输出原始 SMILES、模型图、置信度、候选化学图和耗时。0.90 只是未校准的筛查阈值；不能解释为正确率或按本次得分降低阈值。多组分、手性、同位素、R 基、低置信度和元素超集触发复核。仍须人工或 AI 看图核对：漏水和电荷错误可能生成语法完全合法的 SMILES。没有可靠的自动接受规则。

用 `local_assist.py review --predictions DIR --case-id ID --output NEW_REVIEW --reviewer NAME --basis "实际看图核对依据"` 保存核对。需纠正时加 `--correction PATCH.json`，补丁只有 reviewed_smiles 与 reason；原预测保持不变。审核单绑定图片、原预测、纠正文件和化学图哈希。`verify --graph PATH` 可重复只读检查。手性/同位素/R 基等下游不支持的图不能通过本桥接强行降级；走专门人工流程。

## 接入完整结构流程

将审核后的 chemical_graph.json 交给原 `crystal_autorun.py` 配置，并提供实际元素、原始 HKL/P4P、实验信息；存在 N–H/O–H 时补充质子化依据。所有新坐标由本次求解得到；不复用历史原子映射或 H 坐标。识别只提供化学假设，后续仍执行空间群候选检查、元素匹配、加氢、精修、权重更新、ADP/占有率/差值检查、本地 PLATON、IUCr 官网和中英文 Word。若不满足原门槛，返回异常包，不修改门槛。

## 安装及资源

此实验采用隔离的 Python 3.10 MolScribe 环境与 Python 3.12 精修报告环境，均在 D 盘。MolScribe 固定作者 Git 提交 7296a30413eb55436702011efdff78131f66d162，权重 SHA256 6f0df56fa32b5ffc21f8c7f311ef333da522f590bf5622e966c6bcb1f2d9ea1d。作者源码支持新 PyTorch，但 PyPI 1.1.1 元数据限制 torch<2，不能简单混装。实际依赖锁和安装说明见实验根目录 README。模型许可和源代码许可随原始来源保留。没有取得未知模型的再分发授权时不打包权重。

## 测试解释

预先固定 14 张 RDKit 控制图，R 基一张不参与完整分子准确率分母。严格比较元素、键、形式电荷、组分重数、手性和同位素的规范化图；预测封存后独立评分。小型合成图测试不代表真实论文截图的总体准确率，也不验证晶体正确性。另测用户原始截图，只报告可验证的错误和边界，不编造精确真值。

读取通用知识和识别阶段的外部 LLM API 调用为零；这不包括开发、审核和异常纠正中的 AI。没有计费遥测，Token 节省值保持 null。对照记录原文字符数、返回字符数和实际介入次数，不把字符减少当作 Token 或总流程同比加速。
