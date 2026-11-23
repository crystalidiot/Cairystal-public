# Normal route and conditional repairs

Normal route: intake → SHELXT → element/H review → SHELXL and weights → local structural/A/B validation → official IUCr checkCIF → final CIF, official PDF and Chinese/English Word.

Every exception needs a trigger, a scoped tool, acceptance evidence, a return step and a stopping condition. Model edits return to refinement/validation. Network/report failures resume delivery, not phasing.

Code-audited gaps: the native stage runner can call SHELXD, but autorun does not automatically switch from SHELXT. A reviewed chemical graph/H basis is still required by autorun. hydrogen-plan builds initial H plans; it is not a complete PLAT420 reorientation module. Rules, executable tools and automatic dispatch are different capabilities.

Priorities: implement and validate the SHELXT→SHELXD fallback and evidence-based OH reorientation branches, then general A/B dispatch. AFIX 3 rides existing coordinates on a preceding non-riding parent; it does not locate the correct H position. Check donor identity, symmetry-related acceptors, density, contacts and occupancy before accepting a reoriented H.

The shared route specification is assets/console/workflow-data.json; its first visual UI is Chinese. It labels implemented versus pending behavior. Selecting a route is read-only and never executes a solver. Existing tasks/parameters remain at /workspace. This update changes explanation/navigation, not scientific solver policy.

Primary sources: https://journals.iucr.org/services/cif/checking/PLAT420.html and https://shelx.uni-goettingen.de/shelxl_html.php.

Update: repair-plan now provides six bounded local recipes, including existing simple OH rotation and AFIX3 trials. Automatic donor chemistry/water-H search and solver fallback remain incomplete. See [repair tools](evidence-repair-tools.en.md).
