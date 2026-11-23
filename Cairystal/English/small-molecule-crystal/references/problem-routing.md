# Diagnose the complete determination

Read this map before explaining a supplied final model or choosing a repair. Start from the actual observations, not the alert letter or a command remembered from a similar-looking molecule. Apply the user's chemical-first priority: establish chemically and crystallographically defensible modelling before using A/B counts to prioritize comparable candidates. Review important chemical contradictions even without an alert.

| Observation or task | First evidence to inspect | Read next |
| --- | --- | --- |
| Initial solution fails or formula is incomplete | CELL/Laue consistency, HKLF role, setting/transformed HKL, expected elements, raw-frame clues | [difficult-data-routing.md](difficult-data-routing.md) |
| New symmetry suggested; many near-equivalent independent atoms | ADDSYM fit/exclusions, symmetry-breaking atoms, systematic absences and intensity merging | [symmetry-and-twins.md](symmetry-and-twins.md) |
| Suspected twin or uncertain absolute structure | domain/overlap records, twin law, BASF context, Friedel pairs and estimates with uncertainties | [symmetry-and-twins.md](symmetry-and-twins.md) |
| Element/connectivity/protonation uncertain | chemical context, density at the site, bond/coordination geometry, relative U, charge balance | [chemical-model-and-density.md](chemical-model-and-density.md) |
| NPD, large U, elongated/flattened ellipsoids or Hirshfeld alerts | distinguish magnitude from shape; element/SOF, actual tensors, correlations, neighbours, map and restraint sensitivity | [adp-model-selection.md](adp-model-selection.md) |
| Split sites, whole-molecule or symmetry-induced disorder | full orbit, distinct orientations/shared sites, PART/FVAR roles, populations and H ownership | [disorder-occupancy.md](disorder-occupancy.md) |
| Solvent void, ABIN/FAB or mask contribution | density in the void, explicit counterions, mask boundary, electrons/volume, original reflection provenance | [solvent-and-data-quality.md](solvent-and-data-quality.md) |
| Poor precision/completeness, extreme weights, outliers | resolution/intensity and frame-wise statistics, missing strong low-order data, absorption/error model | [solvent-and-data-quality.md](solvent-and-data-quality.md) |
| Repeated shifts or singularity | responsible LST parameter, covariance, redundant/unsupported freedom | [nonconvergence.md](nonconvergence.md) |
| Formula/Z/density mismatch or an apparently clean checkCIF | modeled cell contents plus masked content, formula-unit choice, report depth/version and exact final-file pairing | [solvent-and-data-quality.md](solvent-and-data-quality.md), [checkcif-diagnostics.md](checkcif-diagnostics.md) |

For each hypothesis record the symptom, competing explanations, discriminating observation, justified trial and rejection conditions. A null result is useful: 'not enough anomalous information', 'no reliable second disorder component' or 'needs upstream integration' is preferable to manufactured certainty. Do not teach software-menu screenshots as physical evidence.

## Evidence coverage of this knowledge base

Two private libraries supplied worked structures and lectures. Automated construction profiles cover 100 earlier and 811 newer HKL/model combinations, not that many independent crystals. A second pass text-reviewed 36 selected lecture pages across six sources; eight relevant pages were rendered and visually inspected. The new collection's 227 named checkCIF PDF paths reduce to 151 distinct PDFs by exact hash; text extraction/alert triage is not full substantive review. Historical report/CIF pairing remains a separate task. The user-excluded complex crystal-jumping case is not reopened.

Theory-informed routes here are not all validated automatic interventions. The tested controls cover occupancy accounting, execution/numerical gates and report parsing/scope. Example reconstruction is described in [learning-from-solved-models.md](learning-from-solved-models.md). Keep private datasets, lecture extractions and detailed reading ledgers outside the distributed skill.

Subsequent full reading includes the complete checkCIF compilation and SHELX-97 manual; consult the private reading ledger for current per-file text/static-page coverage. The earlier extraction/selected-page figures above describe a different historical pass. Full-source reading and derived diagnostic guidance still do not certify every case or enable automatic repair. See [validation-evidence.md](validation-evidence.md) for the targeted evidence framework.
