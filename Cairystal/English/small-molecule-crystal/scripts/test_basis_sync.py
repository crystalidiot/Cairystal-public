import json,tempfile,unittest
from pathlib import Path
from crystal_runtime import sha
from experiment_metadata_state import check_basis_audit

class Basis(unittest.TestCase):
 def fixture(self,p):
  ev=p/'addsym.log';ev.write_text('Synthetic transform evidence')
  a={'matrix':[[0,0,-1],[-1,0,0],[0,1,0]],'reason':'Synthetic signed permutation','evidence':[{'path':str(ev),'sha256':sha(ev)}],'reviewed_angle_idealization_max_deg':.06}
  path=p/'basis.json';path.write_text(json.dumps(a))
  native='CELL .71073 24 9 11 90 93.75 90\nHKLF 4 1 0 0 -1 -1 0 0 0 1 0\nEND\n'
  return path,native,[9,11,24,86.25,90.05,89.99],[24,9,11,90,93.75,90]
 def test_audited_setting_retains_angle_deviation(self):
  with tempfile.TemporaryDirectory() as td:
   r=check_basis_audit(*self.fixture(Path(td)))
   self.assertEqual(r['scientific_status'],'candidate_symmetry_requires_review');self.assertAlmostEqual(abs(r['angle_changes_deg'][2]),.05)
 def test_wrong_native_matrix_rejected(self):
  with tempfile.TemporaryDirectory() as td:
   a=list(self.fixture(Path(td)));a[1]='HKLF 4\n'
   with self.assertRaises(ValueError):check_basis_audit(*a)
 def test_wrong_cell_rejected(self):
  with tempfile.TemporaryDirectory() as td:
   a=list(self.fixture(Path(td)));a[3][1]=11
   with self.assertRaises(ValueError):check_basis_audit(*a)
 def test_changed_evidence_rejected(self):
  with tempfile.TemporaryDirectory() as td:
   p=Path(td);a=self.fixture(p);(p/'addsym.log').write_text('changed')
   with self.assertRaises(ValueError):check_basis_audit(*a)

if __name__=='__main__':unittest.main()
