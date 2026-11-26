# Cairystal

[中文](README.md)

Cairystal provides small-molecule crystal solving, refinement, checkCIF and bilingual reporting workflows for assistants with local file and process access, including ChatGPT/Codex, WorkBuddy and agents connected to a Windows execution host. Install scientific programs separately.

**Version: 0.3.5-preview (2026-11-26).** This public source repository uses [Noncommercial Academic Use License 1.1](LICENSE). It is not a permissive open-source licence. Platform, statutory and third-party exceptions remain applicable.

## Download and setup

- [Complete package](downloads/Cairystal-0.3.5-preview-public-academic.zip) · [Release](https://github.com/crystalidiot/Cairystal-public/releases/tag/v0.3.5-preview)
- [Chinese import ZIP](downloads/Cairystal-zh-CN.skill.zip) · [English import ZIP](downloads/Cairystal-en.skill.zip)
- [Installation](Cairystal/INSTALL.md) · [Handoff](Cairystal/HANDOFF.en.md) · [Host requirements](Cairystal/跨平台使用.md) · [SHA256](downloads/SHA256.json)

Extract the complete package, read INSTALL.md and run `python -B verify_package.py`. Install dependencies, generate a local profile and run doctor. A skill import supplies instructions and resources, not scientific software or a Windows execution connection.

For a clone, enter the Cairystal folder to verify package integrity. Choose the complete [Chinese skill](Cairystal/Chinese/small-molecule-crystal/SKILL.md) or [English skill](Cairystal/English/small-molecule-crystal/SKILL.md). Do not copy SKILL.md alone.

## Use

From the selected skill directory run `python -B cairystal.py version`, `workflow` or `list`. All 67 tools remain available. Chemistry and current diffraction evidence take priority; low R or zero A/B alerts does not establish correctness. Same-job report rendering can be reused only when content and environment match, with full QA. Official reports must match the final CIF.

This release consolidates the cairystal.py entry, authoritative release_info.json version and shared mainline/tool map. Use standard autorun by default or select fast explicitly. All 67 tools and scientific checks remain available; the previous release is retained. Regression counts are not crystal counts or accuracy estimates. WorkBuddy and Feishu end-to-end execution remains unverified. See [validation](Cairystal/VALIDATION.md) and the [distribution review](docs/PUBLIC_REVIEW.md).

## Licence and feedback

Commercial use, modification and redistribution require separate permission, subject to applicable exceptions. Third-party components retain their own rights. See [notices](THIRD_PARTY_NOTICES.md) and [privacy](PRIVACY.md). The project contains AI-assisted code and documentation.

Remove unpublished specimen data and credentials from feedback. Contact: caizhuoerr@qq.com; WeChat crystal-idiot.

## Changes

See [release notes](CHANGELOG.md). Refinement, AB checks and authorized IUCr validation remain required. A converged working model is not a certification of publication readiness. Generate a profile for your own computer.


交付完成后自动同步任务状态；重复续跑不会重新解结构或上传。旧版任务只需使用状态恢复命令，详见 [delivery state recovery](Cairystal/Chinese/small-molecule-crystal/references/delivery-state-sync.md)。

Completed helper delivery now synchronizes the coordinator and page. Repeated resume verifies the existing files without re-solving or re-uploading. The previous release remains available.
