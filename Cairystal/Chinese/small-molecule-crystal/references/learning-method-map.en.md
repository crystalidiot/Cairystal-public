# Source methods and executable tools

Nine relevant user-supplied documents were text-indexed, with targeted reading of treatment sections. The main presentation has503 slides and the checkCIF compilation524 pages. Extraction is not a claim that every image, video or page was read. Source hashes, reviewed pages and limitations are in `assets/learning-method-sources.json`. Original teaching material, published case replies and historical atomic coordinates are not bundled into the tools.

Here PPT means 单晶解析相关知识.pptx; PDF means Checkcif所有检测内容汇总及解释案例.pdf. Page/slide numbers start at1.

| Situation | Source sections | Tools / remaining judgment |
|---|---|---|
| Solution failure | PPT175,385; failure-link sheet1 | inspect/stage; choose explicit alternative solver and justified symmetry/composition. The one-page sheet is mainly links, not executable algorithms. |
| C/N/O misassignment | PPT248; PDF232,239 | initial-review, diagnose, element_scan; chemical connectivity, valence, occupancy and density jointly assessed. |
| Nonconvergence / rotating H | PPT261,265,307; PDF132,145 | Locate the parameter in final LST; h_freeze comparison. Do not freeze an entire wrong model. |
| OH without acceptor | PPT229,260–262; PDF314 | oh_rotate and contact/density/PLATON comparison; acceptor chemistry remains uncertain. |
| Missing H / isolated O | PPT258–265; PDF261 | hydrogen-plan, omit_map; water identity/protonation and H positions require evidence. |
| ADP shape, magnitude, rigid-bond failures | PPT246–248; PDF203,209,212,218,222,227,229 | adp_local, element_scan, disorder, restraint-tension; compare competing causes. |
| Short bonds, equivalent distances, planarity | PPT229–230,310 | geometry_local / omit_map; independent chemical targets required. |
| Disorder, special sites and occupancies | PPT238,241–247 | disorder/trials/occupancy; whole configurations, site multiplicity and shared atoms/H need consistent bookkeeping. |
| Residual peaks | PPT264,317; PDF153,155 | diagnose / omit_map; a Q list is not a complete map. |
| Unresolved solvent | PPT68,254,325 | squeeze with authorization, host-model and ABIN/FAB checks. |
| Reflection outliers and weighting | PPT305–306,332; PDF409,418,423 | Independent fixed-list sensitivity trial and finish; investigate causes, completeness and sigma-only versus optimized-weight S. |
| Experimental metadata / data reduction | Rigaku reduction guide and Z notes | inspect/metadata/project-metadata; raw-frame problems cannot all be repaired through INS edits. |

Corrections to informal teaching shorthand:

- AFIX137 to23 is not a generic convergence repair: methyl and methylene require different H counts. AFIX3 retains an existing relative vector; it does not find its correct direction.
- SHELXD solves structures; it is not the refinement engine. Some introductory slide descriptions conflict with later material and the official definitions.
- SIMU is a similarity restraint, EADP an equality constraint. ISOR restrains shape; it does not guarantee a smaller Ueq or repair an occupancy error. Common paired esds are not a mandatory numerical ratio.
- Do not force every short C–C bond to1.46 Å or use an arbitrarily tiny esd. A restrained target cannot independently prove that target.
- AFIX93 denotes terminal planar X=CH2/X=NH2+ geometry, not every NH2 environment.
- Do not truncate high-angle data simply to remove warnings or lower R. Record fixed OMIT hypotheses and completeness effects.
- Modern solvent-mask handling preserves raw HKL and paired ABIN/FAB contributions; older replacement-HKL examples do not replace current consistency checks.

There are501 indexable PLAT identifiers in the source compilation; this is not501 automated repairs. Six bounded local recipes now share the existing trial engine. Arbitrary disorder reconstruction, automatic water H search, general solver fallback and raw-frame integration are not all automated.

Official cross-checks: [SHELXL instructions](https://shelx.uni-goettingen.de/shelxl_html.php), [PLAT420](https://journals.iucr.org/services/cif/checking/PLAT420.html), [PLAT234](https://journals.iucr.org/services/cif/checking/PLAT234.html), [PLAT242](https://journals.iucr.org/services/cif/checking/PLAT242.html).
