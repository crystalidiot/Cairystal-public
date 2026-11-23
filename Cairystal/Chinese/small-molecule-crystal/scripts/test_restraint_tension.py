import unittest
from restraint_tension import parse_final_listing

class ListingTests(unittest.TestCase):
 def test_final_cycle_only(self):
  v=parse_final_listing('Disagreeable restraints before cycle 1\n 1.000 1.390 -.390 .01 DFIX C1 C2\nSummary of restraints applied\nDisagreeable restraints before cycle 8\n 1.38 1.39 -.01 .01 DFIX C1 C2\nSummary of restraints applied')
  self.assertEqual(v['cycle'],8);self.assertFalse(v['needs_review']);self.assertEqual(len(v['listed_geometry']),1)
 def test_dang_trigger(self):
  v=parse_final_listing('Disagreeable restraints before cycle 61\n2.2589 2.4076 -0.1487 0.0200 DANG C37^a C38^a\nSummary of restraints applied')
  self.assertTrue(v['needs_review']);self.assertAlmostEqual(v['listed_geometry'][0]['absolute_error_over_sigma'],7.435)
 def test_no_report_not_pass(self):self.assertIsNone(parse_final_listing('R1 = .02')['needs_review'])
 def test_no_listed_geometry(self):
  v=parse_final_listing('Disagreeable restraints before cycle 2\n -.02 .03 RIGU zz C1 C2\nSummary of restraints applied');self.assertEqual(v['listed_geometry'],[])
 def test_zero_sigma_review(self):self.assertTrue(parse_final_listing('Disagreeable restraints before cycle 2\n1.0 1.2 -.2 0.0 DFIX C1 C2')['needs_review'])
 def test_unparsed_flagged(self):self.assertEqual(parse_final_listing('Disagreeable restraints before cycle 2\n***** 1.2 -.2 .01 DFIX C1 C2')['status'],'incomplete_parse')

if __name__=='__main__':unittest.main()
