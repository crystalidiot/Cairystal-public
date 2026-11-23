# Workflow and stage gates

## Job layout

Create one job directory per attempted structure determination:

```text
job-name/
|-- input/          immutable copies of the supplied data
|-- solve/          SHELXT solution outputs
|-- refine/         numbered SHELXL cycles and diffs
|-- validate/       CIF, FCF, PLATON reports, and plots
|-- report_render/  internal document QA only; not a user deliverable
|-- delivery/       final model/data, IUCr_checkCIF.pdf, Chinese and English Word reports
|-- manifest.json   software versions, commands, hashes, and status
`-- report.md       interpretation, decisions, and unresolved issues
```

Never reuse a directory from a previous run. Keep the source directory outside the job unchanged.

## Execution preference: no Olex2 window by default

The user prefers solution, refinement, fragment assembly, saving and report preparation without opening Olex2. Run SHELXT/SHELXD, SHELXL and local validation through recorded command-line jobs; use file-based crystallographic analysis and rendered views for inspection. A solver executable located inside the Olex2 installation directory does not require launching the Olex2 application.

Do not open Olex2 automatically at job start, after every cycle or merely to save files. Use it when the user requests interactive viewing, or after explaining a specific review/unsupported-format need that cannot safely be handled with the available headless route. An unverified Olex2 command-line option is not evidence of a supported headless mode. Do not close a user's existing Olex2 session just to follow this preference.

## Efficient execution and staged delivery

Use the [reusable automation commands](routine-automation.md) as the default for supported routine jobs: run an explicitly prepared candidate with `run_crystal_stage.py`; freeze and deliver a chosen model with `crystal_delivery.py`. Load the command reference once, retain compact summaries and avoid recreating execution, validation upload or report code per case. The driver preserves full logs and review gates.

Use these practices to reduce avoidable orchestration and report work without weakening scientific checks:

- Inspect permitted source files and available runtimes once per job; retain hashes, metadata provenance and tool paths. Reuse those findings while the files/environment are unchanged, and invalidate only the affected result after an input, model or tool change. Never reuse a previous specimen's coordinates or interpretation as a shortcut in an independent test.
- Group independent reads and metrics extraction. Use one reusable stage runner for command execution, logging and numerical gates instead of writing a new near-identical helper for every refinement. Dependent model decisions remain sequential; save the baseline and each meaningful candidate, including failures.
- Reserve element, disorder and restraint comparisons for actual ambiguity or diagnostic evidence. Once the chosen model is stable, end unchanged or uninformative repetition; apply the weighting-review stopping criteria below. Speed is not a reason to omit a necessary scientific comparison.
- When a coherent viewing model is ready, promptly provide its RES/HKL path, R values and known limitations, with validation/report status explicitly pending. Continue the authorized checkCIF and Word work in the same task; do not wait for document layout to show the model or stop after this interim handover.
- Record software execution, model/data analysis, online validation and document preparation time separately. Do not describe report-building delays as solver runtime or promise a universal completion time.
- Before final online submission, settle the actual model, reflection pairing, experimental metadata and software/graphics provenance. Generate tables once from the frozen CIF. Reuse an exact-hash matched official result within this job for DOCX-only formatting changes; changed CIF content requires a fresh matched validation.
- Probe document dependencies before authoring. On a host with known missing LibreOffice, select an available supported renderer once; on Windows an installed Word COM export with `Visible=False` and page rasterization is a possible fallback. Use only the document/application instance created for this task. Keep the PDF and page images in `report_render/`, record the real renderer, and visually check the final Word pages. Do not repeatedly invoke a known-unavailable renderer, silently install a new office suite, or claim conversion passed when it failed. A report-rendering failure does not block delivery of already finished scientific files.
- Produce concise Chinese and English reports from one shared final-CIF table dataset; translate the narrative and headings without repeating scientific analysis or online validation when the submitted CIF hash is unchanged. Reuse available authoritative figures; do not add a new plotting dependency, elaborate dashboard or extra document format solely for presentation. If a figure is omitted, report the actual graphics provenance rather than a planned but unused program.

## Stage 1: inspect

Complete [chemical/specimen intake](beginner-mode.md#each-new-specimen-chemistry-and-experiment-facts-before-solving): expected structure if known, possible elements including solvent/counterions, and actual colour/habit/dimensions if available. Reuse facts already supplied. Missing appearance does not stop solution; the documented draft-default route does not establish experimental facts.

The inspection/setup helpers expect a same-stem `.hkl` and `.ins`. Inspect the instruction file for at least `CELL`, `ZERR`, `LATT`, `SFAC`, `UNIT`, and `HKLF`. Record all `SYMM` instructions. Treat the chemical formula and expected atom types as user/domain evidence, not something to infer only from peak heights or directory names. If an authorized test instead supplies structured parameters and HKL, construct a new INS in the job directory from the permitted fields and recorded hypotheses. An element list specifies types, not counts; record SFAC order and keep atom-type indices consistent. Unresolved necessary composition/symmetry assumptions are not confirmed input facts.

Do not continue automatically when:

- multiple same-stem pairs exist and no target was chosen;
- the reflection file or instruction file is empty;
- cell, wavelength, lattice, symmetry, scattering factors, or unit contents are absent or internally inconsistent;
- the instruction file references a different reflection source that cannot be resolved.

In beginner mode, translate this inspection into a simple readiness result. Keep raw directive details in the technical appendix unless one explains a blocker.

## Stage 2: solve

Use SHELXT for the normal small-molecule solution path. Invoke it in the copied working directory with the shared basename. Preserve `.lxt`, candidate `.res`, and any transformed `.hkl` files. Record the proposed space group, R1, Rweak, CFOM, inferred formula, and any alternative solutions.

Solution output is a hypothesis. Compare it with systematic absences, expected composition, chemical connectivity, and plausible displacement parameters before promoting it to refinement.

If SHELXT yields no interpretable candidate, a bounded SHELXD branch can be justified after input checks; record each search hypothesis and its budget instead of treating timeout or normal exit as a solved structure. FIND values from one example are not reusable defaults. Use the case-free [sparse light-atom route](sparse-light-atom-solution.md) for few independent observations, high symmetry or averaged density; check canonical SHELX symmetry encoding and parameter semantics before attributing failure to the data. Do not impose a historical 300-second limit when none was requested; limit unchanged or uninformative repetition and record the stopping reason. The [LYH worked case](lyh-case-lessons.md), when reference access is allowed, distinguishes independent phasing from subsequent 2D-assisted atom assignment and difference-map completion.

## Stage 3: refine

Run SHELXL on a numbered copy of the current `.ins`. Preserve `.lst` and `.res` from every cycle. A refinement cycle is successful only when the process exits normally, expected outputs exist, and the log contains a normal completion banner.

For generated instructions, check ordering as well as atom selection before launching SHELXL: all required SFAC definitions must precede UNIT, and UNIT follows that element order. Preserve existing instruction placement when replacing a value rather than inserting UNIT at the top. HFIX must precede its target atoms, and ANIS must precede the atoms it converts. Diagnose an instruction-order failure from the log before changing chemistry or adding refinement cycles. Preserve the failed input, fix the syntax in a separate run and verify the actual H/ADP output. See the [SHELXL instruction reference](https://shelx.uni-goettingen.de/shelxl_html.php).

### Structure-factor output: default LIST 4

For routine small-molecule refinement and delivery, use exactly one active `LIST 4` instruction. This selects the FCF output format, not the reflection-input type (`HKLF 4`), and does not improve the model by itself. Verify that the generated FCF actually contains h, k, l, Fc², Fo², sigma(Fo²) and the status flag. Retain the original HKL and generate the FCF from the matching model; never relabel a LIST 6 file as LIST 4.

Use `LIST 6` only in a separately labelled diagnostic branch when the downstream operation explicitly requires its amplitudes/phases; record the reason and keep the primary delivery at LIST 4. Do not rewrite historical runs. For unchanged-model structure-factor output, `L.S. 0` can be used in a separate diagnostic copy without `ACTA`. The installed SHELXL 2018/3 rejects both `L.S. 0` + `ACTA` and `DAMP 0 0` + `ACTA`; neither is a working unchanged-model CIF-export recipe on this build. Do not resume refinement merely to satisfy a cosmetic/output-only request. Retain previous CIFs separately and state when a newly regenerated CIF is pending. Label zero-cycle output as diagnostic, verify model equivalence, and retain the convergence status of the preceding actual refinement: zero cycles cannot establish convergence. See the [SHELXL instruction reference](https://shelx.uni-goettingen.de/shelxl_html.php) for LIST and L.S.

Track at least:

- R1 for observed and all data;
- wR2, GooF, and restraint count;
- maximum and mean shift/esd;
- highest residual peak and deepest hole;
- parameter and reflection counts;
- non-positive-definite atoms and split-atom suggestions;
- absolute-structure statistics when applicable;
- warnings, omitted reflections, and weighting changes.

An unchanged-model convergence loop must have a small explicit cycle limit. Do not repeatedly copy `.res` to `.ins` without recording the transition.

Run `scripts/refinement_gate.py <stage-directory> --stem <basename>` on preserved process.log/LST/RES. It flags empty outputs, missing completion summaries, NPD atoms, unconverged shifts and nonphysical twin contributions. Its result is a numerical gate, not a correctness certificate; continue with chemistry, symmetry and validation review even when it reports numerical convergence.

### Weighting review

Review weighting during refinement, not only after a validation alert. Follow the [SHELXL WGHT documentation](https://shelx.uni-goettingen.de/shelxl_html.php); model completeness and the analysis of variance matter more than making GooF approach 1.

- Do not confuse the refined SHELXL GooF with PLAT939's S calculated using the supplied intensity uncertainties alone. Record both, their definitions and the exact report version. A near-one weighted GooF can coexist with an extreme PLAT939; inspect the contributing reflections and sigma(I), particularly PLAT919/934, rather than chasing 939 by changing WGHT alone. See the [case-free A/B action playbook](ab-alert-action-playbook.md#plat939).
- Record the **active** `WGHT` from the executed INS/LST separately from the next-job suggestion after `END` in RES. The suggestion is not automatically applied. To test it, replace the active instruction in a new numbered INS, retain exactly one active WGHT, and record old/new coefficients.
- For a new initial model, the ordinary `WGHT 0.1` starting scheme is reasonable; do not reset a justified existing scheme blindly. Normally wait until the model is essentially complete, including justified H/disorder treatment, before adopting suggested coefficients routinely. Investigate conspicuous weighting problems earlier when warranted; changing weights cannot supply missing atoms or disorder.
- Preserve a fixed-weight baseline for model comparisons. Test a weighting change separately from new restraints, OMIT or other model changes. Set a small explicit job/cycle limit, and stop if shifts oscillate, coefficients drift or the model becomes unphysical rather than repeatedly chasing the latest suggestion.
- Compare R1, wR2, GooF, shift/esd, ADPs, populations and difference density, plus residual/variance trends by intensity and resolution. wR2 and GooF under different weighting schemes are not directly like-for-like; inspect unweighted intensity discrepancies too. SHELXL's suggested scheme aims to flatten variance against calculated intensity, not necessarily resolution. Large coefficients or persistent trends warrant checking model adequacy, intensity uncertainties and data processing, not an automatic diagnosis or further down-weighting.
- Do not force GooF to 1 or tune weights solely to cross an A/B threshold. A reflection no longer exceeding a weighted outlier threshold is not thereby proven sound. Retain negative measured intensities in refinement; the `max(0,Fo²)` in the weighting expression is not an instruction to discard them.
- Before final validation, verify that CIF `_refine_ls_weighting_scheme` and `_refine_ls_weighting_details` describe the weights actually used, not an unused suggestion. Generate matching final outputs after an adopted change and validate the resulting CIF. A reminder about weights or an output-only request does not authorize resuming a paused refinement.

## Model-change checkpoint

Before changing the chemical model, summarize the evidence and expected effect. This checkpoint applies to:

- atom-type changes;
- disorder, PART/FVAR, or occupancy models;
- restraints or constraints beyond routine hydrogen placement;
- TWIN/BASF or changed reflection treatment;
- space-group changes;
- solvent masking or SQUEEZE;
- deletion or omission of reflections.

The record must distinguish data-supported corrections from choices made for stability or presentation. In an authorized autonomous run, this is a logged decision and comparison, not a requirement to ask again before each reversible trial. Preserve the baseline and failed trials; do not automatically accept a candidate merely because its alert count or R value falls. A user's explicit pause or withheld permission still takes precedence.

## Stage 4: validate

Before launching validation, run the [experimental-metadata preflight](experimental-metadata-preflight.md). A regenerated SHELXL CIF can lose collection records even when the original CIF contains them. Separate experiment facts from model-derived quantities; do not let avoidable missing-field alerts stand in for model quality. Record unknowns/conflicts and retain the exact pre-merge model and data.

Generate final CIF and FCF data, then run local PLATON as a preflight check. Preserve `.chk` and `.ckf`; preserve plots when generated. Label these outputs as local validation, not an official IUCr report. Classify every alert by level and by likely cause:

- metadata or CIF construction;
- experimental data quality or completeness;
- structural model deficiency;
- methodology/query;
- informational.

For this user's workflow, prioritize investigating and justifiably resolving A/B alerts, then compare the quality of scientifically defensible candidates. Read [ab-priority-refinement.md](ab-priority-refinement.md). A clean report obtained with an unsupported model, invented metadata or concealed evidence is not an acceptable result. Keep material C/G alerts visible and resolved or explained.

### Official IUCr checkCIF

For a complete structure-processing delivery, submit the final CIF containing reflection data to https://checkcif.iucr.org/ and request structure-factor validation. Confirm that the embedded reflection data belong to this final refinement; an external FCF sitting beside a CIF is not evidence that the uploaded CIF contains them.

- Upload only with the user's authorization to share the structure and reflection data with IUCr. An explicit request to upload to IUCr is sufficient; otherwise explain the destination and ask before uploading. Do not enable unrelated deposition, email, or duplicate-database services without authorization.
- Verify the website's actual response confirms that structure factors were supplied and checked. Upload success alone is not enough. Resolve any CIF syntax errors before final delivery.
- Save the official, unmodified report as `delivery/IUCr_checkCIF.pdf`. Keep the structure-factor HTML/CKF when available and the submission record under validation/audit outputs; these are supporting records, not additional user-facing checkCIF formats. Record the uploaded CIF hash, date, options, report URLs and alert counts. Do not reconstruct or translate a PDF and label it an official report.
- Record local and online alert counts separately. If the final CIF or model changes, its earlier official report no longer validates the changed file; resubmit the changed final file within authorized scope.
- If upload is unauthorized, unavailable, or unsuccessful, preserve the final files and local diagnostics and mark official validation as pending. Do not claim the full delivery requirement is met.

### Crystallographic report and delivery

#### Headless assembly, saving and round-trip check

Before handing over even a preliminary viewing copy, preserve the previous version and use a supported, audited script to assemble symmetry-equivalent fragments. This does not require an Olex2 window. [Gemmi's unit-cell, symmetry and tensor operations](https://gemmi.readthedocs.io/en/latest/cell.html) are useful building blocks, not a turnkey SHELX-preserving assembly guarantee. The current skill has case-specific rendering/auditing experience, not a generally validated automatic assembly writer.

- Use the full cell metric and validated space-group operations to choose connected symmetry-equivalent representatives, guided by chemical connectivity. Do not independently wrap each fractional coordinate into 0–1: that can split a molecule across cell faces. Centre a rendered view with the camera, not an arbitrary coordinate-origin shift.
- Keep solvent/counterions as separate molecules. Do not invent bonds to bring all components together. Keep alternative disorder components coherent; preserve PART, FVAR, site multiplicity/SOF, atom labels, AFIX-dependent H atoms and the semantics of restraints/constraints. Transform any affected symmetry-coded references consistently. Decline unsupported syntax instead of dropping instructions during serialization.
- Apply the coordinate transformation to the anisotropic tensor in the correct crystallographic basis; do not blindly apply a Cartesian rotation to SHELX Uij. An isolated test on an orthogonal cell does not validate nonorthogonal-cell handling. An ASU on a special position may require symmetry-generated display atoms for a full molecular view; these are not extra independent atoms. For polymers show a bounded, labelled fragment.
- Save into a new version and parse the actual written INS/RES again. Check atom identities, symmetry-equivalent positions, transformed ADPs, occupancies, H/AFIX relationships, formula, connectivity and unchanged raw HKL. Where calculable, compare structure-factor intensities and R values within justified serialization tolerance. Render from the saved files to inspect the assembled structure, rather than only viewing the in-memory transformation. Never label a static image as proof of an Olex2 reopen test that did not occur.
- Prefer assembly before the last authorised refinement/output stage, then generate matching CIF/FCF and metadata from that representation. Do not carry stale coordinate/geometry uncertainties into a changed representation without valid transformation or recalculation. Freeze the resulting files before online validation and Word-report extraction. For a presentation-only request on a paused model, do not resume refinement merely to force CIF generation; retain earlier files separately and label pending outputs.

If Olex2 is explicitly used, the installed orange toolbar button runs `compaq >> compaq -a >> center` (verified in `etc/gui/blocks/snum-info.htm`). On the tested build, File > Save wrote INS while RES remained unchanged: verify the real outputs and reopen the delivered file. An optional Olex2 model/view file may preserve symmetry-grown display. This GUI route is a fallback, not the default delivery gate.

Assembly is a presentation/representation requirement, not proof that disorder, large U values, convergence or validation alerts have been resolved. Keep scientific limitations visible.

By default, produce **two separate editable `.docx` crystallographic reports: one Chinese and one English**. Use `<sample>_晶体学报表_中文.docx` and `<sample>_Crystallographic_Report_EN.docx` to distinguish them. Translate titles, table headings, captions, methods, conclusions and alert explanations into the language of each document; retain standard atom labels, symbols, units, software names and official alert codes. Both reports must use the same frozen final CIF and shared numerical table dataset, with identical values, uncertainties, atom labels, symmetry codes, occupancies, alert counts and scientific limitations. Preserve useful native template tables, mathematical headers and styling, replace scientific values with current results, and correct template errors. Keep the official IUCr PDF unchanged in its original language.

Render both Word documents separately for internal visual QA and inspect every page. Cross-check table row counts and scientific meaning between the two language versions; neither translation may omit an unresolved warning or make a stronger claim. Keep resulting PDF/PNG files under `report_render/` or an equivalent QA directory, not `delivery/`, the user-facing index, the final answer or the delivery ZIP. Do not deliver a separate `晶体学报表.pdf` unless explicitly requested. A complete delivery needs both checked DOCX files and the official `IUCr_checkCIF.pdf`; no additional report PDF is delivered unless requested.

Include crystal data and refinement statistics, fractional coordinates and Ueq/Uiso, anisotropic displacement parameters, chemically meaningful bond lengths/angles and symmetry codes, refinement methods, references, and official validation findings. State unresolved alerts and model limitations. Distinguish special-position SHELX SOF normalization from chemical/CIF occupancy, and document disorder/PART/occupancy treatment when applicable.

Do not invent collection metadata, hydrogen positions, deposition identifiers, or deposition status. Attribute inherited experiment metadata to the supplied records and flag what the collecting laboratory must confirm. Do not copy coordinates, ADPs, geometry, or validation results from an older template model. Render and inspect every final report page for clipping, broken tables, incorrect mathematical labels, and misplaced section breaks.

Deliver the exact uploaded final CIF, FCF, final INS/RES, associated HKL and refinement log, original `IUCr_checkCIF.pdf`, both Chinese and English Word reports, and submission/audit record in a clearly named output directory; provide a ZIP when useful using an explicit delivery file list that excludes document QA previews and superseded validation PDFs. Check basename and reflection-source references (including an Olex2 `HklSrc` remark if present) against the delivered HKL; renaming a file is not enough to repair its references. Verify the user's input files and template remain unchanged. Keep provisional or older local-only reports separate from the primary final delivery.

For an end-to-end structure-processing request, proceed from the frozen final model to the authorised official IUCr validation and template-based report as part of the requested work; do not stop at a structure file and ask whether reports are wanted. If the user has paused modelling, respect that checkpoint: a preliminary viewing copy is not a final completion, and any requested interim checkCIF/report must be labelled preliminary. Outstanding upload consent, unavailable services, missing template/data or unresolved science must be stated rather than concealed.

An unresolved but usable candidate also deserves matched Chinese and English preliminary crystallographic reports, both clearly labelled and, within the current user's authorization and service capabilities, official structure-factor checkCIF. Do not present it as publication-ready. If no template was supplied, create generic editable Chinese and English crystallographic reports using the same current model rather than blocking solely on a template request. Report individual delivery stages (model, CIF/FCF, official checkCIF PDF, Chinese DOCX, English DOCX) as completed, pending or failed; an overall report file cannot stand in for a missing official result. The [routine delivery driver](routine-automation.md) now bundles a bounded IUCr uploader, shared-data bilingual DOCX generator and Word/LibreOffice rendering adapters. Its default layout is reusable; a different requested template or unsupported scientific format needs a separately checked adapter. Probe the host dependencies and verify actual output; this is not universal format or scientific-model coverage.

## Windows PLATON completion rule

On the local Windows bundle, `platon.exe -u <name>.cif` generated complete `.chk`, `.ckf`, `.fcf`, `.ps`, and `platon.out` files but kept the interactive process alive. The bundled routine runner implements these completion checks; specialist runners must also:

1. launch PLATON in its isolated validation directory;
2. wait for the expected report files;
3. confirm that `platon.out` contains the CheckCIF and CheckFCF output lines and that report sizes have stabilized;
4. enforce a bounded timeout;
5. terminate only the exact PLATON process it launched if the reports are complete but the process remains alive;
6. record this as `reports_complete_process_terminated` (or an equivalent explicit termination state), not a normal exit.

Do not terminate an unrelated PLATON or Olex2 process.

## Final acceptance

Final acceptance requires reproducible inputs, normal SHELXL completion, stable refinement, chemically plausible geometry and displacement parameters, CIF/FCF validation, and an explanation for material alerts. Inspect connectivity, ellipsoids, disorder, packing and residual density using numerical checks and views rendered from saved data; Olex2 is an optional interactive review tool, not a requirement to finish a headless run.

Distinguish delivery completeness from scientific acceptance: a complete package may still require crystallographer review. State `needs_review` when material alerts or unresolved model/data questions remain. Do not promise that an arbitrary dataset can be solved perfectly or that absence of A/B alerts proves the structure correct.

Produce two layers of reporting:

1. a short Chinese beginner summary stating whether the structure is ready, needs review, or is blocked, plus the next action;
2. a technical appendix containing program versions, commands, metrics, alerts, model changes, and output paths.
