import unittest
from parse_platon_alerts import parse

class Tests(unittest.TestCase):
    def test_omitted_zero(self):
        r=parse('001_ALERT_1_A missing\n 1 ALERT_Level_A = serious\nALERT_Level and ALERT_Type Summary\n')
        self.assertEqual(r['counts'],dict(A=1,B=0,C=0,G=0));self.assertEqual(r['warnings'],[])
    def test_overflow(self):
        r=parse('\n'.join(['001_ALERT_1_C check']*1001)+'\n*** ALERT_Level_C = check\n')
        self.assertEqual(r['counts']['C'],1001);self.assertEqual(r['warnings'],[])
    def test_mismatch_and_partial(self):
        r=parse('001_ALERT_1_A missing\n 2 ALERT_Level_A = serious\n')
        self.assertFalse(r['report_footer_present']);self.assertTrue(r['warnings'])

if __name__=='__main__':unittest.main()
