"""Delivery routing checks, not a proof of absence/presence of twinning."""
import unittest
from crystal_runtime import records
from twin_delivery import classify, check_batch_columns, review_priority


def route(controls='', hkl='4'):
    return classify(records('CELL .71073 10 12 14 90 90 90\nLATT -1\nSFAC C\nUNIT 1\n'+controls+'\nHKLF '+hkl+'\nEND\n'))


class TwinDeliveryTests(unittest.TestCase):
    def test_ordinary_model_continues_without_speculative_search(self):
        r = route()
        self.assertTrue(r['supported_for_pairing'])
        p = review_priority(r)
        self.assertFalse(p['new_twin_search_requested'])
        self.assertEqual(p['action'], 'ordinary_refinement_continue')
        self.assertTrue(p['no_alert_is_not_exclusion'])

    def test_basf_only_is_batch_scale_not_population(self):
        r = route('BASF 1.5 2.3')
        self.assertEqual(r['kind'], 'HKLF4_batch_scales')
        self.assertTrue(r['supported_for_pairing'])
        self.assertFalse(review_priority(r)['existing_model_treatment'])
        check_batch_columns(r, [(1, 0, 1, 100., 5., 3)])

    def test_batch_id_outside_scales_is_not_silently_accepted(self):
        r = route('BASF 1.5')
        with self.assertRaisesRegex(ValueError, 'exceeds'):
            check_batch_columns(r, [(1, 0, 1, 100., 5., 3)])

    def test_default_and_explicit_inversion_match(self):
        a = route('TWIN\nBASF .20')
        b = route('TWIN -1 0 0 0 -1 0 0 0 -1 2\nBASF .20')
        self.assertEqual(a, b)
        self.assertTrue(a['supported_for_pairing'])
        self.assertEqual(a['kind'], 'HKLF4_inversion_twin')

    def test_supported_two_domain_law_is_not_called_inversion(self):
        r = route('TWIN -1 0 0 0 -1 0 0 0 1\nBASF .20')
        self.assertEqual(r['kind'], 'HKLF4_two_domain_twin')
        self.assertTrue(r['supported_for_pairing'])

    def test_no_alert_does_not_discard_active_twin(self):
        r = route('TWIN\nBASF .20')
        p = review_priority(r)
        self.assertEqual(p['action'], 'preserve_existing_model_and_continue')
        self.assertFalse(p['new_twin_search_requested'])
        self.assertTrue(p['existing_model_treatment'])
        self.assertEqual(r['BASF'], [.20])

    def test_real_diagnostics_route_review(self):
        for code in ['PLAT930_ALERT_2_B', 'PLAT931', '987', 'PLAT033_ALERT_2_B']:
            self.assertTrue(review_priority(route(), [code])['new_twin_search_requested'])
        self.assertFalse(review_priority(route(), ['PLAT183_ALERT_1_A'])['new_twin_search_requested'])
        self.assertTrue(review_priority(route(), [], ['split reflections in raw frames'])['new_twin_search_requested'])

    def test_931_alone_does_not_restart_search_for_an_existing_twin(self):
        r = route('TWIN\nBASF .20')
        p = review_priority(r, ['PLAT931_ALERT_5_G'])
        self.assertFalse(p['new_twin_search_requested'])
        self.assertEqual(p['reported_existing_twin_alerts'], ['PLAT931_ALERT_5_G'])
        self.assertTrue(review_priority(r, ['PLAT931_ALERT_5_G','PLAT930_ALERT_2_B'])['new_twin_search_requested'])

    def test_hklf5_not_treated_as_regular_intensity_rows(self):
        r = route('BASF .20', '5')
        self.assertEqual(r['kind'], 'HKLF5_overlap')
        self.assertFalse(r['supported_for_pairing'])

    def test_negative_component_batch_rejected_in_hklf4(self):
        with self.assertRaisesRegex(ValueError, 'negative'):
            check_batch_columns(route(), [(1, 0, 1, 100., 5., -1)])

    def test_batch_zero_is_a_valid_overall_scale_batch(self):
        check_batch_columns(route('BASF 1.5'), [(1, 0, 1, 100., 5., 0), (2, 0, 1, 100., 5., 2)])

    def test_unsupported_or_corrupt_twin_controls_are_explained(self):
        for controls in ['TWIN', 'TWIN 1 0 0 0 1 0 0 0 1\nBASF .2',
                         'TWIN -1 0 0 0 -1 0 0 0 -1 4\nBASF .2 .2 .2',
                         'TWIN .5 0 0 0 -1 0 0 0 -1\nBASF .2',
                         'TWIN -1 0\nBASF .2', 'TWIN\nBASF nan',
                         'BASF -1.5']:
            with self.subTest(controls=controls):
                r = route(controls)
                self.assertFalse(r['supported_for_pairing'])
                self.assertTrue(r['reason'])

    def test_unphysical_fraction_remains_a_review_finding_not_relabelled_scale(self):
        r = route('TWIN\nBASF -.003')
        self.assertTrue(r['fraction_outside_unit_interval'])
        self.assertEqual(r['kind'], 'HKLF4_inversion_twin')
        self.assertFalse(r['scientific_acceptance'])

    def test_continuation_and_comments_do_not_change_controls(self):
        r = route('REM TWIN is not an active law\nBASF 1.5 =\n 2.3 ! scales')
        self.assertEqual(r['BASF'], [1.5, 2.3])
        self.assertEqual(r['kind'], 'HKLF4_batch_scales')


if __name__ == '__main__':
    unittest.main()
