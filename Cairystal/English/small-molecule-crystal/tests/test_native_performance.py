from pathlib import Path
import json,tempfile,unittest
from unittest.mock import patch
from native_resources import effective,configure
from platon_execution import completion_fingerprint

class ResourceTests(unittest.TestCase):
    def setUp(self):
        self.addCleanup(patch.stopall)
        patch('native_resources.hardware',return_value={'logical_processors':24,'usable_logical_processors':24,'available_ram_bytes':16*1024**3}).start()
    def test_auto_caps_at_eight_and_honours_small_cpu_counts(self):
        self.assertEqual(effective(logical_processors=24)['threads'],8)
        self.assertEqual(effective(logical_processors=3)['threads'],2)
        self.assertEqual(effective(logical_processors=1)['threads'],1)
    def test_capacity_units_and_explicit_overrides(self):
        self.assertEqual(effective(4,12000,24),{'threads':4,'matrix_parameters':12000})
    def test_invalid_knobs_rejected(self):
        for t,b in [(True,6000),(0,6000),(25,6000),(4,True),(4,2.5),(4,64),(4,999999)]:
            with self.assertRaises(ValueError):effective(t,b,24)
    def test_single_shelxl_command_is_normalized_once(self):
        with patch('native_resources.os.cpu_count',return_value=24):
            cmd,settings=configure(['shelxl.exe','case','-m0'])
            self.assertEqual(cmd,['shelxl.exe','case','-m0','-t8','-b6000'])
            self.assertEqual(configure(cmd)[0],cmd)
    def test_other_native_programs_are_not_given_shelxl_flags(self):
        for cmd in [['platon.exe','-u','case.cif'],['shelxd.exe','case'],['shelxt.exe','case']]:self.assertEqual(configure(cmd),(cmd,None))
    def test_explicit_flags_preserved(self):
        with patch('native_resources.os.cpu_count',return_value=24):
            cmd,v=configure(['shelxl.exe','case','-b12000','-t4']);self.assertEqual(v,{'threads':4,'matrix_parameters':12000});self.assertEqual(cmd[-2:],['-t4','-b12000'])
    def test_ambiguous_repeated_flags_rejected(self):
        with self.assertRaisesRegex(ValueError,'Repeated'):configure(['shelxl.exe','case','-t2','-t4'])

class CompletionEvidenceTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup);self.d=Path(self.tmp.name)
        self.log=':: CheckCIF out on :case.chk\n:: CheckFCF out on :case.ckf\n:: CheckPlots on :case.ps [ 7 Plots]\n'
        (self.d/'platon.out').write_text(self.log);(self.d/'case.chk').write_text('validated checks\n'*20);(self.d/'case.ckf').write_text('structure factor checks\n'*20)
        (self.d/'case.ps').write_text('%!PS-Adobe-2.0\n%%Pages: 7\n%%EOF\n')
    def test_full_native_notices_and_closed_plots_produce_content_proof(self):
        p=completion_fingerprint(self.d,'case');self.assertEqual(set(p),{'case.chk','case.ckf','platon.out','case.ps'})
    def test_missing_postscript_eof_is_not_fast_completion(self):
        (self.d/'case.ps').write_text('%!PS-Adobe-2.0\n%%Pages: 7\n')
        self.assertIsNone(completion_fingerprint(self.d,'case'))
    def test_mismatched_page_count_is_not_fast_completion(self):
        (self.d/'case.ps').write_text('%!PS-Adobe-2.0\n%%Pages: 6\n%%EOF\n')
        self.assertIsNone(completion_fingerprint(self.d,'case'))
    def test_missing_FCF_notice_is_not_fast_completion(self):
        (self.d/'platon.out').write_text(self.log.replace(':: CheckFCF out on :case.ckf\n',''))
        self.assertIsNone(completion_fingerprint(self.d,'case'))
    def test_equal_size_output_rewrite_changes_completion_proof(self):
        first=completion_fingerprint(self.d,'case');p=self.d/'case.ckf';size=p.stat().st_size;p.write_text(p.read_text().replace('checks','CHECKS'))
        self.assertEqual(p.stat().st_size,size);self.assertNotEqual(first,completion_fingerprint(self.d,'case'))
    def test_unknown_output_format_uses_conservative_route(self):
        (self.d/'case.ps').unlink();self.assertIsNone(completion_fingerprint(self.d,'case'))

if __name__=='__main__':unittest.main()
