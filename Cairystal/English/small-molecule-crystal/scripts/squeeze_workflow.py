"""Preserved-control, reviewed host-only PLATON SQUEEZE -> SHELXL comparison."""
import argparse,json,shutil,subprocess,sys,time,os
from pathlib import Path
from crystal_runtime import regular,new_directory,sha,write_json,utc_now,records,canonical,read_hkl,paired_bundle,run_command,flags,local_validation,freeze_bundle
from pipeline_intake import unlinked,verify_profile
from squeeze_bundle import parse_fab,bilingual_notes

REVIEW_FIELDS=['host_complete_including_H','host_disorder_resolved','separate_diffuse_solvent_region','no_target_or_required_counterion_masked','no_host_solvent_coupled_disorder','charge_balance_reviewed','no_significant_anomalous_scatterers_in_mask','low_order_data_and_resolution_reviewed']

def eligible(review):
 missing=[k for k in REVIEW_FIELDS if review.get(k) is not True]
 if not review.get('basis'):missing.append('basis')
 return missing

def preflight(cfg):
 """Shared read-only gate before asking a customer or starting PLATON."""
 if isinstance(cfg.get('timeout',600),bool) or not 1<=float(cfg.get('timeout',600))<=3600:raise ValueError('timeout must be 1..3600 seconds per operation')
 if isinstance(cfg.get('cycles',20),bool) or not isinstance(cfg.get('cycles',20),int) or not 1<=cfg.get('cycles',20)<=100:raise ValueError('cycles must be an integer in 1..100')
 missing=eligible(cfg.get('review',{}))
 if missing:raise ValueError('Unresolved host/solvent review: '+', '.join(missing))
 for e in cfg.get('evidence',[]):
  if sha(regular(unlinked(e['path'])))!=e['sha256']:raise ValueError('Current-run scientific evidence changed')
 if not cfg.get('evidence'):raise ValueError('Current-run solvent/host evidence files are required')
 source=unlinked(cfg['source']);stem=cfg.get('stem','model');audit=paired_bundle(source,stem)
 if audit.get('solvent_mask'):raise ValueError('Use the unsqueezed host checkpoint; repeated mask application is not automatic')
 rows=records(Path(audit['files']['res']).read_text('latin1'))
 if any(r[0].upper() in {'TWIN','BASF','ABIN','SWAT'} for r in rows):raise ValueError('Twin/existing mask model needs a separately reviewed route')
 if next(r for r in rows if r[0].upper()=='HKLF')!=['HKLF','4']:raise ValueError('Nontrivial HKLF transform/scaling requires specialist pairing')
 if audit['gate']['review_reasons']:raise ValueError('Host refinement has unresolved numerical issues: '+str(audit['gate']['review_reasons']))
 return audit

def completed_platon(exe,folder,timeout):
 cmd=[str(exe),'-q','model.cif'];started=time.monotonic();stable_since=None;previous=None
 required=[folder/('model_sq.'+ext) for ext in ['ins','hkl','fab','lis']]
 with (folder/'process.log').open('w') as log:
  startup=None
  if os.name=='nt':startup=subprocess.STARTUPINFO();startup.dwFlags|=subprocess.STARTF_USESHOWWINDOW;startup.wShowWindow=0
  p=subprocess.Popen(cmd,cwd=folder,stdin=subprocess.DEVNULL,stdout=log,stderr=subprocess.STDOUT,creationflags=flags(),startupinfo=startup)
  state='running';calc=False
  try:
   while True:
    if all(f.exists() and f.stat().st_size for f in required):
     signature=[(f.stat().st_size,f.stat().st_mtime_ns) for f in required]
     listing=required[-1].read_text('latin1')
     calc='NORMAL END of PLATON' in listing and 'SQUEEZE  fab on' in listing
     if calc and signature==previous:
      stable_since=stable_since or time.monotonic()
     else:stable_since=None
     previous=signature
    if p.poll() is not None:state='exited';break
    if calc and stable_since and time.monotonic()-stable_since>=3:
     # Some Windows PLATON builds retain their virtual terminal after NORMAL END.
     # Stop only this child after complete, stable outputs; preserve the actual return code.
     parse_fab((folder/'model_sq.fab').read_text('latin1'))
     p.terminate();p.wait(timeout=10);state='terminated_after_verified_calculation_outputs';break
    if time.monotonic()-started>timeout:
     p.kill();p.wait();state='timeout';break
    time.sleep(.3)
  finally:
   if p.poll() is None:p.kill();p.wait()
 result={'command':cmd,'elapsed_s':round(time.monotonic()-started,3),'returncode':p.returncode,'process_state':state,'normal_end_listing':calc,'outputs_complete':calc and all(f.exists() for f in required),'log':str(folder/'process.log')}
 write_json(folder/'execution.json',result)
 if not result['outputs_complete'] or state=='timeout':raise ValueError('SQUEEZE did not complete; see '+str(folder/'execution.json'))
 return result

def run(plan,profile,output):
 plan_path=regular(unlinked(plan));cfg=json.loads(plan_path.read_text('utf-8-sig'));profile_path=regular(profile);tools=verify_profile(json.loads(profile_path.read_text('utf-8-sig')))
 out=new_directory(unlinked(output));shutil.copy2(plan_path,out/'plan.json');state={'schema':1,'started_at':utc_now(),'status':'checking','scientific_acceptance':False,'ai_calls':0,'events':[]}
 def save():write_json(out/'result.json',state)
 save()
 try:
  if isinstance(cfg.get('timeout',600),bool) or not 1<=float(cfg.get('timeout',600))<=3600:raise ValueError('timeout must be 1..3600 seconds per operation')
  if isinstance(cfg.get('cycles',20),bool) or not isinstance(cfg.get('cycles',20),int) or not 1<=cfg.get('cycles',20)<=100:raise ValueError('cycles must be an integer in 1..100')
  if cfg.get('squeeze_preference')!='allow_if_justified':raise ValueError('Saved SQUEEZE preference does not authorize this trial')
  missing=eligible(cfg.get('review',{}))
  if missing:state.update(status='needs_host_model_review',missing=missing);save();return state,out
  from squeeze_request import verify_authorization
  verify_authorization(cfg)
  audit=preflight(cfg)
  text=Path(audit['files']['res']).read_text('latin1')
  state['input_audit']=audit;state['before']=audit['gate']['metrics'];save()
  baseline=out/'before';baseline.mkdir()
  for ext,path in audit['files'].items():shutil.copy2(path,baseline/('model.'+ext))
  calc=out/'squeeze';calc.mkdir()
  for ext in ['cif','fcf']:shutil.copy2(baseline/('model.'+ext),calc/('model.'+ext))
  state['events'].append(completed_platon(tools['platon'],calc,float(cfg.get('timeout',600))));save()
  fab=calc/'model_sq.fab';mask=parse_fab(fab.read_text('latin1'));state['mask']={k:v for k,v in mask.items() if k not in ['rows','metadata']}
  if read_hkl((calc/'model_sq.hkl').read_text('latin1'))!=read_hkl((baseline/'model.hkl').read_text('latin1')):raise ValueError('PLATON-generated HKL differs from original observations; no implicit conversion adopted')
  generated=(calc/'model_sq.ins').read_text('latin1')
  ignored={'L.S.','CGLS','LIST','ACTA','FMAP','PLAN','ABIN'}
  signature=lambda t:[r for r in canonical(t) if r[0] not in ignored]
  if signature(text)!=signature(generated):raise ValueError('Unexpected host model/control change in generated SQUEEZE INS')
  if not any(r[0].upper()=='ABIN' for r in records(generated)):raise ValueError('ABIN missing from generated SQUEEZE model')
  after=out/'after';after.mkdir()
  from routine_finish import weight_ins,read_weights
  ins=weight_ins(generated,read_weights(text)[0],cycles=int(cfg.get('cycles',20)))
  (after/'model.ins').write_text(ins,encoding='ascii');shutil.copy2(baseline/'model.hkl',after/'model.hkl');shutil.copy2(fab,after/'model.fab')
  state['events'].append(run_command([tools['shelxl'],'model'],after,after/'process.log',float(cfg.get('timeout',600))));save()
  if state['events'][-1]['returncode']!=0:raise ValueError('SHELXL refinement process failed')
  from routine_finish import carry_metadata
  metadata_changes=carry_metadata(baseline/'model.cif',after/'model.cif',0)
  for change in metadata_changes:change['source']='Preserved same-experiment host checkpoint before SQUEEZE'
  write_json(out/'metadata_carry_forward.json',metadata_changes)
  result=paired_bundle(after,'model');state['after']=result['gate']['metrics'];state['after_pairing']=result
  if sha(after/'model.hkl')!=sha(baseline/'model.hkl'):raise ValueError('Original HKL changed')
  state['original_HKL_unchanged']=True
  notes=bilingual_notes(state['mask']);write_json(out/'squeeze_report_notes.json',notes)
  # Both full local checks remain attached even when scientific acceptance is withheld.
  for label,folder in [('before',baseline),('after',after)]:
   audit2=paired_bundle(folder,'model');frozen=out/(label+'_frozen');freeze_bundle(audit2,frozen,'model')
   check=local_validation(tools['platon'],frozen,out/(label+'_validation'),'model',float(cfg.get('timeout',600)))
   state[label+'_local_counts']=check['alerts']['counts'];state[label+'_AB']=[a for a in check['alerts']['alerts'] if a['level'] in 'AB'];save()
  if not all(sha(p)==audit['source_sha256'][ext] for ext,p in audit['files'].items()):raise ValueError('Source bundle changed')
  state.update(status='comparison_complete_requires_review',source_unchanged=True,next_step='Review host geometry/ADP, residuals, low-order data, masked electrons and composition accounting. Use normal finish/delivery with matching FAB for final weights, AB checks, authorized exact-CIF IUCr and bilingual Word; this result is not final delivery.')
 except Exception as e:state.update(status='failed',failure=str(e))
 state['finished_at']=utc_now();save();return state,out

def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--plan',required=True);p.add_argument('--profile',required=True);p.add_argument('--output',required=True);a=p.parse_args();s,o=run(a.plan,a.profile,a.output)
 print(json.dumps({k:s[k] for k in ['status','before','after','before_local_counts','after_local_counts','failure','missing'] if k in s}|{'output':str(o)},ensure_ascii=False));return int(s['status']=='failed')
if __name__=='__main__':sys.exit(main())
