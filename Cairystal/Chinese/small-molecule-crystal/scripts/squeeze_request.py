"""Prepare one specimen-specific SQUEEZE choice; reuse consent and execute a preserved trial. No LLM."""
import argparse,hashlib,html,json,shutil,sys
from pathlib import Path
from crystal_runtime import new_directory,regular,sha,utc_now,write_json
from pipeline_intake import unlinked

CHOICES={'allow':'同意尝试 SQUEEZE，保留处理前后版本','decline':'不同意，继续显式溶剂模型路线','defer':'暂不决定，先保留当前结果'}
TITLE='主体模型已通过当前检查，难点集中在溶剂区域。是否同意尝试 SQUEEZE？'
EXPLANATION='仅处理已有证据支持的独立溶剂区域，保留原始反射数据和处理前后版本。SQUEEZE 计算溶剂的散射贡献，不提供这些溶剂的明确原子坐标，也不保证消除全部警告。之后仍要精修、检查 AB、按已有授权做官网 checkCIF，并生成中英文 Word。主体/溶剂归属和化学计量仍需核对。'

def read(p):return json.loads(regular(unlinked(p)).read_text('utf-8-sig'))
def fingerprint(value):return hashlib.sha256(json.dumps(value,ensure_ascii=False,sort_keys=True,separators=(',',':')).encode()).hexdigest()
def locks(root):
 from contextlib import contextmanager
 @contextmanager
 def guard():
  lock=root/'choice.lock'
  try:
   with lock.open('x',encoding='utf-8') as f:f.write(utc_now())
  except FileExistsError:raise ValueError('Another or interrupted choice operation owns this request; inspect choice.lock')
  token=sha(lock)
  try:yield
  finally:
   if lock.exists() and sha(lock)==token:lock.unlink()
 return guard()

def question_form(root,record):
 text=html.escape;options=''.join('<option value="'+key+'">'+text(value)+'</option>' for key,value in CHOICES.items())
 # Download-only local form: no server, upload or browser-specific API.
 embedded=json.dumps({'schema':1,'request_id':record['request_id']},ensure_ascii=False).replace('<','\\u003c')
 page='''<!doctype html><html lang="zh-CN"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Cairystal · 溶剂处理选择</title><style>body{font:16px/1.8 'Microsoft YaHei',sans-serif;max-width:800px;margin:40px auto;padding:20px;color:#203449;background:#f5f8fc}main{background:white;border:1px solid #dae4ed;border-radius:12px;padding:28px}label{display:block;margin:22px 0}select,textarea,button{font:inherit;padding:10px;max-width:100%;box-sizing:border-box}select,textarea{width:100%}button{background:#1467a3;color:white;border:0;border-radius:6px;cursor:pointer}.muted{color:#567;font-size:14px}</style><main><p class="muted">Cairystal · 仅针对本次模型</p><h1>溶剂难以建模：是否尝试 SQUEEZE？</h1>'''
 page+='<p><b>主体情况：</b>'+text(record['host_summary'])+'</p><p><b>溶剂难点：</b>'+text(record['solvent_challenge'])+'</p><p>'+text(EXPLANATION)+'</p>'
 page+='<label>请选择<select id="decision"><option value="">尚未选择</option>'+options+'</select></label><label>备注（可不填）<textarea id="comment" rows="3"></textarea></label><button id="save">保存本次选择</button><p id="message" role="status"></p><p class="muted">保存回答 JSON 后交给运行 Cairystal 的 agent；不会上传晶体文件，也不改变官网上传授权。</p></main>'
 page+='''<script>
'use strict';const request=REQUEST;
function answer(){const decision=document.getElementById('decision').value;if(!['allow','decline','defer'].includes(decision))throw new Error('请先明确选择，默认不视为同意');return {...request,decision,comment:document.getElementById('comment').value,basis:'客户在本次专用表单中明确选择'};}
document.getElementById('save').addEventListener('click',()=>{try{const value=answer(),blob=new Blob([JSON.stringify(value,null,2)],{type:'application/json;charset=utf-8'}),url=URL.createObjectURL(blob),a=document.createElement('a');a.href=url;a.download='Cairystal_squeeze_choice.json';a.click();URL.revokeObjectURL(url);document.getElementById('message').textContent='已保存选择，请将 JSON 交给运行 Cairystal 的 agent。';}catch(e){document.getElementById('message').textContent=e.message;}});
</script>'''.replace('REQUEST',embedded)
 (root/'index.html').write_text(page,encoding='utf-8')

def verified(root):
 root=unlinked(root);record=read(root/'request.json');seal=read(root/'seal.json')
 for rel,h in seal.items():
  if sha(regular(unlinked(root/rel)))!=h:raise ValueError('Frozen SQUEEZE request changed: '+rel)
 cfg=read(root/'plan.json')
 from squeeze_workflow import preflight
 audit=preflight(cfg)
 if audit['source_sha256']!=record['source_sha256']:raise ValueError('Host checkpoint changed since the customer request')
 if record.get('intake_path') and sha(regular(unlinked(record['intake_path'])))!=record['intake_sha256']:raise ValueError('Saved specimen intake changed; review the existing choice')
 return record,cfg

def consent_plan(root,decision,basis,origin,comment=''):
 record,cfg=verified(root)
 if decision not in CHOICES:raise ValueError('Unknown choice')
 if not isinstance(basis,str) or not basis.strip():raise ValueError('Record the actual customer response/intake basis')
 response={'schema':1,'request_id':record['request_id'],'decision':decision,'basis':basis,'origin':origin,'comment':comment,'recorded_at':utc_now()}
 write_json(root/'response.json',response)
 status={'allow':'ready_for_squeeze_trial','decline':'declined_continue_explicit_model','defer':'deferred_no_repeated_prompt'}[decision]
 result={'schema':1,'status':status,'request_id':record['request_id'],'ai_calls':0,'official_upload_authorization_changed':False}
 if decision=='allow':
  cfg['squeeze_preference']='allow_if_justified'
  cfg['customer_choice']={'request':str(root/'request.json'),'request_sha256':sha(root/'request.json'),'response':str(root/'response.json'),'response_sha256':sha(root/'response.json')}
  write_json(root/'authorized_plan.json',cfg);result['plan']=str(root/'authorized_plan.json')
 write_json(root/'result.json',result);return result

def prepare(plan,output,intake=None):
 plan_path=regular(unlinked(plan));cfg=read(plan_path);out=new_directory(unlinked(output));shutil.copy2(plan_path,out/'plan.json')
 from squeeze_workflow import preflight
 try:
  # These are current-run reviewed conclusions; no threshold infers chemical truth.
  for key in ['host_summary','solvent_challenge']:
   if not isinstance(cfg.get(key),str) or not cfg[key].strip():raise ValueError('Document '+key+' from current-run evidence')
  audit=preflight(cfg)
  source={};intake_path=None
  if intake:
   intake_path=regular(unlinked(intake));source=read(intake_path)
   if source.get('schema')!=1 or source.get('questionnaire_completed') is not True:raise ValueError('Use the saved current-specimen intake_state.json')
  data=source.get('data',{});preference=data.get('squeeze','undecided')
  if preference not in ['allow_if_justified','never','undecided']:raise ValueError('Unknown saved SQUEEZE preference')
  if data.get('purpose')=='full_composition':raise ValueError('Full-composition goal requires specific solvent-composition review before offering the host-priority branch')
  binding={'plan_sha256':sha(out/'plan.json'),'source_sha256':audit['source_sha256'],'intake_sha256':sha(intake_path) if intake_path else None}
  record={'schema':1,'request_id':fingerprint(binding),'created_at':utc_now(),**binding,'intake_path':str(intake_path) if intake_path else None,'saved_preference':preference,'title':TITLE,'explanation':EXPLANATION,'options':CHOICES,'host_summary':cfg['host_summary'],'solvent_challenge':cfg['solvent_challenge'],'metrics':audit['gate']['metrics'],'scientific_acceptance':False}
  write_json(out/'request.json',record);write_json(out/'seal.json',{name:sha(out/name) for name in ['request.json','plan.json']})
  if preference in ['allow_if_justified','never']:
   return consent_plan(out,'allow' if preference=='allow_if_justified' else 'decline','已保存的本例一次性问卷选择','saved_specimen_intake'),out
  question_form(out,record);state={'schema':1,'status':'needs_customer_choice','request_id':record['request_id'],'question':{'title':TITLE,'options':list(CHOICES.values())},'form':str(out/'index.html'),'ai_calls':0}
  write_json(out/'result.json',state);return state,out
 except (ValueError,OSError,KeyError,TypeError) as e:
  state={'schema':1,'status':'needs_model_review','reason':str(e),'question_generated':False,'ai_calls':0};write_json(out/'result.json',state);return state,out

def respond(root,answer=None,decision=None,basis=None):
 root=unlinked(root)
 with locks(root):
  record,_=verified(root)
  if answer:
   value=read(answer)
   if value.get('schema')!=1 or value.get('request_id')!=record['request_id']:raise ValueError('Answer belongs to a different request/model')
   decision=value.get('decision');basis=value.get('basis');comment=value.get('comment','');origin='customer_answer_file'
  else:comment='';origin='recorded_customer_message'
  if decision not in CHOICES:raise ValueError('Unknown or unanswered decision')
  if (root/'response.json').exists():
   existing=read(root/'response.json')
   if existing['decision']==decision:return read(root/'result.json')
   raise ValueError('Decision already recorded; preserve it and document a new request for an explicit change')
  return consent_plan(root,decision,basis,origin,comment)

def verify_authorization(cfg):
 """Called by the native workflow for plans produced by this helper."""
 choice=cfg.get('customer_choice')
 if not choice:return
 for key in ['request','response']:
  if sha(regular(unlinked(choice[key])))!=choice[key+'_sha256']:raise ValueError('Recorded customer choice changed')
 root=Path(choice['request']).parent;record,original=verified(root);response=read(choice['response'])
 if response.get('request_id')!=record['request_id'] or response.get('decision')!='allow':raise ValueError('No matching approval for this SQUEEZE trial')
 expected=dict(original,squeeze_preference='allow_if_justified',customer_choice=choice)
 if expected!=cfg:raise ValueError('SQUEEZE plan changed after the recorded customer choice')

def execute(root,profile,output):
 root=unlinked(root)
 with locks(root):
  verified(root)
  if read(root/'result.json')['status']!='ready_for_squeeze_trial':raise ValueError('This request is not authorized and ready')
  cfg=read(root/'authorized_plan.json');verify_authorization(cfg)
  record=root/'execution.json'
  if record.exists():return read(record)  # Never repeat a completed/failed/uncertain native trial automatically.
  state={'status':'started','output':str(unlinked(output)),'started_at':utc_now(),'ai_calls':0,'official_upload_performed':False};write_json(record,state)
  try:
   from squeeze_workflow import run
   native,out=run(root/'authorized_plan.json',profile,output)
   state.update(status=native['status'],result=str(out/'result.json'),scientific_acceptance=False,next_step=native.get('next_step'),failure=native.get('failure'))
  except Exception as e:state.update(status='failed',failure=str(e))
  state['finished_at']=utc_now();write_json(record,state);return state

def main():
 p=argparse.ArgumentParser(description=__doc__);sub=p.add_subparsers(dest='command',required=True)
 s=sub.add_parser('prepare');s.add_argument('--plan',required=True);s.add_argument('--output',required=True);s.add_argument('--intake')
 s=sub.add_parser('respond');s.add_argument('--request',required=True);g=s.add_mutually_exclusive_group(required=True);g.add_argument('--answer');g.add_argument('--decision',choices=list(CHOICES));s.add_argument('--basis')
 s=sub.add_parser('execute');s.add_argument('--request',required=True);s.add_argument('--profile',required=True);s.add_argument('--output',required=True)
 a=p.parse_args()
 try:
  if a.command=='prepare':state,out=prepare(a.plan,a.output,a.intake);state=dict(state,output=str(out))
  elif a.command=='respond':state=respond(a.request,a.answer,a.decision,a.basis)
  else:state=execute(a.request,a.profile,a.output)
  print(json.dumps(state,ensure_ascii=False));return 1 if state['status']=='failed' else 2 if state['status'] in ['needs_model_review','needs_customer_choice'] else 0
 except Exception as e:print(json.dumps({'status':'blocked','error':str(e)},ensure_ascii=False));return 1
if __name__=='__main__':sys.exit(main())
