# TEMP and PLAT196

PLAT196 checks missing TEMP in the embedded RES when the CIF cell-measurement
temperature is not 293 K. It is not evidence for a measured temperature of 0 K:
unknown values can be represented as zero in diagnostic text. Source:
[IUCr PLAT196](https://journals.iucr.org/services/cif/checking/PLAT196.html).

SHELXL `TEMP` is **degrees Celsius**, not kelvin: 100 K → `TEMP -173.15`;
293.15 K → `TEMP 20`. TEMP must precede all atoms. It affects reported temperature,
default U values and default X–H distances, so a changed TEMP needs renewed native
refinement/H checks, paired products, local A/B checking, authorized official
checkCIF and bilingual reports. Merely editing a CIF does not perform these steps.
[SHELXL manual](https://shelx.uni-goettingen.de/shelxl_html.php).

## Implemented checks

`routine_consistency.audit_files` now calls `temperature_consistency.audit_temperature`:
it checks the explicit current RES (otherwise embedded RES), scalar CIF temperatures,
missing/duplicate/invalid/late TEMP and disagreement with collection temperature.
Definite control/value contradictions stop ordinary delivery; unresolved facts stop
automatic acceptance. Numeric agreement is only a consistency check, not provenance.
The 0.51 K screening tolerance accommodates whole-K serialization; it is not a
measurement uncertainty. Both original temperature tokens remain in the audit.

Use `_diffrn_ambient_temperature` for diffraction collection temperature. Do not assume
`_cell_measurement_temperature` is the same: these can describe different operations.
Unknown temperature remains unknown unless a current user has explicitly adopted the separate [room-temperature convention](user-temperature-default.md). That route requires source/conflict checks and external assumption disclosure; it is not a measured-source import. Do not add TEMP merely to remove a warning.

## Source-driven new INS

The existing inspector supports explicitly permitted CIF-text PCF/CIF_OD and headerless
fragments. The existing session parser supports its documented P4P CSIZE dialect.
This helper does not claim universal raw-instrument parsing. Do not read forbidden
reference CIFs in a blind test; the inspector internally reads the whole file.

Record independently established same-experiment pairing in `temperature_evidence.json`:

```json
{
  "source_sha256": "actual SHA256 of the explicitly permitted source file",
  "res_sha256": "actual SHA256 of the current native model",
  "same_experiment_confirmed": true,
  "collection_temperature_confirmed": true,
  "basis": "Specific acquisition identifier/HKL lineage and temperature locator; not just matching filenames"
}
```

Then run, using the configured Python runtime:

```text
python scripts/temperature_consistency.py --source sample.pcf --res current.res --evidence temperature_evidence.json --output NEW_TEMP_TRIAL
```

For multiple source blocks select `--source-block`. Cell-temperature fallback requires
`--tag _cell_measurement_temperature` AND explicit recorded
`cell_temperature_is_collection_temperature: true`; a conflicting ambient temperature
still refuses this fallback. An existing conflicting TEMP requires an evidence-based
`--replace-reason`. These arguments record a decision, not independently verify it.

The helper writes only new `model.ins` and `temperature_audit.json`; all input hashes,
original source token including uncertainty, conversion, previous TEMP and reason are
retained. Other active instructions/atoms must be unchanged. It refuses overwrites,
ambiguous sources, unknown/nonphysical values and unsupported native scopes.

Status is `prepared_not_refined`. Continue with the same paired HKL in this new trial;
run SHELXL, review existing H instructions and regenerated X–H geometry, merge verified
experimental scalars into the regenerated CIF, and run the normal delivery checks.
Do not reuse an old FCF or IUCr PDF after refinement. Rigid H coordinates do not become
appropriate automatically just because TEMP was inserted. Preserve the before version.

Tests: `python -m unittest test_temperature_consistency test_routine_consistency`.

## 输入不完整与原生程序默认值

P4P 没有 CSIZE、或 CSIZE 未包含温度时，记录温度未知并继续能做的步骤，不强制补室温。若本项目已有用户明确授权的缺省室温约定，按 [室温假设规则](user-temperature-default.md) 单独记录和披露后处理；不能伪造采集来源。若提供数值，应有限且大于 0 K。直接使用 `crystal_session.start` 也检查用户观测是否明确确认，不能通过绕过问卷把草稿写成实测。

用户提供的衍射温度只同步对应字段；不要无条件另写成独立测定的晶胞温度。SHELXL 有时会根据 TEMP 输出 `_cell_measurement_temperature`，保留这种原生记录并说明来源，不能据此声称另有晶胞温度测量。
