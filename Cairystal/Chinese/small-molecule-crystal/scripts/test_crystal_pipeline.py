import json,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
import gemmi
from pipeline_intake import discover,normalize_elements,validate_specimen,inspect,verify_profile
from candidate_packet import make_packet,factual_annotations
from crystal_pipeline import identifier,make_summary,checked,run_lock,main
from crystal_runtime import write_json,sha

P4P='FILEID SAINT synthetic\nCELL 8 10 15 90 95 90 1200\nCELLSD .001 .001 .001 0 .01 0\nSOURCE MO .71073\nBRAVAIS Monoclinic(b-unique) P\nSAINGL 2500 2.5 26.3 0\nCSIZE ? ? ? ? 26.85\n'
HKL=f'{1:4d}{0:4d}{1:4d}{100.:8.2f}{5.:8.2f}{1:4d}\n'+f'{0:4d}{0:4d}{0:4d}{0.:8.2f}{0.:8.2f}{0:4d}\n'

class PipelineTests(unittest.TestCase):
    def setup_data(self,p,stem='sample_0m'):
        (p/(stem+'.hkl')).write_text(HKL);(p/(stem+'.p4p')).write_text(P4P)
    def test_intake_not_open_old_model_or_nested_directory(self):
        with tempfile.TemporaryDirectory() as t:
            p=Path(t);self.setup_data(p);(p/'old.res').write_text('unreadable reference poison');(p/'old.cif').write_text('poison');(p/'nested').mkdir();self.setup_data(p/'nested','other')
            original=Path.read_text;seen=[]
            def read(path,*args,**kwargs):seen.append(path);return original(path,*args,**kwargs)
            with patch.object(Path,'read_text',read):result=inspect(p,['C','H','N','O','Cl'])
            self.assertFalse(any(x.suffix in {'.res','.cif'} for x in seen));self.assertEqual(result['metadata']['measurement_reflections'],2500);self.assertEqual(result['sfac_order'],['C','H','N','O','Cl']);self.assertEqual(result['missing_specimen_facts'],['colour','habit','three_dimensions'])
    def test_ambiguous_pair_requires_selection(self):
        with tempfile.TemporaryDirectory() as t:
            p=Path(t);self.setup_data(p,'one');self.setup_data(p,'two')
            with self.assertRaises(ValueError):discover(p)
            self.assertEqual(discover(p,'two')[0]['hkl'].name,'two.hkl')
    def test_no_hkl_p4p_pair_not_fallback_to_res(self):
        with tempfile.TemporaryDirectory() as t:
            p=Path(t);(p/'sample.res').write_text('model');(p/'sample.hkl').write_text(HKL)
            with self.assertRaises(ValueError):discover(p)
    def test_path_traversal_in_stage_or_stem_rejected(self):
        for x in ['../answer','a/b','a\\b','..','a;run']:
            with self.assertRaises(ValueError):identifier(x)
    def test_input_hashes_and_optional_abs_provenance(self):
        with tempfile.TemporaryDirectory() as t:
            p=Path(t);self.setup_data(p);(p/'sample.abs').write_text('original processing record');r=inspect(p,['C','H'])
            self.assertEqual(r['inputs']['hkl']['sha256'],sha(p/'sample_0m.hkl'));self.assertEqual(r['inputs']['absorption_log']['path'],str(p/'sample.abs'))
            (p/'sample_0m.abs').write_text('conflicting processing record')
            with self.assertRaises(ValueError):discover(p)
    def test_elements_are_symbols_and_order_is_preserved(self):
        self.assertEqual(normalize_elements(['Cl','C','H','C','O']),['Cl','C','H','O'])
        for x in [[],['H'],['D'],['Carbon'],['Xx']]:
            with self.assertRaises(ValueError):normalize_elements(x)
    def test_specimen_drafts_or_wrong_units_order_rejected(self):
        with tempfile.TemporaryDirectory() as t:
            p=Path(t)/'facts.json';valid={'provenance':'User measured specimen','cif_fields':{'_exptl_crystal_size_max':.1,'_exptl_crystal_size_mid':.09,'_exptl_crystal_size_min':.08}}
            write_json(p,valid);self.assertEqual(validate_specimen(p)[1],['colour','habit'])
            write_json(p,dict(valid,draft_defaults=True))
            with self.assertRaises(ValueError):validate_specimen(p)
            valid['cif_fields']['_exptl_crystal_size_max']=.01;write_json(p,valid)
            with self.assertRaises(ValueError):validate_specimen(p)
    def test_bad_hkl_and_theta_fail_before_solver(self):
        with tempfile.TemporaryDirectory() as t:
            p=Path(t);self.setup_data(p);(p/'sample_0m.p4p').write_text(P4P.replace('2.5 26.3','28 26.3'))
            with self.assertRaises(ValueError):inspect(p,['C'])
            (p/'sample_0m.p4p').write_text(P4P);(p/'sample_0m.hkl').write_text('unrecognized')
            with self.assertRaises(ValueError):inspect(p,['C'])
    def test_profile_changed_executable_rejected(self):
        import sys
        with tempfile.TemporaryDirectory() as t:
            p=Path(t)/'shelxl.exe';p.write_bytes(b'original');profile={'python':sys.executable,'tools':{'shelxl':{'path':str(p),'sha256':sha(p)}}}
            self.assertEqual(verify_profile(profile)['shelxl'],str(p));p.write_bytes(b'changed')
            with self.assertRaises(ValueError):verify_profile(profile)
    def test_packet_ranks_but_does_not_select_or_assign(self):
        candidates=[]
        for stage,r1 in [('stage_N',.06),('stage_O',.05)]:
            candidates.append({'stage':stage,'metrics':{'R1_observed':r1},'review':{'space_group':'P 1','formula':'unknown','atoms':[{'label':'N1','element':'N','Ueq':.03,'neighbors':[]}],'difference_density':['.5','-.5']}})
        packet=make_packet(Path('.'),{'candidates':candidates});self.assertFalse(packet['automatic_selection']);self.assertEqual(packet['numerical_rank_only'][0],'stage_O')
    def test_factual_narrative_retains_processing_limitations(self):
        with tempfile.TemporaryDirectory() as t:
            p=Path(t);(p/'plans').mkdir();log=p/'sample.abs';log.write_text('Additional spherical absorption correction applied with mu*r = 2.0000\nEstimated minimum and maximum transmission: 0.05 0.09')
            write_json(p/'session.json',{'events':[{'name':'00_solution','status':'completed'}],'laue_basis':'Recorded monoclinic','inputs':{'absorption_log':{'copy':str(log)}},'prior_conversation_exposure':True})
            write_json(p/'plans/step.json',{'reason':'Evidence-based H treatment'})
            a=factual_annotations(p,'Reviewed connectivity')['_publ_section_exptl_refinement']
            self.assertIn('2.0000',a);self.assertIn('needs review',a);self.assertIn('Evidence-based H treatment',a);self.assertIn('naive blind',a)
    def test_summary_includes_all_native_weight_runs_and_null_tokens(self):
        with tempfile.TemporaryDirectory() as t:
            p=Path(t);(p/'session/stages/a').mkdir(parents=True);write_json(p/'session/stages/a/attempt.json',{'elapsed_s':1,'command':['shelxl','model'],'gate':{'metrics':{'R1_observed':.05}}})
            state={'created_at':'2026-01-01T00:00:00+00:00','finished_at':'2026-01-01T00:00:10+00:00','status':'complete','context_measurements':[{'full_characters':100,'compact_characters':20}],'events':[{'seconds':3}]}
            result=make_summary(p,state);self.assertEqual(result['between_actions_s'],7);self.assertEqual(result['token_usage']['character_reduction_percent'],80);self.assertIsNone(result['token_usage']['exact_total']);self.assertEqual(result['native_elapsed_s'],1)
    def test_same_run_concurrent_mutation_is_blocked_and_lock_released(self):
        with tempfile.TemporaryDirectory() as t:
            p=Path(t)
            with run_lock(p):
                self.assertTrue((p/'pipeline.lock').exists())
                with self.assertRaises(ValueError):
                    with run_lock(p):pass
            self.assertFalse((p/'pipeline.lock').exists())
    def test_rejected_repeat_command_does_not_destroy_completed_status(self):
        import sys,io,contextlib
        with tempfile.TemporaryDirectory() as t:
            p=Path(t);state={'status':'complete','events':[]};write_json(p/'pipeline.json',state);write_json(p/'runtime_profile.json',{})
            args=['crystal_pipeline.py','finalize','--run',str(p),'--review-note','not permitted repeat']
            with patch.object(sys,'argv',args),patch('crystal_pipeline.bootstrap'),patch('crystal_pipeline.checked'),patch('crystal_pipeline.render_summary'),contextlib.redirect_stdout(io.StringIO()):code=main()
            self.assertEqual(code,1);saved=json.loads((p/'pipeline.json').read_text());self.assertEqual(saved['status'],'complete');self.assertIn('last_command_error',saved)

if __name__=='__main__':unittest.main()
