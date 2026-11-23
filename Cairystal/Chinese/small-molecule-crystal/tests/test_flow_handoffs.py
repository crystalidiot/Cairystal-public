"""State transitions use synthetic fixtures; no crystallographic acceptance claims."""
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import crystal_autorun as autorun
import deliver_ready
from crystal_runtime import sha, write_json


class HandoffTests(unittest.TestCase):
    def setUp(self):
        t=tempfile.TemporaryDirectory();self.addCleanup(t.cleanup)
        self.root=Path(t.name);self.pipeline=self.root/'pipeline';self.finish=self.pipeline/'finish'
        self.finish.mkdir(parents=True)

    def local(self,sub,alerts):
        model=self.finish/sub/'frozen';model.mkdir(parents=True)
        for ext in ['cif','fcf']:(model/('model.'+ext)).write_text(sub+ext)
        validation=model.parent/'local_validation';validation.mkdir()
        write_json(validation/'local_validation.json',{'validation_complete':True,
            'input_sha256':{e:sha(model/('model.'+e)) for e in ['cif','fcf']},
            'validated_counts':{level:sum(a['level']==level for a in alerts) for level in ['A','B']},
            'alerts':{'alerts':alerts}})
        return model,validation

    def selected(self):
        self.local('',[dict(code='919',level='B',text='old reflection warning')])
        model,validation=self.local('working_omit',[])
        write_json(self.pipeline/'pipeline.json',{'finish_root':str(self.finish)})
        write_json(self.finish/'state.json',{'selected':str(model),'selected_omit':{'selected':True},'local_validation_directory':str(validation)})
        return {'pipeline_seal':autorun.seal(self.pipeline)}

    def test_selected_report_does_not_show_old_baseline_B(self):
        result=autorun.local_report_at_checkpoint(self.root,self.selected())
        self.assertEqual(result['counts'],{'A':0,'B':0})
        self.assertIn('working_omit',result['record'])

    def test_changed_selection_is_not_silently_adopted(self):
        state=self.selected();write_json(self.finish/'state.json',{'selected':str(self.finish/'frozen')})
        self.assertIsNone(autorun.local_report_at_checkpoint(self.root,state)['counts'])

    def test_wrong_selected_reflections_are_rejected(self):
        state=self.selected();p=self.finish/'working_omit/frozen/model.fcf';p.write_text('changed')
        # Seal has changed, but validation is still bound to the preceding FCF.
        state['pipeline_seal']=autorun.seal(self.pipeline)
        self.assertIsNone(autorun.local_report_at_checkpoint(self.root,state)['counts'])

    def report_state(self,target=True):
        dr=self.finish/'delivery_run';dr.mkdir()
        write_json(self.finish/'config.json',{'data_dir':str(self.root/'raw')} if target else {})
        return {'status':'awaiting_visual_review','code_sha256':{p.name:sha(p) for p in Path(deliver_ready.__file__).parent.glob('*.py')}}

    def test_resumed_delivery_runs_qa_and_exports_once(self):
        state=self.report_state();write_json(self.finish/'state.json',state)
        def final(a):
            self.assertEqual(a.data_dir,str(self.root/'raw'));self.assertFalse(a.reviewed_zh)
            write_json(Path(a.run)/'result.json',{'status':'delivery_complete_needs_scientific_review','customer_delivery':{'directory':str(self.root/'raw/Cairystal')},'customer_notice':'ready','zip':{}})
        with patch('report_autoqa.run',return_value={'status':'automatic_checks_passed','findings':[]}) as qa,patch('crystal_delivery.finalize',side_effect=final) as seal,patch.object(deliver_ready,'_run') as native:
            result=deliver_ready.run(self.finish,complete=True)
            self.assertEqual(result['status'],'delivery_complete_needs_scientific_review')
            qa.assert_called_once();seal.assert_called_once();native.assert_not_called()

    def test_report_failure_never_publishes(self):
        state=self.report_state()
        with patch('report_autoqa.run',return_value={'status':'needs_review','findings':['official A/B']}) as qa,patch('crystal_delivery.finalize') as seal:
            result=deliver_ready.complete_artifacts(self.finish,state)
            self.assertEqual(result['status'],'needs_report_review');seal.assert_not_called()

    def test_missing_destination_does_not_guess_intermediate_folder(self):
        state=self.report_state(False)
        with patch('report_autoqa.run',return_value={'status':'automatic_checks_passed','findings':[]}),patch('crystal_delivery.finalize') as seal:
            result=deliver_ready.complete_artifacts(self.finish,state)
            self.assertEqual(result['status'],'awaiting_visual_review');self.assertIn('--data-dir',result['next_step']);seal.assert_not_called()

    def test_new_upload_still_needs_authorization(self):
        state=self.report_state();state['status']='ready_for_official_delivery';write_json(self.finish/'state.json',state)
        with self.assertRaisesRegex(ValueError,'authorized'):deliver_ready.run(self.finish,complete=True)

    def test_unresolved_scientific_status_does_not_enter_qa(self):
        with patch('report_autoqa.run') as qa:
            state={'status':'needs_alert_review'}
            self.assertEqual(deliver_ready.complete_artifacts(self.finish,state),state);qa.assert_not_called()
