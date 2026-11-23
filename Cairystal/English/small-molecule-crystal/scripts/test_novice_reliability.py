"""Input semantics and cross-artifact invariants; synthetic edge cases only."""
import json,tempfile,unittest,zipfile
from pathlib import Path
from unittest.mock import patch
from intake_once import normalized,export,dimensions
from crystal_runtime import sha,write_json
from crystal_session import parse_p4p
from experiment_metadata_state import p4p_fields
from customer_status import describe
import test_delivery_completion as fixtures
import delivery_contract as dc

class NoviceInputs(unittest.TestCase):
 def test_example_with_unit_and_fullwidth(self):
  for value in ['0.05 × 0.052 × 0.054 mm','０．０５＊０．０５２＊０．０５４ 毫米','0.05x0.052x0.054','0.05 0.052 0.054']:
   self.assertEqual(dimensions(value),[.05,.052,.054])
 def test_explicit_unknown_stays_unknown(self):
  for value in [None,'','不清楚','未知','不知道','unknown','?',[]]:self.assertIsNone(dimensions(value))
 def test_invalid_and_other_units_never_guessed(self):
  for value in [False,True,0,{},[True,.052,.054],'0.05*0.052*0.054 mm3','50*52*54 um','0.05*0.052*0','NaN 1 2','0.1 0.2']:
   with self.subTest(value=value),self.assertRaises(ValueError):dimensions(value)
 def test_explorer_quoted_path_and_preserved_confirmed_dimensions(self):
  with tempfile.TemporaryDirectory() as tmp:
   p=Path(tmp);raw=p/'raw';raw.mkdir();src=p/'form.json'
   write_json(src,{'schema':1,'data_dir':' "'+str(raw)+'" ','elements':'C H O','dimensions_mm':'0.05 × 0.052 × 0.054 mm','observations_confirmed':True})
   state,out=export(src,p/'out');self.assertEqual(state['status'],'ready_for_raw_data_inspection')
   self.assertEqual(state['data']['data_dir'],str(raw))
   spec=json.loads((out/'specimen.json').read_text('utf-8'));self.assertEqual(spec['cif_fields']['_exptl_crystal_size_max'],.054)
 def test_missing_directory_retains_all_answers_and_blocks_config(self):
  with tempfile.TemporaryDirectory() as tmp:
   p=Path(tmp);src=p/'form.json';write_json(src,{'schema':1,'data_dir':'missing','elements':['C'],'colour':'绿色','observations_confirmed':True})
   state,out=export(src,p/'out');self.assertEqual(state['status'],'needs_input');self.assertEqual(state['data']['colour'],'绿色');self.assertFalse((out/'autorun_config.json').exists())

class P4POrigin(unittest.TestCase):
 TEXT='FILEID SAINT synthetic\nCELL 10 11 12 90 95 90\nCELLSD .001 .001 .001 0 .01 0\nSOURCE MO .71073\nBRAVAIS Monoclinic(b-unique) P\nSAINGL 2000 2.5 25.0 0\nCSIZE 0 0 0 0 0\n'
 def test_reconstructed_source_rejected_by_both_entrypoints(self):
  text='FILEID Created by OLEX2: synthetic fixture\n'+self.TEXT
  with self.assertRaisesRegex(ValueError,'Reconstructed Olex2'):parse_p4p(text)
  with tempfile.TemporaryDirectory() as tmp:
   p=Path(tmp)/'model.p4p';p.write_text(text)
   with self.assertRaisesRegex(ValueError,'Reconstructed Olex2'):p4p_fields(p,'both')
 def test_genuine_zero_celsius_not_globally_deleted(self):
  self.assertEqual(parse_p4p(self.TEXT)['temperature_K'],273.15)
 def test_kelvin_conversion_and_scope_remain(self):
  with tempfile.TemporaryDirectory() as tmp:
   p=Path(tmp)/'raw.p4p';p.write_text(self.TEXT.replace('CSIZE 0 0 0 0 0','CSIZE .05 .06 .07 0 -173.15'))
   fields,_,_=p4p_fields(p,'diffraction');self.assertEqual(float(fields['_diffrn_ambient_temperature']),100)
   self.assertNotIn('_cell_measurement_temperature',fields)

class DeliveryBinding(unittest.TestCase):
 def setUp(self):
  fixture=fixtures.CompletionContracts();fixture.setUp();self.addCleanup(fixture.doCleanups);self.root=fixture.p;self.folder=fixture.complete_fixture()
  p=patch('iucr_validation.validate_saved',return_value=({},{'counts':{'A':0,'B':0}}));p.start();self.addCleanup(p.stop)
  p=patch('squeeze_bundle.companion_fab',return_value=None);p.start();self.addCleanup(p.stop)
 def test_valid_fixture_is_complete_but_not_accepted(self):
  r=dc.audit(self.root);self.assertEqual(r['status'],'artifacts_complete');self.assertEqual(r['scientific_acceptance'],'not_established_by_file_completion')
 def test_old_valid_word_file_is_rejected(self):
  for name in ['晶体学报表_中文.docx','Crystallographic_Report_EN.docx']:
   path=self.folder/name;original=path.read_bytes()
   with zipfile.ZipFile(path,'w') as z:z.writestr('word/document.xml','<document>other crystal</document>')
   self.assertEqual(dc.audit(self.root)['status'],'incomplete');path.write_bytes(original)
 def test_native_mixing_rejected(self):
  for ext in ['res','hkl','fcf','lst']:
   path=self.folder/('model.'+ext);old=path.read_bytes();path.write_bytes(old+b'changed')
   self.assertEqual(dc.audit(self.root)['status'],'incomplete');path.write_bytes(old)
 def test_report_from_different_cif_rejected(self):
  path=self.root/'qa/report_build.json';v=json.loads(path.read_text());v['cif_sha256']='old';write_json(path,v)
  self.assertEqual(dc.audit(self.root)['status'],'incomplete')
 def test_table_manifest_without_numeric_binding_rejected(self):
  path=self.root/'qa/report_build.json';v=json.loads(path.read_text());v['outputs']['en']['data_sha256']='different';write_json(path,v)
  self.assertEqual(dc.audit(self.root)['status'],'incomplete')

class CustomerStatus(unittest.TestCase):
 def test_local_only_not_delivered(self):self.assertIn('尚未完整交付',describe({'status':'local_ready'})['title'])
 def test_zero_alerts_never_prove_correctness(self):self.assertEqual(describe({'status':'complete','official_counts':{'A':0,'B':0}})['scientific_correctness'],'not_established_by_workflow_status')
 def test_scientific_problem_goes_to_assistant(self):self.assertIn('助手',describe({'status':'needs_attention','category':'scientific_decision'})['next_action_owner'])
 def test_unknown_chemistry_does_not_demand_invented_formula(self):self.assertIn('无需编造',describe({'status':'needs_attention','category':'chemical_graph_required'})['explanation'])

if __name__=='__main__':unittest.main()
