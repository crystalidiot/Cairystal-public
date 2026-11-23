"""One entry for a reviewed candidate: continuation, weights, AB, official checkCIF and both Word reports."""
import argparse,contextlib,io,json,shutil,sys,time
from pathlib import Path
from types import SimpleNamespace
from crystal_runtime import regular,new_directory,sha,write_json,utc_now,paired_bundle,check_stem
from pipeline_intake import unlinked,verify_profile

def pending_delivery(finished,where,local_only):
 """Expected checkpoints are distinct from failures; no upload consent inferred."""
 delivery=Path(where)/'delivery_run/result.json'
 if finished.get('phase')=='official_and_bilingual_delivery' and delivery.is_file():
  attempt=json.loads(delivery.read_text(encoding='utf-8'))
  if attempt.get('continuation'):
   return {'status':attempt['status'],'full_delivery_complete':False,'checkpoint':str(delivery.parent),
           'next_tool':'deliver','continuation':attempt['continuation'],'reason':attempt.get('failure'),
           'local_counts':attempt.get('local_counts'),'official_counts':attempt.get('official',{}).get('counts')}
 if finished['status'] in {'ready_for_official_delivery','official_upload_not_authorized'}:
  return {'status':'local_complete_waiting_delivery' if local_only else 'awaiting_upload_authorization',
          'full_delivery_complete':False,'checkpoint':str(where),
          'reason':'Local finishing retained; official PDF and bilingual delivery are still pending.',
          'next_tool':'resume-delivery',
          'resume_arguments':['--run',str(where)],
          'upload_authorization_required':True,
          'next_evidence':str(where/'state.json')}
 return {'status':'incomplete','blocked_stage':finished.get('phase'),
         'reason':finished.get('failure') or finished['status'],
         'next_evidence':str(where/'decision_packet.json') if (where/'decision_packet.json').exists() else str(where/'state.json')}

def exit_status(state,local_only=False):
 return 0 if state['status']=='artifacts_complete' or (local_only and state['status']=='local_complete_waiting_delivery') else 2

def run(a):
 source=unlinked(a.input);target=unlinked(a.output)
 if target==source or source in target.parents:raise ValueError('Output must be separate from the source candidate')
 if not 0<=a.max_weight_updates<=6 or not 0<a.timeout<=86400:raise ValueError('Invalid weight-update or process-timeout budget')
 root=new_directory(target);start=time.perf_counter();state={'schema':1,'status':'running','started_at':utc_now(),'scientific_acceptance':'not_established','ai_calls':0,'required_deliverables':['refined native bundle','official IUCr_checkCIF.pdf','Chinese Word','English Word'],'events':[]}
 def save():write_json(root/'result.json',state)
 def step(name,fn):
  event={'stage':name,'status':'running','started_at':utc_now()};state['events'].append(event);save();t=time.perf_counter();capture=io.StringIO()
  try:
   with contextlib.redirect_stdout(capture):value=fn()
   event['status']='completed';return value
  except Exception as e:event.update(status='failed',reason=str(e));raise
  finally:
   event['seconds']=round(time.perf_counter()-t,3);(root/(name+'.log')).write_text(capture.getvalue(),encoding='utf-8');save()
 save()
 try:
  profile=regular(unlinked(a.profile));cfg=json.loads(profile.read_text('utf-8-sig'));tools=verify_profile(cfg);shutil.copy2(profile,root/'runtime_profile.json')
  review_path=regular(unlinked(a.review));review=json.loads(review_path.read_text('utf-8-sig'));shutil.copy2(review_path,root/'review.json')
  from model_priority import reference_provenance
  review=reference_provenance(review);write_json(root/'effective_review.json',review)
  if review.get('chemistry_and_h_reviewed') is not True or not str(review.get('basis','')).strip():raise ValueError('Current-model chemistry/H review and evidence basis are required; continue scientific work before final completion')
  stem=check_stem(a.stem);audit=step('paired_input',lambda:paired_bundle(unlinked(a.input),stem));write_json(root/'input_audit.json',audit)
  before=root/'before';before.mkdir()
  for ext,p in audit['files'].items():shutil.copy2(p,before/('model.'+ext))
  from routine_finish import read_weights,weight_ins,carry_metadata,finish
  text=(before/'model.res').read_text('latin1');ins=root/'continuation.ins';ins.write_text(weight_ins(text,read_weights(text)[0],cycles=20),encoding='ascii')
  from run_crystal_stage import run as native_run
  args=SimpleNamespace(executable=tools['shelxl'],ins=str(ins),hkl=str(before/'model.hkl'),fab=str(before/'model.fab') if (before/'model.fab').is_file() else None,stem='model',output=str(root/'continued'),reason='Final continuation from the reviewed current candidate; same chemistry, populations, ADP types and original reflections. Not scientific acceptance.',timeout=a.timeout)
  if step('native_continuation',lambda:native_run(args)):raise ValueError('Continuation failed; see native_continuation.log and continued/attempt.json')
  metadata=step('carry_experiment_metadata',lambda:carry_metadata(before/'model.cif',root/'continued/model.cif',0));write_json(root/'metadata_carry_forward.json',metadata)
  rcfg={'candidate':str(root/'continued'),'stem':'model',**tools,'renderer':cfg['renderer'],'timeout':a.timeout,'max_weight_updates':a.max_weight_updates,'review':review,'collect_reports_with_alerts':True}
  rcfg['data_dir']=str(unlinked(getattr(a,'data_dir',None) or source))
  write_json(root/'finish_config.json',rcfg)
  finished,where=step('finish_and_reports',lambda:finish(root/'finish_config.json',root/'finish',not a.local_only,a.authorize_iucr_upload))
  state.update(finish_status=finished['status'],finish_root=str(where),metrics=finished.get('metrics'),local_counts=finished.get('local_counts'),official_counts=finished.get('official_counts'),AB_alerts=finished.get('AB_alerts'))
  dr=where/'delivery_run'
  if (dr/'delivery').is_dir():
   from delivery_contract import require
   state['completion']=step('delivery_completeness',lambda:require(dr,'model'));state['delivery']=str(dr/'delivery');state['structure_viewer']=json.loads((dr/'result.json').read_text('utf-8')).get('structure_viewer')
   from report_autoqa import run as report_qa
   qa=step('report_qa',lambda:report_qa(dr,dr/'automatic_qa.json'));state['report_qa']=qa['status'];state['report_qa_findings']=qa['findings']
   if qa['status']=='automatic_checks_passed':
    from crystal_delivery import finalize
    final=SimpleNamespace(run=str(dr),data_dir=getattr(a,'data_dir',None) or str(source),automatic_qa=str(dr/'automatic_qa.json'),reviewed_zh=False,reviewed_en=False,reviewed_official=False,review_note='Automated exact-file report checks passed; no actual visual inspection or scientific correctness claim.')
    step('package',lambda:finalize(final));delivered=json.loads((dr/'result.json').read_text('utf-8'));state.update(status='artifacts_complete',zip=str(dr/'structure_and_reports.zip'),working_delivery=str(dr/'delivery'),delivery=delivered['customer_delivery']['directory'],customer_delivery=delivered['customer_delivery'],customer_notice=delivered['customer_notice'])
   else:state['status']='artifacts_complete_needs_review'
  else:
   state.update(pending_delivery(finished,where,a.local_only))
  if any(sha(p)!=audit['source_sha256'][k] for k,p in audit['files'].items()):raise ValueError('Original candidate changed during completion')
  state['source_unchanged']=True
 except Exception as e:
  from support_report import try_record
  state.update(status='incomplete',reason=str(e),support_report=try_record(root,'execution_error',str(e),'complete',e))
 if state['status'] in {'incomplete','artifacts_complete_needs_review'} and not state.get('support_report'):
  from support_report import try_record
  state['support_report']=try_record(root,'report_review',state.get('reason') or str(state.get('report_qa_findings')),'complete')
 state.update(full_delivery_complete=state['status']=='artifacts_complete',finished_at=utc_now(),seconds=round(time.perf_counter()-start,3));save();return state

def main():
 p=argparse.ArgumentParser(description=__doc__)
 for name in ['input','profile','review','output']:p.add_argument('--'+name,required=True)
 p.add_argument('--data-dir',help='Original specimen directory when --input is an intermediate candidate folder')
 p.add_argument('--stem',default='model');p.add_argument('--authorize-iucr-upload',action='store_true');p.add_argument('--local-only',action='store_true');p.add_argument('--timeout',type=float,default=180);p.add_argument('--max-weight-updates',type=int,default=4)
 a=p.parse_args();state=run(a);print(json.dumps(state,ensure_ascii=False));return exit_status(state,a.local_only)
if __name__=='__main__':sys.exit(main())
