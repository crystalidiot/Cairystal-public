# CIF 标签大小写 / CIF data-name case

适用于“CIF 有数值，Word 却显示未提供”，或元数据继承误报 protected token changed。

CIF 数据名称不区分大小写，数据值必须保留大小写。因此 `_exptl_absorpt_correction_T_min` 与其小写名称相同；不能把整份 CIF 转成小写，原子标签、元素、说明及嵌入 RES/HKL 都不得这样修改。依据：[IUCr CIF1 syntax §26](https://www.iucr.org/what-we-do/digital-standards/cif/cif1/file-syntax)。

- `routine_finish.carry_metadata` 的许可字段与 snapshot 用相同的小写名称比较；结构/反射 token 保护检查仍执行，不能关闭保护来绕过报错。
- `bilingual_report.normalized_scalars` 只生成查找视图；原始 CIF、报告审计 JSON 的来源名称及数值保持原样。表格、公式/空间群说明和来源说明的选择按不区分大小写处理，`_SHELX*` 仍排除于报表 scalar 集合。
- 比较中英文 Word 的实际数值，不只比较两者一致：两版同时“未提供”也可能是同一个读取错误。未知 `?` / `.` 继续标为未提供，不填零。
- 如果仅修复报表显示且最终 CIF/FCF/官方 PDF 的哈希仍匹配，可在新目录复用已核实官网结果、重新生成并检查两版 Word，不必再次 POST。任何 CIF 内容改变都不能沿用旧上传哈希作为新验证证据。

The metadata carry-forward allowlist uses the same lowercase data-name representation as its protected-token snapshot. The protection is not disabled. Report lookup normalizes names only; source spelling stays in the audit dataset and values, atom labels, formula case and embedded input are preserved.

Check report values against the CIF, as bilingual agreement alone can hide identical omissions. Unknown values stay unknown. Report-only corrections may reuse an exactly matched, intact official result in a new output directory; changed CIF bytes require renewed validation evidence. `tests/test_cif_tag_case.py` covers lowercase, uppercase and dictionary spelling, protected-coordinate rejection, missing values, source preservation and both DOCX tables using synthetic fixtures. These tests do not establish scientific correctness or a new IUCr result.
