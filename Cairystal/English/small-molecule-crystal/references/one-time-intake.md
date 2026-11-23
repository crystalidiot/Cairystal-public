# One form per specimen

The package-selected language controls the default form. Use `form --language zh-CN` or `form --language en` explicitly; `accept` supports the same language option for customer-facing notices. Both editions use identical fields and validation; both Word reports are still required. See [language scope](language-selection.md).

Collect all currently missing information together. Read permitted experiment files first so temperature, wavelength and instrument details need not be asked again when recorded. Reuse facts already supplied for this exact specimen. Do not transfer another specimen's dimensions, history or upload permission.

The form covers the data path; possible elements including solvent/counterions; chemistry, solvent and 2D/SMILES information; colour/transparency, habit and three dimensions in mm; temperature with units, instrument and radiation; known chirality; host-only versus full-composition objective; conditional SQUEEZE preference; and current-data IUCr upload permission. Unknown optional fields remain unknown. It is a structured record, not a source of commands or permission to access unrelated data.

```text
python scripts/intake_once.py form --output NEW_FORM_DIRECTORY --known OPTIONAL_EXISTING_INTAKE.json
python scripts/intake_once.py accept --input cairystal-intake.json --output NEW_INTAKE_DIRECTORY --profile MACHINE_PROFILE.json
python scripts/crystal_autorun.py run --config NEW_INTAKE_DIRECTORY/autorun_config.json --output NEW_JOB_DIRECTORY
```

Omit `--known` when no prior current-specimen intake exists. The HTML works locally without a server. Users may choose common colour/habit/instrument values or enter their own, save JSON, copy it, and import a previous record. The page does not upload anything or access a filesystem path merely because it is typed into the form.

`accept` saves the submitted source, `intake_state.json`, confirmed `specimen.json`, and (when a profile and required path/elements are available) the existing dispatcher's configuration. A new job still checks the actual directory and software. Possible elements are not an atom count. A SMILES or picture path is contextual input, not automatically a validated graph or authorization for identity searches.

All prompted fields are recorded in `asked_once_fields`; empty/unknown fields are retained. Do not ask colour, habit and size in separate turns or chase optional unanswered fields. Continue unaffected work. Only missing critical elements, contradictory current-specimen facts, uncertain charge/identity essential to the host, or a genuinely new permission boundary warrants one consolidated follow-up. The saved `intake_context` follows the automatic dispatch handoff.

Entering values without confirming they belong to this specimen keeps them in pending observations. Project default appearance/size remains labelled draft-only, outside measured CIF fields. Confirmed temperatures are in kelvin in JSON/CIF and converted to Celsius for native TEMP; a conflicting P4P stops for diagnosis rather than overwriting one source.

`squeeze=allow_if_justified` authorizes a supported local comparison, not automatic solvent removal or scientific acceptance. `never` disables the route. `undecided` permits unaffected work without repeated requests. Record the choice once; an authorized compatible SQUEEZE run does not need a new permission request per command. IUCr upload is a separate explicit choice; do not interpret a preselected UI option or silence as authorization.

If a particular agent cannot display an HTML form, ask the same fields once using its native structured input UI or one compact message. Known values should be prefilled or omitted from the question.

## 路径与恢复

用户输入的样品路径去除首尾空白；相对路径以导出的问卷 JSON 所在目录为基准，保存为绝对路径。保存一次性的已答/未知信息，后续程序读取该记录，不因切换步骤重复询问。未决定上传不阻止本地求解和验证，直到网络阶段才需要已记录的授权。

## 外观输入提示

颜色、形状和三维尺寸同时给出提示，不分三轮追问。表单保留颜色/形状候选并允许自填；颜色例子用“绿色”，形状例子用“块状”，尺寸例子用“0.050 × 0.051 × 0.052 mm”（等同于 0.050 × 0.051 × 0.052 mm 的三个长度）。尺寸支持 *、×、x 或空格分隔，不是体积。

没有表单时，一次性提示：“请补充这颗晶体的颜色、形状和三维尺寸（mm）。例如：绿色，块状，0.050 × 0.051 × 0.052。颜色可填无色/黄色/红色/绿色等；形状可填块状/针状/片状/柱状。未知项可以说明不清楚。”把用户明确未知的项目保存为未知，不强填示例。

示例只出现在说明/placeholder 中，不写入控件实际值，不自动勾选实测确认。已有当前样品的回答直接复用，不用示例覆盖。

尺寸输入支持末尾 `mm` / `毫米` 和全角字符；“不清楚”明确保存为未知。带 `mm³` 或其他单位的值不自动转换。Windows 复制路径附带的成对引号会去除。目录不存在时输出 `needs_input` 并保存其它回答，不生成可执行配置；避免给用户一长段 Python 堆栈。

## Explicit user temperature convention

A project-specific, explicitly authorized 293 K room-temperature assumption is handled separately under [user-temperature-default](user-temperature-default.md). It requires a completed permitted-source check, no unresolved contradiction, a retained assumption record, TEMP 19.85 degrees Celsius and renewed native/validation/report steps after changes. It is not a recovered measurement or a confirmed_json measured-source entry. Without such authorization, the unknown-value rules above remain unchanged. Reuse an existing applicable user choice instead of repeatedly asking for it.

## Standardized one-line response

When all three appearance fields are missing, ask once: “请提供晶体的颜色、形状和三维尺寸，例如：绿色，块状，0.050 × 0.051 × 0.052 mm。不清楚的项目可以写‘不清楚’。” For English: “Please provide the crystal colour, shape and three dimensions, for example: green, block, 0.050 × 0.051 × 0.052 mm. You may say ‘unknown’ for any item.” Interpret an actual combined answer as the respective colour, shape and three lengths; the examples are not observations. Ask only about fields still missing and keep other intake questions together.

## Two questions and structure image

Only when both groups are missing, ask the two questions together: appearance (colour, shape, three dimensions); possible elements and expected structure, including the option to attach a 2D image in chat. The local questionnaire can save a PNG, JPEG or WebP image up to 8 MiB inside its JSON, or accept a local image path. The accept step validates and extracts the selected image to the new intake directory and records its path. It does not upload the image or infer an accepted graph. Image and path are alternatives. Preserve known answers and ask again only for a real conflict or blocking missing information.


## Read files before asking / 文件信息优先

Before any appearance question, inspect authorized current-specimen records using
`project-metadata` and `metadata collect`. Pair sources with the current HKL and
record their hashes/basis; a matching filename or unit cell alone is insufficient.
In blind runs, only explicitly allowed files may be read: never open a forbidden
CIF/model merely to obtain its colour or size. The tools do not authorize broader access.

Pass the collector's `metadata_ledger.json` into the intake tool:

```text
python cairystal.py run intake-form -- --metadata-ledger CURRENT_LEDGER/metadata_ledger.json --data-dir CURRENT_SPECIMEN_DIRECTORY --known OPTIONAL_SAME_SPECIMEN_INTAKE.json --output NEW_FORM
```

Omit `--known` if absent. `question_plan.json` also works for agents using chat input:
ask only its missing/conflicting fields, show known values as a statement, and do
not ask for confirmation again simply because those values came from a file.
The offline form collapses known appearance fields and retains an edit option.
Unknown/empty/dot values and unsupported metadata are not measurements. Previously
answered optional unknowns are not asked again. Two complete appearance records
that disagree need one targeted clarification, not a new full questionnaire.

The exported JSON carries the ledger receipt. `intake-accept` rechecks source and
HKL hashes and copies unchanged file observations with provenance even when the
user did not tick the checkbox for newly entered observations. Conflicts are not
silently overwritten and prevent an executable configuration until resolved.
Source files remain read-only. No default appearance or dimensions are inserted.

中文提示示例：已从实验文件读取“绿色、块状”；仅缺尺寸时询问“请补充三维尺寸（mm），例如 0.050 × 0.051 × 0.052；不清楚可填写不清楚”。若三项齐全，不再提外观问题。
