"""Input layout controls; these do not establish structure correctness."""
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from inspect_case import reflection_stats, input_format_blockers


def record(h, k, l, value, sigma, batch=1):
    return f"{h:4d}{k:4d}{l:4d}{value:8.2f}{sigma:8.2f}{batch:4d}\n"


class InputFormatTests(unittest.TestCase):
    def stats(self, data):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / 'case.hkl'
            path.write_text(data, encoding='ascii')
            return reflection_stats(path)

    def test_adjacent_signs_and_negative_intensity_are_valid(self):
        result = self.stats(record(-123, -456, 789, -1234.56, 789.01))
        self.assertTrue(result['standard_layout_recognized'])
        self.assertEqual(result['standard_record_count'], 1)

    def test_optional_batch_and_negative_twin_components(self):
        data = record(1, 2, 3, 45, 6, -2) + record(2, 1, 3, 45, 6, 1)
        data += record(3, 2, 1, -2, 1)[:28] + '\n'
        result = self.stats(data)
        self.assertEqual(result['standard_record_count'], 3)
        self.assertEqual(input_format_blockers({'HKLF': '5'}, result), [])

    def test_four_indices_are_not_read_as_three(self):
        # Actual layout of exp_13370, including a 000m satellite.
        result = self.stats('   2   0   0   0-4.21189 2.85924   7\n'
                            '   0   0   0   1-4.21189 2.85924   7\n')
        self.assertFalse(result['standard_layout_recognized'])
        self.assertEqual(result['format_issue_count'], 2)
        self.assertFalse(result['terminator_found'])
        self.assertIn('four_index', result['format_issue_samples'][0]['reason'])

    def test_footer_after_zero_or_blank_terminator_is_not_data(self):
        for end in ('   0   0   0\n', '\n'):
            with self.subTest(end=end):
                result = self.stats(record(1, 2, 3, 45, 6) + end + 'CELL footer\n')
                self.assertTrue(result['standard_layout_recognized'])
                self.assertTrue(result['terminator_found'])
                self.assertEqual(result['standard_record_count'], 1)

    def test_empty_or_terminator_only_is_not_a_dataset(self):
        for text in ('', '\n', '   0   0   0\n'):
            self.assertFalse(self.stats(text)['standard_layout_recognized'])

    def test_malformed_and_nonfinite_numeric_values_need_review(self):
        for text in ('not reflection data\n', record(1, 2, 3, float('nan'), 2)):
            self.assertGreater(self.stats(text)['format_issue_count'], 0)

    def test_unhandled_hklf_types_are_review_not_silent_conversion(self):
        stats = self.stats(record(1, 2, 3, 10, 1))
        for kind in ('1', '2', '6', '-4', '4.5', ''):
            self.assertTrue(input_format_blockers({'HKLF': kind}, stats))
        for kind in ('3', '4', '5'):
            self.assertEqual(input_format_blockers({'HKLF': kind}, stats), [])

    def test_inspect_and_setup_refuse_four_index_before_creating_job(self):
        with tempfile.TemporaryDirectory() as temp:
            folder = Path(temp)
            (folder / 'case.ins').write_text(
                'CELL .71073 10 11 12 90 90 90\nZERR 1 .01 .01 .01 0 0 0\n'
                'LATT -1\nSFAC C H N O\nUNIT 1 1 1 1\nHKLF 4\nEND\n')
            path = folder / 'case.hkl'
            path.write_text('   2   0   0   0-4.21189 2.85924   7\n')
            before = path.read_bytes()
            for name in ('inspect_case.py', 'setup_job.py'):
                command = [sys.executable, '-X', 'utf8', str(Path(__file__).with_name(name)), str(folder), '--json']
                if name == 'setup_job.py':
                    command += ['--output-root', str(folder / 'output')]
                result = subprocess.run(command, capture_output=True, text=True, encoding='utf8')
                self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
                payload = json.loads(result.stdout)
                if name == 'inspect_case.py':
                    self.assertFalse(payload['ready'])
                else:
                    self.assertEqual(payload['status'], 'stopped')
            self.assertFalse((folder / 'output').exists())
            self.assertEqual(before, path.read_bytes())


if __name__ == '__main__':
    unittest.main()
