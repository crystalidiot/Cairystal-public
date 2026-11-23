import copy,json,math,tempfile,unittest
from pathlib import Path
import gemmi
from common_disorder_fixtures import fixture
from common_disorder import detect,generate,positions,screen_poses,h_groups,load_catalog,matches_template,normalize_solvents,run_prepared,pairing_review
from candidate_trials import build,controls,IMMUTABLE
from crystal_runtime import records
from structure_diagnostics import res_records
from audit_occupancy import audit

class CommonDisorderTests(unittest.TestCase):
 def setUp(self):self.temp=tempfile.TemporaryDirectory();self.root=Path(self.temp.name);self.base=fixture(self.root/'base')
 def tearDown(self):self.temp.cleanup()
 def config(self,family='cf3'):
  site=next(s for s in detect(self.base,possible_solvents=['ethanol'])['sites'] if s['family']==family)
  return dict(atoms=site['atoms'],axis=site['axis'],rigid_axis=[0,0,1],angle_deg=40,occupancy_start=.7,parts=[1,2],adp='ISO',basis='Synthetic fixture evidence')
 def generate(self,c):return generate(res_records(self.base/'case.res'),gemmi.cif.read_file(str(self.base/'case.cif')).sole_block(),c)
 def plan(self,c):return dict(name='trial',kind='diagnostic_refinement',reason='synthetic test',evidence='artificial coordinates',common_disorder=c)
 def test_all_requested_motifs_detected(self):
  for family in ['cf3','tert_butyl','alkyl_chain','solvent']:
   with self.subTest(family=family):
    self.base=fixture(self.root/family,family,hydrogens=family=='alkyl_chain')
    sites=detect(self.base,possible_solvents=['ethanol'])['sites'];self.assertTrue(any(x['family']==family and x['status']=='screenable' for x in sites))
 def test_unknown_solvent_not_treated_as_confirmed(self):
  self.base=fixture(self.root/'ethanol','solvent');s=next(x for x in detect(self.base)['sites'] if x['family']=='solvent')
  self.assertEqual(s['status'],'needs_review');self.assertIn('solvent_identity_not_supplied:ethanol',s['review_reasons'])
 def test_solvent_names_normalized_without_AI(self):
  self.assertEqual(normalize_solvents(['乙醇','EtOH','THF','二氯甲烷']),{'ethanol','thf','dichloromethane'})
  with self.assertRaises(ValueError):normalize_solvents(['未知混合溶剂'])
 def test_tampered_prepared_baseline_stops_before_native_work(self):
  from unittest.mock import patch
  script=Path(__file__);job={'software':{'shelxl':str(script),'platon':str(script)},'baseline':str(self.base),'baseline_sha256':{'case.res':'wrong'},'implementation_sha256':{}}
  path=self.root/'plan.json';path.write_text(json.dumps(job))
  with patch('candidate_trials.run_plan') as native:
   with self.assertRaisesRegex(ValueError,'baseline changed'):run_prepared(path)
   native.assert_not_called()
 def test_encoded_fixed_coordinate_is_not_unfixed(self):
  p=res_records(self.base/'case.res');b=gemmi.cif.read_file(str(self.base/'case.cif')).sole_block();c=self.config()
  next(a for a in p['atoms'] if a['label']=='F1')['row'][2]='10.25'
  with self.assertRaisesRegex(ValueError,'Encoded/fixed'):generate(p,b,c)
 def test_PART_sof_override_or_partial_CIF_is_rejected(self):
  p=res_records(self.base/'case.res');b=gemmi.cif.read_file(str(self.base/'case.cif')).sole_block();c=self.config()
  b.find_values('_atom_site_occupancy')[2]='0.5'
  with self.assertRaisesRegex(ValueError,'physical occupancy'):generate(p,b,c)
 def test_axis_anchor_special_site_is_rejected(self):
  p=res_records(self.base/'case.res');b=gemmi.cif.read_file(str(self.base/'case.cif')).sole_block();c=self.config()
  a=next(a for a in p['atoms'] if a['label']=='C1');a['xyz']=[0,0,0]
  with self.assertRaises(ValueError):generate(p,b,c)
 def test_overlap_pairing_guard_is_not_bypassed(self):
  from unittest.mock import patch
  with patch('crystal_runtime.paired_bundle',side_effect=ValueError('UNIT/orbit accounting requires specialist review')):
   result=pairing_review(self.root);self.assertEqual(result['status'],'needs_specialist_review');self.assertFalse(result['scientific_acceptance'])
 def test_file_pairing_success_does_not_accept_science(self):
  from unittest.mock import patch
  with patch('crystal_runtime.paired_bundle',return_value={'gate':{'status':'needs_review'}}):
   result=pairing_review(self.root);self.assertEqual(result['status'],'file_pairing_passed');self.assertFalse(result['scientific_acceptance'])
 def test_catalog_graphs_are_distinct(self):
  for name,t in load_catalog().items():
   heavy={str(i):{'element':el} for i,el in enumerate(t['elements'])};graph={k:set() for k in heavy}
   for i,j in t['bonds']:graph[str(i)].add(str(j));graph[str(j)].add(str(i))
   self.assertTrue(matches_template(set(heavy),heavy,graph,t),name)
 def test_no_Q_peaks_no_disorder_trial(self):
  s=detect(self.base)['sites'][0];self.assertEqual(screen_poses(self.base,s),[])
 def add_peaks(self):
  c=self.config();p=res_records(self.base/'case.res');b=gemmi.cif.read_file(str(self.base/'case.cif')).sole_block();cell,amap,fn=positions(p,b,c)
  with (self.base/'case.res').open('a') as f:
   for i,k in enumerate(c['atoms']):
    v=cell.fractionalize(gemmi.Position(*fn(amap[k],True)));f.write(f'Q{i+1} 1 {v.x:.7f} {v.y:.7f} {v.z:.7f} 11 .05 1.2\n')
 def test_Q_support_generates_distinct_alternates(self):
  self.add_peaks();poses=screen_poses(self.base,detect(self.base)['sites'][0]);self.assertGreater(len(poses),0)
  self.assertTrue(all(len(p['peak_support'])>=2 for p in poses));self.assertLessEqual(len(poses),2)
 def test_one_peak_cannot_support_multiple_atoms(self):
  self.add_peaks();text=(self.base/'case.res').read_text();(self.base/'case.res').write_text(text[:text.index('Q2')])
  self.assertEqual(screen_poses(self.base,detect(self.base)['sites'][0]),[])
 def test_complementary_occupancy_and_UNIT_preserved(self):
  source=(self.base/'case.res').read_text();text,edits=build(self.base,self.plan(self.config()),self.root)
  p=self.root/'trial.res';p.write_text(text);a=audit(p,gemmi)
  self.assertFalse(a['unit_discrepancies']);self.assertEqual(controls(source,IMMUTABLE),controls(text,IMMUTABLE))
  occ=[x['inferred_cif_occupancy'] for x in a['atoms'] if x['element']=='F']
  for a,b in zip(sorted(occ),[.3,.3,.3,.7,.7,.7]):self.assertAlmostEqual(a,b)
 def test_chain_H_follow_parents_and_population(self):
  self.base=fixture(self.root/'chain','alkyl_chain',True);text,edits=build(self.base,self.plan(self.config('alkyl_chain')),self.root)
  out=self.root/'H.res';out.write_text(text);p=res_records(out);groups,unsupported=h_groups(p);self.assertFalse(unsupported)
  for a in p['atoms']:
   for h in groups[a['label'].upper()]:self.assertEqual((a['part'],a['encoded_sof']),(h['part'],h['encoded_sof']))
  a=audit(out,gemmi);self.assertFalse(a['unit_discrepancies']);self.assertTrue(any(r[0]=='EXYZ' for r in p['rows']))
  for i,r in enumerate(p['rows']):
   if r[0]=='AFIX' and r[1]!='0':self.assertNotEqual(p['rows'][i+1][0],'AFIX','No empty AFIX groups after selected H removal')
 def test_chain_without_hybridization_evidence_is_held(self):
  self.base=fixture(self.root/'chain','alkyl_chain');sites=detect(self.base)['sites']
  self.assertTrue(all(x['status']=='needs_review' for x in sites if x['family']=='alkyl_chain'))
 def test_geometry_is_rigid_and_HKL_controls_immutable(self):
  c=self.config();p=res_records(self.base/'case.res');b=gemmi.cif.read_file(str(self.base/'case.cif')).sole_block();cell,amap,fn=positions(p,b,c)
  for k in c['atoms']:
   for j in c['atoms']:
    d=lambda alt:math.dist(fn(amap[k],alt),fn(amap[j],alt))
    self.assertAlmostEqual(d(False),d(True),places=10)
 def test_ANI_and_ISO_use_different_ADP_instructions(self):
  c=self.config();iso=self.generate(c);c['adp']='ANI';ani=self.generate(c)
  self.assertFalse(any(r[0]=='ANIS' for r in iso['rows']));self.assertTrue(any(r[0]=='RIGU' for r in ani['rows']))
 def test_special_position_rejected(self):
  text=(self.base/'case.res').read_text();lines=text.splitlines();lines=[('F1 2 0 0 0 11 .04' if s.startswith('F1 ') else s) for s in lines];(self.base/'case.res').write_text('\n'.join(lines)+'\n')
  with self.assertRaisesRegex(ValueError,'Special position'):self.generate(self.config())
 def test_existing_PART_and_partial_population_rejected(self):
  c=self.config();p=res_records(self.base/'case.res');b=gemmi.cif.read_file(str(self.base/'case.cif')).sole_block()
  for attr,val in [('part',1),('encoded_sof',.5),('residue','1'),('afix',66)]:
   with self.subTest(attr=attr):
    q=copy.deepcopy(p);next(a for a in q['atoms'] if a['label']=='F1')[attr]=val
    with self.assertRaises(ValueError):generate(q,b,c)
 def test_bad_population_nonfinite_pose_or_part_rejected(self):
  for key,value in [('occupancy_start',0),('occupancy_start',float('nan')),('angle_deg',float('nan')),('translation_A',[float('inf'),0,0]),('parts',[1,1]),('adp','bad')]:
   with self.subTest(key=key,value=value):
    c=self.config();c[key]=value
    with self.assertRaises(ValueError):self.generate(c)
 def test_existing_restraint_reference_requires_mapping_review(self):
  p=self.base/'case.res';p.write_text(p.read_text().replace('HKLF 4','DFIX 1.3 C2 F1\nHKLF 4'))
  with self.assertRaisesRegex(ValueError,'reference split targets'):build(self.base,self.plan(self.config()),self.root)
 def test_long_labels_allocate_unique_safe_names(self):
  p=res_records(self.base/'case.res');b=gemmi.cif.read_file(str(self.base/'case.cif')).sole_block();c=self.config()
  p['atoms'][2]['label']='F123';c['atoms'][0]='F123'
  col=b.find_values('_atom_site_label');col[2]='F123'
  result=generate(p,b,c);names=[v for row in result['mapping'].values() for v in row.values()]
  self.assertTrue(all(len(v)<=4 for v in names));self.assertEqual(len(names),len(set(names)))
 def test_source_stays_byte_identical_after_build(self):
  old={p.name:p.read_bytes() for p in self.base.iterdir()};build(self.base,self.plan(self.config()),self.root)
  self.assertEqual(old,{p.name:p.read_bytes() for p in self.base.iterdir()})

if __name__=='__main__':unittest.main(verbosity=2)
