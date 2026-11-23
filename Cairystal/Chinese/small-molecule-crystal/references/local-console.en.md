# Local visual console

The optional first console has a Chinese UI. It displays saved progress, A/B alerts, model viewers and actual artifacts; author mode adds immutable parameter plans. Scientific solver policy is unchanged.

    python -B scripts/toolbox.py run console -- --workspace WORKSPACE --profile PROFILE.json --open

Use the Python configured by PROFILE.json. WORKSPACE must be separate from both the frozen skill and raw inputs. All assets are bundled; no Node installation is needed by users. The service binds only to 127.0.0.1. Register explicit result folders, or save a new plan and explicitly start it. Saving does not run a solver. The automatic start currently requires a unique matching HKL/P4P pair.

Supply possible elements (including solvents/counterions), optional 2D image, and actual crystal colour/habit/three dimensions. Unknown or unconfirmed observations are not inserted as measured facts. An attached image is retained for review and is not silently treated as a validated chemical graph. Missing reviewed graph/scientific ambiguities use the existing review gates.

Plans retain hashes and snapshots of configuration, specimen information and reviewed graphs. New revisions do not alter old jobs. Parent images are retained only for the same raw-data directory. Moving nodes changes layout only, not execution order; layout is not persistent across reloads. No arbitrary execution graph is provided.

Uploads are not implicitly authorized. Agents may reuse an already documented, applicable IUCr authorization and resume the existing delivery workflow. Required deliverables remain final CIF, official checkCIF PDF, Chinese Word and English Word in the raw-data folder/Cairystal. Existing files and record metrics are not fresh validation. Unknown values remain null; low R/zero A/B are not proof of correctness.

Built-in UI operations make no language-model calls. Frontend source and pinned dependencies are in assets/console-source, third-party licenses in licenses/console. The server is for a single local user, not public/network hosting. Tests: scripts/test_crystal_console.py. See local-console.md for details.
