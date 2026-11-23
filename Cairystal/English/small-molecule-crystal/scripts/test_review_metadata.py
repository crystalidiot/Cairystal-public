import json,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
from crystal_runtime import sha,write_json
import pipeline_metadata as pm

class MetadataRecoveryTests(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup);self.root=Path(self.tmp.name);self.session=self.root/'session';self.session.mkdir()
  h=self.session/'raw.hkl';h.write_text('synthetic preserved reflections')
  s=self.session/'specimen.json';write_json(s,{'confirmed':True,'basis':'Synthetic test observations, not a real specimen','cif_fields':{'_diffrn_ambient_temperature':'100'}})
  self.inputs={'hkl':{'copy':str(h),'sha256':sha(h)},'specimen':{'copy':str(s),'sha256':sha(s)}}
  write_json(self.session/'session.json',{'inputs':self.inputs});self.out=self.root/'metadata'
 def test_same_inputs_reuse_verified_ledger(self):
  ledger=pm.initialize(self.session,self.out);before=sha(ledger)
  with patch.object(pm,'collect',side_effect=AssertionError('Must not collect twice')):
   self.assertEqual(pm.initialize(self.session,self.out),ledger)
  self.assertEqual(before,sha(ledger))
 def test_changed_source_blocks_reuse(self):
  pm.initialize(self.session,self.out);Path(self.inputs['specimen']['copy']).write_text('changed')
  with self.assertRaisesRegex(ValueError,'source changed'):pm.initialize(self.session,self.out)
 def test_different_session_bindings_block_reuse(self):
  pm.initialize(self.session,self.out);self.inputs['specimen']['copy']='different.json';write_json(self.session/'session.json',{'inputs':self.inputs})
  with self.assertRaisesRegex(ValueError,'different session'):pm.initialize(self.session,self.out)
 def test_resync_keeps_previous_attempt(self):
  stage=self.session/'stages/refine';stage.mkdir(parents=True);state={'experimental_metadata_ledger':'test-ledger'};payload={'candidates':[{'stage':str(stage)}]}
  def synchronize(*args):
   out=args[-1];out.mkdir(parents=True);(out/'evidence.txt').write_text('preserved')
   return {'output':str(out/'model.cif'),'status':'synchronized','native_refinement_required':False}
  with patch.object(pm,'synchronize',side_effect=synchronize):
   a=pm.sync_summary(self.root,state,payload);b=pm.sync_summary(self.root,state,payload)
  self.assertNotEqual(a[0]['cif'],b[0]['cif']);self.assertEqual((self.root/'metadata_sync/refine/evidence.txt').read_text(),'preserved')
  self.assertEqual(len(state['metadata_sync_history']),2)
 def test_successful_summary_clears_old_error(self):
  import crystal_pipeline as cp
  summary=self.root/'summary.json';write_json(summary,{'candidates':[]});state={'context_measurements':[],'metadata_sync_error':'old source error'}
  with patch('crystal_session.compact_candidates',return_value={'candidates':[]}),patch('candidate_packet.make_packet',return_value={'candidates':[]}),patch.object(pm,'sync_summary',return_value=[]):
   cp.register_summary(self.root,state,summary)
  self.assertNotIn('metadata_sync_error',state)
  self.assertNotIn('metadata_sync_error',json.loads((self.root/'pipeline.json').read_text()))

if __name__=='__main__':unittest.main()
