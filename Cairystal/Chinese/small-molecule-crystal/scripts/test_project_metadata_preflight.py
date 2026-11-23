"""Synthetic project-side metadata and lineage regressions; no real sample read."""
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from crystal_runtime import sha
from experiment_metadata_state import collect
from inspect_experiment_metadata import inspect_metadata
from pipeline_intake import discover
from project_metadata_preflight import preflight, inventory, fingerprint


def hkl(value=100):
    return f'{1:4d}{0:4d}{1:4d}{value:8.2f}{5.:8.2f}{1:4d}\n' + f'{0:4d}{0:4d}{0:4d}{0.:8.2f}{0.:8.2f}{0:4d}\n'


P4P = ('FILEID SAINT synthetic\nCELL 8 10 15 90 95 90 1200\n'
       'CELLSD .001 .001 .001 0 .01 0\nSOURCE MO .71073\n'
       'BRAVAIS Monoclinic(b-unique) P\nSAINGL 2500 2.5 26.3 0\n'
       'CSIZE ? ? ? ? -173.150\n')


class ProjectMetadataTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.raw = self.root / 'raw'
        self.project = self.root / 'supplied_project'
        self.raw.mkdir()
        (self.project / 'olex2').mkdir(parents=True)
        self.hkl = self.raw / 'sample_0m.hkl'
        self.p4p = self.raw / 'sample_0m.p4p'
        self.hkl.write_text(hkl(), encoding='ascii')
        self.p4p.write_text(P4P, encoding='ascii')

    def metadata(self, body):
        p = self.project / 'olex2/sample_0m.metacif'
        p.write_text(body, encoding='utf-8')
        return p

    def test_reproducible_temperature_brand_and_hkl_difference(self):
        # Reproduce the reported conditions, without embedding real case data.
        self.metadata('data_test\n' + '# padding\n' * 36 +
                      '_diffrn_ambient_temperature 100.15\n_cell_measurement_temperature 100.15\n' +
                      '# padding\n' * 18 + '_diffrn_measurement_device_type Bruker\n')
        phil = self.project / 'olex2/sample_0m.phil'
        phil.write_text('# padding\n' * 62 + 'diffractometer = "Bruker"\n', encoding='utf-8')
        (self.project / self.hkl.name).write_text(hkl(101), encoding='ascii')
        (self.project / self.p4p.name).write_bytes(self.p4p.read_bytes())
        result = preflight(self.project, self.hkl, raw_companions=[self.p4p])
        cell = result['observations']['_cell_measurement_temperature'][0]
        self.assertEqual(cell['source_line'], 39)
        self.assertEqual(cell['value'], '100.15')
        self.assertFalse(cell['measurement_origin_verified'])
        instruments = result['observations']['_diffrn_measurement_device_type']
        self.assertEqual({r['source_line'] for r in instruments}, {58, 63})
        self.assertTrue(all(r['device_specificity'] == 'manufacturer_only' for r in instruments))
        comparisons = result['lineage_comparisons']
        different = next(r for r in comparisons if r['kind'] == 'hkl')
        self.assertEqual(different['input']['reflection_count'], different['project']['reflection_count'])
        self.assertFalse(different['numeric_equal'])
        self.assertTrue(next(r for r in comparisons if r['kind'] == 'raw_companion')['hash_equal'])
        self.assertEqual(len(result['conflicts']), 2)
        self.assertEqual({r['difference_K'] for r in result['conflicts']}, {'0.15'})
        self.assertFalse(result['ready_for_merge'])
        self.assertFalse(result['same_experiment_confirmed'])
        self.assertTrue(result['inputs_unchanged'])

    def test_missing_project_files_not_reported_as_found(self):
        result = preflight(self.raw, self.hkl)
        self.assertEqual(result['source_reports'], [])
        self.assertEqual(result['observations'], {})
        self.assertIn('metacif', result['missing_source_hint'])

    def test_discovery_lists_sidecars_without_reading(self):
        (self.raw / 'olex2').mkdir()
        sidecar = self.raw / 'olex2/sample_0m.metacif'
        sidecar.write_text('invalid text deliberately not read')
        original = Path.open
        def guarded(path, *args, **kwargs):
            if path == sidecar:
                raise AssertionError('Discovery opened a sidecar')
            return original(path, *args, **kwargs)
        with patch.object(Path, 'open', guarded):
            selected, scope = discover(self.raw)
        self.assertIn(str(sidecar), scope['additional_metadata_not_read'])
        self.assertEqual(set(selected), {'hkl', 'p4p'})

    def test_no_model_unrelated_or_recursive_reads(self):
        self.metadata('_cell_measurement_temperature 100.15\n')
        for p in [self.project/'sample_0m.cif', self.project/'sample_0m.res',
                  self.project/'olex2/other.metacif']:
            p.write_text('PROTECTED_REFERENCE')
        (self.project/'olex2/nested').mkdir()
        (self.project/'olex2/nested/sample_0m.metacif').write_text('PROTECTED_REFERENCE')
        result = preflight(self.project, self.hkl)
        self.assertEqual(len(result['source_reports']), 1)
        self.assertNotIn('PROTECTED_REFERENCE', json.dumps(result))
        self.assertEqual(len(result['inventory']['directories_listed']), 2)

    def test_explicit_outside_metadata_and_link_rejected(self):
        p = self.metadata('_cell_measurement_temperature 100.15\n')
        with self.assertRaises(ValueError):
            preflight(self.raw, self.hkl, sources=[p])
        original = Path.is_symlink
        with patch.object(Path, 'is_symlink', lambda item: True if item == p else original(item)):
            with self.assertRaises(ValueError):
                inspect_metadata(p)
            self.assertEqual(inventory(self.project, self.hkl.stem)['candidates'], [])

    def test_phil_is_literal_only_does_not_follow_include(self):
        p = self.project/'olex2/sample_0m.phil'
        p.write_text('include file missing_secret.phil\nother = "not emitted"\ndiffractometer = "Bruker" # source\n')
        r = inspect_metadata(p)
        self.assertEqual(r['blocks'][0]['fields']['_diffrn_measurement_device_type']['source_line'], 3)
        self.assertNotIn('missing_secret', json.dumps(r))
        for expression in ['$(type secret)', '"${MODEL}"', 'f("model")']:
            p.write_text('diffractometer = ' + expression)
            with self.assertRaises(ValueError):
                inspect_metadata(p)

    def test_repeated_phil_does_not_silently_select_last(self):
        p = self.project/'olex2/sample_0m.phil'
        p.write_text('diffractometer = "Bruker"\ndiffractometer = "Rigaku"\n')
        r = preflight(self.project, self.hkl)
        self.assertEqual(len(r['conflicts']), 1)
        self.assertFalse(r['ready_for_merge'])

    def test_cell_and_diffraction_temperatures_are_not_forced_equal(self):
        self.metadata('_diffrn_ambient_temperature 100\n_cell_measurement_temperature 120\n')
        r = preflight(self.project, self.hkl)
        self.assertEqual(r['conflicts'], [])
        self.assertEqual(set(r['observations']), {'_diffrn_ambient_temperature', '_cell_measurement_temperature'})

    def test_line_numbers_multiple_blocks_and_text_fields(self):
        p = self.metadata('# header\n_cell_measurement_temperature 100\n_exptl_absorpt_process_details\n;\nfirst\nsecond\n;\n')
        r = inspect_metadata(p)
        self.assertEqual(r['blocks'][0]['fields']['_cell_measurement_temperature']['source_line'], 2)
        self.assertEqual(r['blocks'][0]['fields']['_exptl_absorpt_process_details']['source_line'], 3)
        p.write_text('data_a\n_cell_measurement_temperature 100\ndata_b\n_cell_measurement_temperature 120\n')
        r = preflight(self.project, self.hkl)
        self.assertEqual(len(r['conflicts']), 1)

    def test_hkl_numeric_formatting_and_invalid_layout(self):
        other = self.project/self.hkl.name
        other.write_bytes(self.hkl.read_bytes().replace(b'100.00', b'100.0 '))
        r = preflight(self.project, self.hkl)['lineage_comparisons'][0]
        self.assertFalse(r['hash_equal'])
        self.assertTrue(r['numeric_equal'])
        other.write_text('unsupported values')
        self.assertIsNone(fingerprint(other, True)['reflection_count'])

    def test_explicit_phil_ledger_preserves_line_and_brand_scope(self):
        p = self.project/'olex2/sample_0m.phil'
        p.write_text('diffractometer = "Bruker"\n')
        config = self.root/'sources.json'
        config.write_text(json.dumps({'hkl': str(self.hkl), 'sources': [{
            'path': str(p), 'source_sha256': sha(p), 'hkl_sha256': sha(self.hkl),
            'kind': 'phil_metadata', 'same_experiment_confirmed': True,
            'basis': 'Synthetic explicit same-experiment assertion for testing only'}]}))
        result = collect(config, self.root/'ledger')
        obs = result['observations']['_diffrn_measurement_device_type'][0]
        self.assertEqual(obs['source_line'], 1)
        self.assertEqual(obs['device_specificity'], 'manufacturer_only')
        self.assertNotIn('_cell_measurement_temperature', result['resolved'])

    def test_transmission_allowlist_is_case_insensitive(self):
        p = self.metadata('_EXPTL_ABSORPT_CORRECTION_T_MIN 0.12\n_exptl_absorpt_correction_t_max 0.80\n')
        fields = inspect_metadata(p)['blocks'][0]['fields']
        self.assertEqual(fields['_exptl_absorpt_correction_T_min']['token'], '0.12')
        self.assertEqual(fields['_exptl_absorpt_correction_T_max']['token'], '0.80')

    def test_cli_outputs_auditable_json_and_no_files(self):
        self.metadata('_cell_measurement_temperature 100.15\n')
        before = {str(p): sha(p) for p in self.root.rglob('*') if p.is_file()}
        script = Path(__file__).with_name('project_metadata_preflight.py')
        cmd = [sys.executable, '-B', str(script), '--project-dir', str(self.project), '--hkl', str(self.hkl)]
        run = subprocess.run(cmd, capture_output=True, text=True, encoding='utf-8')
        self.assertEqual(run.returncode, 0, run.stderr)
        self.assertFalse(json.loads(run.stdout)['ready_for_merge'])
        self.assertEqual(before, {str(p): sha(p) for p in self.root.rglob('*') if p.is_file()})


if __name__ == '__main__':
    unittest.main()
