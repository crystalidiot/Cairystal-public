import unittest
from iucr_validation import parse_official_text

def fixture(rows,counts='2 1 0 0'):
 s='Structure factors have been supplied\nNo syntax errors found.\n'+'\n'.join(rows)+'\n'
 s+='\n'.join(f'{n} ALERT level {k} = test' for k,n in zip('ABCG',counts.split()))
 return s

class AlertFamilies(unittest.TestCase):
 def test_mixed_dictionary_and_platon_alerts(self):
  p=parse_official_text(fixture(['EXPT005_ALERT_1_A Missing habit','DIFF003_ALERT_1_A Missing device','PLAT214_ALERT_2_B C36 ratio']))
  self.assertEqual(p['counts'],dict(A=2,B=1,C=0,G=0));self.assertEqual(p['alerts'][0]['code'],'EXPT005_ALERT_1_A');self.assertEqual(p['alerts'][2]['code'],'214_ALERT_2_B');self.assertEqual(p['alerts'][2]['full_code'],'PLAT214_ALERT_2_B')
 def test_repeated_alert_instances_kept(self):
  p=parse_official_text(fixture(['PLAT214_ALERT_2_B C1','PLAT214_ALERT_2_B C2'],'0 2 0 0'));self.assertEqual(len(p['alerts']),2)
 def test_missing_family_still_fails_count_gate(self):
  with self.assertRaises(ValueError):parse_official_text(fixture(['PLAT214_ALERT_2_B C36']))
 def test_letter_and_number_names_kept(self):
  p=parse_official_text(fixture(['CHEMW03_ALERT_1_A Formula','ABSMU01_ALERT_1_A Absorption'],'2 0 0 0'));self.assertEqual(p['alerts'][0]['code'],'CHEMW03_ALERT_1_A')
 def test_missing_structure_factors_refused(self):
  with self.assertRaises(ValueError):parse_official_text(fixture(['PLAT214_ALERT_2_B C1'],'0 1 0 0').replace('Structure factors have been supplied','No factors'))

if __name__=='__main__':unittest.main(verbosity=2)
