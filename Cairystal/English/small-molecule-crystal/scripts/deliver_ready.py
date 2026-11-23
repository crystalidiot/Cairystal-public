"""Deliver an intact locally finished checkpoint without repeating refinement."""
import argparse,contextlib,io,json,sys,time
from pathlib import Path
from types import SimpleNamespace
from crystal_runtime import regular,sha,write_json,utc_now,paired_bundle

def seal_ready(root,state):
 root=Path(root)
 paths=[root/'config.json',root/'input_audit.json',Path(state['notes'])]
 paths += [p for p in Path(state['selected']).iterdir() if p.is_file()]
 return {str(p.relative_to(root)):sha(p) for p in paths}

def verify_ready(root,state):
 root=Path(root)
 if state['status'] not in {'ready_for_official_delivery','official_upload_not_authorized'}:raise ValueError('Checkpoint is not ready; no automatic replay. Use deliver continue --inspect-only on delivery_run with the expected CIF and HKL.')
 if not state.get('ready_artifacts'):raise ValueError('This checkpoint has no ready-artifact seal; preserve it and prepare an audited new checkpoint')
 if state['ready_artifacts']!=seal_ready(root,state):raise ValueError('Ready model/config/notes changed; refinement and validation must be reviewed again')
 if state['code_sha256']!={p.name:sha(p) for p in Path(__file__).parent.glob('*.py')}:raise ValueError('Skill version changed since local finishing')
 if (root/'delivery_run').exists():raise ValueError('Delivery was already attempted; inspect its record, do not replay submission')
 audit=json.loads((root/'input_audit.json').read_text('utf-8'))
 if any(sha(regular(p))!=audit['source_sha256'][k] for k,p in audit['files'].items()):raise ValueError('Original reviewed source bundle changed')
 return audit

def run(root,authorize=False,complete=False,data_dir=None):
 root=Path(root)
 if not authorize:
  saved=root/'state.json'
  if not complete or not saved.is_file() or json.loads(saved.read_text('utf-8')).get('status') not in {'awaiting_visual_review','needs_report_review'}:
   raise ValueError('Official upload has not been authorized; local checkpoint remains ready')
 lock=root/'delivery_resume.lock'
 try:
  with lock.open('x',encoding='utf-8') as f:json.dump({'started_at':utc_now()},f)
 except FileExistsError:raise ValueError('Another or interrupted delivery owns this checkpoint; inspect delivery_resume.lock, do not replay')
 digest=sha(lock)
 try:
  previous=json.loads((root/'state.json').read_text('utf-8'))
  if complete and previous.get('status') in {'awaiting_visual_review','needs_report_review'}:
   if previous['code_sha256']!={p.name:sha(p) for p in Path(__file__).parent.glob('*.py')}:raise ValueError('Skill version changed since delivery')
   return complete_artifacts(root,previous,data_dir)
  result=_run(root,authorize)
  return complete_artifacts(root,result,data_dir) if complete else result
 finally:
  if lock.exists() and sha(lock)==digest:lock.unlink()

def _run(root,authorize=False):
 root=Path(root);state=json.loads((root/'state.json').read_text('utf-8'))
 if not authorize:raise ValueError('Official upload has not been authorized; local checkpoint remains ready')
 audit=verify_ready(root,state);cfg=json.loads((root/'config.json').read_text('utf-8'))
 paired_bundle(state['selected'],'model')
 a=SimpleNamespace(input=state['selected'],stem='model',output=str(root/'delivery_run'),notes=state['notes'],
  platon=cfg['platon'],renderer=cfg['renderer'],powershell=cfg.get('powershell'),soffice=cfg.get('soffice'),pdftoppm=cfg['pdftoppm'],
  authorize_iucr_upload=True,official_cache=None,local_cache=str(Path(state['selected']).parent/'local_validation' if state.get('selected_omit') else root/'local_validation'),timeout=cfg.get('timeout',180),metadata_source=None,pairing_evidence=None)
 event={'name':'official_and_bilingual_delivery','started_at':utc_now(),'status':'running','resumed_from_local_checkpoint':True}
 state['events'].append(event);state.update(status='delivering',phase=event['name']);write_json(root/'state.json',state);start=time.perf_counter()
 try:
  from crystal_delivery import run as native_delivery
  with contextlib.redirect_stdout(io.StringIO()) as output:rc=native_delivery(a)
  if rc:raise ValueError('Delivery failed; inspect delivery_run/result.json. '+output.getvalue())
  result=json.loads((root/'delivery_run/result.json').read_text('utf-8'))
  state.update(delivery=str(root/'delivery_run/delivery'),completion=result.get('completion'),status=result['status'],official_counts=result['official']['counts'],AB_alerts=result['AB_alerts'],
   render_manifest=str(root/'delivery_run/qa/render_manifest.json'),official_pages_manifest=str(root/'delivery_run/qa/official_pages_manifest.json'))
  state['source_unchanged']=all(sha(p)==audit['source_sha256'][k] for k,p in audit['files'].items())
  if not state['source_unchanged']:raise ValueError('Source bundle changed during delivery')
  event['status']='completed'
 except Exception as e:
  event.update(status='failed',error=str(e));state.update(status='failed',failure=str(e))
 finally:
  event.update(seconds=round(time.perf_counter()-start,3),finished_at=utc_now());state['finished_at']=utc_now();write_json(root/'state.json',state)
 return state

def complete_artifacts(root,state,data_dir=None):
 """CLI continuation includes measured report QA and publishing, without refinement."""
 root=Path(root)
 if state.get('status') not in {'awaiting_visual_review','needs_report_review'}:return state
 from pipeline_intake import unlinked
 cfg=json.loads((root/'config.json').read_text('utf-8'))
 dr=root/'delivery_run'
 from report_autoqa import run as report_qa
 qa=report_qa(dr,dr/'automatic_qa.json')
 state['automatic_report_qa']={'status':qa['status'],'record':str(dr/'automatic_qa.json'),'findings':qa['findings']}
 if qa['status']!='automatic_checks_passed':
  state.update(status='needs_report_review',next_step='Inspect the specific findings in delivery_run/automatic_qa.json; retain current artifacts.')
 else:
  target=data_dir or cfg.get('data_dir')
  if not target:
   state.update(status='awaiting_visual_review',next_step='Report checks passed. Supply the original specimen directory with --data-dir to publish without rerunning refinement or upload.')
  else:
   from crystal_delivery import finalize
   a=SimpleNamespace(run=str(dr),data_dir=str(unlinked(target)),automatic_qa=str(dr/'automatic_qa.json'),reviewed_zh=False,reviewed_en=False,reviewed_official=False,
                     review_note='Exact-file automated report checks passed during checkpoint continuation. No manual visual inspection or scientific correctness is claimed.')
   finalize(a)
   delivered=json.loads((dr/'result.json').read_text('utf-8'))
   state.update(status=delivered['status'],customer_delivery=delivered['customer_delivery'],customer_notice=delivered['customer_notice'],
                zip=delivered['zip'],working_delivery=str(dr/'delivery'),delivery=delivered['customer_delivery']['directory'])
 state['finished_at']=utc_now();write_json(root/'state.json',state)
 return state

if __name__=='__main__':
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--run',required=True);p.add_argument('--authorize-iucr-upload',action='store_true');p.add_argument('--data-dir',help='Original specimen folder for the Cairystal deliverables');a=p.parse_args()
 try:
  s=run(a.run,a.authorize_iucr_upload,complete=True,data_dir=a.data_dir)
  print(json.dumps({k:s.get(k) for k in ['status','official_counts','failure','automatic_report_qa','customer_delivery','customer_notice','next_step']},ensure_ascii=False))
  sys.exit(0 if s['status']=='delivery_complete_needs_scientific_review' else 2)
 except Exception as e:print(json.dumps({'status':'blocked','error':str(e)},ensure_ascii=False));sys.exit(1)
