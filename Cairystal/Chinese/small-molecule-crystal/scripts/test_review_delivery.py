import json,tempfile,unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
import gemmi
from crystal_runtime import sha,write_json
import deliver_ready as dr

class ResumeDeliveryTests(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup);self.base=Path(self.tmp.name);self.root=self.base/'finish';self.root.mkdir();self.src=self.base/'source.res';self.src.write_text('synthetic source')
  selected=self.root/'frozen';selected.mkdir();(selected/'model.cif').write_text('synthetic frozen CIF');notes=self.root/'reviewer_notes.json';write_json(notes,{'synthetic':True})
  write_json(self.root/'config.json',{'platon':'not_executed','renderer':'word','pdftoppm':'not_executed'})
  write_json(self.root/'input_audit.json',{'files':{'res':str(self.src)},'source_sha256':{'res':sha(self.src)}})
  self.state={'status':'ready_for_official_delivery','selected':str(selected),'notes':str(notes),'events':[],'code_sha256':{p.name:sha(p) for p in Path(dr.__file__).parent.glob('*.py')}}
  self.state['ready_artifacts']=dr.seal_ready(self.root,self.state);write_json(self.root/'state.json',self.state)
 def test_authorization_only_gates_delivery(self):
  with patch('crystal_delivery.run') as fn,self.assertRaisesRegex(ValueError,'authorized'):dr.run(self.root,False)
  fn.assert_not_called();self.assertEqual(json.loads((self.root/'state.json').read_text())['status'],'ready_for_official_delivery')
 def test_parallel_or_interrupted_owner_blocks_delivery(self):
  lock=self.root/'delivery_resume.lock';lock.write_text('preserved owner')
  with patch('crystal_delivery.run') as fn,self.assertRaisesRegex(ValueError,'owns this checkpoint'):dr.run(self.root,True)
  fn.assert_not_called();self.assertEqual(lock.read_text(),'preserved owner')
 def test_changed_notes_block_delivery(self):
  Path(self.state['notes']).write_text('changed')
  with patch('crystal_delivery.run') as fn,self.assertRaisesRegex(ValueError,'changed'):dr.run(self.root,True)
  fn.assert_not_called()
 def test_changed_original_blocks_delivery(self):
  self.src.write_text('changed')
  with self.assertRaisesRegex(ValueError,'source bundle'):dr.verify_ready(self.root,self.state)
 def test_success_does_not_refine_or_replay(self):
  def fake(a):
   p=Path(a.output);p.mkdir();write_json(p/'result.json',{'status':'awaiting_visual_review','official':{'counts':{'A':0,'B':0}},'AB_alerts':[]});return 0
  with patch.object(dr,'paired_bundle'),patch('crystal_delivery.run',side_effect=fake) as send,patch('run_crystal_stage.run') as refine:
   r=dr.run(self.root,True);self.assertEqual(r['status'],'awaiting_visual_review');self.assertEqual(send.call_count,1);refine.assert_not_called()
   with self.assertRaisesRegex(ValueError,'replay'):dr.run(self.root,True)
   self.assertEqual(send.call_count,1)
 def test_failed_delivery_not_replayed(self):
  with patch.object(dr,'paired_bundle'),patch('crystal_delivery.run',return_value=1) as send:
   self.assertEqual(dr.run(self.root,True)['status'],'failed')
   with self.assertRaises(ValueError):dr.run(self.root,True)
   self.assertEqual(send.call_count,1)

class MapPairingTests(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup);self.root=Path(self.tmp.name)
  self.fcf=self.root/'map.fcf';self.fcf.write_text('''data_fixture
_shelx_refln_list_code 6
_cell_length_a 10
_cell_length_b 10
_cell_length_c 10
_cell_angle_alpha 90
_cell_angle_beta 90
_cell_angle_gamma 90
loop_
_space_group_symop_operation_xyz
x,y,z
-x,-y,-z
loop_
_refln_index_h
_refln_index_k
_refln_index_l
_refln_F_squared_meas
_refln_F_squared_sigma
_refln_F_calc
_refln_phase_calc
1 0 0 4 1 1 0
''')
 def test_same_cell_different_symmetry_is_rejected_before_map_export(self):
  import local_difference_map as lm
  block=gemmi.cif.read_string('data_model\nloop_\n_space_group_symop_operation_xyz\nx,y,z\n').sole_block()
  with patch.object(lm,'structure',return_value=(block,gemmi.UnitCell(10,10,10,90,90,90),None,[],{})),self.assertRaisesRegex(ValueError,'symmetry'):lm.calculate(self.fcf,self.root/'map','unused','unused',[])
  self.assertFalse((self.root/'map/difference.ccp4').exists())
 def test_fractional_hkl_not_silently_rounded(self):
  import local_difference_map as lm
  self.fcf.write_text(self.fcf.read_text().replace('1 0 0 4 1 1 0','1.5 0 0 4 1 1 0'))
  block=gemmi.cif.read_file(str(self.fcf)).sole_block()
  with patch.object(lm,'structure',return_value=(block,gemmi.UnitCell(10,10,10,90,90,90),None,[],{})),self.assertRaisesRegex(ValueError,'Noninteger'):lm.calculate(self.fcf,self.root/'map','unused','unused',[])
 def test_invalid_grid_rejected_before_directory_creation(self):
  import local_difference_map as lm
  with self.assertRaises(ValueError):lm.calculate(self.fcf,self.root/'map','unused','unused',[],step=0)
  self.assertFalse((self.root/'map').exists())

if __name__=='__main__':unittest.main()
