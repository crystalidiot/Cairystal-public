"""Synthetic CIF fixtures only; no solver, reference structure or network calls."""
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import gemmi
from docx import Document
import bilingual_report
import routine_finish
from prepare_validation_metadata import snapshot


VALUES = {
    '_chemical_formula_sum': 'C2 H6 Cl2',
    '_space_group_name_H-M_alt': 'P 1',
    '_exptl_absorpt_correction_type': 'multi-scan',
    '_exptl_absorpt_correction_T_min': '0.74952',
    '_exptl_absorpt_correction_T_max': '1.00000',
    '_cell_formula_units_Z': '2',
    '_exptl_crystal_F_000': '160',
    '_refine_ls_R_factor_gt': '0.0485',
    '_refine_ls_wR_factor_gt': '0.0962',
    '_refine_ls_R_factor_all': '0.0512',
    '_refine_ls_wR_factor_ref': '0.0999',
    '_diffrn_reflns_av_R_equivalents': '0.0182',
    '_diffrn_measured_fraction_theta_max': '0.998',
    '_publ_section_exptl_refinement': 'Keep Cl, Cu and C34B CASE exactly.',
}


def fixture(case=str, unknown_transmission=False):
    doc = gemmi.cif.Document()
    block = doc.add_new_block('SyntheticOnly')
    for tag, value in VALUES.items():
        if unknown_transmission and tag.lower().endswith(('correction_t_min', 'correction_t_max')):
            value = '?'
        block.set_pair(case(tag), '?' if value == '?' else gemmi.cif.quote(value))
    block.set_pair(case('_shelx_res_file'), gemmi.cif.quote('REM Private Case-Sensitive Embedded Text'))
    block.init_loop('', [case(t) for t in (
        '_atom_site_label', '_atom_site_type_symbol', '_atom_site_fract_x',
        '_atom_site_fract_y', '_atom_site_fract_z', '_atom_site_U_iso_or_equiv',
        '_atom_site_occupancy', '_atom_site_adp_type')]).add_row(
            ['C34B', 'C', '0.125', '0.25', '0.375', '0.04(1)', '0.25', 'Uiso'])
    block.init_loop('', [case('_space_group_symop_id'), case('_space_group_symop_operation_xyz')]).add_row(['1', 'x,y,z'])
    block.init_loop('', [case(t) for t in ('_refln_index_h', '_refln_index_k', '_refln_index_l', '_refln_F_squared_meas')]).add_row(['1', '2', '3', '123.4'])
    return doc


class CifTagCase(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)

    def write(self, name, case=str, unknown=False):
        path = self.root / name
        fixture(case, unknown).write_file(str(path))
        return path

    def carry(self, case):
        source = self.write('source.cif', case)
        target = self.write('target.cif', case, True)
        source_bytes = source.read_bytes()
        before = snapshot(gemmi.cif.read_file(str(target)))
        changed = routine_finish.carry_metadata(source, target, 0)
        after = snapshot(gemmi.cif.read_file(str(target)))
        allowed = {item['tag'].lower() for item in changed}
        for name, fields in before.items():
            for tag, value in fields.items():
                if tag not in allowed:
                    self.assertEqual(after[name][tag], value)
        self.assertEqual(source.read_bytes(), source_bytes)
        self.assertEqual(after['SyntheticOnly']['_exptl_absorpt_correction_t_min'], ('scalar', '0.74952'))
        self.assertEqual(after['SyntheticOnly']['_exptl_absorpt_correction_t_max'], ('scalar', '1.00000'))

    def test_carry_lowercase_tags_preserves_model_and_reflections(self):
        self.carry(str.lower)

    def test_carry_uppercase_tags_preserves_model_and_reflections(self):
        self.carry(str.upper)

    def test_carry_dictionary_spelling_preserves_model_and_reflections(self):
        self.carry(str)

    def test_protected_coordinate_change_still_rejected_before_write(self):
        source = self.write('source.cif')
        target = self.write('target.cif', str.lower, True)
        original = target.read_bytes()
        real_snapshot = routine_finish.snapshot
        calls = []
        def corrupt_after(doc):
            out = real_snapshot(doc)
            calls.append(1)
            if len(calls) == 2:
                out['SyntheticOnly']['_atom_site_fract_x'] = ('loop', ('0.9',))
            return out
        with patch.object(routine_finish, 'snapshot', side_effect=corrupt_after):
            with self.assertRaisesRegex(ValueError, 'Protected CIF token'):
                routine_finish.carry_metadata(source, target, 0)
        self.assertEqual(target.read_bytes(), original)

    def test_unknown_source_does_not_replace_known_transmission(self):
        source = self.write('source.cif', str.upper, True)
        target = self.write('target.cif', str.lower)
        routine_finish.carry_metadata(source, target, 0)
        block = gemmi.cif.read_file(str(target)).sole_block()
        self.assertEqual(block.find_value('_exptl_absorpt_correction_T_min'), '0.74952')

    def test_extract_keeps_source_tag_spelling_and_value_case(self):
        path = self.write('source.cif', str.upper)
        original = path.read_bytes()
        data = bilingual_report.extract(path)
        self.assertEqual(data['scalars']['_CHEMICAL_FORMULA_SUM'], 'C2 H6 Cl2')
        self.assertEqual(data['scalars']['_PUBL_SECTION_EXPTL_REFINEMENT'], VALUES['_publ_section_exptl_refinement'])
        self.assertEqual(data['atoms'][0][0], 'C34B')
        self.assertEqual(data['atoms'][0][-1], 'Uiso')
        self.assertEqual(path.read_bytes(), original)
        self.assertEqual(json.loads(json.dumps(data))['scalars'], data['scalars'])

    def test_embedded_shelx_exclusion_is_case_insensitive(self):
        data = bilingual_report.extract(self.write('upper.cif', str.upper))
        self.assertFalse(any(k.lower().startswith('_shelx') for k in data['scalars']))

    def report(self, case, unknown=False):
        path = self.write('model.cif', case, unknown)
        original = path.read_bytes()
        out = self.root / 'reports';out.mkdir()
        qa = self.root / 'qa';qa.mkdir()
        notes = {lang: {'summary': 'Synthetic fixture only.', 'methods': 'Synthetic formatter test; no crystal was solved.'} for lang in ['zh', 'en']}
        notes['provisional'] = True
        official = {'counts': dict.fromkeys('ABCG', 0), 'alerts': []}  # Synthetic input, never an IUCr result.
        record = bilingual_report.build_reports(path, official, notes, out, qa)
        expected = [
            'C2 H6 Cl2', 'P 1', '? / 2', '? / 160',
            '0.0485 / 0.0962', '0.0512 / 0.0999', '0.0182 / 0.998',
            'multi-scan / ? / ?' if unknown else 'multi-scan / 0.74952 / 1.00000',
        ]
        for lang, item in record['outputs'].items():
            doc = Document(item['path'])
            values = [r.cells[1].text.replace('未提供', '?').replace('Not supplied', '?') for r in doc.tables[0].rows[1:]]
            for value in expected:
                self.assertIn(value, values, (lang, value))
            self.assertEqual(doc.tables[1].rows[1].cells[0].text, 'C34B')
        self.assertEqual(path.read_bytes(), original)
        self.assertTrue(record['same_numeric_tables'])
        self.assertEqual(record['visual_review'], 'pending')

    def test_both_word_reports_from_lowercase_tags(self):
        self.report(str.lower)

    def test_both_word_reports_from_uppercase_tags(self):
        self.report(str.upper)

    def test_both_word_reports_from_dictionary_spelling(self):
        self.report(str)

    def test_unknown_transmission_remains_unknown_in_reports(self):
        self.report(str.lower, True)

    def test_factual_summary_and_source_narrative_uppercase(self):
        path = self.write('model.cif', str.upper)
        state = {'weight_trials': [], 'weights': {'active': [.05, 1.0], 'status': 'coefficients_stable'}}
        notes = routine_finish.factual_notes(path, state, {})
        for lang in ['zh', 'en']:
            self.assertIn('C2 H6 Cl2', notes[lang]['summary'])
            self.assertIn('P 1', notes[lang]['summary'])
        self.assertEqual(notes['audit_records']['source_narratives']['_publ_section_exptl_refinement'], VALUES['_publ_section_exptl_refinement'])


if __name__ == '__main__':
    unittest.main()
