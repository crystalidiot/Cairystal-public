# Reliability after real A/B trials

These checks are executable rules, not repeated instructions for an agent. Continue using `autorun` / `complete`, preserve controls, and validate each proposed model.

- Cell pairing uses displayed-digit rounding, not standard uncertainty, and records differences. All embedded RES/HKL, atom, symmetry and reflection checks remain active; similar cells alone never establish specimen identity.
- Atom-specific 213/214/234 alerts with unchanged identity but changed numeric payload remain unresolved and appear in `value_changed`. Duplicates, PART suffixes, severity, type and symmetry context are preserved. Unknown text is not broadly stripped of numbers.
- Metadata overlays require unchanged HKL and CELL/symmetry controls. Six cell parameters and volume retain source precision together. Unknown source volume remains unknown; placeholder ZERR must not create apparent experimental precision. No atom or reference model is copied.
- Incomplete local validation records `validation_complete=false`, `validated_counts=null` and `alerts=null`; `partial_parse`, failure reason and hashes remain available. Empty output is never zero A/B. A failed independent candidate does not imply batch failure; failed shared controls stop invalid comparisons.
- For 241/242, disordered or partially occupied bonded neighbors defer a full-occupancy site's automatic Ueq-only element scan to disorder review. This does not confirm its current element. An explicit evidence-supported hypothesis may still use `repair-plan`.
- Reports use heading-level page breaks. QA checks body content excluding headers/footers; images and vector figures count as content. Bilingual tables, preserved text and rendered pages must pass. Official PDFs may only be reused for the exact same CIF hash; changed models need fresh validation.

The four-case replay tests engineering behavior on existing working models, not new independent solutions or reference-scored accuracy. Disorder topology, uncertain chemistry, unsupported water H and unresolved alerts still require scientific review.
