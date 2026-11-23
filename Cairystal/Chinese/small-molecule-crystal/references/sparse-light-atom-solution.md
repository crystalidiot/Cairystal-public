# Sparse light-atom data and high-symmetry solution

Case-free diagnostic guidance. Use when a carbon-only or other light-atom search fails, independent observations are few, or maps suggest averaged molecular density. No specimen identity, reference coordinates or transferable atom-count recipe is supplied here.

## Establish what is known

- A folder name is not a formula. A user request to try carbon only establishes an explicit `SFAC C` trial, not a carbon count, absence of other elements, or permission to add H. Preserve the element assumption when interpreting failure.
- Count measured records, symmetry-independent observations and refined parameters separately. Record resolution and intensity agreement by candidate symmetry and resolution shell. Many symmetry equivalents do not supply as many independent constraints as their line count suggests.
- Some different space groups share diffraction symmetry and absence conditions. Equal merging statistics cannot select between them alone. Keep candidate settings, Friedel treatment and the remaining ambiguities explicit; lowering symmetry does not recover unmeasured information.

## Rule out instruction errors before blaming the data

SHELX uses positive `LATT` for centrosymmetric groups and negative `LATT` for noncentrosymmetric groups. Centering and inversion belong in `LATT`, not in redundant `SYMM` records. In a centrosymmetric SHELX setting the origin must be on an inversion centre. A general parser can reconstruct equivalent operations from a noncanonical encoding while a program still branches on the `LATT` sign. Therefore inspect both the full operations and the program's echoed centric/acentric interpretation. See the [SHELXL LATT/SYMM instructions](https://shelx.uni-goettingen.de/shelxl_html.php).

Correct an encoding in a separate branch. If the origin/setting changes, transform coordinates and reflection indices as required and record the transformation; do not just flip the sign. Compare operations, multiplicities, populations and calculated intensities. Unexpected absolute-structure output for a centric hypothesis is a reason to inspect encoding, not to report a Flack determination.

For SHELXD, distinguish Fourier grid sampling from the high-resolution cutoff. `FRES` and the first `PSMF` argument specify sampling ratios; they are not distances in Å. `ESEL` has a separate resolution-limit argument. Check argument meanings, signs and defaults against the relevant version's [SHELXD/D and E documentation](https://citeseerx.ist.psu.edu/document?doi=7e8c91c5c39ca1e4443f999c0ddd183e19602fbe&repid=rep1&type=pdf). A smaller sampling ratio is not a finer real-space grid. Record a mistaken setting as a setup error, preserve it, and rerun a justified corrected trial before attributing its failure to the crystal.

NaN normalization, invalid matrices or an empty peak list warrant inspecting the first log error and input assumptions. They do not by themselves prove intrinsic unsolvability. Distinguish setup failure from a valid search that found no interpretable candidate. Vary one justified factor at a time and retain whether it produced new information; unlimited total time does not justify an unchanged failing loop.

## Treat molecular hypotheses as hypotheses

Shell-like or smeared density can motivate an orientational-disorder hypothesis but does not identify a particular molecule or its atom count. Record map coefficients, phase source, averaging and resolution; a map based on candidate phases is not independent confirmation of that candidate. Bragg data alone at one temperature may not separate static disorder from motion.

A mathematically generated cage or rigid fragment is a model prior, even when no reference structure was read. Label that route **model-assisted hypothesis testing** and preserve the unsuccessful direct-method result. Record the assumed connectivity, atom count, geometry, orientation populations and their provenance.

Before adding adjustable orientations, audit site multiplicities and total cell content using [disorder occupancy](disorder-occupancy.md). Distances within one orientation are different from contacts between mutually exclusive orientations. Do not let a neighbour finder create bonds or geometry restraints across alternatives. Shared/special-site population factors must be counted once, not inferred from the displayed atom count.

## Decide whether to retain the candidate

Keep a fixed-data, fixed-weight baseline. Compare connectivity, within-component geometry, tensor shapes, parameter uncertainties/correlations and local residuals, alongside fit statistics. Positive-definite ADPs and small shifts alone do not rescue a distorted molecular model. If geometry restraints restore plausible bonds but worsen the fit substantially, investigate the assumed topology/orientation/symmetry rather than deleting inconvenient data or simply weakening the geometry restraints.

Use [weighting review](workflow.md#weighting-review) and [ADP model selection](adp-model-selection.md) for those interventions; do not duplicate their recipes here. A large R improvement from an insignificant or unstable extra correction is a sensitivity result, not proof of its physical cause.

If no candidate passes these checks, preserve an explicitly labelled partial/unsolved model and explain the confirmed failures, remaining hypotheses and missing evidence. A generated CIF, visually recognizable cage or clean alert category cannot change that status. Local and official validation remain separately recorded.
