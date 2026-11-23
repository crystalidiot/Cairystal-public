import copy,json,math,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
import gemmi,numpy as np
from common_disorder_fixtures import fixture
from common_disorder import detect,positions,generate
from structure_diagnostics import res_records
from density_disorder import config,fitted_angle,rigid_fit,rotation_config,match_score,propose,choose_screens,run,prepare,short_trial,split_special_sites

class DensityDisorderTests(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.root=Path(self.tmp.name);self.base=fixture(self.root/'base')
 def tearDown(self):self.tmp.cleanup()
 def seed(self,angle=37.2):
  site=detect(self.base)['sites'][0];c={'atoms':site['atoms'],'axis':site['axis'],'angle_deg':angle,'parts':[1,2],'adp':'ISO','occupancy_start':.7,'basis':'synthetic density test'}
  p=res_records(self.base/'case.res');b=gemmi.cif.read_file(str(self.base/'case.cif')).sole_block();cell,amap,fn=positions(p,b,c)
  with (self.base/'case.res').open('a') as f:
   for i,k in enumerate(c['atoms']):
    v=cell.fractionalize(gemmi.Position(*fn(amap[k],True)));f.write(f'Q{i+1} 1 {v.x:.7f} {v.y:.7f} {v.z:.7f} 11 .04 1.5\n')
  return site
 def test_angle_from_density_not_fixed_grid(self):
  a=math.radians(37.2);self.assertAlmostEqual(fitted_angle([0,1,0],[0,math.cos(a),math.sin(a)],[1,0,0]),37.2)
 def test_angle_sign(self):self.assertAlmostEqual(fitted_angle([1,0,0],[0,-1,0],[0,0,1]),-90)
 def test_refined_split_atom_on_inversion_centre_is_flagged(self):
  cell=gemmi.UnitCell(10,10,10,90,90,90);ops=list(gemmi.SpaceGroup('P -1').operations())
  hits=split_special_sites(cell,ops,[{'label':'Cl2B','element':'Cl','xyz':[.5,1,1],'occupancy':.21}],['CL2B'])
  self.assertEqual(hits[0]['site_stabilizer_order'],2)
 def test_general_site_and_unsplit_special_atom_not_flagged(self):
  cell=gemmi.UnitCell(10,10,10,90,90,90);ops=list(gemmi.SpaceGroup('P -1').operations())
  atoms=[{'label':'Cl2B','element':'Cl','xyz':[.51,.91,1],'occupancy':.1},{'label':'Ag1','element':'Ag','xyz':[0,0,0],'occupancy':1}]
  self.assertEqual(split_special_sites(cell,ops,atoms,['Cl2B']),[])
 def test_axis_atom_no_direction(self):self.assertIsNone(fitted_angle([0,0,1],[1,0,0],[0,0,1]))
 def test_rigid_fit_and_config_preserve_pose(self):
  a=np.array([[0,0,0],[1.4,0,0],[0,1.4,.2],[.2,.3,1.2]])
  for angle in [0,37.2,180]:
   t=math.radians(angle);rot=np.array([[math.cos(t),math.sin(t),0],[-math.sin(t),math.cos(t),0],[0,0,1]])
   b=a@rot+np.array([.3,-.2,.1]);rr,sh,err=rigid_fit(a,b);self.assertLess(err,1e-10);self.assertAlmostEqual(np.linalg.det(rr),1)
   c=rotation_config(rr,sh,a.mean(0));from split_fragment_seed import rotate
   rebuilt=np.array([a.mean(0)+np.array(rotate(list(x-a.mean(0)),c['rigid_axis'],math.radians(c['angle_deg'])))+c['translation_A'] for x in a])
   np.testing.assert_allclose(rebuilt,b,atol=1e-8)
 def test_mirror_not_fitted_by_reflection(self):
  a=np.array([[0,0,0],[1,0,0],[0,2,0],[0,0,3]]);r,s,e=rigid_fit(a,a*[-1,1,1]);self.assertAlmostEqual(np.linalg.det(r),1);self.assertGreater(e,.1)
 def test_collinear_rejected(self):
  with self.assertRaises(ValueError):rigid_fit([[0,0,0],[1,0,0],[2,0,0]],[[0,1,0],[1,1,0],[2,1,0]])
 def test_invalid_settings_rejected(self):
  for val in [{'unknown':2},{'short_cycles':30},{'max_raw_poses':True},{'min_peak':float('nan')},{'population_start':1}]:
   with self.assertRaises(ValueError):config(val)
 def test_no_q_does_not_split(self):self.assertEqual(propose(self.base,detect(self.base)['sites'][0])['status'],'insufficient_supported_density')
 def test_review_site_does_not_split(self):
  site=detect(self.base)['sites'][0];site.update(status='needs_review',review_reasons=['unestablished identity']);self.assertEqual(propose(self.base,site)['poses'],[])
 def test_real_coordinate_fitted_angle_has_evidence(self):
  result=propose(self.base,self.seed());self.assertGreater(len(result['poses']),0);self.assertLessEqual(len(result['poses']),4)
  self.assertTrue(any(abs(p['config']['angle_deg']-37.2)<.1 for p in result['poses']))
  for p in result['poses']:self.assertGreaterEqual(len(p['peak_support']),2)
 def test_one_peak_cannot_be_reused(self):
  score,matches,_=match_score([[1,0,0],[1,.1,0]],['C','C'],[[0,0,0],[0,1,0]],['C','C'],[{'xyz':[1,.05,0],'height':1,'peak':'Q1'}],.5)
  self.assertEqual(len(matches),1)
 def test_original_equivalent_endpoints_not_support(self):
  score,matches,count=match_score([[0,1,0],[0,0,0]],['C','C'],[[0,0,0],[0,1,0]],['C','C'],[],.5);self.assertEqual(count,0)
 def test_symmetry_images_do_not_inflate_peak_count(self):
  peaks=[{'xyz':[1,0,0],'peak':'Q1','height':1},{'xyz':[2,0,0],'peak':'Q1','height':1}]
  _,matches,_=match_score([[1,0,0],[2,0,0]],['C','C'],[[0,0,0]],['C'],peaks,.5);self.assertEqual(len(matches),1)
 def test_mixed_ADP_keeps_only_A_anisotropic(self):
  site=self.seed();p=res_records(self.base/'case.res');b=gemmi.cif.read_file(str(self.base/'case.cif')).sole_block();c=propose(self.base,site)['poses'][0]['config'];c['adp']='MAJOR_ANI';v=generate(p,b,c)
  anis=[x for row in v['rows'] if row[0]=='ANIS' for x in row[1:]];self.assertTrue(anis);self.assertTrue(all(x.endswith('A') for x in anis))
 def test_noncarbon_CF3_anchor_detected(self):
  p=self.base/'case.res';p.write_text(p.read_text().replace('SFAC C F','SFAC C F O').replace('UNIT 4 6','UNIT 2 6 2').replace('C1 1 ','C1 3 '))
  doc=gemmi.cif.read_file(str(self.base/'case.cif'));b=doc.sole_block();b.find_values('_atom_site_type_symbol')[0]='O';doc.write_file(str(self.base/'case.cif'))
  self.assertTrue(any(s['family']=='cf3' for s in detect(self.base)['sites']))
 def test_short_model_defaults_retain_major_anisotropy(self):self.assertEqual(config()['short_adp'],'MAJOR_ANI')
 def test_review_only_sites_do_not_consume_native_site_budget(self):
  sites=[{'id':'unknown','status':'needs_review','review_reasons':['identity']},{'id':'a','status':'screenable'},{'id':'b','status':'screenable'}]
  files={e:str(self.base/('case.'+e)) for e in ['cif','res']}
  with patch('density_disorder.paired_bundle',return_value={'files':files}),patch('density_disorder.detect',return_value={'sites':sites}),patch('density_disorder.propose',return_value={'poses':[]}),patch('native_resources.effective',return_value={'threads':1,'matrix_parameters':6000}):
   plan=prepare(self.base,self.root/'new',{'shelxl':__file__,'platon':__file__},settings={'max_sites':1})
  self.assertEqual([s['id'] for s in plan['sites']],['unknown','a']);self.assertEqual(plan['deferred_sites'][0]['id'],'b');self.assertIsNone(plan['deferred_sites'][0]['AB'])
 def test_failed_short_trial_has_no_validated_AB(self):
  with patch('density_disorder.build',side_effect=ValueError('unsupported fragment')),patch('density_disorder.run_command') as native:
   result=short_trial(self.base,self.root/'failed',{'name':'x'},{},{})
   self.assertEqual(result['status'],'screen_failed');self.assertIsNone(result['AB']);self.assertFalse(result['validation_complete']);native.assert_not_called()
 def test_CF3_shared_carbon_bonds_are_restrained(self):
  site=self.seed();p=res_records(self.base/'case.res');b=gemmi.cif.read_file(str(self.base/'case.cif')).sole_block();c=propose(self.base,site)['poses'][0]['config'];v=generate(p,b,c)
  rows=[x for x in v['rows'] if x[0]=='SADI' and 'C2' in x];self.assertEqual(len(rows),3)
 def test_only_complete_screens_are_ranked_not_accepted(self):
  data=[{'name':'bad','status':'screen_failed','metrics':{'R1_observed':.01}},{'name':'good','status':'screen_complete','metrics':{'R1_observed':.08,'NPD_atoms':None},'model_adopted':False,'AB':None}]
  winners=choose_screens(data,1);self.assertEqual(winners[0]['name'],'good');self.assertFalse(winners[0]['model_adopted']);self.assertIsNone(winners[0]['AB'])
 def test_tampered_native_binary_stops(self):
  p=self.root/'plan.json';p.write_text(json.dumps({'settings':{},'output':str(self.root),'baseline':str(self.base),'software':{'shelxl':__file__,'platon':__file__},'software_hashes':{'shelxl':'wrong','platon':'wrong'}}))
  with patch('density_disorder.run_plan') as native:
   with self.assertRaisesRegex(ValueError,'Native executable changed'):run(p)
   native.assert_not_called()

if __name__=='__main__':unittest.main()
