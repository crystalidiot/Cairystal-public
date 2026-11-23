# When structure solution fails

Use alongside the main solution workflow. This is a diagnostic order, not a guarantee that known elements determine a unique structure. Keep originals read-only and preserve each candidate in a separate job directory.

## 1. Check the input before increasing search

Establish the actual observation format (F, F², grouped twin observations, or a special experiment), uncertainty fields, fixed-column layout, terminator and scaling. A file extension does not establish HKLF. Verify wavelength, unit cell, setting, symmetry, atom-type ordering and plausible cell content; title text is not authoritative. A solver that ignores batch/domain information may need a specifically prepared diagnostic input, not the unmodified grouped observations. Never overwrite the original reflection file.

Check merging and absence statistics together with raw-image/reduction evidence if available. Large apparent extinction can come from a format mismatch, beamstop shadow or overload; do not compensate automatically with EXTI. Heavy atoms, special positions and twins can distort E-statistics. Historical Rint, volume-per-atom or resolution rules are screening clues, not pass/fail gates for every current solver.

A high completeness percentage calculated after excluding systematic absences does not resolve strong measured absence violations. Check the earlier space-group search even when the final model has no A/B alerts: a plausible metric and centric E-statistics may coexist with an unsuccessful space-group selection. Trace settings and overlapping reflection conditions before counting violations, and investigate data/model alternatives rather than automatically loosening tolerances or omitting the conflicting reflections.

## 2. Retain more than the top-ranked candidate

For sparse light-atom/high-symmetry data, use the case-free [specialized route](sparse-light-atom-solution.md) for canonical LATT/SYMM encoding, SHELXD grid-versus-resolution settings, averaged density and model-prior provenance. An invalid setup trial and a correctly configured unsuccessful search are different outcomes.

Record solver/version, settings, seed where meaningful, resources used and diagnostic scores. Inspect chemically and crystallographically plausible alternative solutions, not only the best internal score. Seeds alone may not reproduce a historical algorithm on another build/machine. Increasing trials is reasonable only after the input checks, with a bounded budget and a log of whether new plausible candidates appear.

A correctly oriented fragment may have the wrong origin or setting. Partial-structure expansion or lower-symmetry diagnostic phasing can help find missing symmetry; it does not establish the final space group. Consider an appropriate heavy-atom/Patterson route where applicable. Do not transplant SHELXS TREF/PATT/TEXP syntax to SHELXT or SHELXD without their own current documentation.

For SHELXT, inspect the actual command and version-specific help before interpreting the candidate list. An explicit space-group restriction can explain why only one group was evaluated; that is not independent confirmation. In the supplied 2018/2 logs, UNIT atom counts were not used as a known composition and initial element-count labels sometimes contradicted the supplied chemistry. CFOM/CHEM, an initial Flack value near one half, or a lower-R noncentrosymmetric candidate do not establish a chemically valid final solution. Distinguish input/unique reflections from expanded P1 and phasing-extrapolated reflections, and distinguish the solver's resolution cutoff from the later refinement range. None of the synthesized reflections becomes an experimental measurement.

## 3. Compare explanations, not cosmetic improvements

Difficulty solving may arise from data limitations, twinning, pseudo-/missed symmetry, disorder or composition errors. Test only evidence-supported hypotheses. Twin domains add intensities with fractions; alternative local conformations use a different model. A dramatic R reduction is useful but must agree with reciprocal-space/chemistry, fractions and uncertainties, ADPs, residual density and validation.

Atom splitting, guessed solvent and restraints can reduce R or hide residual features without resolving identifiability. A solver's split suggestion is a candidate, not an instruction. Distinguish a continuous anisotropic distribution from resolvable alternative sites and inspect shared-atom hydrogens for each component.

## 4. Audit model/data boundaries

- Physical site occupancy and the program's multiplicity-weighted SOF are different quantities. Verify the site orbit and cell contents before interpreting values below one or constructing SUMP. Do not make all special-position SOFs equal to one.
- PART/AFIX scope and occupancy overrides, atom ordering, external includes and connectivity edits can change H generation and restraints. Check actual expanded/output parameters. A shared PART0 parent can need component-specific H positions; one automatic H set may represent only one component.
- An exact EXYZ/EADP/rigid-group constraint is not the same as a soft distance/ADP restraint. State the assumption and what freedom remains. A constrained small SU is not independent proof from diffraction.
- Numerical stabilization, fixed parameters, zero applied shifts, CGLS convergence and a final full-matrix uncertainty evaluation are distinct. DAMP 0 0 does not itself establish convergence. Report conditional uncertainties when variables were frozen.
- Refinement reflections, Fourier-map reflections and exported FCF may differ in merging/corrections. Verify actual format and pairing, not raw numerical equality alone. Preserve the original data and processing history.

Never fill missing measurements by statistical phasing-generated reflections, alter metadata to evade validation, or fit observed intensities to the current model and present that as independent evidence. Historical SHELXA/model-derived HKL correction and protein water-building recipes are not approved automatic small-molecule repair routes.

Evidence scope: original synthesis following complete private reading of the 154-page SHELX-97 manual, including its examples and limitations. Current software semantics and example results have not all been verified/reproduced. This page does not enable unattended expert repairs or certify any tutorial model.
