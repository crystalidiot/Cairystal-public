from pathlib import Path
import contextlib,io,json,os,tempfile,unittest
from unittest.mock import patch
from candidate_trials import run_plan
from trial_checkpoint import prepare_resume,hashes
from trial_summary import render
from solver_fallback import candidate,header

class ContinuationTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup);self.root=Path(self.tmp.name)
        self.base=self.root/'baseline';self.base.mkdir();(self.base/'case.hkl').write_text('synthetic test, no diffraction')
        self.job={'schema':1,'recipe':'synthetic_test_only','baseline':str(self.base),'output':str(self.root/'run'),'software':{},'trials':[{'name':n} for n in ['control','a','b']],'stop_on_control_failure':True}
        self.plan=self.root/'plan.json';self.save();(self.root/'request.json').write_text('{}')
        self.addCleanup(patch.stopall);patch('candidate_trials.analyse',return_value={}).start()
    def save(self):self.plan.write_text(json.dumps(self.job))
    def stub(self,fail=None,interrupt=None):
        def run(base,out,plan,*args):
            out.mkdir();(out/'working.ins').write_text('synthetic native stub')
            if plan['name']==interrupt:raise KeyboardInterrupt('Controlled interruption, not native failure')
            result={'name':plan['name'],'status':'failed' if plan['name']==fail else 'completed','elapsed_s':1.5,
                'AB':None if plan['name']==fail else [],'metrics':None if plan['name']==fail else {'R1_observed':.03,'wR2':.08,'GooF':1.01},
                'errors':[{'error':'<script> synthetic failure'}] if plan['name']==fail else [],'model_adopted':False}
            (out/'result.json').write_text(json.dumps(result));return result
        return run
    def initial(self,fail=None,interrupt='a'):
        with patch('candidate_trials.execute',side_effect=self.stub(fail,interrupt)),contextlib.redirect_stdout(io.StringIO()):
            if interrupt:
                with self.assertRaises(KeyboardInterrupt):run_plan(self.plan)
            else:run_plan(self.plan)
    def test_resume_preserves_completed_and_only_runs_missing(self):
        self.initial();before=hashes(self.root/'run');p=prepare_resume(self.plan,self.root/'continued')
        self.assertEqual(p['reused_trials'],['control']);self.assertEqual(p['pending_trials'],['a','b'])
        with patch('candidate_trials.execute',side_effect=self.stub()) as native,contextlib.redirect_stdout(io.StringIO()):rows=run_plan(p['plan'])
        self.assertEqual(native.call_count,2);self.assertEqual(len(rows),3);self.assertTrue(rows[0]['resume_reuse'])
        self.assertEqual(before,hashes(self.root/'run'))
        ck=json.loads((self.root/'continued/trials/checkpoint.json').read_text());self.assertEqual(ck['state'],'completed');self.assertEqual(ck['reused_trials'],1)
    def test_changed_completed_artifact_not_reused(self):
        self.initial();(self.root/'run/control/working.ins').write_text('changed')
        with self.assertRaisesRegex(ValueError,'artifacts changed'):prepare_resume(self.plan,self.root/'next')
        self.assertFalse((self.root/'next').exists())
    def test_resume_pins_resource_choice_despite_free_ram_change(self):
        from native_resources import GIB
        high={'usable_logical_processors':24,'available_ram_bytes':16*GIB}
        low={'usable_logical_processors':24,'available_ram_bytes':GIB//2}
        with patch('native_resources.hardware',return_value=high):self.initial()
        with patch('native_resources.hardware',return_value=low):
            p=prepare_resume(self.plan,self.root/'continued')
            job=json.loads(Path(p['plan']).read_text());self.assertEqual(job['shelxl_resources']['threads'],8)
            with patch('candidate_trials.execute',side_effect=self.stub()),contextlib.redirect_stdout(io.StringIO()):run_plan(p['plan'])
        self.assertEqual(json.loads((self.root/'continued/trials/checkpoint.json').read_text())['context']['native_resources']['threads'],8)
    def test_changed_explicit_thread_request_still_refused(self):
        self.job['shelxl_resources']={'threads':1,'matrix_parameters':6000};self.save();self.initial()
        self.job['shelxl_resources']['matrix_parameters']=7000;self.save()
        with self.assertRaisesRegex(ValueError,'resources or trial'):prepare_resume(self.plan,self.root/'next')
    def test_changed_baseline_refused(self):
        self.initial();(self.base/'case.hkl').write_text('changed input')
        with self.assertRaisesRegex(ValueError,'Baseline, software'):prepare_resume(self.plan,self.root/'next')
    def test_changed_hypothesis_refused(self):
        self.initial();self.job['trials'][1]['cycles']=24;self.save()
        with self.assertRaisesRegex(ValueError,'trial definitions'):prepare_resume(self.plan,self.root/'next')
    def test_changed_checkpoint_after_preparation_refused(self):
        self.initial();p=prepare_resume(self.plan,self.root/'continued');ck=self.root/'run/checkpoint.json';ck.write_text(ck.read_text()+' ')
        with patch('candidate_trials.execute') as native:
            with self.assertRaisesRegex(ValueError,'checkpoint changed'):run_plan(p['plan'])
            native.assert_not_called()
    def test_running_comparison_is_not_resumed(self):
        self.initial();(self.root/'run/running.json').write_text(json.dumps({'pid':os.getpid()}))
        with self.assertRaisesRegex(ValueError,'still running'):prepare_resume(self.plan,self.root/'next')
    def test_completed_plan_not_needlessly_rerun(self):
        self.initial(interrupt=None)
        with self.assertRaisesRegex(ValueError,'nothing to continue'):prepare_resume(self.plan,self.root/'next')
    def test_control_failure_does_not_start_other_candidates(self):
        self.initial(fail='control',interrupt=None)
        rows=json.loads((self.root/'run/results.json').read_text())['cases'];self.assertEqual(len(rows),1)
        with self.assertRaisesRegex(ValueError,'Control did not complete'):prepare_resume(self.plan,self.root/'next')
    def test_failed_trial_needs_explicit_retry_and_has_bound(self):
        self.initial(fail='control',interrupt=None);p=prepare_resume(self.plan,self.root/'again',True)
        with patch('candidate_trials.execute',side_effect=self.stub(fail='control')) as native,contextlib.redirect_stdout(io.StringIO()):run_plan(p['plan'])
        native.assert_called_once()
        with self.assertRaisesRegex(ValueError,'already retried once'):prepare_resume(p['plan'],self.root/'third',True)
    def test_same_baseline_checked_again_when_continuing(self):
        self.initial();p=prepare_resume(self.plan,self.root/'continued');(self.root/'continued/baseline/case.hkl').write_text('changed copy')
        with patch('candidate_trials.execute') as native:
            with self.assertRaises(ValueError):run_plan(p['plan'])
            native.assert_not_called()
    def test_duplicate_names_preflight_before_native_work(self):
        self.job['trials']=[{'name':'a'},{'name':'A'}];self.save()
        with patch('candidate_trials.execute') as native:
            with self.assertRaisesRegex(ValueError,'Repeated trial name'):run_plan(self.plan)
            native.assert_not_called()
    def test_legacy_without_checkpoint_not_reused(self):
        with self.assertRaisesRegex(ValueError,'No verifiable checkpoint'):prepare_resume(self.plan,self.root/'next')
    def test_summary_lists_pending_and_failure_as_unknown_not_zero_AB(self):
        self.initial(fail='control',interrupt=None);page,summary=render(self.root/'run')
        self.assertEqual(len(summary['cases']),3);self.assertIsNone(summary['cases'][0]['AB_counts']);self.assertIsNone(summary['cases'][1]['AB'])
        self.assertEqual(summary['cases'][1]['status'],'not_run');self.assertIn('&lt;script&gt;',page);self.assertNotIn('<script>',page)
    def test_summary_distinguishes_true_zero_alerts_and_reuse(self):
        self.initial();p=prepare_resume(self.plan,self.root/'continued')
        with patch('candidate_trials.execute',side_effect=self.stub()),contextlib.redirect_stdout(io.StringIO()):run_plan(p['plan'])
        page,summary=render(self.root/'continued/trials');self.assertTrue(summary['cases'][0]['reused']);self.assertEqual(summary['cases'][0]['AB'],[])
        self.assertEqual(summary['cases'][0]['AB_counts']['other']['A'],0);self.assertIn('复用，未重算',page)

class SolverCellTests(unittest.TestCase):
    TEXT='CELL .71073 8 9 10 90 98 90\nLATT -1\nSFAC C\nUNIT 1\nC1 1 .2 .3 .4 11 .04\nHKLF 4\nEND\n'
    def test_nonfinite_or_short_cell_and_wrong_wavelength_rejected(self):
        import gemmi
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp)/'case.res'
            for text in [self.TEXT.replace('8 9 10','nan 9 10'),self.TEXT.replace('90 98 90','90 98'),self.TEXT.replace('.71073','1.54184')]:
                p.write_text(text);self.assertEqual(candidate(p,gemmi.UnitCell(8,9,10,90,98,90),['C'],.71073)['status'],'unusable_output')
    def test_matching_wave_and_cell_remains_usable(self):
        import gemmi
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp)/'case.res';p.write_text(self.TEXT)
            self.assertEqual(candidate(p,gemmi.UnitCell(8,9,10,90,98,90),['C'],.71073)['status'],'candidate_requires_refinement')

if __name__=='__main__':unittest.main()
