# Pairing, recovery and evidence provenance

Read before processing a directory containing multiple versions, archives, or no matching INS.

## Choose an input set, not just two filenames

Record the exact HKL/model hashes, cell, wavelength, setting, HKLF type, timestamps and origin. Same filename or same molecular drawing does not establish that two files belong together. Distinguish identical copies, successive model versions, transformed reflection sets and genuinely different experiments. Report their counts separately.

SHELXT may change the cell/setting. A candidate `name_a.res` must be paired with its own `name_a.hkl`, not blindly with the original HKL. Preserve transformation information. A historical checkCIF belongs to the CIF that was uploaded then; it does not validate a newly refined version.

A reused stem can leave a completed old LXT beside a later model with a different group; compare recorded command, cell and candidate metrics, not filenames alone. For reindexing, check the index transformation and matched intensities/uncertainties, together with cell metrics and centering. A larger conventional-cell volume need not mean a supercell: the supplied C-to-R example increases volume by about 3/2 while primitive-cell volumes agree. Exact index correspondence does not prove the newly imposed metric symmetry or space group. A log ending mid-trial is incomplete evidence even if every saved line has been read.

## Recovery routes

- If a CIF embeds `_shelx_res_file`, `_shelx_hkl_file` and optionally `_shelx_fab_file`, extract them into a new job, check their consistency, and record the CIF hash and block. Embedded inputs may be an older model version.
- Inspect ZIP member names and sizes before extraction. Read data only; do not execute bundled scripts, follow traversal paths, or unpack executable content automatically. Record archive hash/member names.
- P4P can supply experimental wavelength, cell and uncertainties for an orphan HKL. It does not establish the chemical formula, hydrogen count, Z, or final space group. Folder labels give provisional element hints only. Mark guessed UNIT/Z explicitly and exclude their resulting density/F(000) from final reporting until checked.
- An ABIN model needs the matching FAB. A missing FAB is a blocker; do not silently drop ABIN or invent solvent content.
- Resolve explicit includes within a safe source boundary; missing includes are a blocker. Do not treat an incompletely parsed model as audited.

Do not send `saturated_reflections.hkl`, diagnostic `lasym.hkl`, history reflections or raw exported observations to a solver merely because the extension is HKL. Establish the intended role, format, setting and paired model first. Keep raw diffraction frames available for re-integration where needed.

## Reproducibility log

Each stage records inputs, executable version/hash, command, timeout, outputs, actual parameterization and termination state. Keep failed and superseded trials. Source hash checks must include reads that failed; a missing file is not an unchanged file. A diagnostic syntax repair may fill a proven absent metadata value with `?` in a separate CIF copy, but must retain the original and an exact change log. Never fill experimental facts from a tutorial example.

Unknown metadata remain unknown. Do not infer temperature from a filename, dimensions from a screenshot, or formula from UNIT placeholders.
