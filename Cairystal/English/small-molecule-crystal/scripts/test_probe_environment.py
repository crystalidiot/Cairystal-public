"""Synthetic file-only tests; deliberately invalid executables must never run."""
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from probe_environment import probe


class EnvironmentProbeTests(unittest.TestCase):
    def files(self, root, *names):
        for name in names:
            (root / name).write_bytes(b'Not an executable\x00SHELXD-2013/2')

    def test_missing_directory_reports_all_selected_requirements_without_creating_it(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / 'absent'
            r = probe(root)
            self.assertFalse(r['ready'])
            self.assertEqual(set(r['missing_required']), {'shelxt.exe', 'shelxl.exe'})
            self.assertFalse(root.exists())

    def test_headless_core_does_not_require_viewer_or_local_validation(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.files(root, 'shelxt.exe', 'shelxl.exe')
            r = probe(root)
            self.assertTrue(r['ready'])
            self.assertFalse(r['profiles']['viewer']['files_ready'])
            self.assertFalse(r['profiles']['validate']['files_ready'])
            self.assertFalse(r['execution_verified'])

    def test_shelxd_alternative_is_detected_with_hash_and_version_hint(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.files(root, 'shelxd.exe', 'shelxl.exe')
            r = probe(root, 'solve_d')
            self.assertTrue(r['ready'])
            self.assertFalse(r['profiles']['solve']['files_ready'])
            d = next(t for t in r['tools'] if t['name'] == 'shelxd.exe')
            self.assertEqual(d['sha256'], hashlib.sha256((root/'shelxd.exe').read_bytes()).hexdigest().upper())
            self.assertEqual(d['version'], '2013/2')
            self.assertEqual(d['version_source'], 'embedded_string_hint')

    def test_validation_does_not_claim_core_solver_availability(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.files(root, 'platon.exe')
            r = probe(root, 'validate')
            self.assertTrue(r['ready'])
            self.assertFalse(r['profiles']['solve']['files_ready'])

    def test_stale_platon_output_is_not_used_as_binary_version(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.files(root, 'platon.exe')
            (root/'platon.out').write_text('version : 991231\nprivate old case')
            with patch.object(Path, 'read_text', side_effect=AssertionError('Must not read old log')):
                r = probe(root, 'validate')
            p = next(t for t in r['tools'] if t['name'] == 'platon.exe')
            self.assertIsNone(p['version'])

    def test_unreadable_required_file_is_reported_as_not_ready(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.files(root, 'shelxl.exe')
            with patch('probe_environment.sha256', side_effect=PermissionError('denied')):
                r = probe(root, 'refine')
            self.assertFalse(r['ready'])
            self.assertIn('shelxl.exe', r['missing_required'])
            item = next(t for t in r['tools'] if t['name'] == 'shelxl.exe')
            self.assertIn('PermissionError', item['error'])

    def test_path_hint_does_not_silently_replace_selected_directory(self):
        with tempfile.TemporaryDirectory() as tmp:
            with patch('probe_environment.shutil.which', return_value='unselected/other.exe'):
                r = probe(Path(tmp))
            self.assertFalse(r['ready'])

    def test_cli_default_and_legacy_bundle_report_different_requirements(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.files(root, 'shelxt.exe', 'shelxl.exe')
            command = [sys.executable, '-B', str(Path(__file__).with_name('probe_environment.py')),
                       '--software-dir', str(root), '--json']
            default = subprocess.run(command, capture_output=True, text=True)
            bundle = subprocess.run(command + ['--profile', 'bundle'], capture_output=True, text=True)
            self.assertEqual(default.returncode, 0)
            self.assertEqual(bundle.returncode, 1)
            self.assertEqual(set(json.loads(bundle.stdout)['missing_required']), {'olex2.exe', 'platon.exe'})


if __name__ == '__main__':
    unittest.main()
