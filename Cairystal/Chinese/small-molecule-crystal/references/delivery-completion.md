# Complete delivery after a reviewed candidate

A solver/native process exit, emitted CIF, local validation, or Markdown narrative is not a complete requested delivery. Do not end the task at one of these milestones.

## Existing scripted jobs
Normal autorun requests complete delivery. Pipeline finish/autofinish now request delivery by default; `--local-only` is an explicit diagnostic opt-out. Upload remains gated by the recorded authorization. Reuse already granted specimen-specific permission rather than asking at every invocation. An intact ready checkpoint can resume through the existing `pipeline deliver` command.

## Manually prepared candidate
After chemistry/H/charge/model review, save a review JSON containing `chemistry_and_h_reviewed: true` and a concrete `basis` referring to this model's evidence. Do not set these merely to unlock the workflow. Include equivalent `bilingual_notes` for additional interpretations.

```text
python cairystal.py complete --input CURRENT_CANDIDATE --stem exp13672 --review REVIEW.json --output NEW_DIRECTORY --authorize-iucr-upload
```

The launcher supplies the pinned profile. Other machines can call `scripts/complete_candidate.py` with their own `--profile`. Use a new directory. It preserves the source bundle, performs a SHELXL continuation with the existing parameterization/reflections, then bounded weights, metadata consistency, local validation, official checkCIF with embedded structure factors, Chinese and English Word, and measured layout/numerical QA. It does not invent atom types or approve chemistry. An upstream numerical or consistency failure returns evidence for correction; do not blindly continue an invalid structure.

## Availability and review are different
Explicit PLATON missing-check.def errors are recorded as unavailable, with null local counts and original logs. Only this narrow availability case may proceed to the independent official route; arbitrary parse, hash or numerical failures remain errors. Use the existing HTTP submission script first. A local rules-file problem is not evidence of an IUCr website problem. Do not repeatedly replay an uncertain upload; recover saved official URLs through `iucr_validation.py recover`.

Remaining AB/965 findings stay in the decision packet and report limitations. Diagnostic reports can be generated for a consistent, numerically admissible candidate before all AB are solved. Automatic report QA still requires scientific review for AB; generating those files is not acceptance. Correct the model in a new version, then validate the exact changed CIF again.

## Concrete completion check
```text
python cairystal.py check-delivery --run DELIVERY_RUN --stem model
```
Requires nonempty paired RES/HKL/CIF/LST/FCF (and required FAB), the saved official response matching the exact delivered CIF and PDF, and both readable Word documents with recorded bilingual numeric agreement. Missing artifacts produce `incomplete`, never success. Keep actual page/render checks and scientific assessment distinct. The final answer for a full crystal job must list four direct links separately: final CIF, official IUCr_checkCIF.pdf, Chinese Word and English Word. Confirm the PDF corresponds to the exact delivered CIF hash and both Word files use that final CIF. A directory, HTML index, ZIP, RES or Markdown narrative cannot substitute for those four files. If any item is missing, state which item, why and the retained checkpoint; do not call the delivery complete. Execution-only rendering PDFs stay in QA, not the customer's final PDF set.

The native/scripts portion invokes no language model. Agent diagnosis, scientific review and communication can still consume tokens; native computation, rendering and network waiting still take time.

The completion checker also binds each delivered Word hash to `qa/report_build.json`, checks that record's `cif_sha256` against the final CIF and the two table-data hashes against each other, and compares all delivered native files (including required FAB) to their frozen copies. A readable but replaced/stale Word or HKL is incomplete, even when the official PDF still matches the CIF. Older deliveries lacking this evidence need a new audited report build, not a fabricated manifest.


For a standalone authorized official PDF request, use `python cairystal.py checkcif --cif CURRENT.cif --output NEW_OFFICIAL_DIRECTORY --authorize-iucr-upload`. It explicitly requests PDF plus structure-factor validation, saves the response page, downloads the linked PDF, verifies the PDF and retains the submitted bytes/hash. The HTML response is not renamed to `.pdf`. Existing URLs can be resumed with `recover-checkcif --directory OFFICIAL_DIRECTORY`; bounded GET retries never repeat an uncertain upload. A PDF is saved before fetching FCF detail so later errors cannot discard it. Partial reports remain explicitly incomplete until all required checks pass.


## 用户最终交付清单

完成一次解析/精修后，最终回复依次提供下列四个真实文件的可点击链接：

1. 最终版 CIF（与官网验证提交的文件完全对应）。
2. IUCr_checkCIF.pdf（官网生成并实际下载）。
3. 晶体学报表_中文.docx。
4. Crystallographic_Report_EN.docx。

另附简短精修指标和未解决问题；目录、完整文件包及 RES/HKL 可作为补充。无需交付晶体学报表 PDF。若模型或后续产物尚未完成，应如实列出缺项，不把中间模型称作最终版。

## 成品保存位置

按[客户交付目录](customer-delivery.md)自动复制到原始数据文件夹中的 `Cairystal`。重复运行另存带时间的子文件夹，不覆盖旧版。完成回复明确说明实际目录，并使用导出记录中的四个直接文件链接。若复制失败，不能声称已经保存至客户目录；保留工作目录成品并如实说明。

## Sealed local completion
Explicit --local-only now returns local_complete_waiting_delivery (exit 0 for the requested local scope, full_delivery_complete=false). Missing upload permission returns awaiting_upload_authorization (exit 2). Neither means full delivery or an execution error. Use the same pinned version and the [resume workflow](workflow-reliability.md); do not repeat refinement just to obtain reports.

## Official browser submission

Install the optional Python package with the interpreter that runs Cairystal: `python -m pip install playwright==1.65.2`. Windows uses the installed Microsoft Edge. Set `CAIRYSTAL_BROWSER_CHANNEL=chrome` to use installed Chrome, or use `chromium` after `python -m playwright install chromium`. Use an interactive desktop for the temporary browser window. See [Playwright browser setup](https://playwright.dev/python/docs/browsers).

Only an explicit refusal (HTTP 403) from the ordinary form or its exact upload endpoint is eligible. The browser uses the authorized byte snapshot, the full structure-factor option, PDF, and a single submit. A timeout, authentication request, challenge, rate limit or uncertain submission requires review. After a receipt, resume report GETs with `recover-checkcif --directory OFFICIAL_DIRECTORY`. The normal delivery step continues with both Word reports.

中文安装说明：在 Cairystal 使用的 Python 环境中安装上述 Playwright 包。Windows 默认使用本机 Edge 和临时窗口。上传记录位于本次交付目录的 official/submission.json，包含提交路线、CIF 指纹、回执和下载记录。已收到回执时，凭回执恢复下载即可。
