import json,tempfile,unittest,urllib.error
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
import iucr_validation as iv
from crystal_runtime import sha,write_json
from platon_execution import validation_ready,native_versions,embedded_reflections,rules_context
REPORT='No syntax errors\nStructure factors have been supplied\n0 ALERT level A =\n0 ALERT level B =\n0 ALERT level C =\n0 ALERT level G ='

class PDFPersistenceTests(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup);self.p=Path(self.tmp.name);(self.p/'submitted.cif').write_text('data_fixture')
  self.rec={'schema':1,'options':iv.OPTIONS,'cif_sha256':sha(self.p/'submitted.cif'),'pdf_url':'https://checkcif.iucr.org/unit/checkcif.pdf','ckf_url':'https://checkcif.iucr.org/unit/ckf.html','state':'reports_available'}
  self.reader=SimpleNamespace(pages=[SimpleNamespace(extract_text=lambda:REPORT)])
 def test_pdf_survives_failed_ckf_and_recovery_only_gets_ckf(self):
  calls=[]
  def fetch(url,**kwargs):
   calls.append(url)
   if url.endswith('.pdf'):return b'%PDF-unit-stub',url
   raise TimeoutError('FCF unavailable temporarily')
  with patch.object(iv,'fetch',side_effect=fetch),patch.object(iv.time,'sleep'),patch('pypdf.PdfReader',return_value=self.reader):
   with self.assertRaises(TimeoutError):iv.download_reports(self.p,self.rec)
  self.assertTrue((self.p/'IUCr_checkCIF.pdf').exists());self.assertEqual(self.rec['state'],'reports_download_failed');self.assertEqual(sum(x.endswith('.pdf') for x in calls),1)
  calls=[]
  def recovered(url,**kwargs):calls.append(url);return b'FCF-File Validation LIST4',url
  with patch.object(iv,'fetch',side_effect=recovered),patch('pypdf.PdfReader',return_value=self.reader):r,parsed=iv.recover(self.p)
  self.assertEqual(r['state'],'completed');self.assertEqual(calls,[self.rec['ckf_url']]);self.assertEqual(parsed['counts']['A'],0)
 def test_html_is_not_saved_with_pdf_extension(self):
  with patch.object(iv,'fetch',return_value=(b'<html>pending</html>',self.rec['pdf_url'])),patch.object(iv.time,'sleep'):
   with self.assertRaisesRegex(ValueError,'non-PDF'):iv.download_reports(self.p,self.rec)
  self.assertFalse((self.p/'IUCr_checkCIF.pdf').exists());self.assertEqual(len(self.rec['report_get_attempts']),3)
 def test_transient_get_recovers_without_post(self):
  calls=[]
  def fetch(url,**kw):
   self.assertNotIn('data',kw);calls.append(url)
   if len(calls)==1:raise TimeoutError('temporary')
   return b'%PDF-stub',url
  with patch.object(iv,'fetch',side_effect=fetch),patch.object(iv.time,'sleep'):self.assertEqual(iv.report_get(self.rec['pdf_url'],self.p,self.rec,'pdf'),b'%PDF-stub')
  self.assertEqual(len(calls),2)
 def test_permanent_403_does_not_repeat(self):
  error=urllib.error.HTTPError(self.rec['pdf_url'],403,'Forbidden',{},None)
  with patch.object(iv,'fetch',side_effect=error) as f,patch.object(iv.time,'sleep') as sleep:
   with self.assertRaises(urllib.error.HTTPError):iv.report_get(self.rec['pdf_url'],self.p,self.rec,'pdf')
   self.assertEqual(f.call_count,1);sleep.assert_not_called()
 def test_retained_pdf_tamper_stops_before_network(self):
  self.rec['downloaded_pdf']={'sha256':'wrong'};(self.p/'IUCr_checkCIF.pdf').write_bytes(b'%PDF-changed')
  with patch.object(iv,'fetch') as f,self.assertRaisesRegex(ValueError,'changed'):iv.download_reports(self.p,self.rec)
  f.assert_not_called()
 def test_failed_post_is_never_retried(self):
  dest=self.p/'attempt';cif=self.p/'input.cif';cif.write_text('data_fixture');calls=[]
  def fetch(url,data=None,headers=None,timeout=180,**kw):
   calls.append(data)
   if data:raise TimeoutError('POST outcome unknown')
   return ''.join('<input name="'+n+'">' for n in [*iv.OPTIONS,'filecif']).encode(),url
  with patch.object(iv,'fetch',side_effect=fetch),self.assertRaises(TimeoutError):iv.validate(cif,dest,True)
  self.assertEqual(sum(x is not None for x in calls),1)
  with patch.object(iv,'fetch') as f,self.assertRaises(ValueError):iv.recover(dest)
  f.assert_not_called()

class PlatonCompletionTests(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup);self.p=Path(self.tmp.name)
 def files(self,chk):
  (self.p/'model.chk').write_text(chk);(self.p/'model.ckf').write_text('FCF detail '*30);(self.p/'platon.out').write_text('CheckCIF CheckFCF')
 def test_empty_report_is_not_ready(self):
  self.files('');self.assertFalse(validation_ready(self.p,'model'))
 def test_incomplete_report_is_not_ready_even_if_files_large(self):
  self.files('partial computation\n'*30);self.assertFalse(validation_ready(self.p,'model'))
 def test_native_header_records_rules_without_external_file(self):
  r=native_versions('# PLATON/CHECK-(210125) versus check.def version 250106, Entry: test')
  self.assertEqual(r['checkdef_version'],'250106');self.assertEqual(r['platon_version'],'210125')
 def test_missing_external_rule_is_not_itself_missing_rules(self):
  with patch.dict('os.environ',{},clear=True):r=rules_context(self.p/'platon.exe')
  self.assertTrue(r['absence_of_external_file_is_not_failure']);self.assertIsNone(r['CHECKDEF'])
 def test_supported_embedded_data_detected(self):
  p=self.p/'model.cif';p.write_text('data_x\n_shelx_res_file\n;'+('x'*120)+'\n;\n_shelx_hkl_file\n;'+('y'*130)+'\n;\n')
  self.assertEqual(embedded_reflections(p),'embedded_SHELX_HKL_and_RES_native_reconstruction')
 def test_no_reflections_is_not_full_validation(self):
  p=self.p/'model.cif';p.write_text('data_x\n_cell_length_a 10\n')
  with self.assertRaisesRegex(ValueError,'reflections'):embedded_reflections(p)
 def test_ready_requires_valid_footer_and_native_markers(self):
  self.files('ALERT_Level and ALERT_Type Summary\n'+' '*140)
  self.assertTrue(validation_ready(self.p,'model'))
  (self.p/'platon.out').write_text('CheckCIF only');self.assertFalse(validation_ready(self.p,'model'))
 def test_missing_external_configuration_change_is_detectable(self):
  exe=self.p/'platon.exe';exe.write_text('fake');first=rules_context(exe);(self.p/'check.def').write_text('new rules');self.assertNotEqual(rules_context(exe),first)

if __name__=='__main__':unittest.main()
