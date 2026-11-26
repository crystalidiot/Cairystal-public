# Cairystal · 从这里开始 / Start here

版本 / Release: `delivery_state_sync_20261126_01`。

1. 解压整个包，在 Windows 上先读 [INSTALL.md](INSTALL.md)，运行 `python -B verify_package.py` 校验文件。
2. 选 [中文](Chinese/small-molecule-crystal/SKILL.md) 或 [English](English/small-molecule-crystal/SKILL.md) 一套 skill；外部软件另行合法安装，按指南生成本机配置。
3. 将 [交接说明](交接说明.md) 的启动文字交给助手。ChatGPT/Codex、WorkBuddy和飞书的能力要求见 [跨平台使用](跨平台使用.md)。
4. 支持上传技能的客户端可用本包内单语言 `.skill.zip`；首次安装仍需保留并阅读本包的安装指南。

本包包含工作指令、脚本、参考说明和离线测试；不包含用户真实晶体数据、SHELX/PLATON二进制、私有软件配置或账户凭据。不要只发 SKILL.md 而丢掉 scripts 和 references。

正常结果交付到原始数据目录的 Cairystal 子文件夹：最终 CIF、IUCr_checkCIF.pdf、中文 Word、英文 Word。每次具体任务的官网上传授权按原范围执行；零AB并非结构准确性的单独证明。

English: Extract everything, read INSTALL.md, verify the package, select one language and create a machine-specific profile. Give HANDOFF.en.md to an agent with local Windows filesystem and command execution. Single-language import ZIPs are included. Native crystallographic software is installed separately. This is a tested preview, not universal host certification.

使用条款 / Terms: [LICENSE](LICENSE)。联系 / Contact: caizhuoerr@qq.com · 微信 / WeChat: crystal-idiot。


2026-11-26 / 0.3.5-preview: one cairystal.py entry; use version --json and workflow. Standard autorun is the default, fast is explicit. Read CHANGELOG.md and VALIDATION.md. Work-model convergence alone does not establish correctness.
