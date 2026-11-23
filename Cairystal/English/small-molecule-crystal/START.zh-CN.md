# Cairystal 当前测试版入口

版本 handoff_flow_20261122_01；旧稳定版保留。新电脑按 references/portable-environment.md 与 references/windows-install.md 安装，重新生成本机 profile。不要复制作者机器路径。

从 SKILL.md 的一条 SOP 开始，正常用 autorun/complete。收尾出现 A/B 后会自动进行有证据的工具试验；具体能力和未支持情形见 references/automatic-ab-mainline.md。工作台 /automation 页展示实际规则，可导出新任务参数。

先 doctor、portable_tests，再用授权样品完成原生精修/AB/官网/双语 Word 全流程。离线回归和合成试验不证明所有晶体能独立解对。

最终交付：输入目录/Cairystal 下的最终 CIF、IUCr_checkCIF.pdf、中英文 Word。缺项或未消除的 A/B 如实说明。遵守随包 LICENSE 及第三方声明。

联系 caizhuoerr@qq.com；微信 crystal-idiot。

新增五项工具及完整用法：[分壳、相关性、占有率多起点、限制强度、备用求解](references/five-tool-enhancements.md)。

新电脑先运行 `doctor --profile LOCAL_PROFILE.json --output-root JOBS_DIRECTORY --output NEW_ENVIRONMENT.json`。自动线程考虑本机可用 CPU 和剩余内存；检测信息和原因写入日志。详见 [资源适配](references/native-performance.md)。


统一入口：`python cairystal.py version`、`python cairystal.py list`；完整版本信息以 `release_info.json` 为准。
