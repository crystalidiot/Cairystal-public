# 语言选择 / Language selection

## 中文

本版提供两个可独立安装的客户包，名字都为 `small-molecule-crystal`，选择一版即可。中文包的 `SKILL.md`、agent 界面名称、开始使用/交接入口和默认问卷为中文；英文包对应内容为英文。两版都保存 `SKILL.zh-CN.md`、`SKILL.en.md` 和两种问卷，运行时可用 `intake_once.py form --language zh-CN|en` 选择。`accept` 同样支持 `--language`。

所有计算脚本、算法、限制和报告模板逐文件相同。分发包仅 `SKILL.md`、`START_HERE.md`、`agents/openai.yaml`、`language.json` 按语言不同；各自清单可核验。安装后不要编辑冻结包改语言，问卷用参数覆盖、对话明确语言；需要更换默认入口时另解压一版供新任务使用。正在运行任务不可切版。

语言选择不改变科学数据：CIF tag、元素符号、SHELX 指令、原子标签、单位和软件名称不翻译；中文 Word 与英文 Word 始终同时交付。共享高级知识文档、原生程序日志及部分自动诊断网页目前保留原语言，不能宣称整个软件界面已全面本地化。agent 按客户所选语言解释摘要，完整日志原样存放，不将英文日志塞进中文报告。

问卷以相同 schema 和字段保存数据；数值、未知值、实测确认、SQUEEZE 选择和上传授权的语义必须一致。切换语言读取同一问卷时保留已填选项，包括自定义文本。示例不代替观察，未作答不代替授权。

## English

Two independently installable editions share the name `small-molecule-crystal`; install one. The chosen edition localizes `SKILL.md`, agent UI metadata, getting-started/handoff entrypoint and the default intake form. Both include `SKILL.zh-CN.md`, `SKILL.en.md` and both forms. Override the form language with `intake_once.py form --language zh-CN|en`; `accept` supports the same option.

All computational scripts, algorithms, constraints and report templates are byte-identical. Only `SKILL.md`, `START_HERE.md`, `agents/openai.yaml` and `language.json` differ between distributions; separate manifests allow verification. Do not edit a frozen package to switch language. Use the form flag and state the conversation language, or extract the other edition into a new directory for new jobs. Never switch a running job's fixed release.

Language does not change scientific data. CIF tags, element symbols, SHELX instructions, atom labels, units and program names are preserved. Both Chinese and English Word reports are always required. Advanced shared references, native logs and some diagnostic pages retain their original languages; this is not a claim of full localization of every software surface. The agent explains summaries in the selected language and preserves full logs separately.

Both forms use the same schema and fields, with equivalent numeric, unknown-value, observation-confirmation, SQUEEZE and upload-permission semantics. Importing the same record across languages preserves supplied select values, including custom text. Examples are not observations, and an unanswered choice is not authorization.
