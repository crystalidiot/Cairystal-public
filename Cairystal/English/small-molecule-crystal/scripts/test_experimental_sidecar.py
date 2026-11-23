import copy,json,tempfile,unittest
from pathlib import Path
from experimental_sidecar import FIELDS,sha,validate_fields,load,export

def fields():
 vals=['block','Bruker D8',4500,2.5,28.,'100(2)','100.15(5)']
 result={}
 import gemmi
 for (tag,unit),v in zip(FIELDS.items(),vals):
  token=gemmi.cif.quote(str(v));value=gemmi.cif.as_number(token) if unit else str(v)
  result[tag]={'raw_token':token,'value':value,'unit':unit}
 return result

class SidecarTests(unittest.TestCase):
 def fixture(self,td):
  p=Path(td);inp=p/'inputs';inp.mkdir();case=inp/'A1'/'CASE_TEST';case.mkdir(parents=True)
  (case/'input.json').write_text('{"elements":["C"]}');(case/'data.hkl').write_text('1 0 0 10 1\n')
  manifest=inp/'manifest.json';manifest.write_text(json.dumps({'cases':[{'case_id':'CASE_TEST','category':'A1','directory':'A1/CASE_TEST'}]}))
  side=p/'sidecar.json';s={'schema':1,'dataset_manifest_sha256':sha(manifest),'cases':[{'case_id':'CASE_TEST','input_sha256':sha(case/'input.json'),'hkl_sha256':sha(case/'data.hkl'),'fields':fields(),'provenance':{'source_sha256':'a'*64,'selected_block_sha256':'b'*64,'extraction':'selected source block; whitelist only'}}]}
  side.write_text(json.dumps(s));return p,inp,manifest,side,s
 def test_unknown_model_field_rejected(self):
  f=fields();f['_space_group_name_H-M_alt']={'raw_token':"'P 1'",'value':'P 1','unit':None}
  with self.assertRaises(ValueError):validate_fields(f)
 def test_injected_token_or_comment_rejected(self):
  for raw in ['block\n_atom_site_label C1','block # reference identity','block\ndata_answer\n_x 1']:
   f=fields();f['_exptl_crystal_description']['raw_token']=raw
   with self.assertRaises(ValueError):validate_fields(f)
 def test_bad_units_and_range_rejected(self):
  f=fields();f['_diffrn_ambient_temperature']['unit']='C'
  with self.assertRaises(ValueError):validate_fields(f)
  f=fields();f['_cell_measurement_theta_min']={'raw_token':'50','value':50,'unit':'degree'}
  with self.assertRaises(ValueError):validate_fields(f)
 def test_hash_change_blocks_export_before_output(self):
  with tempfile.TemporaryDirectory() as td:
   p,inp,m,s,data=self.fixture(td);(inp/'A1/CASE_TEST/data.hkl').write_text('changed')
   with self.assertRaises(ValueError):export(s,m,inp,p/'out')
   self.assertFalse((p/'out').exists())
 def test_export_preserves_su_temperatures_and_native_plan(self):
  import gemmi
  with tempfile.TemporaryDirectory() as td:
   p,inp,m,s,data=self.fixture(td);r=export(s,m,inp,p/'out')
   b=gemmi.cif.read_file(r['entries'][0]['metadata_cif']).sole_block()
   self.assertEqual(b.find_value('_cell_measurement_temperature'),'100(2)')
   self.assertEqual(b.find_value('_diffrn_ambient_temperature'),'100.15(5)')
   plan=json.loads(Path(r['entries'][0]['temperature_plan']).read_text('utf-8'))
   self.assertEqual(plan['target_TEMP_degrees_C'],'-173.00');self.assertTrue(plan['requires_native_review']);self.assertFalse(r['scientific_acceptance'])
   self.assertEqual(set(i.pair[0] for i in b),set(FIELDS))
 def test_ledger_bridge_retains_separate_temperatures(self):
  from experiment_metadata_state import collect
  with tempfile.TemporaryDirectory() as td:
   p,inp,m,s,data=self.fixture(td);hp=inp/'A1/CASE_TEST/data.hkl';ip=inp/'A1/CASE_TEST/input.json'
   cfg={'hkl':str(hp),'sources':[{'path':str(s),'kind':'anonymous_sidecar','source_sha256':sha(s),'hkl_sha256':sha(hp),'same_experiment_confirmed':True,'basis':'synthetic same-experiment binding','case_id':'CASE_TEST','manifest':str(m),'input_json':str(ip)}]}
   cp=p/'config.json';cp.write_text(json.dumps(cfg));r=collect(cp,p/'ledger')
   self.assertEqual(r['resolved']['_cell_measurement_temperature'],'100(2)');self.assertEqual(r['resolved']['_diffrn_ambient_temperature'],'100.15(5)')
if __name__=='__main__':unittest.main()
