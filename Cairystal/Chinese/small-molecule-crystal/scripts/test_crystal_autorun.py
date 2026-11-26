"""Synthetic coordinator contract tests; no crystallographic correctness claim."""
import contextlib
import io
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch
from types import SimpleNamespace

import crystal_autorun as ar
import crystal_pipeline as cp
from crystal_runtime import sha,write_json


class AutorunTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.base=Path(self.tmp.name);self.data=self.base/'raw';self.data.mkdir()
        self.hkl=self.data/'sample.hkl';self.hkl.write_text('synthetic diffraction fixture')
        self.profile=self.base/'profile.json';write_json(self.profile,{'python':sys.executable})
        self.graph=self.base/'graph.json';write_json(self.graph,{'synthetic_graph':True})
        self.config=self.base/'config.json';self.calls=[]
        self.cfg={'data_dir':str(self.data),'profile':str(self.profile),'elements':['C','H','N','O','Cl'],
                  'graph':str(self.graph),'donor_basis':'explicit synthetic test prior','authorize_iucr_upload':True}
        self.candidates=[{'stage':'solution_a'}];self.match_status='ready_for_model_review';self.finish_status='complete'
        # This suite checks dispatch only. Exact delivery validation has its own
        # negative-path tests and a real-package replay; never invoke it on mocks.
        self.delivery_check=patch('coordinator_completion.verified_pipeline_delivery',side_effect=lambda root,state,ps:ar.read(Path(ps['finish_root'])/'delivery_run/result.json'))
        self.delivery_check.start();self.addCleanup(self.delivery_check.stop)
    def create(self,**options):
        cfg=dict(self.cfg,**options)
        write_json(self.config,cfg);self.root,self.state=ar.create(self.config,self.base/'run')
        return self.root,self.state
    def runner(self,cmd,log):
        action=cmd[3];self.calls.append(action);log.write_text('Synthetic runner only')
        folder=self.root/'pipeline';folder.mkdir(exist_ok=True);p=folder/'pipeline.json'
        ps=ar.read(p) if p.exists() else {'intake':{'inputs':{'hkl':{'path':str(self.hkl),'sha256':sha(self.hkl)}}}}
        if action=='start':ps.update(status='needs_scientific_review',candidates=self.candidates)
        elif action=='match':ps.update(status='needs_scientific_review',graph_matching={'status':self.match_status,'hydrogen_stage':'auto_graph_H'})
        elif action in {'autofinish','deliver'}:ps.update(status=('ready_for_official_delivery' if action=='autofinish' and '--deliver' not in cmd and self.finish_status=='complete' else self.finish_status),official_counts={'A':0,'B':0},delivery='synthetic_delivery',zip={'path':'synthetic.zip'})
        else:raise AssertionError(action)
        if ps.get('status')=='complete':
            finish=folder/'synthetic_finish';dr=finish/'delivery_run';dr.mkdir(parents=True,exist_ok=True)
            receipt={'directory':'synthetic_delivery','files':{}}
            write_json(dr/'result.json',{'customer_delivery':receipt,'customer_notice':'Synthetic test delivery only','official_counts':{'A':0,'B':0},'zip':{'path':'synthetic.zip'}})
            write_json(dr/'customer_delivery.json',receipt);ps['finish_root']=str(finish)
        write_json(p,ps);return 0
    def drive(self,runner=None):
        with contextlib.redirect_stdout(io.StringIO()):return ar.drive(self.root,self.state,runner or self.runner)
    def test_continuous_route_and_completed_resume_is_noop(self):
        self.create();self.drive();self.assertEqual(self.calls,['start','match','autofinish'])
        self.assertEqual(self.state['status'],'complete');self.drive();self.assertEqual(len(self.calls),3)
        summary=ar.publish(self.root,self.state);self.assertEqual(summary['ai_calls'],0);self.assertIsNone(summary['token_usage']['exact_saving'])
    def test_missing_graph_resume_does_not_resolve_again(self):
        self.create(graph=None);self.drive();self.assertEqual(self.calls,['start']);self.assertEqual(self.state['category'],'chemical_graph_required')
        packet = ar.read(self.root/'handoff.json')
        self.assertEqual(packet['next_step']['owner'], 'assistant')
        self.assertEqual(ar.publish(self.root,self.state)['next_step'], packet['next_step'])
        ar.amend(self.root,self.state,graph=str(self.graph));self.drive()
        self.assertIsNone(ar.publish(self.root,self.state)['next_step'])
        self.assertEqual(self.calls,['start','match','autofinish']);self.assertEqual(self.state['status'],'complete');self.assertNotIn('category',self.state)
    def test_unavailable_initial_screen_stops_before_chemical_matching(self):
        self.candidates=[{'stage':'solution_a','initial_review':{'status':'review_unavailable'}}]
        self.create();self.drive()
        self.assertEqual(self.calls,['start'])
        self.assertEqual(self.state['category'],'initial_model_review_unavailable')
    def test_screen_flags_do_not_replace_reviewed_graph_assignment(self):
        self.candidates=[{'stage':'solution_a','initial_review':{'status':'needs_review','scientific_acceptance':False}}]
        self.create();self.drive()
        self.assertEqual(self.calls,['start','match','autofinish'])
    def test_multiple_candidates_never_selected_by_r(self):
        self.candidates=[{'stage':'a','R1':.01},{'stage':'b','R1':.2}];self.create();self.drive()
        self.assertEqual(self.calls,['start']);self.assertEqual(self.state['category'],'scientific_decision')
        with self.assertRaises(ValueError):ar.amend(self.root,self.state,source='b')
        ar.amend(self.root,self.state,source='b',basis='current synthetic symmetry evidence');self.drive()
        command=self.state['actions'][1]['command'];self.assertEqual(command[command.index('--source')+1],'b')
    def test_ambiguous_graph_stops_before_finish(self):
        self.match_status='needs_review';self.create();self.drive();self.assertEqual(self.calls,['start','match'])
        self.assertEqual(self.state['category'],'scientific_decision');self.drive();self.assertEqual(len(self.calls),2)
    def test_existing_authorization_can_be_recorded_on_resume(self):
        self.create(authorize_iucr_upload=False);self.drive();self.assertEqual(self.calls,['start','match','autofinish'])
        self.assertEqual(self.state['category'],'upload_authorization_required')
        self.assertEqual(self.state['next_step']['owner'],'user_if_no_prior_consent')
        self.assertNotIn('--deliver',self.state['actions'][-1]['command'])
        ar.amend(self.root,self.state,authorize=True);self.drive();self.assertEqual(self.calls,['start','match','autofinish','deliver'])
        self.assertEqual(self.state['status'],'complete')
    def test_local_mode_does_not_claim_official_completion(self):
        self.finish_status='ready_for_official_delivery';self.create(deliver=False,authorize_iucr_upload=False);self.drive()
        self.assertEqual(self.state['status'],'local_ready');self.assertNotIn('--deliver',self.state['actions'][-1]['command'])
    def test_nonzero_return_never_replayed(self):
        self.create()
        def fail(cmd,log):self.runner(cmd,log);return 1
        self.drive(fail);self.drive();self.assertEqual(self.calls,['start']);self.assertEqual(self.state['category'],'execution_error')
    def test_uncertain_action_not_replayed_after_interruption(self):
        self.create()
        def interrupted(cmd,log):self.calls.append(cmd[3]);raise OSError('simulated interrupted child')
        self.drive(interrupted);self.drive();self.assertEqual(self.calls,['start']);self.assertEqual(self.state['pending'],'solve')
        self.assertEqual(self.state['category'],'interrupted_action')
    def test_pipeline_running_is_not_success(self):
        self.create()
        def incomplete(cmd,log):
            self.runner(cmd,log);p=self.root/'pipeline/pipeline.json';v=ar.read(p);v['status']='running';write_json(p,v);return 0
        self.drive(incomplete);self.assertEqual(self.calls,['start']);self.assertEqual(self.state['category'],'execution_error')
    def test_autoqa_failure_cannot_be_marked_complete(self):
        self.finish_status='needs_report_review';self.create();self.drive()
        self.assertEqual(self.state['category'],'report_review');self.assertEqual(self.state['status'],'needs_attention')
    def test_ab_gate_cannot_be_bypassed(self):
        self.finish_status='needs_alert_review';self.create();self.drive();self.assertEqual(self.state['status'],'needs_attention')
    def test_original_raw_change_on_resume_stops(self):
        self.create(graph=None);self.drive();self.hkl.write_text('changed');self.drive()
        self.assertEqual(self.calls,['start']);self.assertEqual(self.state['category'],'integrity_error')
    def test_frozen_graph_change_stops_before_execution(self):
        self.create();self.graph.write_text('{}');self.drive();self.assertEqual(self.calls,[])
        self.assertEqual(self.state['category'],'integrity_error')
    def test_external_current_run_model_edit_stops(self):
        self.create(graph=None);self.drive();(self.root/'pipeline/new_model.res').write_text('outside edit');self.drive()
        self.assertEqual(self.calls,['start']);self.assertEqual(self.state['category'],'integrity_error')
    def test_script_version_change_stops(self):
        self.create()
        with patch.object(ar,'stamp',return_value={'changed.py':'x'}):self.drive()
        self.assertEqual(self.state['category'],'integrity_error');self.assertEqual(self.calls,[])
    def test_output_cannot_be_created_inside_input(self):
        write_json(self.config,self.cfg);out=self.data/'bad_output'
        with self.assertRaises(ValueError):ar.create(self.config,out)
        self.assertFalse(out.exists())
    def test_unknown_and_invalid_config_rejected(self):
        for extra in [{'do_omit':True},{'authorize_iucr_upload':'yes'},{'max_candidates':7},{'timeout':0},{'elements':'C H'},{'max_weight_updates':True}]:
            with self.subTest(extra=extra):
                write_json(self.config,dict(self.cfg,**extra))
                with self.assertRaises(ValueError):ar.create(self.config,self.base/'run')
                self.assertFalse((self.base/'run').exists())
    def test_amendment_is_validated_before_snapshot(self):
        self.create(graph=None);self.drive()
        with self.assertRaises(ValueError):ar.amend(self.root,self.state,graph=str(self.graph),source='solution_a')
        self.assertFalse((self.root/'inputs/graph.json').exists());self.assertIsNone(self.state['options']['graph'])
    def test_changed_chemical_prior_after_match_rejected(self):
        self.create(authorize_iucr_upload=False);self.drive()
        with self.assertRaises(ValueError):ar.amend(self.root,self.state,donor_basis='new unsupported prior')
    def test_locks_refuse_parallel_coordinator_and_release_normally(self):
        self.create()
        with ar.lock(self.root):
            with self.assertRaises(ValueError):
                with ar.lock(self.root):pass
        self.assertFalse((self.root/'autorun.lock').exists())
    def test_command_uses_frozen_profile_and_recorded_limits(self):
        self.create(max_candidates=2,max_weight_updates=1,timeout=60)
        cmd=ar.arguments(self.root,self.state,'finish','auto_graph_H');self.assertEqual(cmd[0],sys.executable)
        self.assertIn('--authorize-iucr-upload',cmd);self.assertEqual(cmd[cmd.index('--timeout')+1],'60')
    def test_existing_run_never_overwritten(self):
        self.create()
        with self.assertRaises(ValueError):ar.create(self.config,self.root)


class AutomaticReviewPropagationTests(unittest.TestCase):
    def test_credit_survives_factor_embedding_and_delivery_cache_boundary(self):
        from crystal_runtime import REFLECTION_TAGS,freeze_bundle
        from routine_finish import freeze_for_validation
        from cif_text_preflight import add_assistance_comment,CAIRYSTAL_COMMENT
        import gemmi
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);cif=root/'input.cif';fcf=root/'input.fcf'
            cif.write_text('data_x\n_cell_length_a 10\n')
            doc=gemmi.cif.Document();b=doc.add_new_block('f');loop=b.init_loop('',REFLECTION_TAGS)
            loop.add_row(['1']*len(REFLECTION_TAGS));doc.write_file(str(fcf))
            audit={'files':{'cif':str(cif),'fcf':str(fcf)},'has_embedded_structure_factors':False}
            frozen=root/'frozen';freeze_for_validation(audit,frozen,root/'credit.json')
            expected=sha(frozen/'model.cif');self.assertIn(CAIRYSTAL_COMMENT,(frozen/'model.cif').read_bytes())
            self.assertEqual(len(gemmi.cif.read_file(str(frozen/'model.cif')).sole_block().find(REFLECTION_TAGS)),1)
            delivery=root/'delivery';freeze_bundle({'files':{'cif':str(frozen/'model.cif'),'fcf':str(frozen/'model.fcf')},'has_embedded_structure_factors':True},delivery,'model')
            add_assistance_comment(delivery/'model.cif',root/'delivery_credit.json')
            self.assertEqual(sha(delivery/'model.cif'),expected)
            self.assertEqual(cif.read_text(),'data_x\n_cell_length_a 10\n')

    def test_bounded_review_mode_reaches_routine_finish(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);stage=root/'session/stages/test';stage.mkdir(parents=True);(stage/'model.res').write_text('synthetic')
            write_json(root/'runtime_profile.json',{'renderer':'word'})
            review=root/'review.json';write_json(review,{'chemistry_and_h_reviewed':True,'basis':'synthetic fixture','review_mode':'bounded_automatic_rules'})
            state={'prior_conversation_exposure':False,'events':[]};a=SimpleNamespace(name='finish',source='test',review=str(review),timeout=60,max_weight_updates=1,deliver=False,authorize_iucr_upload=False)
            seen={}
            def routine(config,*args):
                seen.update(ar.read(config));return {'status':'needs_alert_review'},None
            with patch.object(cp,'checked',return_value={}),patch('candidate_packet.factual_annotations',return_value={}),patch('crystal_session.prepare'),patch('routine_finish.finish',side_effect=routine):cp.finish(root,state,a)
            self.assertEqual(seen['review']['review_mode'],'bounded_automatic_rules')


if __name__=='__main__':unittest.main()
