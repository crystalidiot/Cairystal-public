"""Exercise actual paired-file collection, prompt selection and specimen export."""
import json
from pathlib import Path
import re
import tempfile
import unittest

from crystal_runtime import sha
from experiment_metadata_state import collect
from intake_metadata import prepare, read_ledger
from intake_once import form, export

COMPLETE = """_exptl_crystal_colour green
_exptl_crystal_description block
_exptl_crystal_size_min 0.050
_exptl_crystal_size_mid 0.051
_exptl_crystal_size_max 0.052
_diffrn_ambient_temperature 100
_diffrn_measurement_device_type 'Bruker D8'
"""


class MetadataIntakeTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.sample = self.root / 'sample'
        self.sample.mkdir()
        self.hkl = self.sample / 'data.hkl'
        self.hkl.write_text('   1   0   0  100.00    2.00\n   0   0   0    0.00    0.00\n', 'ascii')

    def ledger(self, text=COMPLETE, extra=None):
        source = self.sample / 'data.pcf'
        source.write_text(text, 'utf-8')
        sources = [source]
        if extra is not None:
            second = self.sample / 'data.cif_od'
            second.write_text(extra, 'utf-8')
            sources.append(second)
        config = self.root / 'metadata_config.json'
        config.write_text(json.dumps({'hkl':str(self.hkl),'sources':[
            {'path':str(p),'kind':'cif_metadata','source_sha256':sha(p),'hkl_sha256':sha(self.hkl),
             'same_experiment_confirmed':True,'basis':'Synthetic fixture: same acquisition record'} for p in sources]}), 'utf-8')
        collect(config, self.root / 'ledger')
        self.source_hashes = {str(p):sha(p) for p in [self.hkl,*sources,config]}
        return self.root / 'ledger' / 'metadata_ledger.json'

    def data(self):
        return {'schema':1,'data_dir':str(self.sample),'elements':['C','H','O']}

    def test_coordinator_reuses_only_submitted_hkl_bound_upload_choice(self):
        from crystal_autorun import create
        from crystal_runtime import write_json
        import sys
        known = self.root/'known.json'
        write_json(known,self.data())
        html = (form(self.root/'form',known,'zh-CN',self.ledger())/'index.html').read_text('utf-8')
        answer = json.loads(re.search(r'id="prefill">(.*?)</script>',html,re.S)[1])
        profile = self.root/'profile.json'
        write_json(profile,{'python':sys.executable})
        for choice, override, tampered in [('allow',None,False),('allow',False,False),
                                             ('allow',None,True),('deny',None,False),('not_answered',None,False)]:
            with self.subTest(choice=choice,override=override,tampered=tampered):
                job = self.root/f'{choice}-{override}-{tampered}'
                job.mkdir()
                raw = job/'answer.json'
                write_json(raw,{**answer,'iucr_upload':choice})
                export(raw,job/'intake',profile)
                cfg_path = job/'intake/autorun_config.json'
                cfg = json.loads(cfg_path.read_text('utf-8'))
                cfg.pop('authorize_iucr_upload')
                cfg.pop('deliver')
                if override is not None:
                    cfg['authorize_iucr_upload'] = override
                if tampered:
                    (job/'intake/submitted_intake.json').write_text('{}')
                write_json(job/'job.json',cfg)
                _, state = create(job/'job.json',job/'run')
                self.assertEqual(state['options']['authorize_iucr_upload'],choice=='allow' and override is None and not tampered)
                self.assertEqual(state['options']['deliver'],choice!='deny')

    def test_complete_appearance_not_asked_and_no_default_authorization(self):
        data, plan, _ = prepare(self.data(), self.ledger())
        self.assertFalse(plan['ask_appearance'])
        self.assertEqual(plan['questions'], [])
        self.assertNotIn('iucr_upload', data)
        self.assertNotIn('observations_confirmed', data)

    def test_only_colour_missing(self):
        _, plan, _ = prepare(self.data(), self.ledger(COMPLETE.replace('_exptl_crystal_colour green','_exptl_crystal_colour ?')))
        self.assertEqual(plan['missing_appearance_fields'], ['colour'])
        self.assertEqual(plan['questions'], ['请只补充缺失项：颜色'])

    def test_file_conflict_not_silently_selected(self):
        _, plan, _ = prepare(self.data(), self.ledger(extra='_exptl_crystal_colour red\n'))
        self.assertEqual(list(plan['conflicts']), ['colour'])
        self.assertNotIn('colour', plan['known_fields'])

    def test_prior_user_difference_is_conflict_only(self):
        _, plan, _ = prepare(dict(self.data(),colour='red',observations_confirmed=True), self.ledger())
        self.assertEqual(list(plan['conflicts']), ['colour'])
        self.assertEqual(plan['missing_appearance_fields'], [])

    def test_equivalent_chinese_answer_not_conflict(self):
        _, plan, _ = prepare(dict(self.data(),colour='绿色',habit='块状',dimensions_mm='0.052 × 0.050 × 0.051 mm'), self.ledger())
        self.assertFalse(plan['conflicts'])

    def test_partial_dimensions_preserved(self):
        data, plan, _ = prepare(self.data(), self.ledger(COMPLETE.replace('_exptl_crystal_size_mid 0.051\n','')))
        self.assertEqual(plan['known_dimensions_mm'], {'min':.05,'max':.052})
        self.assertEqual(plan['missing_appearance_fields'], ['dimensions_mm'])
        self.assertNotIn('dimensions_mm', data)

    def test_partial_dimension_disagreement_detected(self):
        _, plan, _ = prepare(dict(self.data(),dimensions_mm=[.04,.051,.052]), self.ledger(COMPLETE.replace('_exptl_crystal_size_mid 0.051\n','')))
        self.assertIn('dimensions_mm', plan['conflicts'])

    def test_stale_source_rejected(self):
        ledger = self.ledger()
        (self.sample/'data.pcf').write_text(COMPLETE.replace('green','red'), 'utf-8')
        with self.assertRaisesRegex(ValueError, 'input changed'):
            prepare(self.data(),ledger)

    def test_different_sample_rejected(self):
        ledger = self.ledger()
        other = self.root/'other'
        other.mkdir()
        with self.assertRaisesRegex(ValueError,'different specimen'):
            read_ledger(ledger,other)

    def test_unknown_prior_answer_not_repeated(self):
        _,plan,_=prepare(dict(self.data(),colour='unknown',habit='block',dimensions_mm=[.05,.051,.052],_previous_asked_fields=['colour']))
        self.assertEqual(plan['questions'],[])

    def test_unknown_and_dot_not_measurements(self):
        _,plan,_=prepare(self.data(),self.ledger(COMPLETE.replace('green','unknown').replace('block','.')))
        self.assertEqual(plan['missing_appearance_fields'],['colour','habit'])

    def test_form_to_export_without_reasking_or_measured_checkbox(self):
        ledger=self.ledger()
        known=self.root/'known.json'
        known.write_text(json.dumps(self.data()),'utf-8')
        for lang in ['zh-CN','en']:
            out=form(self.root/lang,known,lang,ledger)
            html=(out/'index.html').read_text('utf-8')
            raw=json.loads(re.search(r'id="prefill">(.*?)</script>',html,re.S)[1])
            raw['observations_confirmed']=False
            submitted=self.root/(lang+'.json')
            submitted.write_text(json.dumps(raw),'utf-8')
            state,accepted=export(submitted,self.root/(lang+'_accepted'))
            specimen=json.loads((accepted/'specimen.json').read_text('utf-8'))
            self.assertEqual(specimen['cif_fields']['_exptl_crystal_colour'],'green')
            self.assertEqual(specimen['cif_fields']['_exptl_crystal_size_max'],.052)
            self.assertEqual(specimen['cif_fields']['_diffrn_ambient_temperature'],100)
            self.assertEqual(state['pending_questions'],[])
            self.assertIn('file_field_provenance',specimen)
        self.assertTrue(all(sha(p)==digest for p,digest in self.source_hashes.items()))

    def test_conflict_blocks_config_and_is_not_measured(self):
        raw,_,_=prepare(dict(self.data(),colour='red',observations_confirmed=True),self.ledger())
        source=self.root/'submitted.json'
        source.write_text(json.dumps(raw),'utf-8')
        state,out=export(source,self.root/'accepted')
        self.assertEqual(state['status'],'needs_input')
        self.assertFalse((out/'autorun_config.json').exists())
        self.assertNotIn('_exptl_crystal_colour',json.loads((out/'specimen.json').read_text('utf-8'))['cif_fields'])

    def test_changed_ledger_receipt_rejected(self):
        ledger=self.ledger()
        data,_,_=prepare(self.data(),ledger)
        ledger.write_text(ledger.read_text('utf-8')+'\n','utf-8')
        with self.assertRaisesRegex(ValueError,'changed since form'):
            prepare(data)


if __name__=='__main__':unittest.main()
