from pathlib import Path
import hashlib,json,tempfile,unittest
from unittest.mock import patch
import native_resources as nr
from runtime_capabilities import environment_report
from install_preflight import default_target

def machine(cpus=24, available=16, usable=None):
    return {'logical_processors':cpus,'usable_logical_processors':cpus if usable is None else usable,
            'available_ram_bytes':None if available is None else int(available*nr.GIB),'warnings':[]}

class DecisionTests(unittest.TestCase):
    def test_low_end_and_high_end_do_not_use_all_cpus(self):
        for cpus,expected in [(1,1),(2,1),(4,3),(8,7),(24,8),(128,8)]:
            with self.subTest(cpus=cpus):self.assertEqual(nr.decision(snapshot=machine(cpus))['effective']['threads'],expected)
    def test_available_ram_not_installed_ram_limits_auto(self):
        h=dict(machine(24,.5),total_ram_bytes=128*nr.GIB)
        self.assertEqual(nr.decision(snapshot=h)['effective']['threads'],1)
    def test_memory_thresholds_and_unknown_do_not_claim_optimality(self):
        for gib,threads in [(.99,1),(1,2),(1.99,2),(2,4),(3.99,4),(4,8),(None,2)]:
            with self.subTest(gib=gib):
                r=nr.decision(snapshot=machine(24,gib));self.assertEqual(r['effective']['threads'],threads)
                self.assertFalse(r['memory_limit_enforced']);self.assertFalse(r['benchmark_optimum_claimed'])
    def test_affinity_limit_takes_priority_over_total_cpu_count(self):
        self.assertEqual(nr.decision(snapshot=machine(24,16,2))['effective']['threads'],1)
        with self.assertRaises(ValueError):nr.decision(threads=4,snapshot=machine(24,16,2))
    def test_manual_override_above_recommendation_is_recorded(self):
        r=nr.decision(threads=4,snapshot=machine(8,.5));self.assertEqual(r['effective']['threads'],4)
        self.assertEqual(r['mode'],'explicit_or_pinned');self.assertTrue(r['warnings'])
    def test_low_memory_does_not_reduce_matrix_model_capacity(self):
        self.assertEqual(nr.decision(snapshot=machine(24,.5))['effective']['matrix_parameters'],6000)
    def test_changing_free_memory_only_changes_new_auto_commands(self):
        cmd,resources,_=nr.prepare(['shelxl.exe','case'],machine())
        pinned,used,info=nr.prepare(cmd,machine(24,.5))
        self.assertEqual(cmd,pinned);self.assertEqual(resources,used);self.assertEqual(info['recommended_threads'],1)
    def test_malformed_or_negative_flags_fail_before_native_execution(self):
        for flag in ['-t-2','-t','-b1.5','-tAUTO','-b0']:
            with self.subTest(flag=flag),self.assertRaises(ValueError):nr.prepare(['shelxl.exe','case',flag],machine())
    def test_other_software_does_not_trigger_hardware_probe(self):
        with patch('native_resources.hardware',side_effect=AssertionError('must not query')):
            self.assertEqual(nr.prepare(['platon.exe','-u','case.cif']),(['platon.exe','-u','case.cif'],None,None))

class HardwareTests(unittest.TestCase):
    def test_denied_memory_and_affinity_have_honest_fallback(self):
        with patch('native_resources._memory',side_effect=PermissionError()),patch('native_resources._affinity_count',side_effect=PermissionError()),patch('native_resources.os.cpu_count',return_value=8):
            h=nr.hardware();self.assertIsNone(h['available_ram_bytes']);self.assertTrue(h['warnings'])
            self.assertEqual(nr.decision(snapshot=h)['effective']['threads'],2)
    def test_all_cpu_probes_unavailable_give_one(self):
        with patch('native_resources._affinity_count',return_value=None),patch('native_resources.os.cpu_count',return_value=None),patch('native_resources._memory',return_value=(None,None,'test')):
            h=nr.hardware();self.assertEqual(h['usable_logical_processors'],1);self.assertIsNone(h['logical_processors'])
    def test_affinity_probe_limits_usable_count(self):
        with patch('native_resources._affinity_count',return_value=2),patch('native_resources.os.cpu_count',return_value=24):
            self.assertEqual(nr.hardware()['usable_logical_processors'],2)
    def test_invalid_memory_values_remain_unknown(self):
        with patch('native_resources._memory',return_value=(-1,-2,'test')):
            h=nr.hardware();self.assertIsNone(h['available_ram_bytes']);self.assertIsNone(h['total_ram_bytes'])
    def test_disk_check_uses_existing_volume_without_creating_directory(self):
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp)/'new/deeper';r=nr.disk_info(p)
            self.assertFalse(p.exists());self.assertIsNotNone(r['free_bytes']);self.assertFalse(r['writable_verified'])
    def test_disk_permission_failure_remains_unknown(self):
        with tempfile.TemporaryDirectory() as tmp,patch('native_resources.shutil.disk_usage',side_effect=PermissionError('denied')):
            r=nr.disk_info(tmp);self.assertIsNone(r['free_bytes']);self.assertIn('error',r)
    def test_only_expected_basic_hardware_information_is_collected(self):
        h=nr.hardware();self.assertNotIn('username',h);self.assertNotIn('serial_number',h);self.assertNotIn('hostname',h)

class DoctorTests(unittest.TestCase):
    def check(self,profile):
        with patch('runtime_capabilities.inspect',return_value={'features':{},'modules':{}}),patch('native_resources.hardware',return_value=machine()):return environment_report(profile)
    def test_current_profile_file_hash_is_verified_without_running_it(self):
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp)/'shelxl.exe';p.write_bytes(b'not executable')
            r=self.check({'tools':{'shelxl':{'path':str(p),'sha256':hashlib.sha256(p.read_bytes()).hexdigest()}}})
            t=r['configured_tools']['shelxl'];self.assertTrue(t['ready']);self.assertFalse(t['execution_verified']);self.assertFalse(r['network_used'])
    def test_stale_profile_from_another_computer_is_explained(self):
        with tempfile.TemporaryDirectory() as tmp:
            r=self.check({'tools':{'shelxl':{'path':str(Path(tmp)/'absent.exe')}}})
            self.assertFalse(r['configured_tools']['shelxl']['ready']);self.assertIn('this computer',r['configured_tools']['shelxl']['error'])
    def test_changed_executable_is_not_silently_accepted(self):
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp)/'tool.exe';p.write_bytes(b'updated')
            t=self.check({'tools':{'x':{'path':str(p),'sha256':'0'*64}}})['configured_tools']['x']
            self.assertFalse(t['ready']);self.assertFalse(t['hash_matches_profile'])
    def test_missing_hash_is_unknown_not_verified(self):
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp)/'tool.exe';p.write_bytes(b'test');t=self.check({'tools':{'x':{'path':str(p)}}})['configured_tools']['x']
            self.assertIsNone(t['hash_matches_profile']);self.assertFalse(t['execution_verified'])
    def test_default_install_uses_d_when_present(self):
        with patch.object(Path,'is_dir',return_value=True):self.assertTrue(str(default_target()).replace('\\','/').startswith('D:/'))
    def test_default_install_uses_system_drive_if_d_absent(self):
        with patch.object(Path,'is_dir',return_value=False),patch.dict('os.environ',{'SystemDrive':'C:'}):self.assertTrue(str(default_target()).replace('\\','/').startswith('C:/'))

if __name__=='__main__':unittest.main()
