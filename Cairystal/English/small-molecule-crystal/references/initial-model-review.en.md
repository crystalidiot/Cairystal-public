# Post-solution screening and C/N/O assignment

A SHELXT output is a candidate. After a short current-run SHELXL baseline, `crystal_session.start` now records `initial_review.json` for each candidate. The candidate packet preserves its path, digest and status. An unavailable review is not treated as completed by the coordinator.

    python -B scripts/toolbox.py run initial-review -- --directory CURRENT_CANDIDATE --stem model --elements C N O Cl --output NEW_REVIEW.json
    python -B scripts/toolbox.py run route-problem -- --initial-review NEW_REVIEW.json --json

The read-only tool uses the selected candidate's paired CIF/RES and same-stem LST/CHK. It records actual scattering types, PART, occupancies, symmetry-aware contacts, contact angles, comparable-neighbour ADPs and reported Q peaks. It neither edits a model nor accepts chemistry. No CIF means the baseline must first produce a paired current-run CIF; never borrow one from an old model.

Use four complementary evidence classes: (1) SFAC and complete connectivity, including symmetry/PART; (2) valence, charge, chemically appropriate bond distances and angles; (3) ADPs compared with similar environments and populations; (4) local signed residual density. A too-light assignment may produce a low U and positive residual, and a too-heavy assignment a larger U and negative residual. These are clues: occupancy, disorder, terminal motion and data errors can give similar behaviour. A Q list or global density extrema cannot replace a signed local map. See [IUCr PLAT242](https://journals.iucr.org/services/cif/checking/PLAT242.html).

Use `match` with a reviewed complete 2D graph within its supported scope. Otherwise use explicitly justified `session refine` alternatives (`variant_site` and `variants`) for current-run C/N/O candidates only. Keep observations, reflection selection, initial weights and restraint assumptions comparable. Compare local chemistry, density, ADP/population and convergence, not only R. Determine type/protonation before generating H and reconciling UNIT/formula. No single bond distance, U value or peak height uniquely determines C/N/O.

Statuses: `needs_review` has explicit flags; `screened_requires_chemical_review` has no implemented numerical flags but is not scientific acceptance; `review_unavailable` records a diagnostic failure. Current thresholds are triage hints, not PLATON thresholds. Ambiguous assignments remain unresolved.
