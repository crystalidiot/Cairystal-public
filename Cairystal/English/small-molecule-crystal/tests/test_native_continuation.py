"""Routing contracts with a synthetic runner; not chemical correctness tests."""
import copy,json,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
import crystal_autorun as ar
import native_continuation as nc
from crystal_runtime import sha,write_json

class NativeContinuationTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name)/'run';self.root.mkdir();(self.root/'logs').mkdir();(self.root/'inputs').mkdir()
        self.raw=self.root.parent/'data';self.raw.mkdir();self.hkl=self.raw/'model.hkl';self.hkl.write_text('Synthetic current-specimen HKL')
        self.candidate=self.root/'manual_candidate';self.candidate.mkdir()
        for ext in ('cif','res','lst','fcf','hkl'):(self.candidate/('model.'+ext)).write_text(self.hkl.read_text() if ext=='hkl' else 'Synthetic '+ext)
        self.profile=self.root/'inputs/profile.json';write_json(self.profile,{'python':'python'})
        self.review=self.root/'current_review.json';write_json(self.review,{'chemistry_and_h_reviewed':True,'basis':'Synthetic path/dispatch test only; no chemical claim'})
        self.state={'status':'needs_attention','category':'scientific_decision','bindings':{},'pipeline_seal':{},'skill_sha256':ar.stamp(),
                    'actions':[{'action':'solve','status':'checkpointed'},{'action':'match','status':'checkpointed'}],
                    'completed_actions':['solve','match'],'interventions':[],'source_hkl':{'path':str(self.hkl),'sha256':sha(self.hkl)},
                    'options':{'data_dir':str(self.raw),'profile':str(self.profile),'deliver':True,'authorize_iucr_upload':False,'timeout':180,'max_weight_updates':4}}
        ar.save(self.root,self.state);self.commands=[]
        self.addCleanup(patch.stopall)
        patch('native_continuation.paired_bundle',side_effect=self.bundle).start()
        patch('support_report.try_record',return_value=None).start()
        patch.dict('os.environ',{'CAIRYSTAL_KNOWLEDGE_INDEX':''}).start()
    def bundle(self,folder,stem):
        paths={e:str(Path(folder)/(stem+'.'+e)) for e in ['cif','res','hkl','lst','fcf']}
        return {'files':paths,'source_sha256':{e:sha(p) for e,p in paths.items()}}
    def runner(self,cmd,log):
        self.commands.append(cmd);log.write_text('Synthetic runner: no native program or upload')
        if Path(cmd[2]).name=='complete_candidate.py':
            out=Path(cmd[cmd.index('--output')+1]);(out/'finish').mkdir(parents=True)
            write_json(out/'result.json',{'status':'awaiting_upload_authorization','full_delivery_complete':False})
            write_json(out/'finish/state.json',{'status':'ready_for_official_delivery'})
            return 2
        if Path(cmd[2]).name=='deliver_ready.py':
            finish=Path(cmd[cmd.index('--run')+1]);dr=finish/'delivery_run';dr.mkdir()
            write_json(dr/'result.json',{'status':'delivery_complete_needs_scientific_review'})
            return 0
        self.fail('Unexpected action: '+str(cmd))
    def start(self):return nc.continue_native(self.root,self.state,self.candidate,self.review,'branch_1',runner=self.runner)
    def test_native_branch_after_graph_preserves_old_run_and_skips_solve(self):
        old=copy.deepcopy(self.state);self.start()
        previous=ar.read(self.root/'native_branches/branch_1/previous_coordinator.json')
        self.assertEqual(previous,old);self.assertEqual(len(self.commands),1)
        self.assertTrue(self.commands[0][2].endswith('complete_candidate.py'))
        self.assertEqual(self.state['completed_actions'],['solve','match','native_finish:branch_1'])
        self.assertEqual(self.state['category'],'upload_authorization_required')
        self.assertNotIn('--authorize-iucr-upload',self.commands[0])
    def test_prior_upload_consent_reused(self):
        self.state['options']['authorize_iucr_upload']=True;self.start()
        self.assertIn('--authorize-iucr-upload',self.commands[0])
    def test_local_only_is_preserved(self):
        self.state['options']['deliver']=False
        with patch('deliver_ready.verify_ready') as check:self.start();check.assert_called_once()
        self.assertIn('--local-only',self.commands[0]);self.assertEqual(self.state['status'],'local_ready')
    def test_wrong_specimen_rejected_before_branch_created(self):
        (self.candidate/'model.hkl').write_text('Other specimen')
        with self.assertRaises(ar.WrongSpecimen):self.start()
        self.assertFalse((self.root/'native_branches').exists());self.assertFalse(self.commands)
    def test_stale_review_rejected_before_model_consumed(self):
        write_json(self.review,{'chemistry_and_h_reviewed':True,'basis':'test','model_sha256':'wrong'})
        with self.assertRaisesRegex(ValueError,'different CIF'):self.start()
        self.assertFalse(self.commands)
    def test_missing_chemical_review_is_not_fabricated(self):
        write_json(self.review,{'basis':'not reviewed'})
        with self.assertRaisesRegex(ValueError,'actual current-model'):self.start()
        self.assertFalse(self.commands)
    def test_existing_branch_not_overwritten(self):
        self.start();before=ar.seal(self.root/'native_branches')
        with self.assertRaisesRegex(ValueError,'new branch name'):self.start()
        self.assertEqual(before,ar.seal(self.root/'native_branches'))
    def test_changed_snapshot_blocks_resume(self):
        self.start();(self.root/'native_branches/branch_1/input/model.res').write_text('Changed')
        with self.assertRaisesRegex(ValueError,'snapshot changed'):ar.drive(self.root,self.state,self.runner)
        self.assertEqual(len(self.commands),1)
    def test_resume_stays_on_native_branch_without_solution_replay(self):
        self.start();ar.drive(self.root,self.state,self.runner)
        self.assertEqual(len(self.commands),1);self.assertEqual(self.state['category'],'upload_authorization_required')
    def test_delivery_resume_reuses_native_finish(self):
        self.start();ar.amend(self.root,self.state,authorize=True)
        delivered={'customer_delivery':{'directory':str(self.raw/'Cairystal')},'official_counts':{'A':1,'B':2},'zip':'synthetic.zip'}
        with patch.object(nc,'_verified_delivery',return_value=delivered):ar.drive(self.root,self.state,self.runner)
        self.assertEqual(len(self.commands),2);self.assertTrue(self.commands[-1][2].endswith('deliver_ready.py'))
        self.assertEqual(self.state['status'],'complete');self.assertEqual(self.state['official_counts'],{'A':1,'B':2})
    def test_full_delivery_is_checked_not_inferred_from_exit_code(self):
        self.start();ar.amend(self.root,self.state,authorize=True)
        with patch.object(nc,'_verified_delivery',side_effect=ValueError('Missing PDF')):
            with self.assertRaisesRegex(ValueError,'Missing PDF'):ar.drive(self.root,self.state,self.runner)
        self.assertNotEqual(self.state['status'],'complete')
    def test_uncertain_native_call_is_not_replayed(self):
        with self.assertRaises(RuntimeError):nc.continue_native(self.root,self.state,self.candidate,self.review,'uncertain',runner=lambda *a:(_ for _ in ()).throw(RuntimeError('interrupted')))
        self.assertIn('pending',self.state)
        ar.drive(self.root,self.state,self.runner);self.assertFalse(self.commands)
        self.assertEqual(self.state['category'],'interrupted_action')
    def test_graph_requirement_handoff_contains_native_return(self):
        from model_strategy import handoff_routes
        hints=handoff_routes(self.root,'chemical_graph_required',[])
        route=hints['return_to_coordinator'];self.assertFalse(route['replays_solution_or_graph'])
        self.assertEqual(route['arguments'][:3],['continue-native','--run',str(self.root)])
    def test_a_second_candidate_keeps_first_branch(self):
        self.start();before=ar.seal(self.root/'native_branches/branch_1')
        nc.continue_native(self.root,self.state,self.candidate,self.review,'branch_2',runner=self.runner)
        self.assertEqual(before,ar.seal(self.root/'native_branches/branch_1'));self.assertEqual(len(self.state['native_branches']),2)

    def test_HKL_without_P4P_binds_specimen_for_native_route(self):
        cfg=self.root.parent/'config.json';write_json(cfg,{'data_dir':str(self.raw),'profile':str(self.profile),'elements':['B','C'],'deliver':False})
        root,state=ar.create(cfg,self.root.parent/'fresh_job')
        self.assertEqual(state['source_hkl']['sha256'],sha(self.hkl))
        ar.check_expected(root,state,self.hkl)
        self.assertIn('raw_helper_note',state)

    def test_ambiguous_HKL_without_stem_is_not_guessed(self):
        (self.raw/'other.hkl').write_text('Other data')
        self.assertIsNone(ar.selected_raw_hkl(self.raw))
        self.assertEqual(ar.selected_raw_hkl(self.raw,'model'),self.hkl)

    def test_HKL_binding_does_not_open_INS_or_CIF(self):
        (self.raw/'model.ins').write_bytes(b'not a supported INS')
        (self.raw/'reference.cif').write_bytes(b'do not read answer')
        self.assertEqual(ar.selected_raw_hkl(self.raw),self.hkl)

    def test_non_ASCII_raw_basename_is_supported(self):
        selected=self.raw/'实验样品.hkl';selected.write_text('Another selected specimen')
        self.assertEqual(ar.selected_raw_hkl(self.raw,'实验样品'),selected)

    def native_validation(self):
        self.start();finish=self.root/'native_branches/branch_1/completion/finish'
        model=finish/'frozen';model.mkdir();validation=finish/'local_validation';validation.mkdir()
        for ext in ['cif','fcf']:(model/('model.'+ext)).write_text('Synthetic current '+ext)
        write_json(validation/'local_validation.json',{'validation_complete':True,'input_sha256':{e:sha(model/('model.'+e)) for e in ['cif','fcf']},'validated_counts':{'A':0,'B':1},'alerts':{'alerts':[{'code':'TEST','level':'B','text':'Synthetic alert'}]}})
        return model

    def test_current_native_AB_is_shown(self):
        self.native_validation();report=ar.local_report_at_checkpoint(self.root,self.state)
        self.assertEqual(report['counts'],{'A':0,'B':1});self.assertEqual(report['branch'],'branch_1')

    def test_changed_native_model_does_not_reuse_alerts(self):
        model=self.native_validation();(model/'model.cif').write_text('Changed')
        self.assertIsNone(ar.local_report_at_checkpoint(self.root,self.state)['counts'])

    def test_no_native_report_does_not_show_old_graph_counts(self):
        self.start();self.state['pipeline_seal']={'old/local_validation/local_validation.json':'old'}
        report=ar.local_report_at_checkpoint(self.root,self.state)
        self.assertEqual(report['branch'],'native');self.assertIsNone(report['counts'])

if __name__=='__main__':unittest.main()
