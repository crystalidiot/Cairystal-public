import unittest
from diagnostic_priorities import priorities

class Priorities(unittest.TestCase):
 def test_rotor_is_distinguished_from_coordinate_shift(self):
  p={'last_shifts':[['.04','1.3','tors H17A'],['.04','-1.2','tors H17A'],['.04','1.2','tors H17A']]}
  f=priorities(p)['findings'][0];self.assertEqual(f['type'],'hydrogen_rotor');self.assertEqual(f['sign_changes_in_last_listings'],2)
 def test_near_degenerate_is_not_hidden_by_native_zero(self):
  p={'gate':{'metrics':{'NPD_atoms':0}},'AB_alerts':[{'code':'211'}]}
  self.assertEqual(priorities(p)['findings'][0]['code'],'near_degenerate_despite_native_NPD_zero')
 def test_symmetry_and_restraint_conflict_precede_acceptance(self):
  p={'AB_alerts':[{'code':'PLAT113_ALERT_2_B'}],'restraint_tension':{'needs_review':True}}
  r=priorities(p);self.assertEqual(r['findings'][0]['priority'],1);self.assertFalse(r['scientific_acceptance']);self.assertEqual(len(r['findings']),2)
 def test_converged_parameters_do_not_trigger_freezing(self):
  self.assertEqual(priorities({'last_shifts':[['.0','.001','U13 C7']]})['findings'],[])

if __name__=='__main__':unittest.main()
