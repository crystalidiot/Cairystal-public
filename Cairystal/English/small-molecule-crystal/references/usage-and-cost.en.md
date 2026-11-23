# Evidence-based removal of repeated work

Chemical reasonableness and current diffraction evidence come first. Invoke tools for the current problem, rather than running the entire toolbox. Zero A/B alerts never replace atom-type, connectivity, occupancy, hydrogen or model review.

- For verified metadata-only A/B reports, `ab-auto` retains pairing/native gates and CHK integrity checks, then returns the unresolved fields and routes. It avoids copying coordinates, scanning all atom neighbourhoods and constructing an unused refinement plan. Mixed, unknown and structural alerts retain full diagnosis.
- Same-job `deliver continue` attempts to reuse pages from the previous delivery. An explicit `deliver run --render-cache SAME_JOB_QA` is also available. No other jobs are searched. Legacy manifests without a reuse contract cause a fresh render.
- Every DOCX package part is hashed; only ZIP container timestamps are ignored. Renderer executables/code, font inventory/size/timestamps, template and relevant settings must match. Dynamic fields, external relationships, unverifiable environments, missing or altered artifacts cause a fresh render. Font file attributes are a conventional local cache invalidation signal, not cryptographic host attestation.
- Both PDFs, every PNG and page counts are verified. Numeric consistency and full source/PDF layout QA still run. Reuse makes no claim of human/AI visual inspection, scientific correctness or permission to read unrelated models. Updated models, alerts or narrative alter the document fingerprint.
- Official checkCIF remains bound to the final CIF and complete receipt. Render reuse does not replace IUCr validation or widen upload authorization.
- Keep rare but necessary SHELXD, special-position, disorder, twin and SQUEEZE routes. Do not add elaborate caches merely to save milliseconds in inexpensive input/chemical checks.

Use `performance --run DELIVERY_RUN` to distinguish rendering, reuse and layout-QA time. A stage replay is not a measured improvement in end-to-end independent structure determination. Unknown token usage stays unknown.

Run maintenance tests through the pinned entry point, avoiding ad-hoc imports from folders containing old same-name scripts. The portable test runner sets UTF-8 for child CLI JSON. Preserve original HKL, models and previous reports.
