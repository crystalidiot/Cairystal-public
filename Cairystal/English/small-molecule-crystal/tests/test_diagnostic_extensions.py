from pathlib import Path
import copy,math,tempfile,unittest
import gemmi
import numpy as np
from compare_diagnostic_trials import changes,compare
from split_fragment_seed import rotate,generate
from structure_diagnostics import res_records

class ComparisonTests(unittest.TestCase):
 def test_repeated_alerts_not_dropped(self):
  a={'code':'214','level':'B','text':'elongated C1'}
  v=changes([a,a],[a]);self.assertEqual(len(v['removed']),1);self.assertEqual(len(v['unchanged']),1)
 def test_lower_R_and_no_AB_cannot_override_bad_geometry(self):
  base={'status':'completed','metrics':{'R1_observed':.05,'unique':100,'last_abs_max_shift_esd':.001,'NPD_atoms':0},'AB':[{'code':'234','level':'B','text':'Ueq'}]}
  trial=copy.deepcopy(base);trial['metrics']['R1_observed']=.04;trial['AB']=[];trial['geometry_results']=[{'within_declared_range':False}]
  v=compare(base,trial);self.assertFalse(v['model_adopted']);self.assertIn('geometry_outside_declared_hypothesis',v['flags']);self.assertEqual(v['classification'],'not_supported_without_further_review')
 def test_missing_metrics_stay_null(self):
  base={'status':'completed','metrics':{}}
  v=compare(base,base);self.assertIsNone(v['comparison']['R1_observed']['delta']);self.assertIsNone(v['metrics'].get('R1_observed'))

class FourierTests(unittest.TestCase):
 def test_centro_cosine_normalization_and_phase_sign(self):
  cell=gemmi.UnitCell(10,10,10,90,90,90);sg=gemmi.find_spacegroup_by_name('P -1')
  for amp in [1.,-1.]:
   data=gemmi.ComplexAsuData(cell,sg,np.array([[1,0,0]],dtype=np.int32),np.array([amp+0j],dtype=np.complex64))
   g=data.transform_f_phi_to_map(exact_size=[16,16,16])
   self.assertAlmostEqual(g.interpolate_value(gemmi.Fractional(0,0,0)),2*amp/1000,places=8)
   self.assertAlmostEqual(g.interpolate_value(gemmi.Fractional(.25,0,0)),0,places=8)
   self.assertAlmostEqual(g.interpolate_value(gemmi.Fractional(.5,0,0)),-2*amp/1000,places=8)

class SplitTests(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();d=Path(self.tmp.name)
  text='TITL synthetic\nCELL .71 10 10 10 90 90 90\nLATT -1\nSFAC C F\nUNIT 3 1\nFVAR 1\nC1 1 .1 .1 .1 11 .04\nC2 1 .25 .1 .1 11 .04\nC3 1 .25 .24 .1 11 .04\nF1 2 .25 .36 .1 11 .04\nHKLF 4\nEND\n'
  (d/'case.res').write_text(text);self.parsed=res_records(d/'case.res')
  self.block=gemmi.cif.read_string('data_test\n_cell_length_a 10\n_cell_length_b 10\n_cell_length_c 10\n_cell_angle_alpha 90\n_cell_angle_beta 90\n_cell_angle_gamma 90\nloop_\n_space_group_symop_operation_xyz\n x,y,z\nloop_\n_atom_site_label\n_atom_site_U_iso_or_equiv\nC1 .04\nC2 .04\nC3 .04\nF1 .04\n').sole_block()
  self.config={'atoms':['C3','F1'],'axis':['C1','C2'],'angles_deg':[-10,10],'occupancy_start':.5,'parts':[1,2],'basis':'Synthetic two-orientation test'}
 def tearDown(self):self.tmp.cleanup()
 def test_rodrigues(self):
  p=rotate([1,0,0],[0,0,1],math.pi/2);self.assertAlmostEqual(p[0],0);self.assertAlmostEqual(p[1],1)
 def test_shared_population_and_complement(self):
  v=generate(self.parsed,self.block,self.config);atoms=[r for r in v['rows'] if r[0]!='PART'];self.assertEqual([r[5] for r in atoms],['21','21','-21','-21']);self.assertEqual(v['free_variable_number'],2)
 def test_not_an_existing_disorder_site(self):
  self.parsed['atoms'][-1]['part']=1
  with self.assertRaises(ValueError):generate(self.parsed,self.block,self.config)
 def test_special_position_refused(self):
  self.block.find_values('_space_group_symop_operation_xyz')[0]='x,y,z'
  self.block.init_loop('',['_space_group_symop_operation_xyz']).add_row(['x,y,z'])
  self.block.find_loop('_space_group_symop_operation_xyz').get_loop().add_row(['-x,-y,-z'])
  self.parsed['atoms'][-1]['xyz']=[0,0,0]
  with self.assertRaises(ValueError):generate(self.parsed,self.block,self.config)
 def test_unassembled_axis_refused(self):
  self.parsed['atoms'][1]['xyz']=[1.25,.1,.1]
  with self.assertRaises(ValueError):generate(self.parsed,self.block,self.config)
 def test_unmatched_initial_population_not_allowed(self):
  self.config['occupancy_start']=1.1
  with self.assertRaises(ValueError):generate(self.parsed,self.block,self.config)

if __name__=='__main__':unittest.main(verbosity=2)
