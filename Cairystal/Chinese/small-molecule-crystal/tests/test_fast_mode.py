"""Fast-mode contracts; synthetic tests do not establish crystal accuracy."""
import copy, json, math, tempfile, unittest
from pathlib import Path
from unittest.mock import patch
from execution_mode import (options, gate_reasons, CONVERGENCE_REASON, weight_stop_blocks,
                            automatic_repairs, annotate_notes, preview_record)
from scientific_report_rules import basic_findings


class FastPolicyTests(unittest.TestCase):
    def gate(self, shift=.05, npd=0, extra=()):
        return {'execution_complete':True,'metrics':{'last_abs_max_shift_esd':shift,'NPD_atoms':npd},
                'review_reasons':[CONVERGENCE_REASON,*extra]}

    def test_standard_preserves_budgets_and_input(self):
        cfg={'max_candidates':6,'max_weight_updates':4,'authorize_iucr_upload':False}
        original=copy.deepcopy(cfg)
        self.assertEqual(options(cfg),dict(cfg,execution_mode='standard'))
        self.assertEqual(cfg,original)

    def test_fast_caps_trials_without_authorizing_upload_or_removing_reports(self):
        r=options({'execution_mode':'fast','max_candidates':6,'max_weight_updates':4,
                   'deliver':True,'authorize_iucr_upload':False})
        self.assertEqual((r['max_candidates'],r['max_weight_updates']),(2,1))
        self.assertTrue(r['deliver']);self.assertFalse(r['authorize_iucr_upload'])

    def test_explicit_zero_weight_budget_stays_zero(self):
        self.assertEqual(options({'execution_mode':'fast','max_weight_updates':0})['max_weight_updates'],0)

    def test_invalid_budgets_and_modes(self):
        for cfg in [{'execution_mode':'quick'}, {'execution_mode':'fast','max_candidates':True},
                    {'execution_mode':'fast','max_weight_updates':-1}, {'execution_mode':None}]:
            with self.subTest(cfg=cfg), self.assertRaises(ValueError):options(cfg)

    def test_standard_shift_requirement_unchanged(self):
        self.assertEqual(gate_reasons(self.gate()),[CONVERGENCE_REASON])

    def test_fast_small_shift_is_provisional_not_rewritten(self):
        g=self.gate();saved=copy.deepcopy(g)
        self.assertEqual(gate_reasons(g,'fast'),[]);self.assertEqual(g,saved)

    def test_fast_boundary(self):
        self.assertEqual(gate_reasons(self.gate(.1),'fast'),[])
        self.assertTrue(gate_reasons(self.gate(.10001),'fast'))

    def test_missing_bad_shifts_never_pass(self):
        for value in [None, math.nan, math.inf, -.1, True]:
            with self.subTest(value=value):self.assertTrue(gate_reasons(self.gate(value),'fast'))

    def test_npd_or_unknown_count_not_relaxed(self):
        for count in [1,None,False]:
            with self.subTest(count=count):self.assertTrue(gate_reasons(self.gate(npd=count),'fast'))

    def test_execution_error_and_parameter_controls_retained(self):
        g=self.gate(extra=['BLOC subset needs review']);g['execution_complete']=False
        self.assertEqual(len(gate_reasons(g,'fast')),2)
        g['execution_complete']=True
        self.assertEqual(gate_reasons(g,'fast'),['BLOC subset needs review'])

    def test_weights_stop_without_extra_trials_only_in_fast_mode(self):
        for stop in ['update_budget_reached','suggestion_missing']:
            self.assertTrue(weight_stop_blocks(stop));self.assertFalse(weight_stop_blocks(stop,'fast'))
        self.assertFalse(weight_stop_blocks('coefficients_stable'))

    def test_automatic_repairs_standard_only(self):
        self.assertTrue(automatic_repairs());self.assertFalse(automatic_repairs('fast'))

    def test_scientific_findings_fast_preserves_other_criteria(self):
        m={'NPD_atoms':0,'last_abs_max_shift_esd':.05,'R1_observed':.04,'GooF':1.1}
        p={'residual_density':[.3,-.4]};g={'atoms':[{'element':'C','formal_charge':0}]}
        self.assertTrue(basic_findings(m,p,g));self.assertEqual(basic_findings(m,p,g,'fast'),[])
        m['NPD_atoms']=1
        self.assertIn('NPD count missing or nonzero',basic_findings(m,p,g,'fast'))
        m['NPD_atoms']=0;g['atoms'][0]['formal_charge']=1
        self.assertIn('Supplied complete graph has nonzero total charge',basic_findings(m,p,g,'fast'))

    def test_notes_mark_even_zero_AB_and_do_not_claim_unmeasured_stable_weights(self):
        notes={'zh':{'summary':'模型','methods':'权重系数已稳定，本次未继续迭代。','limitations':''},
               'en':{'summary':'model','methods':'The weight coefficients were already stable; no further iteration was performed.','limitations':''}}
        annotate_notes(notes,{'execution_mode':'fast','weights':{'status':'suggestion_missing'},'weight_trials':[]})
        self.assertTrue(notes['provisional'])
        self.assertIn('快速候选',notes['zh']['summary']);self.assertIn('provisional',notes['en']['summary'])
        self.assertNotIn('已稳定',notes['zh']['methods']);self.assertNotIn('already stable',notes['en']['methods'])

    def test_standard_notes_unchanged(self):
        notes={'zh':{},'en':{}};self.assertEqual(annotate_notes(copy.deepcopy(notes),{}),notes)

    def test_preview_is_not_fake_official_report(self):
        import time
        with tempfile.TemporaryDirectory() as td:
            p=Path(td)
            for ext in ['res','hkl','cif','fcf']:(p/('model.'+ext)).write_text('synthetic '+ext)
            r=preview_record(p,{'available':False},{'metrics':{'R1_observed':None}},time.perf_counter())
            self.assertEqual(r['official_report'],'not_yet_obtained')
            self.assertEqual(r['scientific_acceptance'],'not_established')
            self.assertIsNone(r['metrics']['R1_observed']);self.assertIsNone(r['alerts'])
            self.assertEqual(len(r['files']),4)

    def test_live_preview_visible_before_delivery_and_rejects_changed_files(self):
        import time
        from execution_mode import live_preview
        from crystal_runtime import write_json
        with tempfile.TemporaryDirectory() as td:
            root=Path(td);p=root/'pipeline/auto_finish/frozen';p.mkdir(parents=True)
            for ext in ['res','hkl','cif','fcf']:(p/('model.'+ext)).write_text('synthetic '+ext)
            r=preview_record(p,{}, {},time.perf_counter())
            write_json(p.parent/'fast_preview.json',r)
            self.assertEqual(live_preview(root)['status'],'provisional_model_available')
            (p/'model.cif').write_text('changed')
            self.assertIsNone(live_preview(root))


class FastAutorunTests(unittest.TestCase):
    def test_create_and_native_finish_forward_the_mode(self):
        import crystal_autorun as ar
        from crystal_runtime import write_json
        import sys
        with tempfile.TemporaryDirectory() as td:
            p=Path(td);(p/'raw').mkdir();write_json(p/'profile.json',{'python':sys.executable})
            write_json(p/'config.json',{'data_dir':str(p/'raw'),'profile':str(p/'profile.json'),'elements':['C'],
                                       'max_candidates':6,'max_weight_updates':4})
            root,state=ar.create(p/'config.json',p/'run',execution_mode='fast')
            self.assertEqual(state['options']['max_candidates'],2)
            self.assertEqual(state['options']['max_weight_updates'],1)
            cmd=ar.arguments(root,state,'finish','new_stage')
            self.assertIn('--execution-mode',cmd);self.assertIn('fast',cmd)
            self.assertNotIn('--authorize-iucr-upload',cmd)
            original=json.loads((p/'config.json').read_text('utf-8'))
            self.assertNotIn('execution_mode',original)

    def test_fast_does_not_remove_required_chemical_review(self):
        import crystal_autorun as ar
        from crystal_runtime import write_json
        import sys
        with tempfile.TemporaryDirectory() as td:
            p=Path(td);(p/'raw').mkdir();write_json(p/'profile.json',{'python':sys.executable})
            write_json(p/'config.json',{'data_dir':str(p/'raw'),'profile':str(p/'profile.json'),'elements':['C']})
            root,state=ar.create(p/'config.json',p/'run',execution_mode='fast')
            def runner(command,log):
                log.write_text('synthetic');(root/'pipeline').mkdir()
                write_json(root/'pipeline/pipeline.json',{'candidates':[{'stage':'new'}]})
                return 0
            result=ar.drive(root,state,runner)
            self.assertEqual(result['category'],'chemical_graph_required')
            self.assertEqual(len(result['actions']),1)


class TwinWeightStabilityTests(unittest.TestCase):
    def text(self,fraction):
        return ('TITL fixture\nCELL .71073 10 11 12 90 90 90\nLATT 1\nSFAC C\nUNIT 2\n'
                'WGHT .05\nFVAR 1\nBASF '+str(fraction)+'\nTWIN -1 0 0 0 -1 0 0 0 1\n'
                'C1 1 .1 .2 .3 11 .025\nHKLF 4\nEND\n')

    def test_refined_BASF_value_does_not_change_parameterization(self):
        from routine_finish import model_signature
        self.assertEqual(model_signature(self.text(.30005)),model_signature(self.text(.2999)))
        self.assertNotEqual(model_signature(self.text(.3)),model_signature(self.text('0.2 0.1')))

    def test_bad_or_large_BASF_change_is_still_rejected(self):
        from routine_finish import movement_review
        with tempfile.TemporaryDirectory() as td:
            p=Path(td);(p/'before.res').write_text(self.text(.3))
            for value in [.5,-.1,1.1,float('nan')]:
                (p/'after.res').write_text(self.text(value))
                with self.subTest(value=value),self.assertRaises(ValueError):
                    movement_review(p/'before.res',p/'after.res',{}, {},'fast')

if __name__=='__main__':unittest.main()
