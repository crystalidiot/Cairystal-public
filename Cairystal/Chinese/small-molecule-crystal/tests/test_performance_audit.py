import json,math,tempfile,unittest
from pathlib import Path
from performance_audit import summarize,inspect_run
from unittest.mock import patch


class PerformanceAudit(unittest.TestCase):
    def test_unknown_is_not_zero(self):
        r=summarize({'unknown':None,'known':2.},3.)
        self.assertEqual(r['unknown_stages'],['unknown']);self.assertEqual(r['unattributed_wall_seconds'],1.)
        self.assertIsNone(r['token_count'])

    def test_empty_zero_and_invalid(self):
        self.assertEqual(summarize({})['stages'],[])
        self.assertIsNone(summarize({'x':0})['stages'][0]['percent_of_recorded_stages'])
        for bad in [-1,float('nan'),float('inf'),True,'3']:
            with self.assertRaises(ValueError):summarize({'x':bad})
            with self.assertRaises(ValueError):summarize({},bad)

    def test_stage_percent_not_wall_percent(self):
        r=summarize({'rendering':3,'official_validation':7},20)
        self.assertEqual(r['stages'][0]['percent_of_recorded_stages'],70)
        self.assertEqual(r['unattributed_wall_seconds'],10)
        self.assertEqual(len(r['next_checks']),2)

    def test_overlap_not_hidden(self):
        r=summarize({'a':7,'b':7},10)
        self.assertTrue(r['stage_sum_exceeds_wall']);self.assertIsNone(r['unattributed_wall_seconds'])

    def test_old_record_no_fabricated_detail(self):
        with tempfile.TemporaryDirectory() as td:
            p=Path(td);(p/'result.json').write_text(json.dumps({'timings_s':{'rendering':37},'automated_elapsed_s':90}))
            r=inspect_run(p)
            self.assertIsNone(r['nested_details']['rendering']);self.assertIsNone(r['report_qa_separate'])
            self.assertEqual(set(r['source_hashes']),{'result.json'})

    def test_nested_details_do_not_double_count(self):
        with tempfile.TemporaryDirectory() as td:
            p=Path(td);(p/'qa').mkdir();(p/'official').mkdir()
            (p/'result.json').write_text(json.dumps({'timings_s':{'rendering':10,'official_validation':30},'automated_elapsed_s':45}))
            (p/'qa/render_manifest.json').write_text(json.dumps({'timings_s':{'export':8,'raster':2},'elapsed_s':10}))
            (p/'official/submission.json').write_text(json.dumps({'timings_s':{'post':26},'report_get_attempts':[{'kind':'pdf','elapsed_s':2}]}))
            (p/'automatic_qa.json').write_text(json.dumps({'elapsed_s':5,'status':'needs_review'}))
            r=inspect_run(p);self.assertEqual(r['recorded_stage_seconds'],40)
            self.assertEqual(r['report_qa_separate']['elapsed_s'],5)
            self.assertEqual(r['nested_details']['rendering']['timings_s']['export'],8)

    def test_does_not_search_other_directories(self):
        with tempfile.TemporaryDirectory() as td:
            p=Path(td);(p/'result.json').write_text('{}')
            with self.assertRaisesRegex(ValueError,'no recursive search'):inspect_run(p)

    def test_official_failed_request_is_timed_once(self):
        import iucr_validation as iv
        rec={}
        with patch.object(iv,'fetch',side_effect=TimeoutError('outcome unknown')) as request,patch.object(iv.time,'perf_counter',side_effect=[10.,12.5]):
            with self.assertRaises(TimeoutError):iv.measured_fetch(rec,'post','https://checkcif.iucr.org/')
        self.assertEqual(request.call_count,1);self.assertEqual(rec['timings_s']['post'],2.5)

    def test_official_successful_request_preserves_bytes(self):
        import iucr_validation as iv
        rec={};value=(b'%PDF unchanged','https://checkcif.iucr.org/test/checkcif.pdf')
        with patch.object(iv,'fetch',return_value=value) as request:
            self.assertEqual(iv.measured_fetch(rec,'get',value[1]),value)
        self.assertEqual(request.call_count,1);self.assertGreaterEqual(rec['timings_s']['get'],0)


if __name__=='__main__':unittest.main()
