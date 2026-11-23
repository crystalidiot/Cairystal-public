# Low-token routine execution

Use code and disk records for stable mechanical work, not a larger always-loaded prompt. The scripts make no LLM/API calls. This does not remove scientific review: an agent or crystallographer must still interpret uncertain models and actually inspect final document pages.

## Reviewed-model completion

`routine_finish.py` accepts a JSON config and a new output directory. It is a continuation of an explicitly reviewed candidate, not a fresh blind solution. A fresh solution first uses the session/native runner and explicit scientific plans.

```json
{
  "candidate": "D:/jobs/current/selected",
  "stem": "model",
  "shelxl": "D:/software/shelxl.exe",
  "platon": "D:/software/platon.exe",
  "max_weight_updates": 4,
  "timeout": 180,
  "renderer": "word",
  "powershell": "C:/approved-runtime/pwsh.exe",
  "pdftoppm": "C:/approved-runtime/pdftoppm.exe",
  "review": {
    "chemistry_and_h_reviewed": true,
    "basis": "Record the actual chemical, geometric and density review here; never set this automatically."
  }
}
```

The candidate must contain matching `model.ins/res/hkl/cif/fcf/lst`. Use real probed executable paths, not the illustrative paths above. LibreOffice is an alternative renderer when already available. Free-form scientific additions can be supplied as `review.bilingual_notes.zh/en`, using `summary`, `methods`, `provenance`, `limitations`; both languages are required. Routine factual text and tables require no AI rewriting.

```text
python scripts/routine_finish.py --config JOB_CONFIG --output NEW_DIRECTORY
python scripts/routine_finish.py --config JOB_CONFIG --output ANOTHER_NEW_DIRECTORY --deliver --authorize-iucr-upload
```

Upload only under the user's authorization for these data. It is not permission to publish unrelated samples. Read compact stdout first. `state.json` retains events, trial paths, timing, metrics and hashes; `decision_packet.json` points to evidence and narrowly relevant guidance if review is needed. Full native logs and model files remain beside each attempt. Do not repeat a completed step unless inputs changed or a diagnostic justifies it.

## Weight review and scientific guards

Default maximum four updates, hard allowed range zero to six. It reads active and suggested SHELXL `WGHT a b`; unsupported multi-coefficient modes stop for review. A change is numerically stable when each coefficient differs by at most 1% (absolute floors 0.00001 for a and 0.0001 for b). These are explicit engineering stop criteria, not scientific proof or universal SHELXL requirements. Never tune weights to force GoF to one.

Each update preserves atom types, ISO/ANI parameterization, AFIX/PART and occupancy controls, symmetry, restraints, ZERR and the measured HKL. It checks convergence, NPD, reflection count, R1 change, coordinate shift, population change and ADP movement. A suspicious change stops automation and preserves the trial. Occupancy/formula or paired-file inconsistencies are not waived to make the workflow pass. Missing suggestions or exhausted budget produce `needs_weight_review`.

Local A/B or remaining PLAT965 yields `needs_alert_review`; do not automatically remove reflections, add H, invent an element or restrain ADPs to hide warnings. The packet contains routes, not diagnoses. Once the issue is independently reviewed, use a documented new candidate or the general delivery runner, preserving any unresolved warnings. An official A/B that differs from local validation remains visible and requires review.

## Avoid repeated validation and report drafting

Local PLATON reuse is permitted only with exact CIF, FCF and executable hashes, validated completion markers and a complete hashed report set. Changed or incomplete evidence is rejected. Official report reuse remains governed by the existing exact-CIF submission cache; a local report is never called an IUCr report.

Both DOCX files are generated from one final CIF and deterministic factual templates. Provenance says reviewed-model continuation, not a new independent solution. Unknown facts remain unknown. Inherited experimental limitations remain in the report. Report-only hydrogen-bond cleanup cannot change coordinates or reflections. Chemistry-specific free text must be supplied with evidence and equivalent Chinese/English wording.

After successful delivery the status is `awaiting_visual_review`. View every rendered Word page and the official PDF. Only then use:

```text
python scripts/crystal_delivery.py finalize --run DELIVERY_RUN --reviewed-zh --reviewed-en --reviewed-official --review-note ACTUAL_REVIEW_NOTE
```

The existing integrity seal prevents edits after validation/rendering from being silently delivered. No automatic assertion of scientific correctness is made.

## Compact raw-data sessions

`crystal_session.py start/refine` saves complete results and atom-neighbor tables, but stdout now includes only metrics, formula/space group, site counts and paths. `--detail` explicitly restores full stdout. This reduces repeated context, not the stored evidence. Use `model_review.json` for targeted atom questions.

Initial SHELXT baselines explicitly request anisotropic conversion and ASU formula bookkeeping. Later candidate edits preserve ISO/ANI choices, existing ZERR and temperature if no new measured value was supplied. H-bond controls remain unless a new discovery/reporting plan explicitly replaces them. This prevents a routine continuation from accidentally altering a reviewed disorder model.

## Measure honestly

Report wall time and output characters/bytes from an actual run. Character reduction is not an exact token or billing measurement. A continuation regression is not comparable to total time for a fresh solve; scientific decisions and external IUCr latency remain variable. Do not advertise full autonomy for complex disorder or elemental ambiguity.
