"""Regression tests use artificial inputs and mocked network responses only."""
import contextlib,io,json,tempfile,unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
import gemmi
from crystal_runtime import sha,write_json
from test_delivery_automation import REPORT
import crystal_session as cs
import crystal_autorun as ar
import crystal_pipeline as cp
import iucr_validation as iv
from intake_once import export,normalized
from runtime_capabilities import inspect

P4P='CELL 8 10 15 90 95 90 1200\nCELLSD .001 .001 .001 0 .01 0\nSOURCE MO .71073\nBRAVAIS Monoclinic(b-unique) P\nSAINGL 2500 2.5 26.3 0\n'

class MetadataAndIntake(unittest.TestCase):
 def test_p4p_without_csize_does_not_invent_temperature(self):self.assertNotIn('temperature_K',cs.parse_p4p(P4P))
 def test_p4p_short_unknown_temperature(self):self.assertNotIn('temperature_K',cs.parse_p4p(P4P+'CSIZE ? ? ?\n'))
 def test_p4p_invalid_temperature_rejected(self):
  for v in ['nan','-280']:
   with self.assertRaises(ValueError):cs.parse_p4p(P4P+'CSIZE ? ? ? ? '+v+'\n')
 def test_boolean_temperature_rejected(self):
  with self.assertRaises(ValueError):normalized({'schema':1,'data_dir':'D:/sample','elements':['C'],'temperature':{'value':True,'unit':'K'}})
 def test_relative_intake_path_bound_to_submission_directory(self):
  with tempfile.TemporaryDirectory() as tmp:
   root=Path(tmp);src=root/'submission.json';write_json(src,{'schema':1,'data_dir':' input ','elements':['C']});s,o=export(src,root/'accepted')
   self.assertEqual(s['data']['data_dir'],str(root/'input'))
 def test_direct_session_rejects_unconfirmed_specimen_before_any_native_work(self):
  with tempfile.TemporaryDirectory() as tmp:
   root=Path(tmp);spec=root/'specimen.json';write_json(spec,{'confirmed':False,'provenance':'draft','cif_fields':{'_exptl_crystal_colour':'red'}})
   with patch.object(cs,'execute') as native,self.assertRaisesRegex(ValueError,'Draft'):
    cs.start(SimpleNamespace(output=str(root/'job'),elements=['C'],specimen=str(spec)))
   self.assertFalse((root/'job').exists());native.assert_not_called()
 def test_missing_fourier_dependency_does_not_disable_core(self):
  def importer(name):
   if name=='numpy':raise ImportError('unit test missing dependency')
   return SimpleNamespace(__version__='test')
  r=inspect(importer);self.assertTrue(r['features']['core_refinement']['ready']);self.assertEqual(r['features']['local_fourier_diagnostics']['missing'],['numpy'])

class FilePreservation(unittest.TestCase):
 def test_stage_retry_does_not_overwrite_prepared_input(self):
  with tempfile.TemporaryDirectory() as tmp:
   root=Path(tmp);(root/'prepared').mkdir();(root/'stages').mkdir();p=root/'prepared/once.ins';p.write_text('preserved original')
   write_json(root/'session.json',{})
   with self.assertRaises(ValueError):cs.execute(root,'once','changed','shelxl','unit test')
   self.assertEqual(p.read_text(encoding='utf-8'),'preserved original')
 def test_renaming_to_existing_atom_is_rejected(self):
  with tempfile.TemporaryDirectory() as tmp:
   root=Path(tmp);(root/'prepared').mkdir();write_json(root/'session.json',{'metadata':{}})
   model=root/'model.res';model.write_text('TITL synthetic\nCELL .71073 10 10 10 90 90 90\nLATT -1\nSFAC C\nUNIT 2\nFVAR 1\nC1 1 .1 .2 .3 11 .02\nC2 1 .4 .5 .6 11 .02\nHKLF 4\nEND\n')
   with self.assertRaisesRegex(ValueError,'collision'):cs.edit_candidate(root,model,{'rename':{'C1':'C2'}})
 def test_solvent_review_survives_pipeline_config(self):
  with tempfile.TemporaryDirectory() as tmp:
   root=Path(tmp);stage=root/'session/stages/test';stage.mkdir(parents=True);(stage/'model.res').write_text('fixture');write_json(root/'runtime_profile.json',{'renderer':'word'})
   review=root/'review.json';write_json(review,{'chemistry_and_h_reviewed':True,'basis':'fixture','solvent_accounting_review':'explicit host, solvent composition unresolved'})
   state={'prior_conversation_exposure':False,'events':[]};a=SimpleNamespace(name='finish',source='test',review=str(review),timeout=30,max_weight_updates=0,deliver=False,authorize_iucr_upload=False);seen={}
   def routine(config,*args):seen.update(json.loads(config.read_text(encoding='utf-8')));return {'status':'needs_alert_review'},None
   with patch.object(cp,'checked',return_value={}),patch('candidate_packet.factual_annotations',return_value={}),patch.object(cs,'prepare'),patch('routine_finish.finish',side_effect=routine):cp.finish(root,state,a)
   self.assertEqual(seen['review']['solvent_accounting_review'],'explicit host, solvent composition unresolved')

class OfficialRecovery(unittest.TestCase):
 def test_frozen_payload_and_download_recovery_never_reposts(self):
  with tempfile.TemporaryDirectory() as tmp:
   root=Path(tmp);cif=root/'input.cif';original=b'data_fixture\n_cell_length_a 10\n';cif.write_bytes(original);dest=root/'official';calls=[];fail=[True]
   def fetch(url,data=None,headers=None,timeout=180,**kwargs):
    calls.append((url,data))
    if url=='https://checkcif.iucr.org/':
     cif.write_bytes(b'data_changed_after_snapshot\n')
     return ''.join('<input name="'+n+'">' for n in [*iv.OPTIONS,'filecif']).encode(),url
    if data is not None:
     self.assertIn(original,data);self.assertNotIn(b'data_changed_after_snapshot',data)
     return b'<a href="https://checkcif.iucr.org/unit/checkcif.pdf">pdf</a><a href="https://checkcif.iucr.org/unit/ckf.html">fcf</a>',url
    if fail[0]:raise TimeoutError('injected download interruption')
    return (b'%PDF-SYNTHETIC-UNIT-STUB' if url.endswith('.pdf') else b'FCF-File Validation LIST4'),url
   with patch.object(iv,'fetch',side_effect=fetch),patch('pypdf.PdfReader',return_value=SimpleNamespace(pages=[SimpleNamespace(extract_text=lambda:REPORT)])):
    with self.assertRaises(TimeoutError):iv.validate(cif,dest,True)
    self.assertEqual((dest/'submitted.cif').read_bytes(),original);rec=json.loads((dest/'submission.json').read_text(encoding='utf-8'));self.assertEqual(rec['state'],'reports_download_failed')
    self.assertIn('pdf_url',rec);self.assertEqual(sum(data is not None for _,data in calls),1)
    fail[0]=False;r,parsed=iv.recover(dest)
    self.assertEqual(r['state'],'completed');self.assertEqual(parsed['counts']['B'],2);self.assertEqual(sum(data is not None for _,data in calls),1)
    count=len(calls);iv.recover(dest);self.assertEqual(count,len(calls))
 def test_changed_submission_blocks_download(self):
  with tempfile.TemporaryDirectory() as tmp:
   root=Path(tmp);(root/'submitted.cif').write_text('changed');write_json(root/'submission.json',{'schema':1,'options':iv.OPTIONS,'cif_sha256':'wrong','state':'reports_download_failed'})
   with patch.object(iv,'fetch') as f,self.assertRaisesRegex(ValueError,'hash'):iv.recover(root)
   f.assert_not_called()
 def test_uncertain_post_without_response_not_retried(self):
  with tempfile.TemporaryDirectory() as tmp:
   root=Path(tmp);cif=root/'submitted.cif';cif.write_text('data_fixture');write_json(root/'submission.json',{'schema':1,'options':iv.OPTIONS,'cif_sha256':sha(cif),'state':'failed_or_submission_outcome_unknown'})
   with patch.object(iv,'fetch') as f,self.assertRaisesRegex(ValueError,'uncertain'):iv.recover(root)
   f.assert_not_called()

if __name__=='__main__':unittest.main()
