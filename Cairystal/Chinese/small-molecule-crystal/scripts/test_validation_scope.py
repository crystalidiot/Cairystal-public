import unittest
from audit_validation_scope import assess_text

class ScopeTests(unittest.TestCase):
    def test_zero_alerts_without_factors_is_incomplete(self):
        r=assess_text('You have not supplied any structure factors.\n0 ALERT level A\n0 ALERT level B')
        self.assertEqual(r['status'],'no_structure_factors')
        self.assertFalse(r['scientific_acceptance'])
    def test_supplied_does_not_authenticate_or_accept(self):
        r=assess_text('Structure factors have been supplied for datablock(s) a')
        self.assertTrue(r['structure_factors_supplied_statement'])
        self.assertFalse(r['exact_current_cif_pairing_verified'])
        self.assertFalse(r['official_authenticity_verified'])
    def test_multiple_blocks_with_mixed_scope_need_review(self):
        r=assess_text('Structure factors have been supplied for datablock(s) a\nYou have not supplied any structure factors for b')
        self.assertEqual(r['status'],'mixed_statements_requires_block_review')
    def test_basic_check_is_not_full_publication_check(self):
        r=assess_text('Structure factors have been supplied\nA basic structural check has been run\nPlease run full publication checks')
        self.assertTrue(r['basic_check_statement'])
        self.assertFalse(r['full_publication_check_statement'])
    def test_unknown_text_is_not_assumed_valid(self):
        r=assess_text('No syntax errors found.\n0 ALERT level A')
        self.assertEqual(r['status'],'scope_unknown')

if __name__=='__main__':unittest.main()
