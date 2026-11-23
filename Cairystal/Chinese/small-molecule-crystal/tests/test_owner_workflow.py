"""Exercise the customer entry point from a folder outside the package."""
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from intake_metadata import prepare
from intake_once import temperature_kelvin
from toolbox import ROOT, load_catalog


class CustomerEntryTests(unittest.TestCase):
    def setUp(self):
        scratch = tempfile.TemporaryDirectory()
        self.addCleanup(scratch.cleanup)
        self.directory = Path(scratch.name)

    def call(self, *args, stdin=None):
        return subprocess.run([sys.executable, '-B', '-X', 'utf8', str(ROOT/'cairystal.py'), *args],
                              cwd=self.directory, input=stdin, capture_output=True,
                              encoding='utf-8', timeout=20)

    def test_empty_command_and_language(self):
        response = self.call()
        self.assertEqual(response.returncode, 0, response.stderr)
        self.assertIn('Cairystal', response.stdout)
        result = json.loads(self.call('--language','en','guide','reports','--json').stdout)
        self.assertEqual(result['language'], 'en')
        self.assertFalse(result['executed'])
        self.assertEqual(result['topics'][0]['tools'][0], 'recover-checkcif')
        self.assertIn('--official-cache', result['topics'][0]['detail'])
        self.assertEqual(list(self.directory.iterdir()), [])

    def test_topic_links_and_tools(self):
        guides = json.loads((ROOT/'assets/user_guide.json').read_text('utf-8'))
        tools = {t['id'] for t in load_catalog()['tools']}
        for topic in guides.values():
            self.assertTrue(set(topic['tools']) <= tools)
            self.assertTrue(all((ROOT/ref).is_file() for ref in topic['references']))
            for language in ('zh-CN','en'):
                self.assertEqual(len(topic[language]), 3)

    def test_full_paste_from_stdin(self):
        paste = ('PLAT306_ALERT_2_B Isolated oxygen\n0 ALERT level A\n'
                 'DEMO99_ALERT_1_A Example. SHFSU_01_ALERT_3_G\nPLAT306_ALERT_2_B')
        reply = self.call('run','route-problem','--','--alert-text','-','--json', stdin=paste)
        self.assertEqual(reply.returncode, 0, reply.stderr)
        data = json.loads(reply.stdout)
        self.assertEqual([(r['test'],r['level']) for r in data['pasted_alerts']],
                         [('306','B'),('DEMO99','A'),('SHFSU01','G')])
        self.assertIn('DEMO99', data['unmapped_alerts'])
        self.assertIn('water', [r['id'] for r in data['routes']])
        self.assertFalse(data['automatic_repairs_performed'])
        self.assertFalse(data['scientific_acceptance'])
        self.assertEqual(list(self.directory.iterdir()), [])

    def test_summary_alone_is_not_an_alert_identifier(self):
        reply = self.call('run','route-problem','--','--alert-text','2 ALERT level A','--json')
        self.assertEqual(reply.returncode, 2)
        self.assertEqual(json.loads(reply.stderr)['status'], 'invalid_alert_text')

    def test_partial_and_conflicting_answers_together(self):
        verified = dict(path='paired', sha256='digest', data_dir=str(self.directory),
                        values={'colour':'green'},conflicts={},partial_sizes_mm={})
        with patch('intake_metadata.read_ledger', return_value=verified):
            _, plan, _ = prepare({'colour':'red'},'paired',language='en')
        self.assertEqual(len(plan['questions']), 2)
        self.assertIn('shape', plan['questions'][0])
        self.assertIn('colour', plan['questions'][0])
        self.assertIn('elements', plan['questions'][1])
        self.assertNotIn('colour', plan['known_fields'])

    def test_optional_temperature_through_export(self):
        raw = self.directory/'answers.json'
        raw.write_text(json.dumps({'schema':1,'data_dir':str(self.directory),'elements':['C','O'],
                                   'temperature':{'unit':'K','value':''},'iucr_upload':'deny',
                                   'observations_confirmed':True}), 'utf-8')
        output = self.directory/'accepted'
        result = self.call('run','intake-accept','--','--input',str(raw),'--output',str(output),'--language','en')
        self.assertEqual(result.returncode, 0, result.stdout)
        state = json.loads((output/'intake_state.json').read_text('utf-8'))
        self.assertIn('shape', state['question_plan']['questions'][0])
        self.assertIsNone(state['data']['temperature_K'])
        self.assertEqual(state['data']['iucr_upload'], 'deny')
        specimen = json.loads((output/'specimen.json').read_text('utf-8'))
        self.assertNotIn('_diffrn_ambient_temperature',specimen['cif_fields'])

    def test_temperature_boundaries(self):
        self.assertEqual(temperature_kelvin({'value':0,'unit':'C'}),273.15)
        self.assertIsNone(temperature_kelvin({'value':' 未知 ','unit':'K'}))
        for record in ({'value':0,'unit':'K'},{'value':float('nan')},{'value':True},{'value':3,'unit':'F'}):
            with self.assertRaises(ValueError):
                temperature_kelvin(record)

    def test_previous_unknown_survives_submission(self):
        raw = self.directory/'known.json'
        raw.write_text(json.dumps({'schema':1, 'data_dir':str(self.directory),'elements':['C'],
            'question_plan':{'answered_unknown_fields':['colour','habit','dimensions_mm']}}),'utf-8')
        output = self.directory/'new'
        result = self.call('run','intake-accept','--','--input',str(raw),'--output',str(output))
        self.assertEqual(result.returncode,0,result.stdout)
        state = json.loads((output/'intake_state.json').read_text('utf-8'))
        self.assertEqual(state['question_plan']['questions'],[])
        self.assertEqual(state['data']['iucr_upload'],'not_answered')
        self.assertFalse(state['data']['observations_confirmed'])
        self.assertEqual(json.loads((output/'specimen.json').read_text('utf-8'))['cif_fields'],{})

    def test_first_prompt_example_never_sets_measurements(self):
        data, plan, _ = prepare({},language='zh-CN')
        self.assertEqual(len(plan['questions']),2)
        self.assertIn('绿色，块状，0.050 × 0.051 × 0.052 mm',plan['questions'][0])
        self.assertNotIn('dimensions_mm', data)
        self.assertEqual(plan['known_fields'],{})
