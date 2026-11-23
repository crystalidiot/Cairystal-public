"""Offline delivery tests; synthetic files, mocked official validation, no upload."""
import contextlib,io,json,tempfile,unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
import customer_delivery as cd
import test_delivery_completion as fixtures
from crystal_runtime import sha,write_json

class CustomerDeliveryTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup);self.base=Path(self.tmp.name)
        self.root=self.base/'work';self.root.mkdir();self.data=self.base/'原始数据';self.data.mkdir()
        self.raw=self.data/'raw.hkl';self.raw.write_bytes(b'untouched synthetic raw input')
        helper=fixtures.CompletionContracts();helper.p=self.root;helper.complete_fixture()
        self.source=self.root/'delivery'
        seal={p.name:sha(p) for p in self.source.iterdir()}
        self.record={'stem':'model','status':'delivery_complete_needs_scientific_review','delivery_seal':seal,'official':{'counts':{'A':1,'B':2}},'AB_alerts':[{'level':'B','code':'234'}],'data_directory':str(self.data)}
        write_json(self.source/'SHA256SUMS.json',seal);self.save()
        official=patch('iucr_validation.validate_saved',return_value=({},{'counts':{'A':1,'B':2}}));official.start();self.addCleanup(official.stop)
        fab=patch('squeeze_bundle.companion_fab',return_value=None);fab.start();self.addCleanup(fab.stop)
    def save(self):write_json(self.root/'result.json',self.record)
    def test_first_copy_exact_four_files_and_input_unchanged(self):
        raw=sha(self.raw);r=cd.publish(self.root,self.data)
        self.assertEqual(Path(r['directory']),self.data/'Cairystal');self.assertEqual(sha(self.raw),raw)
        self.assertEqual(len(r['files']),4)
        for n,h in r['source_hashes'].items():self.assertEqual(sha(Path(r['directory'])/n),h)
        self.assertIn(str(self.data/'Cairystal'),r['notice']);self.assertIn('A/B',r['notice'])
    def test_successful_retry_no_duplicate(self):
        a=cd.publish(self.root,self.data);b=cd.publish(self.root,self.data)
        self.assertEqual(a,b);self.assertFalse(list((self.data/'Cairystal').glob('运行_*')))
    def test_existing_folder_and_old_files_not_overwritten(self):
        old=self.data/'Cairystal';old.mkdir();(old/'model.cif').write_text('old crystal')
        r=cd.publish(self.root,self.data);self.assertEqual(Path(r['directory']).parent,old)
        self.assertEqual((old/'model.cif').read_text(encoding='utf-8'),'old crystal')
    def test_modified_customer_copy_is_not_silently_replaced(self):
        r=cd.publish(self.root,self.data);p=Path(r['files']['final_cif']);p.write_text('user edits')
        with self.assertRaisesRegex(ValueError,'customer copy changed'):cd.publish(self.root,self.data)
        self.assertEqual(p.read_text(encoding='utf-8'),'user edits')
    def test_missing_word_blocks_export(self):
        (self.source/'晶体学报表_中文.docx').unlink()
        with self.assertRaisesRegex(ValueError,'incomplete'):cd.publish(self.root,self.data)
        self.assertFalse((self.data/'Cairystal').exists())
    def test_stale_pdf_blocks_export(self):
        (self.source/'IUCr_checkCIF.pdf').write_bytes(b'stale')
        with self.assertRaises(ValueError):cd.publish(self.root,self.data)
        self.assertFalse((self.data/'Cairystal').exists())
    def test_unreviewed_blocks_export(self):
        self.record['status']='awaiting_visual_review';self.save()
        with self.assertRaisesRegex(ValueError,'Finalize'):cd.publish(self.root,self.data)
    def test_missing_destination_not_created(self):
        with self.assertRaisesRegex(ValueError,'does not exist'):cd.publish(self.root,self.base/'missing')
        self.assertFalse((self.base/'missing').exists())
    def test_target_file_conflict_preserved(self):
        (self.data/'Cairystal').write_text('existing file')
        with self.assertRaisesRegex(ValueError,'not a directory'):cd.publish(self.root,self.data)
        self.assertEqual((self.data/'Cairystal').read_text(encoding='utf-8'),'existing file')
    def test_nested_work_target_rejected(self):
        with self.assertRaisesRegex(ValueError,'inside'):cd.publish(self.root,self.source)
    def test_copy_failure_preserves_verified_source(self):
        h=sha(self.source/'model.cif')
        with patch.object(cd.shutil,'copy2',side_effect=PermissionError('synthetic read-only destination')):
            with self.assertRaises(PermissionError):cd.publish(self.root,self.data)
        self.assertFalse((self.data/'Cairystal').exists());self.assertEqual(sha(self.source/'model.cif'),h)
        self.assertEqual(json.loads((self.root/'customer_delivery_attempt.json').read_text(encoding='utf-8'))['status'],'failed')
    def test_checksum_mismatch_blocks_export(self):
        write_json(self.source/'SHA256SUMS.json',{})
        with self.assertRaisesRegex(ValueError,'checksum'):cd.publish(self.root,self.data)
    def test_copy_only_recovery_updates_completion_record(self):
        self.record.update(status='customer_export_failed',customer_export_error='old path failure');self.save()
        r=cd.publish(self.root,self.data);saved=json.loads((self.root/'result.json').read_text('utf-8'))
        self.assertEqual(saved['status'],'delivery_complete_needs_scientific_review')
        self.assertEqual(saved['customer_delivery']['directory'],r['directory']);self.assertNotIn('customer_export_error',saved)
    def test_pipeline_summary_links_customer_folder_outside_work(self):
        import crystal_pipeline as cp
        r=cd.publish(self.root,self.data)
        state={'status':'complete','events':[],'delivery':r['directory'],'customer_notice':r['notice'],'prior_conversation_exposure':False}
        report={'elapsed_wall_s':1,'timed_actions_s':1,'between_actions_s':0,'token_usage':{'exact_total':None}}
        with patch.object(cp,'make_summary',return_value=report):cp.render_summary(self.root,state)
        text=(self.root/'index.html').read_text('utf-8')
        for path in r['files'].values():self.assertIn(Path(path).as_uri(),text)
        self.assertIn(str(self.data/'Cairystal'),text)
    def test_finalize_exports_and_emits_notice(self):
        import crystal_delivery
        self.record.update(status='awaiting_visual_review',qa_seal={},input_paths={},inputs={},report_pages={'zh':1,'en':1},viewer_auto_open=False);self.save()
        a=SimpleNamespace(run=str(self.root),data_dir=str(self.data),reviewed_zh=True,reviewed_en=True,reviewed_official=True,review_note='Synthetic integration fixture, not a scientific review')
        with patch('structure_viewer.open_generated',return_value={'status':'disabled'}),contextlib.redirect_stdout(io.StringIO()) as out:
            self.assertEqual(crystal_delivery.finalize(a),0)
        r=json.loads(out.getvalue());self.assertIn(str(self.data/'Cairystal'),r['customer_notice'])
        self.assertTrue(Path(r['customer_delivery']['files']['word_en']).exists())
    def test_finalize_copy_failure_not_reported_complete(self):
        import crystal_delivery
        self.record.update(status='awaiting_visual_review',qa_seal={},input_paths={},inputs={},report_pages={'zh':1,'en':1});self.save()
        a=SimpleNamespace(run=str(self.root),data_dir=str(self.data),reviewed_zh=True,reviewed_en=True,reviewed_official=True,review_note='Synthetic integration fixture')
        with patch.object(cd.shutil,'copy2',side_effect=PermissionError('blocked')):
            with self.assertRaises(PermissionError):crystal_delivery.finalize(a)
        self.assertEqual(json.loads((self.root/'result.json').read_text(encoding='utf-8'))['status'],'customer_export_failed')
        self.assertTrue((self.root/'structure_and_reports.zip').exists())

if __name__=='__main__':unittest.main()
