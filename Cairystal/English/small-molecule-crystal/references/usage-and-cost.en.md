# Evidence-based removal of repeated work

Chemical reasonableness and current diffraction evidence come first. Invoke tools for the current problem, rather than running the entire toolbox. Zero A/B alerts never replace atom-type, connectivity, occupancy, hydrogen or model review.


## Compact sequence from trials to delivery

These are agent execution instructions, not a new automatic geometry classifier or a measured end-to-end speedup.

1. **Compare once per round.** Address one explicit question using existing tools and the same-job runner. Read a compact candidate summary of R1/wR2/GoF, convergence, occupancies, NPD/ADPs, density, complete-fragment geometry, restraints and A/B changes; expand native logs for anomalies. Missing evidence remains unknown and needs inspection. Independent computations may run concurrently; model selection and dependent steps remain sequential.
2. **Review geometry before preparing an upload.** For disorder, inspect each conformer's complete connected fragment, shared pivots, terminal angles, occupancy and H atoms, not just split carbons. Use symmetry and PART to distinguish real contacts from mutually exclusive conformers. Zero A/B does not admit chemically implausible geometry. A clearly labelled diagnostic submission remains possible for unresolved questions.
3. **Run only a next step that can change the decision.** Retain the current candidate, rejected alternatives with reasons, and unresolved questions. Do not repeat failed equivalent trials without new evidence. Follow concrete new evidence; where the data are insufficient, retain the best-supported model with its limitations rather than declaring success because time is short or R is low. Avoid rewriting full narratives or duplicating helper scripts after every trial.
4. **Deliver after selection.** Complete chemical, geometry, native-output and local validation first; fix CIF/structure-factor fingerprints, obtain the matching official report under applicable authorization, then build both Word reports. Use existing complete / deliver and check-delivery entry points for pairing, numerical/layout checks, copying and destination hashes. Avoid repeated formal reports while models are changing. Add only a minimal, documented adapter when existing tools cannot handle the task.
5. **Invalidate only affected outputs.** A changed temperature model does not require rerunning other temperatures. A changed final CIF requires renewed matching of authorization and official report. Report-only layout edits retain the still-matching official report but require rendering and checking changed documents. Reuse unchanged artifacts only under the fingerprint rules below, retaining final verification of all four deliverables and disclosed limitations.

Positive case: an implausible terminal angle despite zero A/B should trigger repair before a formal upload. Counterexample: changing only Word column widths with an unchanged model/receipt should not rerun refinement or upload; the changed document still needs rendering and QA. Separate native runtime, analysis gaps, official validation, reporting and interaction waits; do not add overlapping intervals or claim unmeasured speedup percentages.


- For verified metadata-only A/B reports, `ab-auto` retains pairing/native gates and CHK integrity checks, then returns the unresolved fields and routes. It avoids copying coordinates, scanning all atom neighbourhoods and constructing an unused refinement plan. Mixed, unknown and structural alerts retain full diagnosis.
- Same-job `deliver continue` attempts to reuse pages from the previous delivery. An explicit `deliver run --render-cache SAME_JOB_QA` is also available. No other jobs are searched. Legacy manifests without a reuse contract cause a fresh render.
- Every DOCX package part is hashed; only ZIP container timestamps are ignored. Renderer executables/code, font inventory/size/timestamps, template and relevant settings must match. Dynamic fields, external relationships, unverifiable environments, missing or altered artifacts cause a fresh render. Font file attributes are a conventional local cache invalidation signal, not cryptographic host attestation.
- Both PDFs, every PNG and page counts are verified. Numeric consistency and full source/PDF layout QA still run. Reuse makes no claim of human/AI visual inspection, scientific correctness or permission to read unrelated models. Updated models, alerts or narrative alter the document fingerprint.
- Official checkCIF remains bound to the final CIF and complete receipt. Render reuse does not replace IUCr validation or widen upload authorization.
- Keep rare but necessary SHELXD, special-position, disorder, twin and SQUEEZE routes. Do not add elaborate caches merely to save milliseconds in inexpensive input/chemical checks.

Use `performance --run DELIVERY_RUN` to distinguish rendering, reuse and layout-QA time. A stage replay is not a measured improvement in end-to-end independent structure determination. Unknown token usage stays unknown.

Run maintenance tests through the pinned entry point, avoiding ad-hoc imports from folders containing old same-name scripts. The portable test runner sets UTF-8 for child CLI JSON. Preserve original HKL, models and previous reports.
