import json
from pathlib import Path
import tempfile
import time
from types import SimpleNamespace
import unittest
from unittest.mock import patch
from urllib.error import URLError

import crystal_autorun as autorun
import delivery_continue as continuation
import iucr_validation as iucr
from crystal_runtime import sha, write_json
from density_disorder import choose_screens


class CaseResume(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name)
        self.frozen=self.root/'frozen'
        self.frozen.mkdir()
        self.cif=self.frozen/'sample.cif'
        self.cif.write_bytes(b'data_example\n')
        self.hkl=self.frozen/'sample.hkl'
        self.hkl.write_bytes(b'original reflections')
        self.official=self.root/'official'
        self.official.mkdir()
        self.notes=self.root/'resume_notes.json'
        self.notes.write_text('{}')
        self.profile=self.root/'profile.json'
        self.profile.write_text('{}')
        self.receipt={'schema':1,'options':iucr.OPTIONS,'state':'awaiting_upload_authorization',
                      'post_may_have_started':False,'cif_sha256':sha(self.cif)}
        (self.official/'submitted.cif').write_bytes(self.cif.read_bytes())
        self.save_receipt()
        release=json.loads((Path(__file__).resolve().parents[1]/'release_info.json').read_text('utf8'))['release_id']
        write_json(self.root/'result.json',{'stem':'sample','inputs':{'hkl':sha(self.hkl)},
                   'workflow_version':{'release':release},'resume_binding':{'frozen_files':continuation.sealed_files(self.frozen),
                   'notes_sha256':sha(self.notes)}})

    def save_receipt(self):
        write_json(self.official/'submission.json',self.receipt)

    def test_wrong_case_rejected_before_writing(self):
        wrong=self.root/'wrong.hkl'
        wrong.write_bytes(b'some other sample')
        with self.assertRaisesRegex(ValueError,'Wrong specimen'):
            continuation.inspect(self.root,self.cif,wrong)
        self.assertFalse((self.root/'continue_delivery.lock').exists())

    def test_related_but_other_cif_version_rejected(self):
        other=self.root/'new.cif'
        other.write_bytes(b'data_new')
        with self.assertRaisesRegex(ValueError,'Wrong specimen'):
            continuation.inspect(self.root,other,self.hkl)

    def test_autorun_source_identity(self):
        state={'source_hkl':{'sha256':sha(self.hkl)},'options':{'case_id':'样品7'}}
        autorun.check_expected(self.root,state,self.hkl)
        self.assertEqual(autorun.specimen_identity(self.root,state)['case_id'],'样品7')
        with self.assertRaises(autorun.WrongSpecimen):
            autorun.check_expected(self.root,state,self.cif)

    def test_unknown_post_is_not_retried(self):
        self.receipt['state']='failed_or_submission_outcome_unknown'
        self.save_receipt()
        self.assertEqual(continuation.inspect(self.root,self.cif,self.hkl)['next'],'inspect_unknown_submission')
        args=SimpleNamespace(run=self.root,cif=self.cif,expected_hkl=self.hkl,inspect_only=False,timeout=1,
                             output=self.root.parent/'unused-output',profile=self.profile,authorize_iucr_upload=True)
        with patch.object(continuation,'verify_profile'),patch.object(iucr,'fetch') as network,self.assertRaisesRegex(ValueError,'may have been'):
            continuation.run(args)
        network.assert_not_called()

    def test_pending_does_not_imply_permission(self):
        (self.official/'submitted.cif').unlink()
        self.assertEqual(continuation.inspect(self.root,self.cif,self.hkl)['next'],'submit_only_with_authorization')
        args=SimpleNamespace(run=self.root,cif=self.cif,expected_hkl=self.hkl,inspect_only=False,timeout=1,
                             output=self.root.parent/'unused-output',profile=self.profile,authorize_iucr_upload=False)
        with patch.object(continuation,'verify_profile'),patch.object(iucr,'fetch') as network,self.assertRaisesRegex(ValueError,'authorization'):
            continuation.run(args)
        network.assert_not_called()

    def test_get_failure_records_no_post(self):
        with patch.object(iucr,'fetch',side_effect=URLError('offline')) as net,self.assertRaises(URLError):
            iucr.submit_snapshot(self.cif.read_bytes(),self.receipt,self.official,1,time.perf_counter())
        self.assertEqual(net.call_count,1)
        self.assertEqual(self.receipt['state'],'form_unreachable_before_submission')
        self.assertFalse(self.receipt['post_may_have_started'])

    def test_post_timeout_is_unknown(self):
        form=' '.join('name="'+v+'"' for v in [*iucr.OPTIONS,'filecif']).encode()
        with patch.object(iucr,'fetch',side_effect=[(form,iucr.iucr_browser.FORM),URLError('timeout')]) as net,self.assertRaises(URLError):
            iucr.submit_snapshot(self.cif.read_bytes(),self.receipt,self.official,1,time.perf_counter())
        self.assertEqual(net.call_count,2)
        self.assertTrue(self.receipt['post_may_have_started'])
        self.assertEqual(continuation.inspect(self.root,self.cif,self.hkl)['next'],'inspect_unknown_submission')

    def test_geometry_changes_ranking(self):
        result={'name':'first','status':'screen_complete','metrics':{'NPD_atoms':0,'R1_observed':.03},'bond_review':{'findings':[{}]}}
        other=dict(result,name='second',metrics={'R1_observed':.04},bond_review={'findings':[]})
        self.assertEqual(choose_screens([result,other],1)[0]['name'],'second')
