# Atom-centred diagnostics and bounded trials (experimental)

This is executable diagnostic support, not a trained structure-prediction model. It does not identify a chemical compound, select a space group, or automatically accept disorder. Stable dispatch, refinement, A/B checking, IUCr validation and bilingual delivery remain required.

## Entry points and dependencies

Use the configured Python environment with Gemmi (tested 0.7.5). Only the full Fourier map helper additionally needs NumPy (tested 1.26.4). SHELXL and PLATON require the user's licensed installations. No proprietary binary or weights are included by these modules.

`crystal_autorun.py` automatically adds `atom_diagnostics` to a scientific/report handoff when the **current run** has `finish_root/frozen/model.{cif,res,lst}` and `finish_root/local_validation/model.chk`. It never searches older jobs. The packet is written outside the sealed pipeline tree. An identical source hash reuses a verified packet; missing inputs yield an explicit reason and preserve the original handoff.

For earlier or manually selected paired models:

```text
python scripts/structure_diagnostics.py CURRENT_PAIR --stem case --status partial_model --output NEW/diagnostic.json
python scripts/candidate_trials.py EXPLICIT_PLAN.json
python scripts/compare_diagnostic_trials.py --control NEW_TRIALS/00_control/result.json --results NEW_TRIALS/results.json --output NEW/comparison.json
```

The concise `.txt` packet contains every A/B occurrence, focused atoms, nearby contacts, ADPs, occupancy/PART/AFIX and listed Q peaks. Full JSON and native logs remain available. No model API is called by these helpers.

## Scientific interpretation

1. Separate observation, hypothesis, intervention and decision. An alert code identifies a check; it is not a diagnosis. Record why each proposed atom/type/geometry change is chemically possible and what would contradict it.
2. A CIF Uij matrix is expressed in the crystallographic basis. Transform it to Cartesian coordinates before inspecting ellipsoid eigenvalues. The PLAT213/214 axis ratio is `sqrt(lambda_max/lambda_min)`, not the variance ratio. Both values are labelled explicitly. Ueq is one third of the Cartesian trace. Values here omit full covariance, so projected displacement differences are not sigma tests. [IUCr PLAT213](https://journals.iucr.org/services/cif/checking/PLAT213.html), [IUCr PLAT214](https://journals.iucr.org/services/cif/checking/PLAT214.html), [Gemmi tensors](https://gemmi.readthedocs.io/en/stable/cell.html).
3. Include symmetry-generated contacts, occupancy, PART and negative-PART exclusions. Geometric proximity is not proof of a chemical bond. Mutually exclusive sites must not become a fictitious bonded group. Only the nearest periodic image per symmetry operation is listed; very small cells may require additional translations.
4. Inspect a chemically connected fragment before splitting isolated elongated sites. A two-state model must preserve the proposed complete fragment and use coupled occupancies where justified. Examine bond lengths, occupancy uncertainty, ADP/occupancy correlation, residual density, restraints and sensitivity to different initial positions. Convergence from two seeds alone is not proof of a unique or correct model.
5. ISOR/RIGU/SIMU can stabilize a supported model. A disappearing alert accompanied by an implausible bond, residual growth, NPD, occupancy/accounting problems or a worse fit is not acceptance. An improvement in R after changing C to O does not prove the atom is O. Compare at unchanged observations/selection and weights first; later weight review is a separate recorded operation.
6. Unknown solvent and uncertain water H positions remain unresolved until chemistry and density support them. Do not invent solvent identity from an isolated O label or force a solvent into an attractive low-R geometry. No map-based integral here is an absolute solvent electron count.

## Explicit trial plan

JSON top-level keys are `baseline`, `output`, `software` (`shelxl`, `platon` absolute executable paths), `trials`, and optional diagnostic `focus`. Each baseline must contain `case.res/cif/hkl`; paired logs and validation files provide additional evidence. Each trial has a unique safe `name`, `kind`, `reason`, `evidence`, and optional `focus`, `cycles`, `geometry_checks` and `expected_unresolved`.

```json
{
  "name": "local_isor_test",
  "kind": "diagnostic_refinement",
  "reason": "Explicit locally justified ADP hypothesis; test against an unchanged continuation",
  "evidence": ["current/diagnostic.json"],
  "focus": ["C7", "C8"],
  "cycles": 20,
  "add_restraints": ["ISOR 0.10 0.20 C7 C8"],
  "geometry_checks": [
    {"atoms": ["C7", "C8"], "range": [1.40, 1.65], "basis": "Explicit single C-C bond hypothesis, not a universal threshold"}
  ],
  "expected_unresolved": ["Chemical identity and disorder uniqueness need review"]
}
```

The example is a schema illustration, not a default treatment. Run an unchanged `kind: baseline` continuation with the same cycle budget. Supported operations are explicit element changes within SFAC with consistent label mapping, selected ANI-to-ISO using paired Ueq, exact removal/addition of whitelisted local restraints, and map-only omission of specified atoms plus their dependent riding H. Units after an element/removal edit are model accounting, not proof of a chemical formula. Independently refined populations can later alter this accounting; such differences are reported rather than silently erased.

`split_fragment_seed.py` is limited to an explicitly reviewed, assembled, hydrogen-free, full-occupancy, general-position PART0 fragment. It rotates two ISO seeds around two shared anchors, uses two unused positive PART numbers and one complementary FVAR pair. Pre-existing AFIX/disorder, special positions, unsupported labels/constraints, periodic bond assembly and ambiguous mappings are rejected. It is not an automatic disorder detector. Actual geometry checks and alternative starts must follow.

Every trial starts from the same preserved baseline. CELL/LATT/SYMM/HKLF, active WGHT and reflection selection are frozen. No reflection OMIT, unit-cell/symmetry change or automatic weight adjustment is performed here. Duplicate successful configurations link prior evidence; failed attempts are never cached as successful. The fingerprint covers instructions, HKL, metadata, optional FAB, executables and implementation hashes. All model trials remain `model_adopted: false`; the comparison helper does not choose a winner.

## Difference maps and native failures

For map-only atom omission, use `kind: omit_map`, `cycles: 0`, `omit_atoms` and no additional repair operation. The runner writes LIST 6 without ACTA; ACTA requires a nonzero least-squares calculation and is incompatible with this diagnostic export. Normal refinement remains LIST 4 + ACTA. Empty AFIX groups and dependent riding H are handled together; unresolved constraints fail closed. Native warnings are retained, not mistaken wholesale for execution failures. Native completion markers and expected files determine execution status. [SHELXL instructions](https://shelx.uni-goettingen.de/shelxl_html.php).

```text
python scripts/local_difference_map.py --fcf MAP/native/case.fcf --output NEW_MAP --baseline-cif CURRENT_PAIR/case.cif --baseline-res CURRENT_PAIR/case.res --labels C7 C8
```

The tested route requires centrosymmetric LIST 6 export. It uses `(sqrt(max(Fo2,0))-Fc)*exp(i*phase)`, crystallographic Fourier normalization and bounded sampling. Negative observed intensities are clipped **only for these derived map amplitudes**, never in the original HKL. Both positive and negative density near selected atoms and a CCP4 map are saved. Omit maps remain phase-biased, exported reflections are derived data, and interpolation/truncation differ from native peak optimization. Analytic cosine/phase tests and comparisons against SHELXL peaks are retained. [Gemmi Fourier documentation](https://gemmi.readthedocs.io/en/stable/hkl.html).

## Acceptance, records and portability

Store case evidence separately from reusable instructions: `observations`, `hypotheses`, `interventions`, `outcomes`, `rejected_or_unresolved`, `next_evidence`, and links to exact files. A failed trial rules out only that tested parameterization under those conditions, not an entire class of models. Historical routing/action labels remain weak labels unless experimentally verified.

An accepted new final model still requires the existing scientific, weighting, paired-CIF/FCF, A/B, official IUCr and Chinese/English Word gates. Metadata-related A/B can be displayed separately but must never disappear from evidence. Uploads require authorization for the actual dataset. If no model is accepted, deliver research candidates and uncertainty rather than labelling a low-R structure final.

No validation accuracy or token saving on unseen chemistry is established by replaying historical models. Report read-only diagnostic time, native execution time, local-validation time and proxy context size separately. Do not equate these with total solving time or billed tokens. New external tests must avoid exposure to reference coordinates and retain the user's blind boundaries.

### Official report integrity (2026-10-29)

Official checkCIF includes dictionary checks such as EXPT, DIFF, CHEMW and ABSMU as well as PLAT. `iucr_validation.py` retains all these alert families and every repeated instance, preserves the full official test name, and requires exact agreement with the printed A/B/C/G totals. Missing-family/count errors must stop delivery, not silently reduce counts. Five synthetic regression cases and two authorized official PDFs exercise this path.

If a saved official response already contains the PDF and structure-factor report links, a failed download may be recovered by GET on those exact HTTPS IUCr links. Verify the original submitted-CIF hash and complete reports; do not POST the data again merely because downloading timed out. Preserve failure and recovery records separately.

CIF cell values can be rounded differently from CELL and FCF. Do not weaken a mismatch check unconditionally: establish that the original CIF value differs only within its display-rounding interval and that the same-run FCF matches the unchanged CELL. Any normalization must be on a derived copy, retain the absence of measured uncertainties, and verify that atom/occupancy/ADP/reflection tokens remain unchanged. Placeholder ZERR uncertainties must not become purported experimental uncertainties. The research pair used an audited, case-specific serialization repair; a general automatic repair is not claimed.
