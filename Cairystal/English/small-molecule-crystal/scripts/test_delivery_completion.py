"""Completion/fallback contracts with synthetic files; no external upload."""
import argparse,contextlib,io,json,sys,tempfile,unittest,zipfile
from pathlib import Path
from unittest.mock import patch
from types import SimpleNamespace
import validation_route as vr
import delivery_contract as dc
import complete_candidate as cc
from crystal_runtime import sha,write_json
from routine_finish import report_alert_policy

class CompletionContracts(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup);self.p=Path(self.tmp.name)
 def local_fixture(self,message='Cannot open check.def - file not found'):
  f=self.p/'frozen';f.mkdir();e=self.p/'platon.exe';e.write_bytes(b'synthetic exe')
  for ext in ['cif','fcf']:(f/f'model.{ext}').write_text('data_fixture')
  def fail(exe,source,target,*args):
   Path(target).mkdir();(Path(target)/'platon.out').write_text(message);raise ValueError('Local validation incomplete')
  with patch('crystal_runtime.local_validation',side_effect=fail):r=vr.validate_local(e,f,self.p/'local','model')
  return f,e,r
 def complete_fixture(self):
  d=self.p/'delivery';d.mkdir();f=self.p/'frozen';f.mkdir();o=self.p/'official';o.mkdir();q=self.p/'qa';q.mkdir()
  for ext in ['cif','res','hkl','fcf','lst']:(d/f'model.{ext}').write_text('synthetic fixture')
  for ext in ['cif','res','hkl','fcf','lst']:(f/f'model.{ext}').write_bytes((d/f'model.{ext}').read_bytes())
  for folder in [d,o]:(folder/'IUCr_checkCIF.pdf').write_bytes(b'synthetic pdf stand-in')
  for name in ['晶体学报表_中文.docx','Crystallographic_Report_EN.docx']:
   with zipfile.ZipFile(d/name,'w') as z:z.writestr('word/document.xml','<document>synthetic</document>')
  write_json(q/'report_build.json',{'same_numeric_tables':True,'cif_sha256':sha(d/'model.cif'),'outputs':{lang:{'sha256':sha(d/name),'data_sha256':'synthetic matched table hash'} for lang,name in [('zh','晶体学报表_中文.docx'),('en','Crystallographic_Report_EN.docx')]}})
  return d
 def test_cif_only_not_complete(self):
  d=self.p/'delivery';d.mkdir();(d/'model.cif').write_text('data_x')
  r=dc.audit(self.p);self.assertEqual(r['status'],'incomplete');self.assertIn('IUCr_checkCIF.pdf',r['missing_artifacts'])
 def test_each_required_report_is_mandatory(self):
  d=self.complete_fixture()
  for n in ['IUCr_checkCIF.pdf','晶体学报表_中文.docx','Crystallographic_Report_EN.docx']:
   old=(d/n).read_bytes();(d/n).write_bytes(b'');r=dc.audit(self.p);self.assertEqual(r['status'],'incomplete');self.assertIn(n,r['missing_artifacts']);(d/n).write_bytes(old)
 def test_exact_report_verification_failure_stops(self):
  self.complete_fixture()
  with patch('iucr_validation.validate_saved',side_effect=ValueError('CIF hash differs')):
   r=dc.audit(self.p);self.assertEqual(r['status'],'incomplete');self.assertIn('CIF hash differs',r['verification_issues'])
 def test_completed_files_do_not_assert_scientific_acceptance(self):
  self.complete_fixture()
  with patch('iucr_validation.validate_saved',return_value=({},{'counts':{'A':1,'B':2}})),patch('squeeze_bundle.companion_fab',return_value=None):
   r=dc.require(self.p);self.assertEqual(r['status'],'artifacts_complete');self.assertEqual(r['official_counts']['A'],1);self.assertEqual(r['scientific_acceptance'],'not_established_by_file_completion')
 def test_corrupt_word_rejected(self):
  d=self.complete_fixture();(d/'晶体学报表_中文.docx').write_text('not docx')
  with patch('iucr_validation.validate_saved',return_value=({},{'counts':{}})):self.assertEqual(dc.audit(self.p)['status'],'incomplete')
 def test_delivered_cif_change_rejected(self):
  d=self.complete_fixture();(d/'model.cif').write_text('changed')
  with patch('iucr_validation.validate_saved',return_value=({},{'counts':{}})):self.assertIn('Delivered CIF differs from frozen candidate',dc.audit(self.p)['verification_issues'])
 def test_missing_local_rules_is_unknown_not_zero(self):
  _,_,r=self.local_fixture();self.assertFalse(r['available']);self.assertIsNone(r['alerts']);self.assertEqual(len(r['evidence']),1)
 def test_arbitrary_local_failure_does_not_fallback(self):
  with self.assertRaises(ValueError):self.local_fixture('Malformed report with inconsistent counts')
 def test_successful_log_mention_is_not_failure(self):
  with self.assertRaises(ValueError):self.local_fixture('check.def opened successfully')
 def test_missing_rule_cache_avoids_second_local_run(self):
  f,e,_=self.local_fixture()
  with patch('crystal_runtime.local_validation') as native:
   r=vr.reuse_local(self.p/'local',f,self.p/'reused','model',e);native.assert_not_called();self.assertFalse(r['available']);self.assertTrue(r['cache_hit'])
 def test_changed_unavailable_log_cannot_be_reused(self):
  f,e,_=self.local_fixture();(self.p/'local/platon.out').write_text('changed')
  with self.assertRaises(ValueError):vr.reuse_local(self.p/'local',f,self.p/'bad','model',e)
 def test_changed_input_cannot_reuse_unavailability(self):
  f,e,_=self.local_fixture();(f/'model.cif').write_text('changed')
  with self.assertRaises(ValueError):vr.reuse_local(self.p/'local',f,self.p/'bad','model',e)
 def test_ab_report_policy_preserves_every_instance(self):
  ab=[{'code':'234','level':'B','text':'C1'},{'code':'234','level':'B','text':'C2'}];local={'alerts':{'alerts':ab}}
  self.assertEqual(report_alert_policy(local,True),(ab,False));self.assertEqual(report_alert_policy(local,False),(ab,True))
 def test_965_still_requires_review(self):
  g={'code':'965','level':'G','text':'density'};self.assertEqual(report_alert_policy({'alerts':{'alerts':[g]}},True),([g],False))
 def test_limits_idempotent_and_bilingual(self):
  notes={};vr.append_local_limit(notes,{'available':False});vr.append_local_limit(notes,{'available':False});vr.mark_provisional(notes,[{'level':'B'}]);vr.mark_provisional(notes,[{'level':'B'}])
  self.assertEqual(notes['zh']['limitations'].count('check.def'),1);self.assertEqual(notes['en']['limitations'].count('diagnostic candidate'),1)
 def test_source_directory_is_not_used_for_output(self):
  source=self.p/'source';source.mkdir()
  with self.assertRaises(ValueError):cc.run(SimpleNamespace(input=str(source),output=str(source/'bad')))
  self.assertFalse((source/'bad').exists())
 def test_missing_review_stops_before_native_or_network(self):
  source=self.p/'source';source.mkdir();profile=self.p/'p.json';write_json(profile,{});review=self.p/'r.json';write_json(review,{'basis':'not reviewed'})
  a=SimpleNamespace(input=str(source),output=str(self.p/'run'),profile=str(profile),review=str(review),timeout=10,max_weight_updates=1)
  with patch.object(cc,'verify_profile',return_value={}),patch('run_crystal_stage.run') as native,patch('iucr_validation.validate') as network:
   r=cc.run(a);self.assertEqual(r['status'],'incomplete');native.assert_not_called();network.assert_not_called()
 def test_pipeline_default_and_explicit_local_only(self):
  import crystal_pipeline as cp
  # Inspect parsed dispatch arguments without loading or writing a job.
  for flag,expected in [([],True),(['--local-only'],False)]:
   seen={}
   original=argparse.ArgumentParser.parse_args
   def capture(parser,*args,**kwargs):
    a=original(parser,*args,**kwargs);seen['deliver']=a.deliver;raise RuntimeError('arguments captured')
   with patch.object(sys,'argv',['crystal_pipeline.py','finish','--run','fixture','--source','candidate','--review','r.json',*flag]),patch.object(argparse.ArgumentParser,'parse_args',capture):
    with self.assertRaisesRegex(RuntimeError,'arguments captured'):cp.main()
   self.assertEqual(seen['deliver'],expected)

if __name__=='__main__':unittest.main()
