import contextlib,copy,io,json,shutil,tempfile,unittest
from pathlib import Path
from ab_auto import generate_requests,load_policy
from auto_water import request as water_request
import toolbox
from test_ab_automation import packet

class UnifiedEntry(unittest.TestCase):
 def test_all_tools_visible_in_text_and_json(self):
  text=io.StringIO();js=io.StringIO()
  with contextlib.redirect_stdout(text):self.assertEqual(toolbox.main(['list']),0)
  with contextlib.redirect_stdout(js):self.assertEqual(toolbox.main(['list','--json']),0)
  v=json.loads(js.getvalue())
  for tool in v['tools']:self.assertIn('  '+tool['id']+' ',text.getvalue())
  self.assertEqual(v['release'],json.loads((toolbox.ROOT/'release_info.json').read_text('utf-8'))['release_id'])
 def test_group_error_cannot_silently_hide_tools(self):
  with tempfile.TemporaryDirectory() as d:
   root=Path(d);(root/'assets').mkdir()
   v=json.loads((toolbox.ROOT/'assets/toolbox.json').read_text('utf-8'));v['tools'][0]['group']='unknown'
   (root/'assets/toolbox.json').write_text(json.dumps(v));shutil.copy2(toolbox.ROOT/'release_info.json',root/'release_info.json')
   with self.assertRaisesRegex(ValueError,'group'):toolbox.load_catalog(root)
 def test_release_count_inconsistency_fails(self):
  with tempfile.TemporaryDirectory() as d:
   root=Path(d);(root/'assets').mkdir();shutil.copy2(toolbox.ROOT/'assets/toolbox.json',root/'assets/toolbox.json')
   (root/'release_info.json').write_text(json.dumps({'release_id':'test','tools':0}))
   with self.assertRaisesRegex(ValueError,'count'):toolbox.load_catalog(root)
 def test_version_is_same_as_plan_identity(self):
  version=io.StringIO();plan=io.StringIO()
  with contextlib.redirect_stdout(version):self.assertEqual(toolbox.main(['version','--json']),0)
  with contextlib.redirect_stdout(plan):self.assertEqual(toolbox.main(['plan','metadata','--','sample.pcf']),0)
  self.assertEqual(json.loads(version.getvalue())['release_id'],json.loads(plan.getvalue())['release'])
 def test_route_output_uses_catalog_release(self):
  import subprocess,sys
  r=subprocess.run([sys.executable,'-B',str(toolbox.ROOT/'scripts/route_problem.py'),'--alerts','420','--json'],capture_output=True,encoding='utf-8')
  self.assertEqual(r.returncode,0,r.stderr)
  self.assertEqual(json.loads(r.stdout)['release'],toolbox.load_catalog()['release'])

class ControlRoutes(unittest.TestCase):
 def test_only_declared_data_changes_are_sensitivity_handoffs(self):
  from ab_auto import sensitivity_handoff
  rows=[{'name':'bad_adp','status':'completed','flags':['non_positive_definite_ADP']},{'name':'omit','status':'completed','flags':['reflection_count_changed']},{'name':'failed','status':'failed'}]
  plans=[{'name':'bad_adp'},{'name':'omit','reflection_omit':{'hkls':[[1,2,3]]}},{'name':'failed','reflection_omit':{'hkls':[[1,2,3]]}}]
  self.assertEqual([x['name'] for x in sensitivity_handoff(rows,plans,'trials')],['omit'])
 def route(self,code,evidence=None):
  p,r=packet(code,());p['refinement_control_evidence']=evidence or {};return generate_requests(p,r,load_policy())
 def test_exti_alert_without_su_is_not_enough(self):self.assertFalse(self.route('031')[0])
 def test_verified_weak_exti_builds_comparison(self):self.assertEqual(self.route('031',{'extinction':{'remove_trial_supported':True}})[0][0]['recipe'],'remove_extinction')
 def test_damp_needs_existing_control(self):self.assertFalse(self.route('936')[0])
 def test_existing_damp_builds_comparison(self):self.assertEqual(self.route('936',{'proposals':['release_damping']})[0][0]['recipe'],'release_damping')
 def test_gof_alone_never_omits_data(self):self.assertFalse(self.route('939')[0])
 def test_verified_outliers_allow_939_sensitivity(self):
  p,r=packet('939',());p['reflection_evidence']={'weighted_outliers':[{'hkl':[1,2,3],'delta_over_sigmaW':12.,'status':'o'}]}
  req,_=generate_requests(p,r,load_policy());self.assertEqual(req[0]['recipe'],'reflection_omit')
 def test_more_than_twenty_outliers_defers(self):
  p,r=packet('939',());p['reflection_evidence']={'weighted_outliers':[{'hkl':[i,2,3],'delta_over_sigmaW':12.,'status':'o'} for i in range(21)]}
  self.assertFalse(generate_requests(p,r,load_policy())[0])

def water_packet():
 atoms=[{'label':s,'res_label':s,'part':0,'residue':'0','occupancy':1,'res_context_status':'matched'} for s in ['O1','H1','H2','O2','O3']]
 contacts=[dict(atom=label,element='O',part_compatible=True,distance=2.8,vector_cart=vec,symmetry='x,y,z',translation=[0,0,0],covalent_radius_screen=False,metal=False) for label,vec in [('O2',[1,0,0]),('O3',[-.2,1,0])]]
 donors=[dict(parent='O1',element='O',hydrogens=[{'hydrogen':'H1'},{'hydrogen':'H2'}],heavy_contacts=contacts)]
 donors += [dict(parent=s,element='O',hydrogens=[],heavy_contacts=[dict(element='S',covalent_radius_screen=True,metal=False)]) for s in ['O2','O3']]
 return {'all_atoms':atoms,'donor_evidence':{'donors':donors,'ambiguous_hydrogens':[]}}

class WaterRoutes(unittest.TestCase):
 def test_complete_water_generates_explicit_images_only(self):
  p=water_packet();original=copy.deepcopy(p);v=water_request(p,['H2']);self.assertEqual(v['recipe'],'water_orient');self.assertEqual(v['parameters']['hydrogens'],['H1','H2']);self.assertEqual(p,original)
 def test_missing_water_h_not_invented(self):
  p=water_packet();p['donor_evidence']['donors'][0]['hydrogens'].pop()
  with self.assertRaises(ValueError):water_request(p,['O1'])
 def test_partial_occupancy_water_deferred(self):
  p=water_packet();p['all_atoms'][0]['occupancy']=.5
  with self.assertRaises(ValueError):water_request(p,['O1'])
 def test_protonated_acceptor_not_assumed(self):
  p=water_packet();p['donor_evidence']['donors'][1]['hydrogens']=[{'hydrogen':'HX'}]
  with self.assertRaises(ValueError):water_request(p,['O1'])
 def test_ambiguous_acceptor_h_deferred(self):
  p=water_packet();p['donor_evidence']['ambiguous_hydrogens']=[{'hydrogen':'HX','parent_candidates':[{'parent':'O2'}]}]
  with self.assertRaises(ValueError):water_request(p,['O1'])
 def test_covalent_heavy_atom_prevents_water_assignment(self):
  p=water_packet();p['donor_evidence']['donors'][0]['heavy_contacts'].append({'covalent_radius_screen':True,'metal':False,'element':'C'})
  with self.assertRaises(ValueError):water_request(p,['O1'])

if __name__=='__main__':unittest.main()
