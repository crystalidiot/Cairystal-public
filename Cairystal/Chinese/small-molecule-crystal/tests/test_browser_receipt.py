import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from urllib.error import HTTPError

import iucr_validation as iv
from iucr_browser import FORM, SUBMIT

PAGE = "<a href='/test/job/checkcif.pdf'>PDF</a><a href='/test/job/ckf.html'>FCF</a>"
FIELDS = (' '.join(f'<input name="{k}">' for k in [*iv.OPTIONS,'filecif'])).encode()


class BrowserReceiptTests(unittest.TestCase):
    def run_receipt(self, responses, browser=None):
        with tempfile.TemporaryDirectory() as tmp:
            dest = Path(tmp)
            record = {}
            with patch.object(iv, 'fetch', side_effect=responses), patch.object(iv.iucr_browser, 'submit', side_effect=browser) as submit:
                try:
                    iv.get_receipt(b'data_fresh\r\n', record, dest, 4)
                finally:
                    self.calls = submit.call_count
            return json.loads((dest/'submission.json').read_text('utf-8'))

    def fake_browser(self, payload, options, timeout, checkpoint, save):
        self.assertEqual(payload, b'data_fresh\r\n')
        self.assertEqual(options, iv.OPTIONS)
        checkpoint('submitting', {})
        save(PAGE, SUBMIT)
        checkpoint('receipt_saved', {})

    def test_explicit_post_403_uses_frozen_bytes(self):
        record = self.run_receipt([(FIELDS,FORM), HTTPError(SUBMIT,403,'Forbidden',{},None)], self.fake_browser)
        self.assertEqual(self.calls,1)
        self.assertEqual(record['state'],'reports_available')
        self.assertEqual(record['ckf_url'], FORM+'test/job/ckf.html')

    def test_explicit_form_403(self):
        record = self.run_receipt([HTTPError(FORM,403,'Forbidden',{},None)], self.fake_browser)
        self.assertEqual(record['browser']['direct_stage'],'form_get')
        self.assertEqual(self.calls,1)

    def test_uncertain_or_restricted_does_not_repost(self):
        for error in (TimeoutError(), HTTPError(SUBMIT,503,'busy',{},None), HTTPError(SUBMIT,403,'cooldown',{'Retry-After':'20'},None),
                      HTTPError(FORM+'elsewhere',403,'redirect',{},None), HTTPError(SUBMIT,401,'login',{},None)):
            with self.subTest(error=str(error)), self.assertRaises(OSError):
                self.run_receipt([(FIELDS,FORM), error])
            self.assertEqual(self.calls,0)

    def test_success_direct_uses_no_browser(self):
        record = self.run_receipt([(FIELDS,FORM),(PAGE.encode(),SUBMIT)])
        self.assertEqual(record['route'],'direct_http')
        self.assertEqual(self.calls,0)

    def test_ambiguous_receipts_are_retained_without_resubmission(self):
        for html in (PAGE.replace('/test/job/ckf','/other/ckf'),PAGE.replace('/test/job/ckf','https://example.org/ckf'),
                     PAGE+'<a href="/other/checkcif.pdf">extra</a>', '<p>queued</p>'):
            with self.subTest(html=html), self.assertRaises(ValueError):
                self.run_receipt([(FIELDS,FORM),(html.encode(),SUBMIT)])
            self.assertEqual(self.calls,0)

    def test_browser_failure_does_not_loop(self):
        with self.assertRaises(TimeoutError):
            self.run_receipt([(FIELDS,FORM),HTTPError(SUBMIT,403,'Forbidden',{},None)],TimeoutError())
        self.assertEqual(self.calls,1)
