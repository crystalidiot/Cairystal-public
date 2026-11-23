import unittest,tempfile,subprocess,sys,json
from pathlib import Path
from refinement_gate import assess

class GateTests(unittest.TestCase):
    def log(self):
        return 'Mean shift/esd = 0.000 Maximum = 0.001\nwR2 = 0.1, GooF = S = 1.0 for all data\nR1 = 0.04 for 50 Fo > 4sig(Fo) and 0.05 for all 70 data\n0 atoms NPD\ncase finished at 12:00 Total elapsed time: 1 secs\n'
    def test_empty_outputs_even_with_finish_banner_fail(self):
        with tempfile.TemporaryDirectory() as temp:
            folder=Path(temp)
            (folder/'case.res').write_text('')
            (folder/'case.lst').write_text('INPUT INSTRUCTION IS LONGER THAN 80 CHARACTERS\ncase finished at 12:00 Total elapsed time: 0 secs')
            result=assess(folder,'case')
            self.assertFalse(result['execution_complete'])
    def test_missing_required_instruction_does_not_report_ready(self):
        with tempfile.TemporaryDirectory() as temp:
            folder=Path(temp)
            (folder/'case.ins').write_text('TITL incomplete\nHKLF 4\nEND\n',encoding='ascii')
            (folder/'case.hkl').write_text('   1   1   1  100.00   10.00\n',encoding='ascii')
            proc=subprocess.run([sys.executable,str(Path(__file__).with_name('inspect_case.py')),str(folder),'--json'],capture_output=True,text=True,encoding='utf8')
            self.assertEqual(proc.returncode,1)
            self.assertFalse(json.loads(proc.stdout)['ready'])
    def test_converged_example_still_is_not_correctness_certificate(self):
        with tempfile.TemporaryDirectory() as temp:
            folder=Path(temp)
            text='Mean shift/esd = 0.000 Maximum = 0.001\nwR2 = 0.1, GooF = S = 1.0 for all data\nR1 = 0.04 for 50 Fo > 4sig(Fo) and 0.05 for all 70 data\n0 atoms NPD\ncase finished at 12:00 Total elapsed time: 1 secs\n'
            (folder/'case.lst').write_text(text,encoding='ascii')
            (folder/'case.res').write_text('TITL fixture\nEND\n',encoding='ascii')
            result=assess(folder,'case')
            self.assertTrue(result['execution_complete'])
            self.assertEqual(result['status'],'numerically_converged_requires_chemical_validation')
    def test_setup_refuses_missing_instructions_before_creating_job(self):
        with tempfile.TemporaryDirectory() as temp:
            folder=Path(temp)
            (folder/'case.ins').write_text('TITL incomplete\nHKLF 4\nEND\n',encoding='ascii')
            (folder/'case.hkl').write_text('   1   1   1  100.00   10.00\n',encoding='ascii')
            target=folder/'outputs'
            proc=subprocess.run([sys.executable,'-X','utf8',str(Path(__file__).with_name('setup_job.py')),str(folder),'--output-root',str(target),'--json'],capture_output=True,text=True,encoding='utf8')
            self.assertEqual(proc.returncode,1)
            self.assertEqual(json.loads(proc.stdout)['status'],'stopped')
            self.assertFalse(target.exists())
    def test_centrosymmetric_inversion_twin_not_identifiable(self):
        with tempfile.TemporaryDirectory() as temp:
            folder=Path(temp);(folder/'case.lst').write_text(self.log())
            (folder/'case.res').write_text('LATT 1\nTWIN -1 0 0 0 -1 0 0 0 -1 2\nBASF 0.5\nEND\n')
            r=assess(folder,'case')
            self.assertTrue(any('not identifiable' in v for v in r['review_reasons']))
    def test_anis_requested_but_not_applied_is_flagged(self):
        with tempfile.TemporaryDirectory() as temp:
            folder=Path(temp);(folder/'case.lst').write_text(self.log())
            (folder/'case.res').write_text('SFAC C H\nC1 1 .1 .2 .3 11 .04\nEND\n')
            (folder/'case.ins').write_text('SFAC C H\nC1 1 .1 .2 .3 11 .04\nANIS\nHKLF 4\nEND\n')
            r=assess(folder,'case')
            self.assertEqual(r['metrics']['isotropic_nonH_atoms'],1)
            self.assertTrue(any('ANIS requested' in v for v in r['review_reasons']))
    def test_wrong_reflection_format_overrides_stale_valid_outputs(self):
        with tempfile.TemporaryDirectory() as temp:
            folder=Path(temp);(folder/'case.lst').write_text(self.log())
            (folder/'case.res').write_text('TITL older valid output\nEND\n')
            (folder/'process.log').write_text('** REFLECTION   13108  HAS WRONG FORMAT **\ncase finished at 12:00 Total elapsed time: 0 secs\n')
            r=assess(folder,'case')
            self.assertFalse(r['execution_complete'])
            self.assertTrue(any('WRONG FORMAT' in v for v in r['failures']))
    def test_no_shift_job_is_not_claimed_as_convergence(self):
        with tempfile.TemporaryDirectory() as temp:
            folder=Path(temp);(folder/'case.lst').write_text(self.log())
            (folder/'case.res').write_text('TITL covariance only\nEND\n')
            (folder/'case.ins').write_text('L.S. 1\nDAMP 0 0\nEND\n')
            result=assess(folder,'case')
            self.assertTrue(result['execution_complete'])
            self.assertEqual(result['status'],'needs_review')
            self.assertTrue(result['metrics']['no_shift_uncertainty_job'])
    def test_hklf5_fraction_checked_without_twin_card(self):
        with tempfile.TemporaryDirectory() as temp:
            folder=Path(temp);(folder/'case.lst').write_text(self.log())
            (folder/'case.res').write_text('BASF -0.15\nHKLF 5\nEND\n')
            result=assess(folder,'case')
            self.assertEqual(result['status'],'needs_review')
            self.assertTrue(any('Twin fraction outside' in s for s in result['review_reasons']))
    def test_hklf4_batch_scale_is_not_mistaken_for_twin_fraction(self):
        with tempfile.TemporaryDirectory() as temp:
            folder=Path(temp);(folder/'case.lst').write_text(self.log())
            (folder/'case.res').write_text('BASF 1.5\nHKLF 4\nEND\n')
            result=assess(folder,'case')
            self.assertNotIn('twin_BASF',result['metrics'])
            self.assertEqual(result['status'],'numerically_converged_requires_chemical_validation')

    def test_positive_xnpd_floor_does_not_certify_unconstrained_adps(self):
        for instruction in ('XNPD','xnpd 0.002 ! positive floor'):
            with self.subTest(instruction=instruction),tempfile.TemporaryDirectory() as temp:
                folder=Path(temp);(folder/'case.lst').write_text(self.log())
                (folder/'case.res').write_text(instruction+'\nEND\n')
                result=assess(folder,'case')
                self.assertTrue(result['execution_complete'])
                self.assertEqual(result['status'],'needs_review')
                self.assertTrue(any('Positive XNPD' in s for s in result['review_reasons']))

    def test_default_negative_floor_and_inactive_controls_do_not_trigger(self):
        with tempfile.TemporaryDirectory() as temp:
            folder=Path(temp);(folder/'case.lst').write_text(self.log())
            (folder/'case.res').write_text('REM XNPD\nREM BLOC -1\nXNPD -0.001\nend\nXNPD .1\nBLOC -1\n')
            result=assess(folder,'case')
            self.assertEqual(result['status'],'numerically_converged_requires_chemical_validation')
            self.assertEqual(len(result['metrics']['parameter_controls_requiring_context']),1)

    def test_block_control_in_res_survives_unrelated_later_ins(self):
        with tempfile.TemporaryDirectory() as temp:
            folder=Path(temp);(folder/'case.lst').write_text(self.log())
            (folder/'case.ins').write_text('TITL later solution attempt\nHKLF 4\nEND\n')
            (folder/'case.res').write_text('bloc -1\nEND\n')
            result=assess(folder,'case')
            self.assertEqual(result['status'],'needs_review')
            self.assertTrue(any('BLOC parameter subsets' in s for s in result['review_reasons']))

    def test_block_schedule_is_review_not_execution_failure(self):
        with tempfile.TemporaryDirectory() as temp:
            folder=Path(temp);(folder/'case.lst').write_text(self.log())
            (folder/'case.res').write_text('BLOC 1 -1 C1 > C4\nBLOC 2 -2 C3 > C6\nEND\n')
            result=assess(folder,'case')
            self.assertTrue(result['execution_complete'])
            self.assertEqual(result['status'],'needs_review')
            self.assertEqual(len(result['metrics']['parameter_controls_requiring_context']),2)

if __name__=='__main__':unittest.main()
