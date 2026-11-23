import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch, Mock

from bilingual_report import build_from_dataset
from crystal_autorun import create
from crystal_runtime import sha
from intake_once import export, form
from interface_language import selected
import iucr_validation as iucr
from route_problem import pasted_alerts


def load(path):
    return json.loads(path.read_text('utf-8'))


def save(path, data):
    path.write_text(json.dumps(data), 'utf-8')
    return path


class PairingTests(unittest.TestCase):
    def setUp(self):
        tmp=tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.base=Path(tmp.name)
        self.raw=self.base/'sample'
        self.raw.mkdir()
        self.hkl=self.raw/'a.hkl'
        self.hkl.write_text('hkl A','ascii')
        self.record=self.raw/'a.pcf'
        self.record.write_text('_exptl_crystal_colour green\n_exptl_crystal_description block\n','ascii')
        self.known=save(self.base/'known.json',{'schema':1,'data_dir':str(self.raw),'elements':['C','O']})

    def paired(self):
        return form(self.base/'form',known=self.known,hkl=self.hkl,paired_records=[self.record],
                    pairing_basis='Acquisition record for A, confirmed in the sample log')

    def accepted(self):
        folder=self.paired()
        ledger=load(folder/'metadata_reuse.json')
        answers=load(self.known)
        answers.update(metadata_ledger={key:ledger[key] for key in ('path','sha256','hkl','hkl_sha256')},
                       dimensions_mm=[.05,.051,.052],observations_confirmed=True,iucr_upload='deny')
        config=save(self.base/'profile.json',{'python':'unused'})
        return export(save(self.base/'answers.json',answers),self.base/'accepted',config)

    def test_only_size_is_missing_and_measured_fields_have_sources(self):
        folder=self.paired()
        plan=load(folder/'question_plan.json')
        question=('Please provide only the missing fields: three dimensions (mm)' if selected()=='en'
                  else '请只补充缺失项：三维尺寸（mm）')
        self.assertEqual(plan['questions'],[question])
        meta=load(folder/'metadata_reuse.json')
        self.assertEqual(meta['hkl_sha256'],sha(self.hkl))
        self.assertEqual(meta['provenance']['_exptl_crystal_colour'][0]['source_sha256'],sha(self.record))

    def test_foreign_record_rejected_before_collection(self):
        b=self.raw/'b.pcf'
        b.write_bytes(self.record.read_bytes())
        with self.assertRaisesRegex(ValueError,'stem'):
            form(self.base/'bad',hkl=self.hkl,paired_records=[b],pairing_basis='claimed pairing')
        self.assertFalse((self.base/'bad').exists())

    def test_matching_name_alone_is_insufficient(self):
        with self.assertRaisesRegex(ValueError,'basis'):
            form(self.base/'bad',hkl=self.hkl,paired_records=[self.record])
        self.assertFalse((self.base/'bad').exists())

    def test_same_directory_has_two_reflections(self):
        b=self.raw/'b.hkl'
        b.write_text('hkl B')
        _,out=self.accepted()
        cfg=load(out/'autorun_config.json')
        self.assertEqual(cfg['stem'],'a')
        fields=load(out/'specimen.json')['cif_fields']
        self.assertEqual(fields['_exptl_crystal_colour'],'green')
        self.assertEqual(fields['_exptl_crystal_size_max'],.052)
        cfg['stem']='b'
        with self.assertRaisesRegex(ValueError,'different HKL'):
            create(save(self.base/'badjob.json',cfg),self.base/'wrong_run')
        with self.assertRaisesRegex(ValueError,'Multiple HKL'):
            form(self.base/'ambiguous',data_dir=self.raw,metadata_ledger=self.base/'form/ledger/metadata_ledger.json')

    def test_changed_hkl_stops_at_start(self):
        _,out=self.accepted()
        self.hkl.write_text('new data with the same name')
        with self.assertRaisesRegex(ValueError,'HKL changed'):
            create(out/'autorun_config.json',self.base/'wrong_run')

    def test_single_anonymous_rigaku_record(self):
        od=self.raw/'cif_od'
        od.write_bytes(self.record.read_bytes())
        folder=form(self.base/'form',hkl=self.hkl,paired_records=[od],pairing_basis='Documented Rigaku acquisition')
        self.assertEqual(load(folder/'metadata_reuse.json')['values']['habit'],'block')
        (self.raw/'b.hkl').write_text('B')
        with self.assertRaisesRegex(ValueError,'multi-sample'):
            form(self.base/'ambiguous',hkl=self.hkl,paired_records=[od],pairing_basis='Documented acquisition')


class OfficialReportTests(unittest.TestCase):
    report=('No syntax errors\nStructure factors have been supplied\nSHFSU_01_ALERT_3_G Entry\n'
            'PLAT242_ALERT_2_B C3 high\nPLAT242_ALERT_2_B C7 high\n'
            '0 ALERT level A =\n2 ALERT level B =\n0 ALERT level C =\n1 ALERT level G =')

    def test_paste_and_official_preserve_names_and_occurrences(self):
        output=iucr.parse_official_text(self.report)
        entries=pasted_alerts(self.report)
        self.assertEqual(output['counts'],{'A':0,'B':2,'C':0,'G':1})
        self.assertEqual(output['alerts'][0]['full_code'],entries[0]['id'])
        self.assertEqual(output['alerts'][0]['code'],'SHFSU01_ALERT_3_G')
        self.assertEqual(entries[1]['occurrences'],['C3 high','C7 high'])
        with self.assertRaisesRegex(ValueError,'counts inconsistent'):
            iucr.parse_official_text(self.report.replace('2 ALERT level B','1 ALERT level B'))

    def test_receipt_checks_expected_cif_without_fetching_or_writing(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            cif=root/'submitted.cif'
            cif.write_bytes(b'data_example\n')
            receipt=save(root/'submission.json',{'schema':1,'options':iucr.OPTIONS,'cif_sha256':sha(cif),
                'state':'reports_available','pdf_url':'https://checkcif.iucr.org/run/checkcif.pdf',
                'ckf_url':'https://checkcif.iucr.org/run/ckf.html'})
            before=sha(receipt)
            wrong=root/'wrong.cif'
            wrong.write_bytes(b'data_other\n')
            with patch.object(iucr,'fetch') as fetch:
                with self.assertRaisesRegex(ValueError,'Selected CIF hash differs'):
                    iucr.recover(root,expected_cif=wrong)
                self.assertIsNone(iucr.recover(root,expected_cif=cif,check_only=True)[1])
                fetch.assert_not_called()
            self.assertEqual(sha(receipt),before)

    def test_inconsistent_partial_receipt_stops_readonly_check(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            cif=root/'submitted.cif'
            cif.write_text('data_test')
            rec={'schema':1,'options':iucr.OPTIONS,'cif_sha256':sha(cif),'state':'pdf_downloaded',
                 'pdf_url':'https://checkcif.iucr.org/one/checkcif.pdf','ckf_url':'https://checkcif.iucr.org/two/ckf.html'}
            save(root/'submission.json',rec)
            with patch.object(iucr,'fetch') as fetch:
                with self.assertRaisesRegex(ValueError,'different jobs'):
                    iucr.recover(root,expected_cif=cif,check_only=True)
                rec['downloaded_pdf']={'sha256':'missing PDF'}
                save(root/'submission.json',rec)
                with self.assertRaisesRegex(ValueError,'Retained PDF'):
                    iucr.recover(root,expected_cif=cif,check_only=True)
                fetch.assert_not_called()

    def test_download_detects_replaced_pdf_before_acceptance(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            (root/'submitted.cif').write_bytes(b'cif')
            rec={'schema':1,'options':iucr.OPTIONS,'cif_sha256':sha(root/'submitted.cif'),
                 'pdf_url':'https://checkcif.iucr.org/test/checkcif.pdf','ckf_url':'https://checkcif.iucr.org/test/ckf.html'}
            def fetch(url,*a,**kw):
                if url.endswith('.pdf'):return b'%PDF-stub',url
                (root/'IUCr_checkCIF.pdf').write_bytes(b'%PDF-replaced')
                return b'FCF-File Validation LIST4',url
            page=Mock()
            page.extract_text.return_value=self.report
            with patch.object(iucr,'fetch',side_effect=fetch),patch('pypdf.PdfReader',return_value=Mock(pages=[page])):
                with self.assertRaisesRegex(ValueError,'PDF|pdf'):
                    iucr.download_reports(root,rec)
            self.assertNotEqual(load(root/'submission.json')['state'],'completed')

    def test_report_dataset_for_other_cif_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            cif=root/'model.cif'
            cif.write_text('data_other')
            with self.assertRaisesRegex(ValueError,'CIF changed'):
                build_from_dataset(cif,{'cif_sha256':hashlib.sha256(b'data_sample').hexdigest()},{},{},root,root)
