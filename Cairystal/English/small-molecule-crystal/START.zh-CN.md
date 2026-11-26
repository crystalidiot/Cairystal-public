# Cairystal 安装与入口

```text
python -B cairystal.py version --json
python -B cairystal.py workflow
python -B cairystal.py run doctor -- --profile LOCAL_PROFILE.json --output NEW_ENVIRONMENT.json
```

版本与路径 / Version and path: `version --json` reads `release_info.json`.
安装 / Installation: [portable environment](references/portable-environment.md), [Windows](references/windows-install.md).
本机生成 profile，不复制作者的路径 / Generate the profile on this machine; do not copy another machine's paths.
主线 / SOP: [SKILL.md](SKILL.md). Standard: `run autorun -- ...`; fast: `run fast -- ...`.
交付 / Delivery: final CIF, IUCr_checkCIF.pdf, Chinese Word, English Word in the input directory's Cairystal subfolder.
旧任务使用原版本 / Resume existing jobs with their pinned release.
授权 / Licensing: [LICENSE](LICENSE), [third-party notices](THIRD_PARTY_NOTICES.md).
联系 / Contact: caizhuoerr@qq.com; WeChat crystal-idiot.
