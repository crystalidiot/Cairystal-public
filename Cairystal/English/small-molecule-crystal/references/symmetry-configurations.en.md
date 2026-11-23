# Review whole configurations near special positions

Use `occupancy` first, then `fragment-orbits` for reviewed complete fragments. Neither tool rewrites occupancies or accepts a model.

Distinguish decoded SHELX SOF q, general multiplicity M and orbit multiplicity m. Cell contribution is Mq; physical CIF occupancy is Mq/m. A site on an inversion centre can therefore have twice the numeric SOF as its CIF occupancy without an arithmetic error. Check whole-molecule counts and configuration compatibility before dividing anything by two.

A different case is a non-centrosymmetric molecule with two inversion-related orientations, whose individual atoms remain in general positions. Half-populated orientations may use SOF 0.5 and a negative PART. Do not also duplicate the inversion-related atom set explicitly. Hydrogen atoms follow the parent population and PART. Negative PART controls symmetry constraints/connectivity, not chemical validity; see the [SHELXL manual](https://shelx.uni-goettingen.de/shelxl_html.php).

For each reviewed compact heavy-atom fragment, supply a configuration such as:

```json
{"fragments":[{"id":"A","atoms":["C1A","Cl1A","Cl2A"]},{"id":"B","atoms":["C1B","Cl1B","Cl2B"]}],"severe_contact_fraction":0.70}
```

```text
python -B scripts/toolbox.py run fragment-orbits -- --directory CURRENT_PAIRED_BUNDLE --config REVIEWED_FRAGMENTS.json --output NEW_AUDIT.json
```

The tool applies each symmetry operation to the entire fragment and uses coherent lattice translations. It reports site accounting, severe interconfiguration contacts and pair/triple exclusion bounds. Three mutually exclusive states must have summed probability at most one, even when every pair passes. Contacts only suggest exclusion; passing these necessary conditions is not a complete global probability or chemistry proof. Unsupported elements, differing SOFs within the fragment, whole-fragment special symmetry or unassembled coordinates require specialist review.

Changing a minor state to (1-f)/2 can change mean solvent content if it replaces two major-state molecules with one minor-state molecule. Record that composition hypothesis; do not treat this as a purely numerical correction.

Before adding H to a singly bonded carbon, check valence and element assignment. An approximately 1.3 Å terminal site adjacent to a carbonyl carbon may be oxygen, subject to current geometry/ADP/refinement evidence. An implausibly short atom pair merits a documented atom-omit map: full light-atom scattering can resemble partially occupied heavier atoms. Reconstruct complete, symmetry-consistent fragments rather than assigning elements from peak height alone. Compare ADP alternatives and keep simpler models when lower-R splits have incompatible configurations.

Native HFIX handles supported symmetry-linked CH2 geometry but must precede all atoms; inspect generated H ownership and occupancy. Compare models with fixed weights first, then update weights in a separate recorded stage. For missing low-angle reflections, compare raw HKL with FCF; never invent intensities or alter reported measurement limits to hide missing observations.

For reviewed mixed-SOF/shared-site or whole-molecule symmetry cases, use the explicit mode in [complete-configurations.en.md](complete-configurations.en.md).
