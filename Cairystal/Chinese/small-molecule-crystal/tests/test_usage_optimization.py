import copy,json,tempfile,unittest
from pathlib import Path
from zipfile import ZipFile,ZipInfo
from unittest.mock import patch
from report_render_cache import package_fingerprint,restore,contract
from crystal_runtime import sha
from ab_auto import non_model_alert_route,load_policy,generate_requests

class ReportCacheTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup);self.root=Path(self.tmp.name)
    def doc(self,name='d.docx',value='same',time=(2020,1,1,0,0,0),extra=None):
        p=self.root/name
        with ZipFile(p,'w') as z:
            z.writestr(ZipInfo('word/document.xml',time),'<a>'+value+'</a>')
            if extra:
                for n,v in extra.items():z.writestr(n,v)
        return p
    def setup_cache(self):
        from pypdf import PdfWriter
        source=self.root/'old';source.mkdir();qa=self.root/'new';qa.mkdir();jobs=[]
        docs={}
        for lang in ('zh','en'):
            folder=source/lang;folder.mkdir();pdf=folder/'report.pdf'
            w=PdfWriter();w.add_blank_page(width=100,height=100);w.write(pdf)
            png=folder/'page-1.png';png.write_bytes(b'test-only-page')
            docx=self.doc(lang+'.docx');docs[lang]={'path':str(docx)}
            jobs.append({'language':lang,'docx':str(docx),'pdf':str(pdf),'pdf_sha256':sha(pdf),'pages':[{'path':str(png),'sha256':sha(png)}]})
        key={'schema':1,'documents':{k:package_fingerprint(v['path']) for k,v in docs.items()},'environment':{'test_fixture':True}}
        data={'renderer':'word','jobs':jobs,'render_contract':key}
        (source/'render_manifest.json').write_text(json.dumps(data))
        return source,qa,{'outputs':docs},key,data
    def test_zip_timestamp_is_not_document_content(self):
        a=self.doc('a.docx');b=self.doc('b.docx',time=(2022,2,2,0,0,0))
        self.assertNotEqual(sha(a),sha(b));self.assertEqual(package_fingerprint(a),package_fingerprint(b))
    def test_every_document_part_affects_key(self):
        a=self.doc('a.docx');b=self.doc('b.docx',extra={'word/styles.xml':'<new/>'})
        self.assertNotEqual(package_fingerprint(a),package_fingerprint(b))
    def test_dynamic_fields_disable_reuse(self):
        xml='<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"><w:fldSimple w:instr="DATE"/></w:document>'
        p=self.doc(extra={'word/header1.xml':xml});self.assertRaises(ValueError,package_fingerprint,p)
    def test_external_links_disable_reuse(self):
        p=self.doc(extra={'word/_rels/document.xml.rels':'<Relationships><Relationship TargetMode="External" Target="url"/></Relationships>'})
        self.assertRaises(ValueError,package_fingerprint,p)
    def test_pair_reuse_preserves_bytes_and_requires_new_qa(self):
        s,q,r,k,d=self.setup_cache();v,reason=restore(s,q,r,k)
        self.assertIsNone(reason);self.assertTrue(v['cache_hit']);self.assertEqual(v['visual_review'],'pending')
        self.assertEqual([j['pdf_sha256'] for j in v['jobs']],[j['pdf_sha256'] for j in d['jobs']])
    def test_changed_context_renders_again(self):
        s,q,r,k,d=self.setup_cache();k=copy.deepcopy(k);k['environment']['test_fixture']=False
        v,reason=restore(s,q,r,k);self.assertIsNone(v);self.assertFalse((q/'render').exists())
    def test_changed_document_renders_again(self):
        s,q,r,k,d=self.setup_cache();k=copy.deepcopy(k);k['documents']['en']='other'
        self.assertIsNone(restore(s,q,r,k)[0])
    def test_tampered_page_renders_again_before_writes(self):
        s,q,r,k,d=self.setup_cache();Path(d['jobs'][0]['pages'][0]['path']).write_bytes(b'changed')
        self.assertIsNone(restore(s,q,r,k)[0]);self.assertFalse((q/'render').exists())
    def test_missing_language_renders_again(self):
        s,q,r,k,d=self.setup_cache();d['jobs'].pop();(s/'render_manifest.json').write_text(json.dumps(d))
        self.assertIsNone(restore(s,q,r,k)[0])
    def test_legacy_manifest_not_trusted(self):
        s,q,r,k,d=self.setup_cache();d.pop('render_contract');(s/'render_manifest.json').write_text(json.dumps(d))
        self.assertIsNone(restore(s,q,r,k)[0])
    def test_path_escape_not_used(self):
        s,q,r,k,d=self.setup_cache();other=self.root/'outside.pdf';other.write_bytes(Path(d['jobs'][0]['pdf']).read_bytes());d['jobs'][0]['pdf']=str(other)
        (s/'render_manifest.json').write_text(json.dumps(d));self.assertIsNone(restore(s,q,r,k)[0])
    def test_missing_environment_is_only_cache_miss(self):
        s,q,r,k,d=self.setup_cache()
        with patch('report_render_cache.environment',side_effect=PermissionError('restricted')):
            stamp,reason=contract(r,'word','raster',powershell='shell');self.assertIsNone(stamp);self.assertIn('PermissionError',reason)

class MetadataRouteTests(unittest.TestCase):
    def alert(self,code,level='A'):return {'code':code,'type':1,'level':level,'text':'Missing field'}
    def test_metadata_keeps_identical_findings(self):
        alerts=[self.alert(x) for x in ('183','184','185')];v=non_model_alert_route({'alerts':alerts},load_policy())
        req,findings=generate_requests({'AB_alerts':[dict(a,atom_labels=[]) for a in alerts],'all_atoms':[],'regions':[]},{'atoms':[]},load_policy())
        for finding in findings:finding['evidence_tools']=[]
        self.assertEqual(v['findings'],findings);self.assertEqual(v['baseline_AB'],{'A':3,'B':0});self.assertEqual(v['status'],'needs_evidence');self.assertEqual(v['native_attempts'],0)
    def test_model_warning_enters_full_diagnosis(self):
        self.assertIsNone(non_model_alert_route({'alerts':[self.alert('183'),self.alert('214','B')]},load_policy()))
    def test_unknown_warning_enters_full_diagnosis(self):
        self.assertIsNone(non_model_alert_route({'alerts':[self.alert('999')]},load_policy()))
    def test_no_ab_not_scientific_acceptance(self):
        r=non_model_alert_route({'alerts':[self.alert('999','C')]},load_policy())
        self.assertEqual(r['status'],'no_AB_in_verified_local_report');self.assertFalse(r['model_adopted']);self.assertEqual(r['scientific_acceptance'],'not_established')
    def test_duplicate_metadata_warnings_retained(self):
        r=non_model_alert_route({'alerts':[self.alert('183')]*2},load_policy());self.assertEqual(len(r['findings']),2)

if __name__=='__main__':unittest.main()
