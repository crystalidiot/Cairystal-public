"""Language changes must not change measured data, permissions or offline form safety."""
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
from intake_once import form,normalized,export
from interface_language import selected,message

ROOT=Path(__file__).resolve().parents[1]

class LanguageIntake(unittest.TestCase):
    def test_explicit_language_and_invalid_language(self):
        self.assertEqual(selected('en'),'en')
        self.assertEqual(selected('zh-CN'),'zh-CN')
        with self.assertRaises(ValueError):selected('../en')
    def test_unknown_english_observations_are_not_measurements(self):
        raw={'schema':1,'data_dir':'fixture','elements':['C','H','O'],'observations_confirmed':True}
        for v in ['unknown',' UNKNOWN ','not provided','Not known','?','不清楚','未知']:
            with self.subTest(v=v):
                value=normalized(dict(raw,colour=v,habit=v,instrument=v,chemistry=v))
                for k in ['colour','habit','instrument','chemistry']:self.assertIsNone(value[k])
    def test_forms_escape_prefill_and_keep_observations(self):
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp);known=p/'known.json'
            payload={'schema':1,'chemistry':'</script><script>alert(1)</script>','colour':'green','dimensions_mm':[.05,.052,.054],'observations_confirmed':True}
            known.write_text(json.dumps(payload),encoding='utf-8')
            for lang in ['zh-CN','en']:
                out=form(p/lang,known,lang);text=(out/'index.html').read_text('utf-8')
                self.assertIn('lang="'+lang+'"',text)
                self.assertNotIn(payload['chemistry'],text)
                from html.parser import HTMLParser
                class Prefill(HTMLParser):
                    active=False
                    value=''
                    def handle_starttag(self,tag,attrs):
                        if tag=='script' and dict(attrs).get('id')=='prefill':self.active=True
                    def handle_data(self,data):
                        if self.active:self.value+=data
                    def handle_endtag(self,tag):
                        if tag=='script':self.active=False
                parser=Prefill();parser.feed(text)
                saved=json.loads(parser.value)
                self.assertEqual({k:saved[k] for k in payload},payload)
                self.assertEqual(saved['question_plan']['known_fields']['colour'],'green')
    def test_same_observations_export_same_cif_values(self):
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp);data=p/'data';data.mkdir();fields=[]
            for lang,colour,habit in [('zh-CN','绿色','块状'),('en','green','block')]:
                f=p/(lang+'.json')
                f.write_text(json.dumps({'schema':1,'data_dir':str(data),'elements':['C','H','O'],'colour':colour,'habit':habit,'dimensions_mm':'0.05*0.052*0.054 mm','temperature':{'value':100,'unit':'K'},'observations_confirmed':True,'iucr_upload':'not_answered','squeeze':'undecided'}),encoding='utf-8')
                state,out=export(f,p/(lang+'_out'))
                self.assertEqual(state['data']['iucr_upload'],'not_answered')
                self.assertEqual(state['data']['squeeze'],'undecided')
                fields.append(json.loads((out/'specimen.json').read_text('utf-8'))['cif_fields'])
            self.assertEqual(fields[0],fields[1])
    def test_failure_notice_english_and_source_preserved(self):
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp);f=p/'bad.json';text=json.dumps({'schema':1,'data_dir':str(p),'elements':['C'],'dimensions_mm':'1 2'})
            f.write_text(text,encoding='utf-8')
            proc=subprocess.run([sys.executable,'-B',str(ROOT/'scripts/intake_once.py'),'accept','--language','en','--input',str(f),'--output',str(p/'out')],capture_output=True,text=True,encoding='utf-8')
            self.assertEqual(proc.returncode,2)
            record=json.loads(proc.stdout);self.assertIn('Enter three',record['error'])
            self.assertNotRegex(record['message']+record['error'],r'[\u4e00-\u9fff]')
            self.assertEqual(f.read_text('utf-8'),text)
    def test_selected_default_language_from_package(self):
        with patch('interface_language.Path.read_text',return_value='{"default_language":"en"}'):
            self.assertEqual(selected(),'en')
    def test_translation_preserves_unrecognized_native_error(self):
        self.assertEqual(message('Native exit 123; log=run.lst','en'),'Native exit 123; log=run.lst')
    def test_missing_language_fails_before_output_created(self):
        with tempfile.TemporaryDirectory() as tmp:
            out=Path(tmp)/'out'
            with self.assertRaises(ValueError):form(out,language='fr')
            self.assertFalse(out.exists())

if __name__=='__main__':unittest.main()
