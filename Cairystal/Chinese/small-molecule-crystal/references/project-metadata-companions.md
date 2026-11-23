# 项目侧实验参数 / Project-side experimental metadata

Use this check when permitted raw records lack experimental fields or a user supplies an additional project directory. A raw-data folder need not contain Olex2 project records. A later supplied folder expands the documented input scope; it is not evidence that a file was overlooked in the original folder.

中文规则：仅检查用户允许的当前样品目录，记录本次范围。常规 intake 自动列出根目录及紧邻 `olex2` 子目录的同名 `.metacif`、`.phil`、`.pcf`、`.cif_od` 和名为 `cif_od` 的候选文件，不读取其内容。确认文件本身属于允许读取的范围后，运行下列只读检查。不能为找参数遍历其他样品、历史试验、身份映射或参考模型。

```text
python scripts/project_metadata_preflight.py --project-dir PROJECT --hkl ORIGINAL/sample_0m.hkl --raw-companion ORIGINAL/sample_0m.p4p
```

Capture stdout as `project_metadata_preflight.json` in the new run directory. Repeat `--raw-companion` for explicitly permitted P4P, `_ls`, RAW or ABS files to compare their hashes with same-named files in the supplied project root. Omit it if those records are unavailable. `--source PROJECT/olex2/sample_0m.metacif` (repeatable) selects an explicitly allowed subset; otherwise the same-stem candidates are inspected. A known legacy encoding can be specified with `--encoding`. This command writes no source files, executes no native program, and performs no upload or automatic merge.

## What is recorded / 保留的证据

- File paths, SHA256 before/after, block, original field spelling/token, one-based source line, value state and project-record origin. CIF parsing is case insensitive, including transmission `T_min`/`T_max` fields.
- CIF-text metadata from metacif/PCF/cif_od use the experimental scalar allowlist. Atom coordinates, formula, symmetry, ADPs, embedded RES/HKL and model-quality fields are not emitted. The entire file is read internally: an allowlist is **not** permission to read a prohibited file during a blind test.
- PHIL support is intentionally limited to a literal `diffractometer = "..."` assignment. Includes, expressions and other PHIL settings are not executed or imported. Multiple assignments remain separate for review; unsupported syntax is an error, not an instruction to repair the source.
- A bare `Bruker` or `Rigaku` is a manufacturer-level record, not a known instrument model. Preserve the recorded text; never append `D8`, `APEX` or another model without a source.
- `_cell_measurement_temperature` and `_diffrn_ambient_temperature` remain distinct. A stored project value such as 100.15 K is not proof of the original sensor measurement or its precision. A supported SAINT P4P value of −173.150 °C converts to 100.00 K; its scope still requires review. A 0.15 K difference is logged, not silently rounded away or used to infer that the two temperature fields are interchangeable.
- Cross-folder HKL hashes and (for supported fixed-column HKLF4) numeric reflection multisets/counts are compared. Equal counts do not imply equal intensities, sigmas or batches. Matching P4P/RAW/ABS hashes can support a common origin, but do not prove that the HKL processing stages are identical. The checker does not reindex, merge or rescale reflections to make them agree.

## Review and import / 复核后导入

`ready_for_merge` and `same_experiment_confirmed` remain false. Discovery and consistent filenames are not a pairing decision. Review the exact experiment, metadata semantics, raw-companion links, HKL processing lineage and conflicts before creating a source entry for `experiment_metadata_state.py collect`. Use `kind: cif_metadata` or `kind: phil_metadata`, the inspected source hash, target HKL hash, explicit block when needed, `same_experiment_confirmed: true`, and a meaningful recorded basis. The assertion must reflect actual evidence; never set it merely to pass a gate. Ledger observations preserve line numbers and manufacturer/project-record limitations. Existing metadata conflict gates and TEMP regeneration requirements continue to apply.

When files are absent, leave the fields unknown and include one grouped note that the user may supply this specimen's Olex2 project, PCF or cif_od. Do not repeatedly ask for optional data, infer a device model, borrow another specimen's parameters, or treat a zero-A checkCIF as provenance evidence. Unaffected solving may continue. Existing published CIFs and official reports are not rewritten by this check.

## Regression scope / 测试范围

`scripts/test_project_metadata_preflight.py` uses synthetic conditions: project temperature 100.15 K versus raw-derived 100.00 K, brand-only Bruker at known source lines, matching P4P but differing same-count HKLs, absent sidecars, protected reference files, linked/out-of-scope paths, PHIL literals/includes, scalar case and distinct temperature scopes. These tests check extraction and safeguards, not a real crystal's structure or measurement accuracy. Real case paths and private data are not bundled.
