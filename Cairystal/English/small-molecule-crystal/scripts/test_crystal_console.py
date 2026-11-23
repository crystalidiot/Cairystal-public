"""Local console contracts; synthetic records, no solver or external upload."""
import http.client,json,os,re,subprocess,sys,tempfile,time,unittest
from pathlib import Path
from unittest.mock import patch
import crystal_console as cc

class ConsoleTests(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup);self.base=Path(self.tmp.name)
  self.data=self.base/'data';self.data.mkdir();(self.data/'sample.hkl').write_text('synthetic HKL')
  self.profile=self.base/'profile.json';cc.write_json(self.profile,{'python':sys.executable})
  self.c=cc.Console(self.base/'workspace',self.profile)
  self.raw={'name':'synthetic','data_dir':str(self.data),'elements':['C','N','O','Cl'],'colour':'绿色','habit':'块状','dimensions_mm':'0.050 × 0.051 × 0.052','observations_confirmed':True}
 def job(self,record):
  folder=self.base/'job';folder.mkdir();cc.write_json(folder/'result.json',record)
  return self.c.register(folder)
 def test_missing_metrics_and_stages_stay_unknown(self):
  j=self.job({});s=self.c.snapshot(j['id']);self.assertIsNone(s['official_counts']);self.assertIsNone(s['metrics']['R1'])
  self.assertEqual(s['status'],'unknown');self.assertTrue(all(x['status']=='unknown' for x in s['stages']))
 def test_partial_counts_do_not_claim_validated(self):
  s=self.c.snapshot(self.job({'local_counts':{'A':None,'B':None},'official_counts':{'C':3}})['id'])
  self.assertEqual(next(x for x in s['stages'] if x['id']=='official')['status'],'unknown')
  self.assertEqual(next(x for x in s['stages'] if x['id']=='validation')['status'],'unknown')
 def test_successful_program_with_review_reasons_stays_review(self):
  j=self.job({});cc.write_json(Path(j['root'])/'attempt.json',{'success':True,'gate':{'execution_complete':True,'review_reasons':['not converged']}})
  self.assertEqual(self.c.snapshot(j['id'])['attempts'][0]['status'],'review')
 def test_presentation_and_unknown_events_not_counted_as_refinement(self):
  j=self.job({'events':[{'name':'rendering','status':'completed','seconds':14},{'name':'structure_viewer','status':'completed','seconds':.1},{'name':'unrecognised_event','status':'completed','seconds':99}]})
  s=self.c.snapshot(j['id']);refine=next(x for x in s['stages'] if x['id']=='refine')
  self.assertEqual(refine['status'],'unknown');self.assertIsNone(refine['seconds']);self.assertEqual(len(s['unmapped_events']),1)
 def test_native_attempt_supplies_timing_and_stage(self):
  j=self.job({});cc.write_json(Path(j['root'])/'attempt.json',{'success':True,'command':['D:/software/shelxl.exe','model'],'elapsed_s':2.7,'started_at':'2026-11-04T01:00:00Z'})
  s=self.c.snapshot(j['id']);refine=next(x for x in s['stages'] if x['id']=='refine');self.assertEqual(refine['seconds'],2.7)
 def test_diagnostic_files_and_low_r_do_not_claim_scientific_success(self):
  s=self.c.snapshot(self.job({'status':'diagnostic_artifacts_complete_scientific_blocked','metrics':{'R1':.02},'official_counts':{'A':1,'B':2},'AB':[{'level':'B','code':'214','text':'ADP'}]})['id'])
  self.assertEqual(s['status_kind'],'failed');self.assertEqual(s['scientific_status'],'not_established');self.assertEqual(len(s['alerts']),1)
  self.assertEqual(next(x for x in s['stages'] if x['id']=='refine')['status'],'review')
 def test_register_idempotent_and_read_only(self):
  j=self.job({'status':'completed'});p=Path(j['root'])/'result.json';before=cc.digest(p)
  self.assertEqual(self.c.register(j['root'])['id'],j['id']);self.c.snapshot(j['id']);self.assertEqual(cc.digest(p),before)
 def test_paths_cannot_escape_registered_root(self):
  j=self.job({});outside=self.base/'secret.json';cc.write_json(outside,{'secret':'synthetic'})
  for rel in ['../secret.json',str(outside)]:
   with self.subTest(rel=rel),self.assertRaises(ValueError):self.c.file(j['id'],rel)
 def test_arbitrary_html_is_not_executed(self):
  j=self.job({});(Path(j['root'])/'unsafe.html').write_text('<script>alert(1)</script>')
  with self.assertRaises(ValueError):self.c.file(j['id'],'unsafe.html')
 def test_save_plan_creates_intake_and_pins_files(self):
  p=self.c.save_plan(self.raw);cfg=p['config'];spec=cc.read_json(cfg['specimen'])
  self.assertFalse(cfg['authorize_iucr_upload']);self.assertTrue(cfg['deliver']);self.assertEqual(p['status'],'saved_not_run')
  self.assertTrue(p['file_hashes']);self.assertTrue(Path(cfg['intake_state']).is_file());self.assertIn('green',json.dumps(spec))
 def test_unknown_appearance_not_substituted(self):
  raw={k:v for k,v in self.raw.items() if k not in ['colour','habit','dimensions_mm','observations_confirmed']}
  p=self.c.save_plan(raw);spec=cc.read_json(p['config']['specimen']);self.assertNotIn('colour',spec.get('fields',{}))
  self.assertNotIn('0.12',json.dumps(spec));self.assertFalse(p['appearance']['observations_confirmed'])
 def test_plan_version_only_records_meaningful_change(self):
  p=self.c.save_plan(self.raw);before=cc.digest(p['config_path']);q=self.c.save_plan({**self.raw,'parent_id':p['id'],'max_weight_updates':5})
  self.assertNotEqual(p['id'],q['id']);self.assertEqual(cc.digest(p['config_path']),before)
  self.assertEqual([x['parameter'] for x in q['changes']],['max_weight_updates'])
 def test_invalid_configuration_is_rejected(self):
  for extra in [{'max_candidates':0},{'max_weight_updates':7},{'timeout':True},{'elements':[]},{'authorize_iucr_upload':True},{'observations_confirmed':'yes'},{'dimensions_mm':'0 x 1 x 2'}]:
   with self.subTest(extra=extra),self.assertRaises((ValueError,TypeError)):self.c.save_plan({**self.raw,**extra})
 def test_modified_evidence_blocks_launch(self):
  p=self.c.save_plan(self.raw);Path(p['config']['specimen']).write_text('{}')
  with self.assertRaisesRegex(ValueError,'证据发生变化'):self.c.start_plan(p['id'])
 def test_modified_profile_blocks_launch(self):
  p=self.c.save_plan(self.raw);cc.write_json(self.profile,{'python':'changed'})
  with self.assertRaisesRegex(ValueError,'环境配置已改变'):self.c.start_plan(p['id'])
 def test_external_graph_is_snapshotted(self):
  graph=self.base/'graph.json';cc.write_json(graph,{'synthetic':True})
  p=self.c.save_plan({**self.raw,'graph':str(graph)});cc.write_json(graph,{'changed':True})
  self.assertEqual(cc.read_json(p['config']['graph']),{'synthetic':True})
 def test_image_inherited_only_for_same_data_directory(self):
  import base64,io
  from PIL import Image
  image=io.BytesIO();Image.new('RGB',(8,8),'white').save(image,format='PNG');url='data:image/png;base64,'+base64.b64encode(image.getvalue()).decode()
  p=self.c.save_plan({**self.raw,'diagram_image_data_url':url})
  same=self.c.save_plan({**self.raw,'parent_id':p['id']});self.assertTrue(same['has_diagram'])
  other=self.base/'other_data';other.mkdir()
  different=self.c.save_plan({**self.raw,'parent_id':p['id'],'data_dir':str(other)});self.assertFalse(different['has_diagram'])
 def test_unsupported_inputs_stop_before_process(self):
  p=self.c.save_plan(self.raw)
  with patch('pipeline_intake.verify_profile'),patch('crystal_console.subprocess.Popen') as launch:
   with self.assertRaisesRegex(ValueError,'暂不能自动开始'):self.c.start_plan(p['id'])
   launch.assert_not_called()

class HTTPTests(unittest.TestCase):
 @classmethod
 def setUpClass(cls):
  cls.tmp=tempfile.TemporaryDirectory();cls.base=Path(cls.tmp.name);cls.ready=cls.base/'ready.json'
  cls.log=(cls.base/'server.log').open('w');env=os.environ.copy();env.update(PYTHONUTF8='1')
  cls.proc=subprocess.Popen([getattr(sys,'_base_executable',sys.executable),'-B',str(Path(cc.__file__)),'--workspace',str(cls.base/'ws'),'--port','0','--ready-file',str(cls.ready)],stdout=cls.log,stderr=cls.log,env=env)
  for _ in range(100):
   if cls.ready.is_file():break
   if cls.proc.poll() is not None:raise RuntimeError('HTTP test server failed')
   time.sleep(.05)
  cls.port=int(cc.read_json(cls.ready)['url'].split(':')[-1].rstrip('/'))
 @classmethod
 def tearDownClass(cls):
  cls.proc.terminate();cls.proc.wait(timeout=5);cls.log.close();cls.tmp.cleanup()
 def request(self,path,method='GET',body=None,headers=None):
  conn=http.client.HTTPConnection('127.0.0.1',self.port,timeout=5);conn.request(method,path,body,headers or {});r=conn.getresponse();data=r.read();h=dict(r.getheaders());conn.close();return r.status,h,data
 def auth(self):
  status,h,b=self.request('/');self.assertEqual(status,200);token=re.search(b'name="cairystal-token" content="([^"]+)',b).group(1).decode()
  return {'Cookie':h['Set-Cookie'].split(';')[0],'Origin':f'http://127.0.0.1:{self.port}','X-Cairystal-Token':token,'Content-Type':'application/json'}
 def test_private_api_requires_cookie_even_when_encoded(self):
  for path in ['/api/jobs','/api%2fjobs']:
   self.assertEqual(self.request(path)[0],400)
  self.assertEqual(self.request('/api/jobs',headers=self.auth())[0],200)
 def test_writes_require_origin_and_token(self):
  h=self.auth();h['Origin']='https://example.invalid'
  self.assertEqual(self.request('/api/register','POST','{}',h)[0],400)
  h=self.auth();h.pop('X-Cairystal-Token');self.assertEqual(self.request('/api/register','POST','{}',h)[0],400)
 def test_unexpected_host_rejected(self):
  self.assertEqual(self.request('/',headers={'Host':'attacker.invalid'})[0],400)
 def test_built_assets_local_and_present(self):
  for path in ['/app.js','/app.css']:
   status,h,b=self.request(path);self.assertEqual(status,200);self.assertGreater(len(b),100)
  status,_,b=self.request('/workflow-data.json')
  self.assertEqual(status,200)
  self.assertEqual(json.loads(b)['release'],cc.read_json(cc.ROOT/'release_info.json')['release_id'])
 def test_real_registration_and_utf8_download(self):
  job=self.base/'httpjob';job.mkdir(exist_ok=True);cc.write_json(job/'result.json',{})
  (job/'晶体学报表_中文.docx').write_bytes(b'synthetic docx payload')
  h=self.auth();status,_,b=self.request('/api/register','POST',json.dumps({'path':str(job)}),h);self.assertEqual(status,200)
  jid=json.loads(b)['id'];path='/file/'+jid+'/'+cc.quote('晶体学报表_中文.docx')
  status,out,b=self.request(path,headers=h);self.assertEqual(status,200);self.assertIn("filename*=UTF-8''",out['Content-Disposition'])

if __name__=='__main__':unittest.main()
