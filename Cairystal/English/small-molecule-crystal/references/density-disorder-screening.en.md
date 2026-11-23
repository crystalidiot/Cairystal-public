# Density-guided disorder proposals and staged screening

This optional tool proposes and compares hypotheses. It neither establishes disorder nor automatically adopts a final structure. Existing stable releases remain unchanged.

Start with a paired current RES/CIF/HKL/FCF/LST/INS bundle. Resolve uncertain atom types, H ownership, connectivity and special positions first. Supported local motifs are CF3, tert-butyl groups, established simple saturated chains and explicitly supported common solvent identities. Non-carbon bonded anchors are allowed.

Current native FMAP 2 Q peaks are expanded to nearby symmetry images. Bond-axis angles are fitted to peak directions; disconnected rigid fragments use proper Kabsch fits with three non-collinear anchors. Reflections are not used as spatial transforms and molecular handedness is not inverted. This is truncated, phase-biased peak-list guidance, not continuous difference-map optimization. At least two distinct displaced peaks must support a proposal, or three for fragments larger than five atoms. Matching is one-to-one. Equivalent endpoint arrangements and serious clashes are screened. No supported density means no split.

Defaults are at most four poses per site and four sites, six short refinement cycles, then one finalist per site. Short screens use anisotropic A and isotropic B (`MAJOR_ANI`); A is the initially major branch and is not silently renamed if its refined population changes. Short-screen AB is **null**, not zero. Slow short-run convergence alone is not rejection. All discarded/deferred candidates remain available.

Finalists restart from the identical baseline, not from short-screen coordinates. Each receives full 30-cycle ISO, ANI and MAJOR_ANI comparisons plus a same-cycle unchanged control. Full branches receive PLATON and checks of pairing, occupancy, H/PART, branch collapse, ADPs, geometry, residual density and AB changes. Lower R alone is not acceptance. Increase `finalists_per_site` in a new run when further alternatives need review.

```text
python -B scripts/toolbox.py run density-disorder -- prepare --baseline CURRENT_BUNDLE --output NEW_COMPARISON --profile LOCAL_PROFILE.json
python -B scripts/toolbox.py run density-disorder -- run --plan NEW_COMPARISON/plan.json
```

Use `--possible-solvents` only with supplied or explicitly reviewed current chemical evidence; record its provenance and uncertainty. `--site-ids` limits sites and `--settings` reads bounded JSON settings. Results include plan.json, screen/*/screen.json, full/* and comparison.json. Baseline/software/code hashes and resources are recorded. Original reflections remain unchanged. After scientific review, `complete` still performs weighting, exact-CIF official IUCr PDF and bilingual Word delivery. Unresolved models may only be delivered as explicitly provisional diagnostic reports.

Existing PART, special sites, unassembled periodic fragments, free H, internal flexible-ring conformations, multi-torsion joint searches and automatic chemical identity determination are outside this version. A broken aromatic graph is not an established saturated chain. Shared-centre 1,2 restraints must be retained for CF3/tert-butyl splits. Whole-ISO models may worsen major-component fits; whole-ANI models may overfit minor components. Assess all against the same data.

An initially general split atom can migrate onto a special position during native refinement. The final audit recomputes its site stabilizer and flags `split_atom_moved_to_special_position`. Recheck physical occupancy, multiplicity and symmetry-related connectivity; do not equate that CIF site occupancy with the entire minor-component population or silently halve/double it to remove alerts.

Staging has overhead and does not guarantee a speedup over an older algorithm that proposes fewer candidates. Report proposal, short/full native, official service and report-rendering timings separately. Zero internal LLM calls does not mean zero whole-task tokens. Reused development data are reference-isolated reanalysis, not unseen external validation. No real experimental models or HKL are shipped in the skill.
