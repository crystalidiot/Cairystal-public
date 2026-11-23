import json,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
from crystal_runtime import sha,write_json
import squeeze_request as sr
import squeeze_workflow as sw

class SqueezeChoiceTests(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup);self.root=Path(self.tmp.name)
  self.model=self.root/'model.res';self.model.write_text('synthetic model')
  self.plan=self.root/'plan.json';write_json(self.plan,{'source':str(self.root),'host_summary':'合成工程主体；非真实晶体','solvent_challenge':'合成独立溶剂区域','review':{k:True for k in sw.REVIEW_FIELDS},'evidence':[]})
  self.target=self.root/'request'
  self.mock=patch.object(sw,'preflight',side_effect=lambda cfg:{'source_sha256':{'res':sha(self.model)},'gate':{'metrics':{'R1':.05}}});self.mock.start();self.addCleanup(self.mock.stop)
 def intake(self,choice,purpose='host_priority'):
  f=self.root/'intake.json';write_json(f,{'schema':1,'questionnaire_completed':True,'data':{'squeeze':choice,'purpose':purpose}});return f
 def prepare(self,intake=None):return sr.prepare(self.plan,self.target,intake)[0]
 def allow(self):
  self.prepare();return sr.respond(self.target,decision='allow',basis='Synthetic simulated customer choice, not a real authorization')
 def test_unknown_creates_one_unanswered_question(self):
  s=self.prepare();self.assertEqual(s['status'],'needs_customer_choice');self.assertTrue((self.target/'index.html').is_file());self.assertFalse((self.target/'authorized_plan.json').exists())
  with self.assertRaises(ValueError):self.prepare()
 def test_existing_allow_reused_without_form(self):
  s=self.prepare(self.intake('allow_if_justified'));self.assertEqual(s['status'],'ready_for_squeeze_trial');self.assertFalse((self.target/'index.html').exists())
  self.assertEqual(sr.read(self.target/'response.json')['origin'],'saved_specimen_intake');sr.verify_authorization(sr.read(self.target/'authorized_plan.json'))
 def test_existing_never_not_asked_again(self):
  s=self.prepare(self.intake('never'));self.assertEqual(s['status'],'declined_continue_explicit_model');self.assertFalse((self.target/'index.html').exists())
 def test_full_composition_goal_not_silently_replaced(self):
  s=self.prepare(self.intake('allow_if_justified','full_composition'));self.assertEqual(s['status'],'needs_model_review');self.assertFalse((self.target/'index.html').exists())
 def test_missing_review_does_not_offer_customer_question(self):
  with patch.object(sw,'preflight',side_effect=ValueError('host/solvent attribution unknown')):s=self.prepare()
  self.assertEqual(s['status'],'needs_model_review');self.assertFalse((self.target/'index.html').exists())
 def test_changed_model_after_question_blocks_approval(self):
  self.prepare();self.model.write_text('changed model')
  with self.assertRaisesRegex(ValueError,'checkpoint changed'):sr.respond(self.target,decision='allow',basis='synthetic')
 def test_answer_from_different_case_rejected(self):
  self.prepare();f=self.root/'answer.json';write_json(f,{'schema':1,'request_id':'another','decision':'allow','basis':'synthetic'})
  with self.assertRaisesRegex(ValueError,'different request'):sr.respond(self.target,answer=f)
 def test_same_answer_idempotent_and_change_preserved(self):
  self.allow();h=sha(self.target/'response.json');sr.respond(self.target,decision='allow',basis='same answer');self.assertEqual(h,sha(self.target/'response.json'))
  with self.assertRaisesRegex(ValueError,'already recorded'):sr.respond(self.target,decision='decline',basis='different answer')
 def test_defer_blocks_execution_and_saves_choice(self):
  self.prepare();s=sr.respond(self.target,decision='defer',basis='synthetic');self.assertEqual(s['status'],'deferred_no_repeated_prompt')
  with patch.object(sw,'run') as run,self.assertRaises(ValueError):sr.execute(self.target,'unused',self.root/'trial')
  run.assert_not_called()
 def test_modified_plan_after_allow_rejected(self):
  self.allow();cfg=sr.read(self.target/'authorized_plan.json');cfg['cycles']=90
  with self.assertRaisesRegex(ValueError,'plan changed'):sr.verify_authorization(cfg)
 def test_changed_intake_blocks_execution(self):
  f=self.intake('allow_if_justified');self.prepare(f);f.write_text('{}')
  with patch.object(sw,'run') as run,self.assertRaisesRegex(ValueError,'intake changed'):sr.execute(self.target,'unused',self.root/'trial')
  run.assert_not_called()
 def test_success_does_not_rerun_or_grant_upload(self):
  self.allow()
  with patch.object(sw,'run',return_value=({'status':'comparison_complete_requires_review'},self.root/'trial')) as run:
   a=sr.execute(self.target,'unused',self.root/'trial');b=sr.execute(self.target,'unused',self.root/'another')
  self.assertEqual(run.call_count,1);self.assertEqual(a,b);self.assertFalse(a['scientific_acceptance']);self.assertFalse(a['official_upload_performed'])
 def test_failed_execution_not_replayed(self):
  self.allow()
  with patch.object(sw,'run',side_effect=RuntimeError('simulated native failure')) as run:
   self.assertEqual(sr.execute(self.target,'unused',self.root/'trial')['status'],'failed');sr.execute(self.target,'unused',self.root/'again')
  self.assertEqual(run.call_count,1)
 def test_unanswered_response_is_not_consent(self):
  self.prepare()
  with self.assertRaisesRegex(ValueError,'Unknown'):sr.respond(self.target,decision=None,basis='synthetic')
 def test_current_chat_requires_basis(self):
  self.prepare()
  with self.assertRaisesRegex(ValueError,'basis'):sr.respond(self.target,decision='allow',basis=None)
 def test_saved_record_tampering_blocks(self):
  self.prepare();p=self.target/'request.json';v=sr.read(p);v['host_summary']='altered';write_json(p,v)
  with self.assertRaisesRegex(ValueError,'request changed'):sr.respond(self.target,decision='allow',basis='synthetic')

class SharedPreflightTests(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup);self.root=Path(self.tmp.name)
  self.res=self.root/'model.res';self.res.write_text('CELL .71073 10 10 10 90 90 90\nSFAC C\nUNIT 1\nHKLF 4\nEND\n')
  self.evidence=self.root/'review.txt';self.evidence.write_text('synthetic evidence')
  self.cfg={'source':str(self.root),'review':{**{k:True for k in sw.REVIEW_FIELDS},'basis':'synthetic fixture'},'evidence':[{'path':str(self.evidence),'sha256':sha(self.evidence)}]}
  p=patch.object(sw,'paired_bundle',side_effect=lambda *a:{'files':{'res':str(self.res)},'gate':{'review_reasons':[]}});p.start();self.addCleanup(p.stop)
 def test_missing_host_review_fails(self):
  self.cfg['review']['host_disorder_resolved']=False
  with self.assertRaisesRegex(ValueError,'Unresolved'):sw.preflight(self.cfg)
 def test_changed_evidence_fails(self):
  self.evidence.write_text('altered')
  with self.assertRaisesRegex(ValueError,'evidence changed'):sw.preflight(self.cfg)
 def test_twin_route_not_implicitly_supported(self):
  self.res.write_text(self.res.read_text().replace('HKLF','TWIN\nHKLF'))
  with self.assertRaisesRegex(ValueError,'Twin'):sw.preflight(self.cfg)
 def test_hkl_transform_not_implicitly_allowed(self):
  self.res.write_text(self.res.read_text().replace('HKLF 4','HKLF 4 1 1 0 0 0 1 0 0 0 1'))
  with self.assertRaisesRegex(ValueError,'HKLF'):sw.preflight(self.cfg)

if __name__=='__main__':unittest.main()
