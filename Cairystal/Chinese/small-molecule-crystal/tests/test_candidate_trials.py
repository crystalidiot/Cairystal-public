from pathlib import Path
import tempfile,unittest,json
from candidate_trials import build,controls,IMMUTABLE

class CandidateTests(unittest.TestCase):
 def setUp(self):
  self.temp=tempfile.TemporaryDirectory();self.d=Path(self.temp.name)
  self.res='TITL test\nCELL .71073 10 11 12 90 90 90\nZERR 1 .01 .01 .01 .1 .1 .1\nLATT -1\nSFAC C O\nUNIT 1 1\nL.S. 20\nWGHT .04 1.2\nFVAR 1\nC1 1 .1 .2 .3 11 .03 .04 .05 .001 .002 .003\nO1 2 .2 .2 .3 11 .04 .04 .04 0 0 0\nHKLF 4\nEND\n'
  (self.d/'case.res').write_text(self.res,encoding='ascii')
  (self.d/'case.cif').write_text('data_test\nloop_\n_atom_site_label\n_atom_site_U_iso_or_equiv\nC1 .04\nO1 .04\n',encoding='ascii')
  self.plan={'name':'test','reason':'test explicit hypothesis','evidence':['synthetic fixture'],'cycles':20}
 def tearDown(self):self.temp.cleanup()
 def test_weights_data_symmetry_preserved(self):
  self.plan['add_restraints']=['ISOR 0.1 0.2 C1'];text,edits=build(self.d,self.plan,self.d)
  self.assertEqual(controls(text,IMMUTABLE),controls(self.res,IMMUTABLE))
  self.assertIn('ISOR 0.1 0.2 C1',text)
 def test_iso_uses_paired_ueq(self):
  self.plan['isotropic']=['C1'];text,_=build(self.d,self.plan,self.d)
  self.assertIn('C1 1 .1 .2 .3 11 0.04000000',text)
 def test_unlisted_element_refused(self):
  self.plan['element_changes']={'C1':'Br'}
  with self.assertRaises(ValueError):build(self.d,self.plan,self.d)
 def test_omit_reflection_injection_refused(self):
  self.plan['add_restraints']=['OMIT 1 2 3']
  with self.assertRaises(ValueError):build(self.d,self.plan,self.d)
 def test_multiline_injection_refused(self):
  self.plan['add_restraints']=['ISOR C1\nOMIT 1 2 3']
  with self.assertRaises(ValueError):build(self.d,self.plan,self.d)
 def test_no_zero_cycle_convergence_claim(self):
  self.plan['cycles']=0
  with self.assertRaises(ValueError):build(self.d,self.plan,self.d)
 def test_unknown_atom_refused(self):
  self.plan['isotropic']=['C999']
  with self.assertRaises(ValueError):build(self.d,self.plan,self.d)
 def test_ambiguous_labels_refused(self):
  (self.d/'case.res').write_text(self.res.replace('HKLF 4','PART 1\nC1 1 .2 .3 .4 11 .04\nHKLF 4'),encoding='ascii')
  with self.assertRaises(ValueError):build(self.d,self.plan,self.d)
 def test_type_change_bookkeeping_not_formula_proof(self):
  self.plan.update(element_changes={'C1':'O'},rename={'C1':'O2'})
  text,edits=build(self.d,self.plan,self.d)
  self.assertIn('UNIT 0.000000 2.000000',text);self.assertFalse(edits[-1]['chemical_formula_confirmed'])
 def test_never_silently_remove_other_constraint(self):
  self.plan['remove_restraints']=['WGHT .04 1.2']
  with self.assertRaises(ValueError):build(self.d,self.plan,self.d)
 def test_omit_parent_removes_riding_H_and_empty_AFIX(self):
  text=self.res.replace('SFAC C O','SFAC C O H').replace('UNIT 1 1','UNIT 1 1 2').replace('O1 2', 'AFIX 23\nH1 3 .1 .2 .4 11 -1.2\nH2 3 .1 .2 .2 11 -1.2\nAFIX 0\nO1 2')
  (self.d/'case.res').write_text(text,encoding='ascii');self.plan.update(kind='omit_map',cycles=0,omit_atoms=['C1'])
  result,edits=build(self.d,self.plan,self.d)
  self.assertNotIn('H1 3',result);self.assertNotIn('H2 3',result);self.assertNotIn('AFIX 23',result)
  self.assertEqual(len(edits[0]['auto_omitted_riding_children']),2)
  self.assertNotIn('ACTA',result);self.assertIn('LIST 6',result)

if __name__=='__main__':unittest.main(verbosity=2)
