# Routine H and factual reporting

`hydrogen_plan.py` generates an explicit HFIX plan without an LLM. It does not identify unknown chemistry. Supply the current H-free RES, a heavy-atom chemical graph, and a one-to-one graph-ID to current-label mapping. Do not reuse reference coordinates or labels during a blind test.

```text
python scripts/hydrogen_plan.py --model CURRENT.res --graph GRAPH.json --mapping MAP.json --output NEW_PLAN_DIR --donor-protonation-basis "Current evidence for N/O protonation" --dependency-dir OPTIONAL_PACKAGE_DIR
python scripts/crystal_pipeline.py step --run RUN --source CURRENT_STAGE --plan NEW_PLAN_DIR/plan.json --name NEW_H_STAGE
```

Graph schema: `atoms` list of `{id, element, formal_charge, hydrogens}` and `bonds` list of `[id1,id2,order]`, where order is 1, 1.5, 2 or 3. Carbon H count may be omitted and derived from neutral tetravalence. Other sites require an explicit count, including zero. `geometry: "planar"` explicitly supports a neutral two-neighbor NH. Mapping is a plain JSON object `{graph_id: current_atom_label}` covering every current heavy atom once. Standard MOL/SDF/SMILES parsing and image recognition are separate upstream capabilities, not claimed by this helper.

## Implemented rules

| Parent environment | HFIX generated |
| --- | --- |
| Neutral C, one single heavy-atom bond, H3 | 137 |
| Neutral C, two single bonds, H2 | 23 |
| Neutral C, three single bonds, H1 | 13 |
| Neutral C, two neighbors with single+double or two aromatic bonds, H1 | 43 |
| Neutral C, one triple bond, H1 | 163 |
| Explicit terminal N+, one single bond, H3, recorded protonation basis | 137 |
| Explicit neutral planar N, two single bonds, H1, recorded protonation basis | 43 |
| Explicit neutral O, one single bond, H1, recorded protonation basis | 147 |

HFIX constructs groups and writes the resulting AFIX constraints. Let SHELXL use the actual TEMP and parent element/environment for distances; do not force all X-H lengths to a single value. Rotating groups are initialized/refined from current structure factors. This is distinct from independently locating/refining every H coordinate.

Hybridization alone is insufficient: sp3 carbons can be CH3, CH2, CH or C. A lone oxygen is not automatically water. The rule generator checks graph valence/charge, current element types, covalent-neighbor consistency with symmetry, full populations and general positions. It rejects existing H/HFIX/nonzero AFIX, custom connectivity, complex syntax, disorder, special positions and mismatched mapping. Water orientation, uncertain protonation/tautomers, coordination compounds and unsupported geometry produce explicit findings; no executable plan is emitted until those findings are resolved. No silent partial model repair.

After execution, check generated H counts and formula/charge, occupancy/PART inheritance, residual density near donors, contacts, convergence and A/B findings. Existing pipeline local PLATON and authorized official IUCr routes remain in force. No automatic OMIT or restraint merely because H addition did not clear an alert. Retain the H-free baseline and each changed candidate.

## Report templates versus scientific interpretation

Use the project name **Cairystal** for a discreet assistance credit. `bilingual_report.py` adds an 8 pt grey footer alongside page numbering: “结构解析与精修由 Cairystal 协助完成” / “Structure solution and refinement assisted by Cairystal”. `crystal_pipeline.py` adds a small footer to result pages; its wording does not imply that an incomplete run succeeded. Credit is generated before rendering, QA and hash sealing. Keep scientific software names and original IUCr PDFs intact; do not retrofit previously sealed reports. A credit does not imply authorship, correctness certification or IUCr endorsement.

The derived final CIF also receives a standalone ASCII header comment: `# Structure solution and refinement assisted by Cairystal.` Use `cif_text_preflight.add_assistance_comment` after all CIF serialization and before local PLATON, IUCr submission and final hashes. It preserves a leading CIF1 version declaration, checks all parsed values and retained original bytes, creates a backup/audit, and is idempotent on repeated passes. Comments are non-data syntax under the [IUCr CIF1 specification, paragraphs 21 and 45](https://www.iucr.org/what-we-do/digital-standards/cif/cif1/file-syntax). Do not add an unknown CIF data item or overwrite actual solver/refiner provenance. Third-party rewrites may discard comments; reapply only in a new derived output before validation, never patch an already sealed CIF while retaining its old official report/hash.

Keep generated plan reasons path-independent and ASCII. `cif_text_preflight.py` checks the entire CIF1 byte stream before networking. In derived working copies only, it can encode Unicode in `_publ_section_exptl_refinement` or `_exptl_absorpt_special_details` as an explicitly labeled reversible JSON string, while preserving the exact original CIF and Unicode text in an audit record. It verifies all other tokens unchanged. Non-ASCII atom labels, unsupported fields and control characters stop locally; never strip characters from the model or embedded reflection data to force submission.

Report bodies contain concise Chinese/English methods, official A/B alerts and supported limitation summaries. `narrative_digest` extracts known absorption-processing statements without inventing a translation of arbitrary logs. Unknown review items remain flagged and require scientific review. Full source narratives, bilingual review notes, weight trials and source hashes are delivered separately in `full_audit_records.json`; `model.lst` and the run directory retain native outputs and full command history. Archive text is not dumped into Word. Detailed coordinates, ADPs, geometry and numerical consistency checks remain intact.

`routine_finish.factual_notes` selects `report_method_templates.hydrogen_method_notes` from the actual final RES. It produces equivalent Chinese/English descriptions of AFIX treatment and relative H Uiso factors. Missing/unsupported control information stays explicit; it does not claim all H were experimentally located. Existing numerical, weight and metadata templates remain active. New chemistry, a cause for an unresolved alert, or a statement that a structure is correct requires evidence and cannot be supplied by a generic author's-response template.

Document content checks, automated geometry checks and actual visual review are separate. Under the user's exception-only review preference, use the implemented [automatic review](automatic-report-review.md) route. It compares DOCX text against rendered PDFs, checks glyph/page/image/table boundaries, numerical tables and exact-file hashes, and seals only when its rules pass. It records `visual_review_performed:false`; never set `reviewed-*` from a template or successful render. Unknown or flagged issues need actual review. Full aesthetic and figure-label semantics remain outside automated coverage.

## Two-dimensional input routing

Prefer machine-readable MOL/SDF/SMILES supplied by the user. If only an image is available, a one-time AI transcription with graph/charge/stereochemistry checks is a practical default for occasional cases; retain the resulting structured graph for all subsequent computation. Exact model-token cost is not available, so do not promise a token figure.

Optional local OCSR can reduce recurring image-to-graph calls for large/private/offline batches, but it is itself an ML model and needs installation, weights and local performance/error benchmarks. MolScribe can return SMILES, MOL, atoms/bonds and confidence on CPU; DECIMER predicts SMILES and uses separately downloaded models. Neither a valid SMILES nor a high confidence score proves that the drawing was read correctly. Preserve explicit charges, stereochemistry, disconnected ions, solvent coefficients and uncertain labels. Validate the graph and, when needed, render back for comparison; only then use it for crystal matching. No local image recognizer was installed by this change.

Sources: [SHELXL AFIX/HFIX](https://shelx.uni-goettingen.de/shelxl_html.php), [MolScribe official repository](https://github.com/thomas0809/MolScribe), [DECIMER official repository](https://github.com/Kohulan/DECIMER-Image_Transformer).

For mixed PART/BIND connectivity, ineffective restraints or H geometry after splitting, read [原生限制与氢几何 / native restraint and H audit](part-hydrogen-native-audit.md). This documents diagnostic limits and conditional trials; it does not enable automatic model acceptance.
