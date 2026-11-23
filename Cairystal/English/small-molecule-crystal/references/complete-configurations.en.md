# Complete configurations and shared special sites

Use the explicit `fragment-orbits` mode when a molecule requires symmetry-generated atoms, mixed SOFs or whole-molecule special symmetry. Supply reviewed complete configurations, an explicit `probability` for each, and atom entries such as `{"label":"C1","symmetry":"1-x,y,1-z"}`. Operations must belong to the current CIF space group modulo integer translations. These are input descriptions, not transferable structural templates.

The tool merges symmetry-duplicate whole configurations using an element-preserving one-to-one atom match and one common lattice translation. It sums configuration probabilities at each physical site and compares them against SOF/site-multiplicity and CIF chemical occupancy. Two half-populated orientations can correctly share a fully occupied inversion-centred atom. The supported bound is 64 space-group operations and 128 unique configurations; larger problems require review.

Negative PART is not a universal special-position repair. A negative-PART atom manually fixed on an axis may export a CIF occupancy inconsistent with its geometric site multiplicity. Preserve a control; restore native special-position handling only for evidence-supported sites and inspect the actual resulting CIF. Never change CIF occupancies merely to pass validation.

Include the actual riding-H labels when changing a parent site's PART. Check AFIX, SOF, H multiplicity and exported H occupancy. Do not guess H labels or select atoms by string prefix: C9 is not C91. Explicit-mode diagnostics follow existing riding parents and flag incompatible nonzero PARTs and H occupancy exports. A shared PART 0 parent may have alternative H orientations, so parent and H chemical occupancies need not be identical.

Compare models with fixed weights. An off-centre split producing NPD/instability for a negligible R1 improvement is not preferable to a valid shared-site model. Refining both mutually exclusive orientations above 0.5 violates their population bound despite a lower R1. A restrained flexible ring with implausible mean bond lengths is not automatically better than its rigid control. Preserve unchanged models when no supported improvement emerges.

Separate structural findings, missing metadata and reflection anomalies. Different line endings or a 000 terminator can change HKL hashes without changing reflections: retain originals, compare only h/k/l, Fo-squared and sigma before the terminator, and do not interpret unknown trailers. Use authorized original reflection copies for final calculations. Record implementation failures separately from scientific outcomes.

These are necessary-condition diagnostics, not proof of identity or globally feasible disorder. Chemistry and configuration membership remain reviewed inputs; severe contacts are review evidence, and only pair/triple exclusion bounds are checked. See the [SHELXL instruction reference](https://shelx.uni-goettingen.de/shelxl_html.php).
