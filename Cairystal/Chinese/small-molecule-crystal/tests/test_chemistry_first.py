import copy
import hashlib
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from ab_auto import rank_rows, review_candidate, load_policy
from model_priority import CHECKS, assessment, bind_review, reference_provenance
from working_omit import checked_selection


def row(name='candidate', alerts=None, checks=None):
    item = {'name': name, 'status': 'completed', 'comparison_context_verified': True,
            'source_unchanged': True, 'flags': [], 'AB': alerts or [], 'model_sha256': 'a'*64,
            'classification': 'alert_reduced_scientific_review_required'}
    if checks is not None:
        item['chemical_review'] = {'model_sha256': item['model_sha256'],
                                   'basis': 'Synthetic evidence fixture, not a crystal result',
                                   'checks': dict.fromkeys(CHECKS, 'pass') | checks}
    return item


class ChemicalPriority(unittest.TestCase):
    def test_supported_one_B_beats_zero_AB_unknown(self):
        supported = row('supported', [{'level': 'B'}], {})
        result = rank_rows([row('unreviewed'), supported])
        self.assertEqual(result[0]['name'], 'supported')
        self.assertFalse(result[0]['scientific_acceptance'])

    def test_zero_AB_wrong_chemistry_is_not_preferred(self):
        wrong = row('wrong', checks={'connectivity_and_elements': 'fail'})
        good = row('good', [{'level': 'A'}, {'level': 'B'}], {})
        result = rank_rows([wrong, good])
        self.assertEqual(result[0]['name'], 'good')
        self.assertFalse(result[1]['eligible_for_priority'])

    def test_zero_AB_screened_geometry_problem_is_not_clear(self):
        wrong = row('short_bond'); wrong['flags'] = ['short_bond_in_disorder_component']
        result = rank_rows([wrong, row('needs_chemistry_review', [{'level': 'B'}])])
        self.assertEqual(result[0]['name'], 'needs_chemistry_review')
        self.assertEqual(result[1]['chemical_priority']['status'], 'needs_review')

    def test_same_supported_chemistry_uses_A_then_B(self):
        a = row('A', [{'level': 'A'}], {})
        b = row('B', [{'level': 'B'}]*3, {})
        self.assertEqual(rank_rows([a, b])[0]['name'], 'B')

    def test_new_B_or_slightly_higher_R_retains_chemical_review_candidate(self):
        good = row('chemical_improvement', [{'level': 'B'}], {})
        good['flags'] = ['new_nonmetadata_AB', 'R1_increased_more_than_screening_margin']
        ranked = rank_rows([row('quiet_unknown'), good])
        self.assertEqual(review_candidate(ranked)['name'], 'chemical_improvement')
        self.assertEqual(len(ranked[0]['flags']), 2)
        self.assertFalse(ranked[0]['scientific_acceptance'])

    def test_stale_and_incomplete_review_are_not_pass(self):
        for defect in ('hash', 'checks', 'basis'):
            item = row(checks={})
            if defect == 'hash': item['chemical_review']['model_sha256'] = 'b'*64
            if defect == 'checks': del item['chemical_review']['checks']['diffraction_support']
            if defect == 'basis': item['chemical_review']['basis'] = ' '
            self.assertEqual(assessment(item)['status'], 'needs_review')

    def test_uncertain_is_not_pass(self):
        self.assertEqual(assessment(row(checks={'symmetry_and_disorder': 'uncertain'}))['status'], 'needs_review')
        self.assertEqual(assessment(row())['status'], 'not_assessed')

    def test_specific_geometry_interpretation_keeps_original_flag(self):
        item = row(checks={}); item['flags'] = ['short_bond_in_disorder_component']
        item['chemical_review']['addressed_flags'] = {'short_bond_in_disorder_component': 'Fixture: supported strained-ring geometry; no actual molecular inference asserted.'}
        result = assessment(item)
        self.assertEqual(result['status'], 'supported')
        self.assertIn('short_bond_in_disorder_component', result['concerns'])

    def test_NPD_cannot_be_overridden_by_prose(self):
        item = row(checks={}); item['flags'] = ['non_positive_definite_ADP']
        item['chemical_review']['addressed_flags'] = {'non_positive_definite_ADP': 'ignore'}
        self.assertEqual(assessment(item)['status'], 'needs_review')

    def test_failed_zero_alert_result_stays_failed(self):
        bad = row('failed', checks={}); bad['status'] = 'failed'
        self.assertEqual(rank_rows([bad, row('completed')])[0]['name'], 'completed')
        self.assertIsNone(bad['AB_priority'])

    def test_review_binds_actual_paired_CIF(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td); (root/'paired').mkdir(); cif = root/'paired/case.cif'
            cif.write_text('data_synthetic\n_chemical_formula_sum C\n')
            actual = hashlib.sha256(cif.read_bytes()).hexdigest()
            trial = {'name': 'x', 'diagnostic': str(root/'diagnostic.json')}
            self.assertEqual(bind_review(trial, {'model_sha256': actual})['model_sha256'], actual)
            cif.write_text('data_changed\n')
            with self.assertRaisesRegex(ValueError, 'fingerprint'):
                bind_review(trial, {'model_sha256': actual})

    def test_unchanged_geometry_conflict_blocks_automatic_OMIT(self):
        context = {'frozen_controls': [], 'hkl_sha256': 'synthetic'}
        tension = {'needs_review': True, 'listed_geometry': []}
        control = {'comparison_context': context, 'restraint_tension': tension}
        trial = {'source_unchanged': True, 'native_gate': {'review_reasons': []},
                 'comparison_context': dict(context, frozen_controls=[['OMIT', '1', '2', '3']]),
                 'restraint_tension': copy.deepcopy(tension)}
        # Rejection occurs before any model files are accessed or overwritten.
        with self.assertRaisesRegex(ValueError, 'restraint conflicts'):
            checked_selection(control, trial, {'flags': []}, [[1,2,3]], Path('unused'))

    def test_policy_is_chemical_first(self):
        self.assertEqual(load_policy()['priority_order'][0], 'chemical_reasonableness_and_current_diffraction_support')


class ReferenceProvenance(unittest.TestCase):
    def fixture(self, root):
        p = root/'reference.res'; p.write_text('TITL synthetic reference\n')
        return {'chemistry_and_h_reviewed': True, 'basis': 'Synthetic test only',
                'reference_model': {'path': str(p), 'sha256': hashlib.sha256(p.read_bytes()).hexdigest(),
                                    'use': 'starting_coordinates', 'comparison_basis': 'Same synthetic sample and setting'}}

    def test_both_languages_and_idempotence(self):
        with tempfile.TemporaryDirectory() as td:
            result = reference_provenance(self.fixture(Path(td)))
            self.assertEqual(result['model_origin'], 'reference_assisted')
            self.assertIn('参考模型辅助', result['bilingual_notes']['zh']['provenance'])
            self.assertIn('not a reference-free', result['bilingual_notes']['en']['provenance'])
            self.assertEqual(reference_provenance(result), result)

    def test_blind_mode_rejects_before_any_reference_read(self):
        for mode in ({'blind_test': True}, {'model_origin': 'fresh_independent'}, {'model_origin': 'blind'}):
            with patch.object(Path, 'read_bytes', side_effect=AssertionError('Must not read reference')) as reader:
                with self.assertRaisesRegex(ValueError, 'conflicts'):
                    reference_provenance(dict(mode, reference_model={'path': 'forbidden'}))
                reader.assert_not_called()

    def test_changed_reference_is_not_silently_used(self):
        with tempfile.TemporaryDirectory() as td:
            original = self.fixture(Path(td)); Path(original['reference_model']['path']).write_text('changed')
            with self.assertRaisesRegex(ValueError, 'fingerprint'):
                reference_provenance(original)

    def test_existing_nonreference_review_still_works(self):
        review = {'chemistry_and_h_reviewed': True, 'basis': 'Current specimen evidence'}
        self.assertEqual(reference_provenance(review), review)

    def test_reference_claim_without_provenance_is_rejected(self):
        with self.assertRaisesRegex(ValueError, 'provenance'):
            reference_provenance({'model_origin': 'reference_assisted'})


if __name__ == '__main__':
    unittest.main()
