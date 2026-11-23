import json
from pathlib import Path
import tempfile
import unittest

import gemmi
from crystal_runtime import sha
from experiment_metadata_state import collect,synchronize,validate
from compare_diagnostic_trials import compare

RES='TITL Synthetic\nCELL .71073 10 10 10 90 90 90\nLATT -1\nSFAC C\nUNIT 1\nTEMP -173.15\nFVAR 1\nC1 1 .2 .3 .4 11 .04\nHKLF 4\nEND\n'


class Metadata(unittest.TestCase):
 def setup_case(self,p,fields=None):
  h=p/'x.hkl';h.write_text('synthetic HKL marker')
  s=p/'x.pcf';s.write_text(fields or '_diffrn_ambient_temperature 100\n_cell_measurement_reflns_used 1234\n_cell_measurement_theta_min 2\n_cell_measurement_theta_max 25\n')
  cfg={'hkl':str(h),'sources':[{'path':str(s),'kind':'cif_metadata','same_experiment_confirmed':True,'basis':'Synthetic paired fixture','hkl_sha256':sha(h),'source_sha256':sha(s)}]}
  c=p/'config.json';c.write_text(json.dumps(cfg))
  collect(c,p/'ledger')
  r=p/'x.res';r.write_text(RES)
  b=gemmi.cif.Document().add_new_block('synthetic')
  b.set_pair('_diffrn_ambient_temperature','?');b.set_pair('_shelx_res_file',gemmi.cif.quote(RES));b.set_pair('_chemical_formula_sum',"'C1'")
  doc=gemmi.cif.Document();doc.add_copied_block(b);f=p/'x.cif';doc.write_file(str(f))
  return p/'ledger/metadata_ledger.json',f,r,h
 def test_sync_repeated_after_regeneration_and_source_unchanged(self):
  with tempfile.TemporaryDirectory() as td:
   p=Path(td);args=self.setup_case(p);hashes=[sha(x) for x in args]
   a=synchronize(*args,p/'out1');b=synchronize(*args,p/'out2')
   self.assertEqual(a['status'],'synchronized');self.assertEqual(a['filled'],b['filled']);self.assertEqual(hashes,[sha(x) for x in args])
   self.assertEqual(gemmi.cif.read_file(a['output']).sole_block().find_value('_chemical_formula_sum'),"'C1'")
 def test_missing_temp_requests_native_refinement(self):
  with tempfile.TemporaryDirectory() as td:
   p=Path(td);args=list(self.setup_case(p));r=args[2];r.write_text(RES.replace('TEMP -173.15\n',''))
   doc=gemmi.cif.read_file(str(args[1]));doc.sole_block().set_pair('_shelx_res_file',gemmi.cif.quote(r.read_text()));doc.write_file(str(args[1]))
   self.assertTrue(synchronize(*args,p/'out')['native_refinement_required'])
 def test_reject_different_hkl_and_changed_source(self):
  with tempfile.TemporaryDirectory() as td:
   p=Path(td);args=self.setup_case(p);args[3].write_text('changed')
   with self.assertRaises(ValueError):synchronize(*args,p/'out')
 def test_native_header_comments_do_not_break_active_model_pairing(self):
  with tempfile.TemporaryDirectory() as td:
   p=Path(td);args=self.setup_case(p);args[2].write_text(RES.replace('CELL','    SHELXL native header\nCELL')+'\nREM native trailing information\n')
   self.assertEqual(synchronize(*args,p/'out')['status'],'synchronized')
 def test_changed_embedded_coordinates_are_rejected(self):
  with tempfile.TemporaryDirectory() as td:
   p=Path(td);args=self.setup_case(p);args[2].write_text(RES.replace('.2 .3 .4','.21 .3 .4'))
   with self.assertRaises(ValueError):synchronize(*args,p/'out')
 def test_conflicting_known_candidate_retained(self):
  with tempfile.TemporaryDirectory() as td:
   p=Path(td);args=self.setup_case(p);d=gemmi.cif.read_file(str(args[1]));d.sole_block().set_pair('_diffrn_ambient_temperature','200');d.write_file(str(args[1]))
   r=synchronize(*args,p/'out');self.assertEqual(r['status'],'needs_review');self.assertEqual(r['conflicts_retained'][0]['current'],'200')
 def test_invalid_values(self):
  for fields in [{'_cell_measurement_theta_max':'110'},{'_exptl_crystal_size_min':'0'},{'_cell_measurement_reflns_used':'12.4'},{'_cell_measurement_theta_min':'20','_cell_measurement_theta_max':'10'}]:
   self.assertTrue(validate(fields))
 def test_unknown_and_not_applicable_not_fabricated(self):
  with tempfile.TemporaryDirectory() as td:
   p=Path(td);args=self.setup_case(p,'_diffrn_ambient_temperature ?\n_exptl_crystal_description .\n');m=json.loads(args[0].read_text())
   self.assertNotIn('_diffrn_ambient_temperature',m['resolved']);self.assertEqual(m['resolved']['_exptl_crystal_description'],'.')


def trial():
 return {'status':'completed','kind':'diagnostic_refinement','metrics':{'R1_observed':.05,'wR2':.1,'GooF':1.0,'NPD_atoms':0,'last_abs_max_shift_esd':.001,'unique':1000},'AB':[],
  'parameters':100,'restraints':10,'difference_density':{'max':.4,'min':-.3},'occupancy_warnings':[],
  'restraint_tension':{'needs_review':False},'comparison_context':{'hkl_sha256':'same','frozen_controls':[['WGHT','.1','0']]}}


class Comparison(unittest.TestCase):
 def test_reduced_alert_does_not_hide_bad_restraints(self):
  b=trial();t=trial();b['AB']=[{'code':'214','level':'B','text':'elongated'}];t['restraint_tension']={'needs_review':True}
  r=compare(b,t);self.assertIn('geometry_restraints_conflict_with_refined_model',r['flags']);self.assertFalse(r['model_adopted'])
 def test_same_reflection_count_is_not_same_input(self):
  b=trial();t=trial();t['comparison_context']['hkl_sha256']='different'
  self.assertFalse(compare(b,t)['comparison_context_verified'])
 def test_positive_negative_residuals_separate(self):
  b=trial();t=trial();t['difference_density']={'max':.6,'min':-.1};t['metrics']['R1_observed']=.04
  self.assertIn('residual_max_worsened',compare(b,t)['flags'])
 def test_model_complexity_retained(self):
  b=trial();t=trial();t['parameters']=125
  self.assertEqual(compare(b,t)['model_complexity']['parameter_delta'],25)


if __name__=='__main__':unittest.main()
