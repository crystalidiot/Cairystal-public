# Cairystal

[English](README.en.md)

Cairystal 为具备本地文件和程序执行能力的 AI 助手提供小分子单晶结构求解、精修、checkCIF 验证及中英文报告工作流。可交给 ChatGPT/Codex、WorkBuddy 或连接 Windows 执行端的助手使用；第三方晶体学软件需另行安装。

**当前版本：0.3.4-preview（2026-11-26）。** 本仓库公开提供完整 skill，采用[非商业学术使用许可 1.1](LICENSE)，不是允许自由商用、修改和再分发的开源许可证。平台和第三方许可例外仍适用。

## 下载与安装

- [完整安装与分享包](downloads/Cairystal-20261126-public-academic.zip) · [版本下载页](https://github.com/crystalidiot/Cairystal-public/releases/tag/v0.3.4-preview)
- [中文技能导入 ZIP](downloads/Cairystal-zh-CN.skill.zip) · [English import ZIP](downloads/Cairystal-en.skill.zip)
- [安装指南](Cairystal/INSTALL.md) · [中文交接](Cairystal/交接说明.md) · [平台能力要求](Cairystal/跨平台使用.md) · [SHA256](downloads/SHA256.json)

完整解压后先阅读 INSTALL.md，运行 `python -B verify_package.py`，再安装依赖、生成本机配置并运行 doctor。单语言 ZIP 只导入技能资源，不会安装 SHELX/PLATON 或建立本机连接。

直接克隆仓库时，进入 `Cairystal` 目录运行完整性校验。中文 skill 位于 [Cairystal/Chinese/small-molecule-crystal](Cairystal/Chinese/small-molecule-crystal/SKILL.md)，英文位于 [Cairystal/English/small-molecule-crystal](Cairystal/English/small-molecule-crystal/SKILL.md)。选择一套完整目录，不要只复制 SKILL.md。

## 使用

在所选 skill 目录运行：

```text
python -B cairystal.py version
python -B cairystal.py workflow
python -B cairystal.py list
```

66 个工具按证据调用。化学合理性和当前衍射证据优先，不能用低 R 或零 A/B 代替科学判断。新任务记录原始数据目录，报告续接可自动 QA 并发布客户文件夹。同任务报表复用仍核对全部页面与数值；官网报告须匹配最终 CIF。

本版统一使用 cairystal.py 入口与 release_info.json 版本信息，主线和工具路线共用一份定义。默认 autorun 标准模式；需要快速工作模型时显式使用 fast，旧版下载保留。66 个工具和科学检查保留。回归测试不等于真实晶体正确率。WorkBuddy、飞书尚未完成端到端认证。[验证范围](Cairystal/VALIDATION.md) · [本次分发核查](docs/PUBLIC_REVIEW.md)

## 许可与反馈

仅在许可证允许范围内使用。商业使用、修改和再分发须另获授权，第三方组件保留各自权利。[第三方声明](THIRD_PARTY_NOTICES.md) · [隐私说明](PRIVACY.md)

本项目含 AI 辅助编写的代码与文档。反馈前请移除未公开晶体数据和凭据。联系：caizhuoerr@qq.com；微信 crystal-idiot。

## 本次更新

[更新记录](CHANGELOG.md)：入口与版本统一、主线/工具衔接、重复 SOP 合并。保留精修、AB 检查及经授权的 IUCr 验证；快速得到工作模型不等于已经达到发表标准。安装后先生成本机 profile，不复用作者电脑配置。
