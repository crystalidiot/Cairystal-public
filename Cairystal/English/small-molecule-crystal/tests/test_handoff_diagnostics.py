import json,shutil,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
from handoff_diagnostics import collect

class HandoffTests(unittest.TestCase):
 def setUp(self):self.t=tempfile.TemporaryDirectory();self.root=Path(self.t.name)
 def tearDown(self):self.t.cleanup()
 def test_no_external_fallback(self):
  with self.assertRaises(ValueError):collect(self.root,{'finish_root':str(self.root.parent/'old_models')})
 def test_no_finish_returns_specific_missing(self):
  self.assertEqual(collect(self.root,{})['status'],'not_available')
 def test_incomplete_pair_does_not_calculate(self):
  p=self.root/'pipeline/finish';p.mkdir(parents=True)
  with patch('handoff_diagnostics.analyse') as a:
   self.assertEqual(collect(self.root,{'finish_root':str(p)})['status'],'not_available');a.assert_not_called()
 def test_unchanged_evidence_cache_and_tamper_detection(self):
  p=self.root/'pipeline/finish';(p/'frozen').mkdir(parents=True);(p/'local_validation').mkdir()
  for ext in ['res','cif','lst']:(p/'frozen'/('model.'+ext)).write_text(ext)
  (p/'local_validation/model.chk').write_text('test')
  dummy={'regions':[],'AB_alerts':[],'elapsed_s':.1}
  with patch('handoff_diagnostics.analyse',return_value=dummy) as a,patch('handoff_diagnostics.brief',return_value='synthetic'):
   first=collect(self.root,{'finish_root':str(p)});second=collect(self.root,{'finish_root':str(p)})
   self.assertFalse(first['cache_hit']);self.assertTrue(second['cache_hit']);self.assertEqual(a.call_count,1)
  Path(first['json']).write_text('tampered')
  with self.assertRaises(ValueError):collect(self.root,{'finish_root':str(p)})

if __name__=='__main__':unittest.main(verbosity=2)
