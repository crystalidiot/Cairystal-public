"""Synthetic dispatch tests; the real-package replay is recorded outside the skill."""
import copy, json, sys, tempfile, unittest
import shutil
from pathlib import Path
from unittest.mock import patch
from contextlib import redirect_stdout
from io import StringIO

import crystal_autorun as ar
import crystal_pipeline as cp
import coordinator_completion as cc
from crystal_runtime import sha, write_json


class CompletionSyncTests(unittest.TestCase):
    def setUp(self):
        tmp=tempfile.TemporaryDirectory();self.addCleanup(tmp.cleanup)
        self.root=Path(tmp.name)/'run';self.pipe=self.root/'pipeline'
        self.finish=self.pipe/'finish';self.dr=self.finish/'delivery_run'
        self.raw=self.root.parent/'raw';self.target=self.raw/'Cairystal'
        for p in [self.dr/'delivery',self.target,self.root/'logs']:p.mkdir(parents=True)
        self.hkl=self.raw/'input.hkl';self.hkl.write_text('current raw reflections')
        names=['model.cif','model.res','model.hkl','model.fcf','model.lst','IUCr_checkCIF.pdf',
               '晶体学报表_中文.docx','Crystallographic_Report_EN.docx']
        for name in names:
            content=self.hkl.read_bytes() if name=='model.hkl' else ('synthetic '+name).encode()
            (self.dr/'delivery'/name).write_bytes(content);(self.target/name).write_bytes(content)
        files=dict(final_cif='model.cif',official_checkcif_pdf='IUCr_checkCIF.pdf',word_zh=names[-2],word_en=names[-1])
        self.receipt=dict(status='exported',source_run=str(self.dr),source_directory=str(self.dr/'delivery'),
                          directory=str(self.target),data_directory=str(self.raw),
                          files={k:str(self.target/v) for k,v in files.items()},
                          exported_hashes={n:sha(self.target/n) for n in names})
        self.data=dict(status='delivery_complete_needs_scientific_review',customer_delivery=self.receipt,
                       customer_notice='All four deliverables are ready',inputs={'hkl':sha(self.hkl)},zip=None)
        write_json(self.dr/'result.json',self.data);write_json(self.dr/'customer_delivery.json',self.receipt)
        self.ps=dict(status='complete',finish_root=str(self.finish),delivery=str(self.target),customer_delivery=self.receipt,
                     intake={'inputs':{'hkl':{'path':str(self.hkl),'sha256':sha(self.hkl)}}},finished_at='2026-11-26T10:00:00+00:00')
        write_json(self.pipe/'pipeline.json',self.ps)
        self.state=dict(status='needs_attention',category='chemical_graph_required',reason='old stop',next_step='old',
                        skill_sha256=ar.stamp(),bindings={},pipeline_seal={'old-checkpoint':'before external completion'},
                        source_hkl={'path':str(self.hkl),'sha256':sha(self.hkl)},
                        options={'data_dir':str(self.raw),'deliver':True},actions=[{'action':'solve','status':'checkpointed'}],
                        completed_actions=['solve'],scientific_correctness='not_established_by_automation')
        ar.save(self.root,self.state);write_json(self.root/'handoff.json',{'category':'chemical_graph_required'})
        self.contract=dict(status='artifacts_complete',official_counts={'A':0,'B':1,'C':2,'G':0},
                           artifacts={n:str(self.dr/'delivery'/n) for n in names},missing_artifacts=[],verification_issues=[])
        self.addCleanup(patch.stopall)
        patch('delivery_contract.audit',return_value=self.contract).start()
        patch('crystal_autorun.default_runner',side_effect=AssertionError('Must not compute or upload')).start()

    def test_external_completion_repairs_state_without_adding_fake_actions(self):
        old=copy.deepcopy(self.state);before=ar.seal(self.pipe)
        self.assertTrue(cc.reconcile(self.root,self.state))
        self.assertEqual(self.state['status'],'complete');self.assertNotIn('category',self.state)
        self.assertEqual(self.state['completed_actions'],['solve'])
        self.assertEqual(self.state['official_counts'],self.contract['official_counts'])
        self.assertEqual(ar.read(self.root/'completion_sync/previous_autorun.json'),old)
        self.assertEqual(ar.read(self.root/'handoff.json')['status'],'resolved')
        self.assertEqual(ar.seal(self.pipe),before)
        self.assertEqual(self.state['scientific_correctness'],'not_established_by_automation')

    def test_resume_is_idempotent_and_does_not_call_runner(self):
        cc.reconcile(self.root,self.state);before=ar.seal(self.root)
        def no_run(*a):self.fail('Unexpected compute/upload')
        for _ in range(2):self.assertEqual(ar.drive(self.root,self.state,no_run)['status'],'complete')
        self.assertEqual(ar.seal(self.root),before)

    def test_child_lock_release_notifies_parent_and_refreshes_page(self):
        with patch.object(ar,'publish') as publish:
            with cp.run_lock(self.pipe):self.assertTrue((self.pipe/'pipeline.lock').exists())
            self.assertEqual(ar.read(self.root/'autorun.json')['status'],'complete');publish.assert_called_once()

    def test_callback_defers_when_coordinator_owns_lock(self):
        with ar.lock(self.root):cc.notify_parent(self.pipe)
        self.assertEqual(ar.read(self.root/'autorun.json')['status'],'needs_attention')
        self.assertFalse((self.root/'completion_sync_error.json').exists())

    def test_missing_pdf_cannot_claim_complete(self):
        (self.target/'IUCr_checkCIF.pdf').unlink()
        with self.assertRaises((ValueError,OSError)):cc.reconcile(self.root,self.state)
        self.assertEqual(self.state['status'],'needs_attention')

    def test_versioned_customer_export_directory_supported(self):
        destination=self.target/'运行_20261126_test';destination.mkdir()
        for name in self.receipt['exported_hashes']:
            shutil.copy2(self.target/name,destination/name)
        self.receipt['directory']=str(destination)
        self.receipt['files']={k:str(destination/Path(v).name) for k,v in self.receipt['files'].items()}
        self.ps['delivery']=str(destination)
        write_json(self.dr/'customer_delivery.json',self.receipt);write_json(self.dr/'result.json',self.data)
        write_json(self.pipe/'pipeline.json',self.ps)
        self.assertTrue(cc.reconcile(self.root,self.state));self.assertEqual(self.state['delivery'],str(destination))

    def test_tampered_word_cannot_claim_complete(self):
        (self.target/'晶体学报表_中文.docx').write_bytes(b'changed')
        with self.assertRaisesRegex(ValueError,'changed'):cc.reconcile(self.root,self.state)

    def test_incomplete_or_unreviewed_child_remains_pending(self):
        for status in ['awaiting_visual_review','needs_report_review','blocked','running']:
            write_json(self.pipe/'pipeline.json',{**self.ps,'status':status})
            self.assertFalse(cc.reconcile(self.root,self.state));self.assertEqual(self.state['status'],'needs_attention')

    def test_missing_official_validation_not_adopted(self):
        self.contract.update(status='incomplete',verification_issues=['No valid IUCr receipt'])
        with self.assertRaisesRegex(ValueError,'incomplete'):cc.reconcile(self.root,self.state)

    def test_different_hkl_is_rejected(self):
        self.data['inputs']['hkl']='wrong';write_json(self.dr/'result.json',self.data)
        with self.assertRaises(ar.WrongSpecimen):cc.reconcile(self.root,self.state)

    def test_finalization_required(self):
        self.data['status']='awaiting_visual_review';write_json(self.dr/'result.json',self.data)
        with self.assertRaisesRegex(ValueError,'review'):cc.reconcile(self.root,self.state)

    def test_wrong_export_record_rejected(self):
        self.receipt['source_run']=str(self.root.parent/'other')
        write_json(self.dr/'customer_delivery.json',self.receipt);write_json(self.dr/'result.json',self.data)
        write_json(self.pipe/'pipeline.json',self.ps)
        with self.assertRaisesRegex(ValueError,'another'):cc.reconcile(self.root,self.state)

    def test_pending_action_not_overridden(self):
        self.state['pending']='finish'
        with self.assertRaisesRegex(ValueError,'active'):cc.reconcile(self.root,self.state)

    def test_child_lock_not_overridden(self):
        (self.pipe/'pipeline.lock').write_text('active')
        with self.assertRaisesRegex(ValueError,'active'):cc.reconcile(self.root,self.state)

    def test_changed_original_input_rejected(self):
        self.hkl.write_text('changed original')
        with self.assertRaisesRegex(ValueError,'Original'):cc.reconcile(self.root,self.state)

    def test_empty_export_hashes_rejected(self):
        self.receipt['exported_hashes']={}
        write_json(self.dr/'customer_delivery.json',self.receipt);write_json(self.dr/'result.json',self.data)
        write_json(self.pipe/'pipeline.json',self.ps)
        with self.assertRaisesRegex(ValueError,'omit'):cc.reconcile(self.root,self.state)

    def test_explicit_old_version_repair_preserves_execution_version(self):
        self.state['skill_sha256']={'old':'old'}
        with self.assertRaisesRegex(ValueError,'changed'):cc.reconcile(self.root,self.state)
        self.assertTrue(cc.reconcile(self.root,self.state,explicit=True))
        self.assertEqual(self.state['skill_sha256'],{'old':'old'})
        self.assertEqual(ar.drive(self.root,self.state)['status'],'complete')

    def test_no_unfinished_version_migration(self):
        write_json(self.pipe/'pipeline.json',{**self.ps,'status':'needs_scientific_review'})
        self.state['skill_sha256']={'old':'old'}
        self.assertFalse(cc.reconcile(self.root,self.state,explicit=True))
        self.assertEqual(ar.drive(self.root,self.state)['category'],'integrity_error')

    def test_changed_child_after_completion_does_not_pass_resume(self):
        cc.reconcile(self.root,self.state)
        (self.pipe/'extra.res').write_text('outside edit')
        self.assertEqual(ar.drive(self.root,self.state)['category'],'delivery_integrity_error')

    def test_status_cli_recovers_and_returns_complete(self):
        with patch.object(sys,'argv',['autorun','status','--run',str(self.root)]),patch.object(ar,'publish',side_effect=lambda r,s:dict(status=s['status'])),redirect_stdout(StringIO()) as out:
            self.assertEqual(ar.main(),0)
        self.assertEqual(json.loads(out.getvalue())['status'],'complete')

    def test_resume_with_repeat_authorization_does_not_amend_finished_job(self):
        with patch.object(sys,'argv',['autorun','resume','--run',str(self.root),'--authorize-iucr-upload']),patch.object(ar,'publish',return_value={}),patch.object(ar,'amend') as amend,redirect_stdout(StringIO()):
            self.assertEqual(ar.main(),0);amend.assert_not_called()


if __name__=='__main__':unittest.main()
