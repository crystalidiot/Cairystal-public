import json,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
from routine_finish import read_weights,weights_close,weight_ins,model_signature,movement_review,factual_notes,decision_packet,carry_metadata
from local_validation_cache import reuse
from crystal_runtime import sha,write_json,records
from crystal_session import compact_candidates,edit_candidate
from parse_platon_alerts import parse

MODEL='''TITL synthetic
CELL .71073 10 10 10 90 90 90
ZERR 1 .001 .001 .001 .01 .01 .01
LATT -1
SFAC C H
UNIT 2 1
TEMP -123
L.S. 6
WGHT .05 .6
FVAR 1
C1 1 .1 .2 .3 11 .02 .02 .02 0 0 0
AFIX 13
H1 2 .15 .2 .3 11 -1.2
AFIX 0
C2 1 .25 .2 .3 11 .02
EQIV $1 -x,1-y,1-z
HTAB C1 C2_$1
HKLF 4
END
WGHT .052 .63
'''
GATE={'review_reasons':[],'execution_complete':True,'metrics':{'unique':20,'R1_observed':.05}}

class LowTokenTests(unittest.TestCase):
    def test_only_weight_cycles_output_change(self):
        value=weight_ins(MODEL,[.052,.63]);self.assertEqual(model_signature(MODEL),model_signature(value));self.assertNotIn('\nANIS',value)
        self.assertIn('LIST 4',value);self.assertIn('TEMP -123',value);self.assertEqual(read_weights(value),([.052,.63],None))
    def test_weight_numeric_stability_not_gof(self):
        self.assertTrue(weights_close([.05,.6],[.0502,.603]));self.assertFalse(weights_close([.05,.6],[.05,.7]));self.assertFalse(weights_close([.05,.6],None))
        for value in ['nan .6','-.1 .6','.1 .6 .2']:
            with self.assertRaises(ValueError):read_weights(MODEL.replace('WGHT .05 .6','WGHT '+value))
    def test_signature_detects_scientific_changes(self):
        for value in [MODEL.replace('C2 1','C2 2'),MODEL.replace('ZERR 1','ZERR 2'),MODEL.replace('AFIX 13','AFIX 3'),MODEL.replace('11 .02\n','21 .02\n'),MODEL.replace('C2 1 .25 .2 .3 11 .02','C2 1 .25 .2 .3 11 .02 .02 .02 0 0 0')]:
            self.assertNotEqual(model_signature(MODEL),model_signature(value))
    def test_weight_shift_adp_and_reflection_guards(self):
        with tempfile.TemporaryDirectory() as t:
            p=Path(t);b=p/'before.res';a=p/'after.res';b.write_text(MODEL);a.write_text(MODEL)
            self.assertEqual(movement_review(b,a,GATE,GATE)['max_cartesian_shift_A'],0)
            for value in [MODEL.replace('C2 1 .25','C2 1 .30'),MODEL.replace('C2 1 .25 .2 .3 11 .02','C2 1 .25 .2 .3 11 .06')]:
                a.write_text(value)
                with self.assertRaises(ValueError):movement_review(b,a,GATE,GATE)
            a.write_text(MODEL)
            with self.assertRaises(ValueError):movement_review(b,a,GATE,dict(GATE,metrics={'unique':19,'R1_observed':.05}))
    def test_generic_edit_preserves_iso_z_temperature_hbond(self):
        with tempfile.TemporaryDirectory() as t:
            p=Path(t);(p/'prepared').mkdir();src=p/'model.res';src.write_text(MODEL);write_json(p/'session.json',{'metadata':{'cell_su':[.001]*6}})
            text,_=edit_candidate(p,src,{'cycles':10})
            self.assertNotIn('\nANIS',text);self.assertIn('TEMP -123',text);self.assertIn('ZERR 1 .001 .001 .001 .01 .01 .01',text);self.assertIn('HTAB C1 C2_$1',text)
    def test_compact_omits_atoms_but_keeps_path_and_metrics(self):
        payload={'candidates':[{'stage':'job/stage','metrics':{'R1':.05},'review':{'formula':'C2','atoms':[{'label':'C1'}]}}]}
        r=compact_candidates(payload);self.assertNotIn('atoms',r['candidates'][0]['review_summary']);self.assertEqual(r['candidates'][0]['review_summary']['atom_sites'],1);self.assertIn('model_review.json',r['candidates'][0]['model_review']);self.assertEqual(len(payload['candidates'][0]['review']['atoms']),1)
    def test_factual_bilingual_shared_data_and_no_one_sided_notes(self):
        data={'scalars':{'_chemical_formula_sum':'C2 H6','_space_group_name_H-M_alt':'P 1'},'atoms':[['C1','C'],['H1','H']],'ani':[],'cif_sha256':'sha'}
        state={'weight_trials':[],'weights':{'active':[.05,.6],'status':'coefficients_stable'}}
        with patch('bilingual_report.extract',return_value=data):
            r=factual_notes('unused',state,{})
            for lang in ['zh','en']:self.assertIn('C2 H6',r[lang]['summary']);self.assertIn('0.05/0.6',r[lang]['methods'])
            self.assertEqual(r['generation']['ai_calls'],0)
            with self.assertRaises(ValueError):factual_notes('unused',state,{'bilingual_notes':{'zh':{'methods':'x'}}})
    def test_repeated_alerts_preserved(self):
        with tempfile.TemporaryDirectory() as t:
            r=decision_packet([{'code':'234','level':'B','text':'C1'},{'code':'234','level':'B','text':'C2'}],Path(t),'review')
            self.assertEqual(len(r['findings']),2);self.assertNotEqual(r['findings'][0]['text'],r['findings'][1]['text'])
    def test_weight_metadata_retains_original_limitations(self):
        import gemmi
        with tempfile.TemporaryDirectory() as t:
            p=Path(t);source=p/'source.cif';target=p/'new.cif'
            source.write_text("data_test\n_publ_section_exptl_refinement 'Absorption applicability remains unconfirmed.'\n")
            target.write_text('data_test\n_audit_creation_method SHELXL\n')
            carry_metadata(source,target,1);value=gemmi.cif.as_string(gemmi.cif.read_file(str(target)).sole_block().find_value('_publ_section_exptl_refinement'))
            self.assertIn('Absorption applicability remains unconfirmed.',value);self.assertIn('Current continuation',value)
    def cache_fixture(self,p):
        s=p/'cache';s.mkdir();f=p/'frozen';f.mkdir();exe=p/'platon.exe';exe.write_bytes(b'fixture')
        files={'model.cif':'data_fixture','model.fcf':'data_fixture','model.chk':'ALERT_Level and ALERT_Type Summary\n','model.ckf':'x'*120,'platon.out':'CheckCIF CheckFCF','process.log':'complete'}
        for name,value in files.items():(s/name).write_text(value)
        for ext in ['cif','fcf']:(f/f'model.{ext}').write_bytes((s/f'model.{ext}').read_bytes())
        record={'input_sha256':{e:sha(f/f'model.{e}') for e in ['cif','fcf']},'artifact_sha256':{n:sha(s/n) for n in files},'executable_sha256':sha(exe),'alerts':parse(files['model.chk'])}
        write_json(s/'local_validation.json',record);return s,f,exe
    def test_cache_reuses_only_intact_inputs_reports_and_executable(self):
        for target in ['model.cif','model.fcf','platon.exe','model.chk','model.ckf']:
            with self.subTest(target=target),tempfile.TemporaryDirectory() as t:
                p=Path(t);s,f,exe=self.cache_fixture(p);self.assertTrue(reuse(s,f,p/'ok','model',exe)['cache_hit'])
                changed=exe if target=='platon.exe' else f/target if target in {'model.cif','model.fcf'} else s/target
                changed.write_text('changed')
                with self.assertRaises(ValueError):reuse(s,f,p/'bad','model',exe)
    def test_cache_missing_completion_rejected_even_if_hashes_match(self):
        with tempfile.TemporaryDirectory() as t:
            p=Path(t);s,f,exe=self.cache_fixture(p);(s/'platon.out').write_text('CheckCIF only')
            r=json.loads((s/'local_validation.json').read_text());r['artifact_sha256']['platon.out']=sha(s/'platon.out');write_json(s/'local_validation.json',r)
            with self.assertRaises(ValueError):reuse(s,f,p/'bad','model',exe)

if __name__=='__main__':unittest.main()
