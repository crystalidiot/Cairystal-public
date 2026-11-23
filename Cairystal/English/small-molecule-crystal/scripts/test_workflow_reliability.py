"""Synthetic regressions for independent-test workflow failures; no uploads."""
import json,tempfile,unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
import routine_finish as rf
import complete_candidate as cc
import report_autoqa as qa
from refinement_gate import assess,duplicate_atom_labels
from hydrogen_plan import generate,plan_from_decisions
from crystal_runtime import sha,write_json

RES='''CELL .71073 10 10 10 90 90 90
ZERR 1 .001 .001 .001 .01 .01 .01
LATT -1
SFAC C H
UNIT 1 0
EXTI .001
FVAR 1
C1 1 .1 .2 .3 11 .02
HKLF 4
END
'''
LOG='Mean shift/esd = 0.000 Maximum = 0.001\nwR2 = 0.1, GooF = S = 1.0 for all data\nR1 = 0.04 for 50 Fo > 4sig(Fo) and 0.05 for all 70 data\n0 atoms NPD\nx finished at 12:00 Total elapsed time: 1 secs\n'

class WeightTests(unittest.TestCase):
 def test_refined_exti_changes_value_not_model(self):
  self.assertEqual(rf.model_signature(RES),rf.model_signature(RES.replace('EXTI .001','EXTI .0011')))
 def test_added_removed_exti_still_changes_model(self):
  self.assertNotEqual(rf.model_signature(RES),rf.model_signature(RES.replace('EXTI .001\n','')))
 def test_invalid_extinction_not_accepted(self):
  for card in ['EXTI nan','EXTI -0.01','EXTI .01 .02','EXTI .01\nEXTI .02']:
   with self.subTest(card=card),self.assertRaises(ValueError):rf.model_signature(RES.replace('EXTI .001',card))
 def test_other_controls_not_relaxed(self):
  self.assertNotEqual(rf.model_signature(RES),rf.model_signature(RES.replace('HKLF 4','OMIT 1 2 3\nHKLF 4')))
  self.assertNotEqual(rf.model_signature(RES+'REM nothing'),rf.model_signature(RES.replace('EXTI .001','EXTI .001\nSIMU .01 C1')))
 def test_weight_review_records_exti_but_still_blocks_adp_motion(self):
  with tempfile.TemporaryDirectory() as td:
   p=Path(td);b=p/'before.res';a=p/'after.res';b.write_text(RES);a.write_text(RES.replace('EXTI .001','EXTI .0011'))
   gate={'execution_complete':True,'review_reasons':[],'metrics':{'unique':70,'R1_observed':.04}}
   result=rf.movement_review(b,a,gate,gate)
   self.assertEqual(result['EXTI_before'],.001);self.assertEqual(result['EXTI_after'],.0011)
   a.write_text(RES.replace('EXTI .001','EXTI .0011').replace('11 .02','11 .07'))
   with self.assertRaisesRegex(ValueError,'ADP changed materially'):rf.movement_review(b,a,gate,gate)

class LabelTests(unittest.TestCase):
 def test_duplicate_h_punctuation_not_skipped(self):
  text=RES.replace('HKLF 4','H00$ 2 .1 .2 .4 11 -.012\nh00$ 2 .2 .2 .4 11 -.012\nHKLF 4')
  self.assertEqual(len(duplicate_atom_labels(text)),1)
  with tempfile.TemporaryDirectory() as td:
   p=Path(td);(p/'x.res').write_text(text);(p/'x.lst').write_text(LOG)
   r=assess(p,'x');self.assertFalse(r['execution_complete']);self.assertIn('Duplicate atom identities',' '.join(r['failures']))
 def test_part_does_not_namespace_labels(self):
  self.assertEqual(len(duplicate_atom_labels(RES.replace('HKLF 4','PART 2\nC1 1 .2 .2 .3 21 .02\nHKLF 4'))),1)
 def test_residues_may_reuse_label_but_same_residue_may_not(self):
  text=RES.replace('C1 1','RESI 1 BEN\nC1 1').replace('HKLF 4','RESI BEN 2\nC1 1 .2 .2 .3 11 .02\nHKLF 4')
  self.assertEqual(duplicate_atom_labels(text),[])
  self.assertEqual(len(duplicate_atom_labels(text.replace('RESI BEN 2','RESI BEN 1'))),1)
 def test_comments_fragments_and_post_hklf_are_not_model_atoms(self):
  text=RES.replace('C1 1','FRAG 17\nC1 1 .2 .3 .4 11 .02\nFEND\nREM C1 1 .2 .3 .4 11 .02\nC1 1')+'C1 1 .2 .3 .4 11 .02\n'
  self.assertEqual(duplicate_atom_labels(text),[])
 def test_safely_scoped_residue_audit(self):
  with self.assertRaisesRegex(ValueError,'RESI'):duplicate_atom_labels(RES.replace('C1 1','RESI BEN\nC1 1'))
 def hydrogen(self,label):
  graph={'atoms':[{'id':'c','element':'C','formal_charge':0,'hydrogens':2},{'id':'a','element':'O','formal_charge':-1,'hydrogens':0},{'id':'b','element':'O','formal_charge':-1,'hydrogens':0}],'bonds':[['c','a',1],['c','b',1]]}
  atoms=[dict(label=l,element=e,part=0,residue='0',inferred_cif_occupancy=1,geometric_site_multiplicity=1,general_multiplicity=1) for l,e in [(label,'C'),('O1','O'),('O2','O')]]
  return generate(graph,{'c':label,'a':'O1','b':'O2'},atoms,{label:{'O1','O2'},'O1':{label},'O2':{label}})
 def test_four_character_multi_h_parent_stops_before_native(self):
  r=self.hydrogen('C100');self.assertEqual(r['status'],'needs_review');self.assertIn('H-label collisions',r['findings'][0]['reason'])
  with self.assertRaises(ValueError):plan_from_decisions(r)
 def test_short_parent_keeps_methylene_rule(self):
  r=self.hydrogen('C12');self.assertEqual(r['status'],'ready_for_refinement');self.assertIn('HFIX 23 C12',r['commands'])

class CheckpointTests(unittest.TestCase):
 def test_local_checkpoint_is_success_of_requested_stage_not_full_delivery(self):
  r=cc.pending_delivery({'status':'ready_for_official_delivery'},Path('new/finish'),True)
  self.assertEqual(r['status'],'local_complete_waiting_delivery');self.assertFalse(r['full_delivery_complete'])
  self.assertEqual(cc.exit_status(r,True),0);self.assertEqual(cc.exit_status(r,False),2)
  self.assertNotIn('--authorize-iucr-upload',r['resume_arguments'])
 def test_expected_authorization_checkpoint_is_not_execution_failure(self):
  r=cc.pending_delivery({'status':'official_upload_not_authorized'},Path('new/finish'),False)
  self.assertEqual(r['status'],'awaiting_upload_authorization');self.assertEqual(cc.exit_status(r),2)
 def test_local_scientific_gate_still_stops(self):
  r=cc.pending_delivery({'status':'needs_alert_review','phase':'local'},Path('new/finish'),True)
  self.assertEqual(r['status'],'incomplete');self.assertEqual(cc.exit_status(r,True),2)
 def test_actual_failure_still_reports_reason(self):
  r=cc.pending_delivery({'status':'failed','phase':'native','failure':'native failure'},Path('new/finish'),True)
  self.assertEqual(r['reason'],'native failure');self.assertEqual(r['blocked_stage'],'native')

class ReportStemTests(unittest.TestCase):
 def fixture(self,p,stem):
  for folder in ['qa','frozen','delivery']:(p/folder).mkdir()
  (p/'frozen'/f'{stem}.cif').write_text('data_synthetic\n')
  record={'official':{'counts':dict.fromkeys('ABCG',0),'cif_sha256':sha(p/'frozen'/f'{stem}.cif')},'delivery_seal':{}}
  record['stem']=stem;write_json(p/'result.json',record)
  for lang in ['zh','en']:(p/f'{lang}.pdf').write_bytes(b'fixture')
  write_json(p/'qa/render_manifest.json',{'jobs':[{'language':l,'pages':[],'pdf':str(p/f'{l}.pdf'),'pdf_sha256':sha(p/f'{l}.pdf'),'docx':str(p/f'{l}.docx')} for l in ['zh','en']]})
  write_json(p/'qa/report_build.json',{'same_numeric_tables':True})
 def run_qa(self,p):
  with patch.object(qa,'check_document',return_value={'status':'automatic_checks_passed'}),patch('pypdf.PdfReader',return_value=SimpleNamespace(pages=[])),patch('iucr_validation.parse_official_text',return_value={'counts':dict.fromkeys('ABCG',0)}):
   return qa.run(p,p/'result_qa.json')
 def test_custom_basename_works(self):
  with tempfile.TemporaryDirectory() as td:
   p=Path(td);self.fixture(p,'sample_42');self.assertEqual(self.run_qa(p)['status'],'automatic_checks_passed')
 def test_custom_basename_still_checks_exact_cif_hash(self):
  with tempfile.TemporaryDirectory() as td:
   p=Path(td);self.fixture(p,'sample_42');(p/'frozen/sample_42.cif').write_text('changed')
   self.assertIn('Official result is not for the frozen CIF',self.run_qa(p)['findings'])
 def test_legacy_model_default_is_supported(self):
  with tempfile.TemporaryDirectory() as td:
   p=Path(td);self.fixture(p,'model');r=json.loads((p/'result.json').read_text());del r['stem'];write_json(p/'result.json',r)
   self.assertEqual(self.run_qa(p)['status'],'automatic_checks_passed')
 def test_path_escape_in_stem_rejected(self):
  with tempfile.TemporaryDirectory() as td:
   p=Path(td);self.fixture(p,'model');r=json.loads((p/'result.json').read_text());r['stem']='../answer';write_json(p/'result.json',r)
   with self.assertRaisesRegex(ValueError,'ASCII basename'):self.run_qa(p)

if __name__=='__main__':unittest.main()
