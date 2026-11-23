# Customer result location

Normal completed jobs export the verified delivery to `<original specimen data directory>/Cairystal`. The first delivery is directly in that folder. If it already exists, use a fresh `Cairystal/运行_YYYYMMDD_HHMMSS_unique` subfolder, with no overwrites. The completion message and four direct links must use the actual returned path, including this subfolder when present.

Required files: the exact final CIF used for official validation, `IUCr_checkCIF.pdf`, `晶体学报表_中文.docx`, and `Crystallographic_Report_EN.docx`. Paired native files, viewer and audit records accompany them. No report-rendering PDF is added. `Cairystal_delivery.json` and `交付说明.txt` record the location, provenance and unresolved alerts. Experimental inputs and prior results stay unchanged.

`pipeline`/`autorun` remember the original data directory. With `complete_candidate.py`, specify `--data-dir ORIGINAL_DATA_FOLDER` if `--input` points at a working candidate; otherwise the input folder is used. Direct `crystal_delivery.py run/finalize` also accept `--data-dir`. Work directories still remain separate from raw inputs; only checked final copies are written under Cairystal.

Copying runs after required-artifact, exact-CIF/PDF/Word and review gates. Missing, changed or incomplete files block export. On a copy permission/disk failure, retain the verified work delivery, report the exact error and do not announce successful customer delivery. After the path problem is resolved, run `scripts/customer_delivery.py --run DELIVERY_RUN --data-dir ORIGINAL_DATA_FOLDER` to retry copying only; no refinement or website resubmission is needed. Successful repeats verify the receipt and do not create duplicates. A strict read-only input/batch instruction overrides the normal destination: retain results in the authorized output area, explicitly record the destination exception, and do not write under protected inputs.

Final response example: “最终 CIF、IUCr 官网 checkCIF PDF 和中英文 Word 晶体学表已保存至：`<actual exported directory>`。” Follow with the four returned clickable file links, plus unresolved issues when present. File completeness is not scientific acceptance.
