"""Behavioral tests: preserve the independent model, don't invent or overwrite."""
import tempfile
import unittest
from pathlib import Path
import gemmi
from prepare_validation_metadata import prepare, sha, snapshot

BASE = '''data_test
_cell_length_a 10
_cell_length_b 11
_cell_length_c 12
_cell_angle_alpha 90
_cell_angle_beta 90
_cell_angle_gamma 90
_diffrn_radiation_wavelength 0.71073
_cell_measurement_reflns_used ?
_exptl_crystal_description ?
_exptl_crystal_colour ?
_exptl_absorpt_correction_T_min ?
_refine_ls_R_factor_gt 0.05
_chemical_formula_sum 'C2 H6'
loop_
_atom_site_label
_atom_site_fract_x
C1 0.123
C2 0.456
_shelx_res_file
;
TITL independent
PART 1
FVAR 1 0.6
END
;
'''


class MetadataTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.source, self.candidate, self.output, self.evidence = [self.root / n for n in ('source.cif','own.cif','new.cif','pairing.json')]
        self.candidate.write_text(BASE, encoding='utf8')
        self.source.write_text(BASE.replace('used ?', 'used 1000').replace('description ?', "description 'block'").replace('T_min ?', 'T_min 0.2').replace('C1 0.123','C1 0.999').replace('gt 0.05','gt 0.01'), encoding='utf8')
        self.evidence.write_text('{"lineage":"synthetic same-experiment fixture"}', encoding='utf8')

    def call(self):
        return prepare(self.source, self.candidate, self.output, self.evidence)

    def test_fill_preserves_model_and_inputs(self):
        original = [sha(p) for p in (self.source, self.candidate)]
        r = self.call()
        self.assertEqual(len(r['filled']), 3)
        b = gemmi.cif.read_file(str(self.output)).sole_block()
        self.assertEqual(b.find_value('_refine_ls_R_factor_gt'), '0.05')
        self.assertEqual(list(b.find_values('_atom_site_fract_x')), ['0.123','0.456'])
        self.assertEqual(b.find_value('_exptl_crystal_colour'), '?')
        self.assertEqual(original, [sha(p) for p in (self.source, self.candidate)])
        with self.assertRaises(FileExistsError): self.call()

    def test_conflict_not_overwritten(self):
        self.candidate.write_text(BASE.replace('description ?', 'description needle'), encoding='utf8')
        r = self.call()
        self.assertEqual(len(r['conflicts_retained']), 1)
        self.assertEqual(gemmi.cif.read_file(str(self.output)).sole_block().find_value('_exptl_crystal_description'), 'needle')

    def test_not_applicable_is_not_unknown(self):
        self.candidate.write_text(BASE.replace('description ?', 'description .'), encoding='utf8')
        r = self.call()
        self.assertIn('_exptl_crystal_description', r['not_applicable_retained'])
        self.assertIn('_exptl_crystal_description', r['essential_missing'])

    def test_wrong_experiment_or_missing_evidence_stops(self):
        self.source.write_text(BASE.replace('length_a 10', 'length_a 99'), encoding='utf8')
        with self.assertRaises(ValueError): self.call()
        self.assertFalse(self.output.exists())
        self.evidence.unlink()
        with self.assertRaises(ValueError): self.call()

    def test_ambiguous_block_stops(self):
        self.source.write_text(BASE + BASE.replace('data_test','data_other'), encoding='utf8')
        with self.assertRaises(ValueError): self.call()
        self.assertFalse(self.output.exists())

    def test_header_precision_within_su_is_logged(self):
        self.candidate.write_text(BASE.replace('length_a 10', 'length_a 8.97830(10)'), encoding='utf8')
        self.source.write_text(BASE.replace('length_a 10', 'length_a 8.97833(9)'), encoding='utf8')
        r = self.call()
        self.assertGreater(r['identity_checks']['_cell_length_a']['numeric_difference'], 0)
        self.assertEqual(gemmi.cif.read_file(str(self.output)).sole_block().find_value('_cell_length_a'), '8.97830(10)')

    def test_multiline_source_preserved_without_model_transfer(self):
        self.source.write_text(self.source.read_text(encoding='utf8') + '\n_computing_data_reduction\n;\nExample software\nsecond line\n;\n', encoding='utf8')
        self.call()
        b = gemmi.cif.read_file(str(self.output)).sole_block()
        self.assertIn('second line', b.find_value('_computing_data_reduction'))
        self.assertIn('PART 1', b.find_value('_shelx_res_file'))

    def test_rich_model_and_embedded_reflections_remain_candidate(self):
        # Synthetic tokens only; no private crystal coordinates or intensities.
        extra = '''
loop_
_atom_site_occupancy
0.6
0.4
loop_
_atom_site_aniso_label
_atom_site_aniso_U_11
C1 0.025(2)
C2 0.035(3)
_shelx_hkl_file
;
   1   0   0   123.0     2.0
   0   0   0     0.0     0.0
;
_refine_ls_weighting_details 'w=1/[sigma^2(Fo^2)+(0.05P)^2]'
'''
        self.candidate.write_text(BASE + extra, encoding='utf8')
        self.source.write_text(
            (BASE + extra).replace('used ?', 'used 1000')
            .replace('C1 0.123', 'C1 0.999').replace('0.6\n0.4', '1.0\n0.0')
            .replace('0.025(2)', '0.080(9)').replace('123.0', '987.0')
            .replace('PART 1', 'PART 2').replace('0.05P', '0.20P'), encoding='utf8')
        before = snapshot(gemmi.cif.read_file(str(self.candidate)))
        inputs = [sha(self.candidate), sha(self.source)]
        r = self.call()
        after = snapshot(gemmi.cif.read_file(str(self.output)))
        expected = {block: dict(fields) for block, fields in before.items()}
        expected['test']['_cell_measurement_reflns_used'] = ('scalar', '1000')
        self.assertEqual(after, expected)
        self.assertEqual(len(r['filled']), 1)
        self.assertEqual(inputs, [sha(self.candidate), sha(self.source)])

    def test_cell_measurement_subset_is_not_refinement_statistics(self):
        extra = '''
_cell_measurement_theta_min ?
_cell_measurement_theta_max ?
_diffrn_reflns_number 2400
_reflns_number_total 800
_diffrn_reflns_theta_min 3.0
_diffrn_reflns_theta_max 60.0
'''
        self.candidate.write_text(BASE + extra, encoding='utf8')
        self.source.write_text(
            (BASE + extra).replace('used ?', 'used 1100')
            .replace('_cell_measurement_theta_min ?', '_cell_measurement_theta_min 2.5')
            .replace('_cell_measurement_theta_max ?', '_cell_measurement_theta_max 65.0')
            .replace('number 2400', 'number 3000').replace('total 800', 'total 900')
            .replace('_diffrn_reflns_theta_max 60.0', '_diffrn_reflns_theta_max 70.0'), encoding='utf8')
        self.call()
        b = gemmi.cif.read_file(str(self.output)).sole_block()
        for tag, value in {
            '_cell_measurement_reflns_used': '1100', '_cell_measurement_theta_min': '2.5',
            '_cell_measurement_theta_max': '65.0', '_diffrn_reflns_number': '2400',
            '_reflns_number_total': '800', '_diffrn_reflns_theta_min': '3.0',
            '_diffrn_reflns_theta_max': '60.0',
        }.items():
            self.assertEqual(b.find_value(tag), value)

    def test_reference_absolute_hand_and_solver_are_not_metadata(self):
        extra = '''
_chemical_absolute_configuration ?
_computing_structure_solution ?
_refine_ls_abs_structure_Flack 0.20(12)
_atom_sites_solution_primary ?
'''
        self.candidate.write_text(BASE + extra, encoding='utf8')
        self.source.write_text(
            (BASE + extra).replace('used ?', 'used 1000')
            .replace('_chemical_absolute_configuration ?', '_chemical_absolute_configuration ad')
            .replace('_computing_structure_solution ?', "_computing_structure_solution 'Example reference solver'")
            .replace('0.20(12)', '0.00(1)')
            .replace('_atom_sites_solution_primary ?', '_atom_sites_solution_primary direct'), encoding='utf8')
        self.call()
        b = gemmi.cif.read_file(str(self.output)).sole_block()
        for tag in ('_chemical_absolute_configuration', '_computing_structure_solution', '_atom_sites_solution_primary'):
            self.assertEqual(b.find_value(tag), '?')
        self.assertEqual(b.find_value('_refine_ls_abs_structure_Flack'), '0.20(12)')


if __name__ == '__main__': unittest.main()
