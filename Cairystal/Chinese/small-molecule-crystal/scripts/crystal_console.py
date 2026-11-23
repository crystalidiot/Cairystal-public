"""Local Cairystal console: observed progress, immutable plans and explicit runs.

The browser never writes existing run records. Only explicitly registered roots
are inspected. No language-model calls. Scientific decisions stay in the runner.
"""
from pathlib import Path
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
from urllib.parse import urlparse,parse_qs,unquote,quote
import argparse,hashlib,json,math,mimetypes,os,re,secrets,subprocess,sys,threading,time,webbrowser
from datetime import datetime,timezone

ROOT=Path(__file__).resolve().parent.parent
STATE_NAMES={'autorun.json','pipeline.json','state.json','result.json','attempt.json','console_run.json'}
SKIP_DIRS={'__pycache__','.git','node_modules','inputs','raw','scratch','support','canonical_before'}
FIELDS={'max_candidates':(1,6,6),'max_weight_updates':(0,6,4),'timeout':(1,3600,180)}
STAGES=[('data','数据检查','核对原始文件、晶胞、元素和实验信息'),('solve','初始求解','由求解程序生成候选模型'),('chemistry','元素与氢','核对化学连接、元素指认和加氢'),('refine','精修与权重','优化坐标和热参数，检查权重与收敛'),('validation','模型与 A/B','查看无序、几何、占有率和警告'),('official','官网 checkCIF','验证确切的最终 CIF 和结构因子'),('reports','报告与交付','官网 PDF、中英文 Word 和最终 CIF')]
STATUS_ZH={'complete':'文件流程已完成','completed':'记录显示已交付','artifacts_complete':'文件已齐全','delivery_complete_needs_scientific_review':'文件已交付，需科学复核','diagnostic_artifacts_complete_scientific_blocked':'诊断报告已出，结构仍待处理','ready_for_official_delivery':'本地完成，待官网验证','local_complete_waiting_delivery':'本地完成，待生成报告','local_ready':'本地阶段完成','awaiting_upload_authorization':'等待官网上传授权','official_upload_not_authorized':'等待官网上传授权','needs_attention':'需要进一步处理','needs_scientific_review':'需要科学判断','needs_report_review':'报告需要复核','needs_weight_review':'权重需要复核','needs_alert_review':'警告需要复核','running':'正在处理','failed':'本次运行失败','blocked':'当前步骤受阻','incomplete':'尚未完成','not_run':'尚未运行','ready':'已准备','needs_review':'需要复核'}

def utc():return datetime.now(timezone.utc).isoformat()
def digest(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def path_checked(value):
 p=Path(os.path.abspath(value))
 for q in [p,*p.parents]:
  if q.is_symlink() or (hasattr(q,'is_junction') and q.is_junction()):raise ValueError('请使用真实目录，不能通过链接或目录联接访问：'+str(q))
 return p
def contained(root,value):
 p=path_checked(value if Path(value).is_absolute() else root/value)
 if not p.is_relative_to(root):raise ValueError('文件不在本次已登记的任务目录内')
 return p
def read_json(path,max_bytes=8*1024*1024):
 p=path_checked(path)
 if not p.is_file() or p.stat().st_size>max_bytes:raise ValueError('记录缺失或过大：'+str(p))
 value=json.loads(p.read_text('utf-8-sig'))
 if not isinstance(value,dict):raise ValueError('记录必须是 JSON 对象')
 return value
def write_json(path,value):
 p=Path(path);temp=p.with_name(p.name+'.'+secrets.token_hex(4)+'.tmp')
 temp.write_text(json.dumps(value,ensure_ascii=False,indent=2,allow_nan=False),'utf-8');temp.replace(p)
def number(v):return v if isinstance(v,(int,float)) and not isinstance(v,bool) and math.isfinite(v) else None
def counts(record,key):
 v=record.get(key)
 if not isinstance(v,dict):return None
 return {k:number(v.get(k)) for k in 'ABCG'}
def metrics(record):
 raw=record.get('metrics') or record.get('native_metrics') or record.get('final_metrics') or (record.get('gate') or {}).get('metrics') or {}
 if not isinstance(raw,dict):raw={}
 def first(*keys):return next((number(raw[k]) for k in keys if number(raw.get(k)) is not None),None)
 return {'R1':first('R1','R1_observed','r1'),'wR2':first('wR2','wr2'),'GoF':first('GoF','GooF','goof'),
         'delta_max':first('residual_max','residual_max_e_A3','difference_max'),'delta_min':first('residual_min','residual_min_e_A3','difference_min'),
         'unique_reflections':first('unique'),'max_shift_esd':first('last_abs_max_shift_esd')}
def stage_id(text):
 text=str(text).lower()
 if any(x in text for x in ['report','bilingual','package','finalize','delivery_completeness','rendering','structure_viewer','assistance_credit','atom_table_order']):return 'reports'
 if any(x in text for x in ['official','iucr','resume_delivery']):return 'official'
 if any(x in text for x in ['local_validation','platon','diagnos','validation','check','routine_consistency_gate','atom_numbering_gate']):return 'validation'
 if any(x in text for x in ['input','intake','metadata','preflight','data']):return 'data'
 if any(x in text for x in ['hydrogen','hfix','match','graph','typing','element','chemistry']):return 'chemistry'
 if any(x in text for x in ['solve','shelxt','shelxd','start']):return 'solve'
 if any(x in text for x in ['refin','weight','shelxl','cycle']):return 'refine'
 return None

def event_time(event):
 try:return datetime.fromisoformat(str(event.get('at') or '').replace('Z','+00:00')).timestamp()
 except (ValueError,TypeError):return 0
def status_kind(s):
 if s in {'running','starting','delivering'}:return 'running'
 if any(x in s for x in ['blocked','failed']):return 'failed'
 if any(x in s for x in ['review','attention','incomplete','waiting','authorization','ready_for_official']):return 'review'
 if s in {'complete','completed','artifacts_complete','local_ready'}:return 'done'
 return 'unknown'

class Console:
 def __init__(self,workspace,profile=None):
  self.workspace=path_checked(workspace);self.workspace.mkdir(parents=True,exist_ok=True)
  if self.workspace==ROOT or self.workspace.is_relative_to(ROOT):raise ValueError('控制台工作目录必须在冻结 skill 之外')
  self.profile=path_checked(profile) if profile else None
  self.registry=self.workspace/'console_registry.json';self.guard=threading.RLock();self.workers={};self.cache={}
  for name in ['plans','runs']:(self.workspace/name).mkdir(exist_ok=True)
  if not self.registry.exists():write_json(self.registry,{'schema':1,'jobs':[]})
 def registered(self):return read_json(self.registry)['jobs']
 def job(self,jid):
  if not re.fullmatch(r'[a-f0-9]{16}',str(jid)):raise ValueError('任务编号无效')
  return next((x for x in self.registered() if x['id']==jid),None) or self.missing()
 def missing(self):raise ValueError('任务不存在')
 def register(self,folder,label=''):
  root=path_checked(folder)
  if not root.is_dir():raise ValueError('找不到任务文件夹')
  if len(root.parts)<3:raise ValueError('请选择具体任务目录，不要选择整个磁盘')
  # Only known root records identify an existing run; no broad drive search.
  if not any((root/n).is_file() for n in STATE_NAMES) and not (root/'execution').is_dir():raise ValueError('此目录没有任务记录；请选择含 result.json / pipeline.json / autorun.json 的运行目录')
  jid=hashlib.sha256(str(root).casefold().encode()).hexdigest()[:16]
  with self.guard:
   registry=read_json(self.registry)
   if any(x['id']==jid for x in registry['jobs']):return self.job(jid)
   item={'id':jid,'root':str(root),'label':str(label or root.name)[:100],'registered_at':utc()}
   registry['jobs'].append(item);write_json(self.registry,registry)
  return item
 def records(self,root):
  found=[];issues=[];visited=0
  def visit(folder,depth=0):
   nonlocal visited
   if depth>9 or visited>=1600:return
   for p in sorted(folder.iterdir()):
    visited+=1
    if visited>1600:break
    if p.is_symlink() or (hasattr(p,'is_junction') and p.is_junction()):continue
    if p.is_dir() and p.name not in SKIP_DIRS:visit(p,depth+1)
    elif p.is_file() and p.name in STATE_NAMES:
     if len(found)>=240:continue
     try:found.append((p,read_json(p)))
     except (ValueError,OSError) as e:issues.append(str(e))
  visit(root)
  if visited>=1600 or len(found)>=240:issues.append('只展示有界索引；目录较大，部分子记录未展开')
  return found,issues
 def snapshot(self,jid,force=False):
  job=self.job(jid);root=path_checked(job['root']);now=time.monotonic()
  cached=self.cache.get(jid)
  if not force and cached and now-cached[0]<2:return cached[1]
  records,issues=self.records(root);by_path={p:r for p,r in records}
  top=next(((p,by_path[p]) for p in [root/'result.json',root/'autorun.json',root/'pipeline.json',root/'state.json',root/'attempt.json',root/'console_run.json'] if p in by_path),(root,{}))
  # The execution subdirectory is authoritative for console-launched tasks.
  for name in ['result.json','autorun.json','pipeline.json']:
   if root/'execution'/name in by_path:top=(root/'execution'/name,by_path[root/'execution'/name]);break
  source,record=top;status=str(record.get('status') or ('unknown' if record.get('success') is None else 'completed' if record.get('success') else 'failed'))
  official=counts(record,'official_counts') or counts(record.get('official') or {},'counts')
  local=counts(record,'local_counts');met=metrics(record)
  ab=record.get('AB_alerts') if isinstance(record.get('AB_alerts'),list) else record.get('AB')
  if not isinstance(ab,list):ab=(record.get('customer_delivery') or {}).get('remaining_AB',[])
  if not isinstance(ab,list):ab=[]
  ab=[{k:str(x.get(k,'')) for k in ['code','full_code','level','text','category']} for x in ab if isinstance(x,dict) and x.get('level') in ['A','B']]
  stages={k:{'id':k,'title':t,'description':d,'status':'unknown','seconds':None,'events':[]} for k,t,d in STAGES}
  attempts=[];timeline=[]
  for p,r in records:
   for ev in (r.get('events') or r.get('actions') or []):
    if not isinstance(ev,dict):continue
    name=ev.get('stage') or ev.get('name') or ev.get('action') or 'step';key=stage_id(name)
    event={'name':str(name),'status':str(ev.get('status','recorded')),'seconds':number(ev.get('seconds')),'at':ev.get('started_at'),'source':p.relative_to(root).as_posix(),'message':ev.get('error') or ev.get('reason')}
    # Keep the top-level elapsed events for a step rather than summing nested work twice.
    if key:stages[key]['events'].append(event)
    else:event['unmapped']=True
    timeline.append(event)
   if p.name=='attempt.json':
    hashes=r.get('inputs') or {};hkl=next((v for k,v in hashes.items() if k.lower().endswith('.hkl')),None)
    attempts.append({'id':hashlib.sha256(p.relative_to(root).as_posix().encode()).hexdigest()[:12],
     'label':p.parent.relative_to(root).as_posix(),'record':p.relative_to(root).as_posix(),'at':r.get('started_at'),
     'metrics':metrics(r),'seconds':number(r.get('elapsed_s')),'status':'review' if (r.get('gate') or {}).get('review_reasons') else 'done' if r.get('success') is True else 'review' if (r.get('gate') or {}).get('execution_complete') else 'failed',
     'reason':r.get('reason'),'warnings':(r.get('gate') or {}).get('review_reasons',[]),'hkl_sha256':hkl,'official_counts':None})
    command=r.get('command') or []
    if isinstance(command,list) and command:
     name=Path(str(command[0])).stem.lower();key=stage_id(name)
     if key in {'refine','solve'}:stages[key]['events'].append({'name':name+' · '+p.parent.relative_to(root).as_posix(),'status':'needs_review' if (r.get('gate') or {}).get('review_reasons') else 'completed' if r.get('success') is True else 'failed','seconds':number(r.get('elapsed_s')),'at':r.get('started_at'),'source':p.relative_to(root).as_posix(),'message':r.get('reason')})
  for s in stages.values():
   events=sorted(s['events'],key=event_time);s['events']=events
   if events:
    latest=events[-1];s['status']='done' if latest['status'] in {'completed','checkpointed'} else status_kind(latest['status'])
    s['seconds']=latest['seconds']
  if attempts and stages['refine']['status']=='unknown':stages['refine']['status']='review'
  if any(v is not None for v in met.values()) and stages['refine']['status']=='unknown':stages['refine']['status']='review'
  if local is not None and all(local.get(k) is not None for k in 'AB'):stages['validation']['status']='review' if any(local[k]>0 for k in 'AB') else 'done'
  if official is not None and all(official.get(k) is not None for k in 'AB'):stages['official']['status']='done'
  if ab or (official and any((official.get(k) or 0)>0 for k in 'AB')):stages['validation']['status']='review'
  if status_kind(status)=='running':
   active=record.get('active_stage') or record.get('phase') or record.get('pending')
   key=stage_id(active) if active else None
   if key:stages[key]['status']='running'
  artifacts=self.artifacts(root,record)
  if sum(x['kind'] in {'cif','official','zh','en'} and x['exists'] for x in artifacts)==4:stages['reports']['status']='done'
  if status_kind(status) in {'review','failed'}:stages['refine']['status']='review'
  result={**job,'status':status,'status_label':STATUS_ZH.get(status,'查看任务记录'),'status_kind':status_kind(status),'metrics':met,'official_counts':official,'local_counts':local,'alerts':ab,
   'stages':list(stages.values()),'attempts':sorted(attempts,key=lambda a:str(a['at'] or '')),'artifacts':artifacts,'source_record':str(source),
   'recorded_version':record.get('pinned_release') or record.get('fixed_skill') or (record.get('workflow_version') or {}).get('release'),
   'reason':record.get('reason') or record.get('failure') or record.get('last_command_error'),
   'scientific_status':record.get('scientific_acceptance') or record.get('scientific_correctness') or 'not_established',
   'input_directory':record.get('input_directory') or (record.get('options') or {}).get('data_dir'),
   'issues':issues[:10],'unmapped_events':[e for e in timeline if e.get('unmapped')],'observed_at':utc(),'elapsed_seconds':number(record.get('seconds') or record.get('elapsed_seconds') or record.get('automated_elapsed_s')),
   'notice':'依据保存的记录展示；未知阶段不推定完成。文件齐全、低 R 或零 A/B 不等于结构正确。'}
  self.cache[jid]=(now,result);return result
 def artifacts(self,root,record):
  mapping={};raw={}
  for candidate in [record.get('artifacts'),record.get('deliverables'),record.get('customer_delivery',{}).get('files')]:
   if isinstance(candidate,dict):raw.update(candidate)
  for kind,keys in [('cif',['final_cif','cif','diagnostic_CIF']),('official',['official_checkcif_pdf','checkcif_pdf']),('zh',['word_zh']),('en',['word_en']),('viewer',['viewer'])]:
   for key in keys:
    if isinstance(raw.get(key),str):
     try:mapping[kind]=contained(root,raw[key]);break
     except ValueError:pass
  for candidate in [record.get('customer_directory'),(record.get('customer_delivery') or {}).get('directory'),record.get('delivery')]:
   if isinstance(candidate,str):
    try:
     folder=contained(root,candidate)
     if folder.is_dir():self.artifact_folder(folder,mapping)
    except ValueError:pass
  if (root/'Cairystal').is_dir():self.artifact_folder(root/'Cairystal',mapping)
  if (root/'delivery').is_dir():self.artifact_folder(root/'delivery',mapping)
  titles={'cif':'最终 / 当前 CIF','official':'IUCr 官网 checkCIF','zh':'中文晶体学表','en':'English report','viewer':'可拖动结构模型'}
  return [{'kind':k,'title':titles[k],'path':p.relative_to(root).as_posix(),'exists':p.is_file()} for k,p in mapping.items()]
 def artifact_folder(self,folder,mapping):
  for k,name in [('official','IUCr_checkCIF.pdf'),('zh','晶体学报表_中文.docx'),('en','Crystallographic_Report_EN.docx'),('viewer','structure_viewer.html')]:
   if k not in mapping and (folder/name).is_file():mapping[k]=folder/name
  cifs=[p for p in folder.glob('*.cif') if p.is_file()]
  if 'cif' not in mapping and len(cifs)==1:mapping['cif']=cifs[0]
 def plan_list(self):
  return [read_json(p) for p in sorted((self.workspace/'plans').glob('*/plan.json'),reverse=True)][:80]
 def save_plan(self,payload):
  allowed={'name','note','parent_id','data_dir','elements','max_candidates','max_weight_updates','timeout','specimen','graph','donor_basis','colour','habit','dimensions_mm','observations_confirmed','diagram_image_data_url'}
  if not isinstance(payload,dict) or set(payload)-allowed:raise ValueError('方案包含不支持的字段')
  values={}
  for k,(lo,hi,default) in FIELDS.items():
   v=payload.get(k,default)
   if type(v) is not int or not lo<=v<=hi:raise ValueError(k+' 超出程序支持范围')
   values[k]=v
  if not self.profile:raise ValueError('启动控制台时需配置本机 runtime profile')
  data=str(payload.get('data_dir','')).strip()
  if not data:raise ValueError('请填写原始数据文件夹')
  data=path_checked(data)
  if not data.is_dir():raise ValueError('原始数据文件夹不存在')
  if self.workspace==data or self.workspace.is_relative_to(data):raise ValueError('数据与控制台工作目录需分开，避免改动原始输入')
  from pipeline_intake import normalize_elements,bootstrap
  try:bootstrap(read_json(self.profile))
  except ImportError as e:raise ValueError('本机 Python 环境缺少依赖，请按安装指南检查：'+str(e)) from e
  elements=payload.get('elements',[])
  if not isinstance(elements,list):raise ValueError('元素应为列表')
  elements=normalize_elements(elements)
  if type(payload.get('observations_confirmed',False)) is not bool:raise ValueError('外观确认必须为布尔值')
  parent=payload.get('parent_id');previous=None
  if parent:
   if not re.fullmatch(r'[0-9a-f]{24}',str(parent)):raise ValueError('父方案编号无效')
   previous=read_json(self.workspace/'plans'/parent/'plan.json')
  from intake_once import normalized,extract_uploaded_diagram,export
  raw={'schema':1,'data_dir':str(data),'elements':elements,'colour':payload.get('colour'),'habit':payload.get('habit'),
       'dimensions_mm':payload.get('dimensions_mm'),'observations_confirmed':payload.get('observations_confirmed',False),
       'diagram_image_data_url':payload.get('diagram_image_data_url'),'iucr_upload':'not_answered'}
  if previous and not raw['diagram_image_data_url'] and str(data)==previous['config']['data_dir']:
   raw['diagram_image_data_url']=read_json(self.workspace/'plans'/parent/'intake.json',12000000).get('diagram_image_data_url')
  normalized(raw);extract_uploaded_diagram(raw)
  if payload.get('specimen') and any(payload.get(k) for k in ['colour','habit','dimensions_mm']):raise ValueError('外观请直接填写或使用已有信息文件，两者选择一种')
  config={'schema':1,'data_dir':str(data),'profile':str(self.profile),'elements':elements,**values,'deliver':True,'authorize_iucr_upload':False}
  for name in ['specimen','graph']:
   if payload.get(name):
    p=path_checked(payload[name])
    if not p.is_file():raise ValueError(name+' 文件不存在')
    config[name]=str(p)
  if payload.get('donor_basis'):config['donor_basis']=str(payload['donor_basis'])[:4000]
  identifier=secrets.token_hex(12);folder=self.workspace/'plans'/identifier;folder.mkdir()
  evidence={}
  for name in ['specimen','graph']:
   if config.get(name):
    source=Path(config[name]);read_json(source)
    target=folder/(name+'.json');target.write_bytes(source.read_bytes());config[name]=str(target)
    evidence[name]={'source':str(source),'sha256':digest(target)}
  write_json(folder/'intake.json',raw);state,intake_dir=export(folder/'intake.json',folder/'intake',self.profile)
  config['intake_state']=str(intake_dir/'intake_state.json')
  if not config.get('specimen') and (intake_dir/'specimen.json').is_file():config['specimen']=str(intake_dir/'specimen.json')
  write_json(folder/'autorun_config.json',config)
  appearance={k:raw[k] for k in ['colour','habit','dimensions_mm','observations_confirmed']}
  changes=[{'parameter':k,'before':previous['config'].get(k),'after':v} for k,v in config.items() if previous and k not in {'specimen','intake_state','graph'} and previous['config'].get(k)!=v]
  if previous:
   for k,v in appearance.items():
    if previous.get('appearance',{}).get(k)!=v:changes.append({'parameter':k,'before':previous.get('appearance',{}).get(k),'after':v})
   for k in ['specimen','graph']:
    before=previous.get('evidence',{}).get(k,{}).get('sha256');after=evidence.get(k,{}).get('sha256')
    if before!=after:changes.append({'parameter':k,'before':before,'after':after})
  value={'id':identifier,'name':str(payload.get('name') or '我的解析方案')[:100],'note':str(payload.get('note') or '')[:2000],
   'created_at':utc(),'parent_id':parent,'config':config,'changes':changes,'config_sha256':digest(folder/'autorun_config.json'),
   'config_path':str(folder/'autorun_config.json'),'status':'saved_not_run','skill_release':read_json(ROOT/'release_info.json').get('release_id'),
   'profile_sha256':digest(self.profile),'appearance':appearance,'evidence':evidence,'has_diagram':bool(raw['diagram_image_data_url']),
   'file_hashes':{p.relative_to(folder).as_posix():digest(p) for p in folder.rglob('*') if p.is_file()},
   'boundary':'保存不会执行，也不会改变旧模型。官网上传仍需针对本次样品的明确授权。'}
  write_json(folder/'plan.json',value);return value
 def start_plan(self,identifier):
  if not re.fullmatch(r'[0-9a-f]{24}',str(identifier)):raise ValueError('方案编号无效')
  folder=self.workspace/'plans'/identifier;plan=read_json(folder/'plan.json');config=folder/'autorun_config.json'
  if digest(config)!=plan['config_sha256']:raise ValueError('方案文件发生变化，请另存新版本')
  for rel,expected in plan.get('file_hashes',{}).items():
   if digest(contained(folder,rel))!=expected:raise ValueError('方案证据发生变化，请核对后另存新版本：'+rel)
  if digest(self.profile)!=plan['profile_sha256']:raise ValueError('本机环境配置已改变，请核对后另存方案')
  if read_json(ROOT/'release_info.json').get('release_id')!=plan['skill_release']:raise ValueError('方案对应其他 skill 版本，请从原版本运行或另存方案')
  if plan['config'].get('authorize_iucr_upload') is not False:raise ValueError('本入口不隐式授权上传')
  from pipeline_intake import verify_profile,discover
  profile=read_json(self.profile);verify_profile(profile)
  # Fail before launching a known unsupported intake instead of a fake progress bar.
  try:discover(path_checked(plan['config']['data_dir']))
  except ValueError as e:raise ValueError('暂不能自动开始：需要唯一一组同名 HKL / P4P。仅有 HKL + JSON 或存在多组数据时，请先交由 agent 准备输入。原始原因：'+str(e)) from e
  with self.guard:
   for existing_id,proc in self.workers.items():
    if proc.poll() is None and read_json(self.workspace/'runs'/existing_id/'console_run.json').get('plan_id')==identifier:raise ValueError('这份方案已有正在运行的任务，请先查看进度')
   run_id=datetime.now().strftime('%Y%m%d_%H%M%S')+'_'+secrets.token_hex(4)
   run=self.workspace/'runs'/run_id;run.mkdir();log=run/'execution.log'
   command=[profile['python'],'-B',str(ROOT/'scripts/crystal_autorun.py'),'run','--config',str(config),'--output',str(run/'execution')]
   write_json(run/'console_run.json',{'status':'running','started_at':utc(),'plan_id':identifier,'command':command,'config_sha256':digest(config),'upload_authorized':False})
   env=os.environ.copy();env.update(PYTHONUTF8='1',PYTHONIOENCODING='utf-8',CAIRYSTAL_NO_OPEN='1')
   stream=log.open('x',encoding='utf-8')
   try:proc=subprocess.Popen(command,stdout=stream,stderr=subprocess.STDOUT,cwd=run,env=env,creationflags=0x08000000 if os.name=='nt' else 0,shell=False)
   except Exception:
    stream.close();write_json(run/'console_run.json',{'status':'failed','reason':'无法启动运行程序','plan_id':identifier});raise
   self.workers[run_id]=proc;item=self.register(run,plan['name'])
   def reap():
    rc=proc.wait();stream.close();r=read_json(run/'console_run.json');r.update(status='completed' if rc==0 else 'needs_review' if rc==2 else 'failed',returncode=rc,finished_at=utc());write_json(run/'console_run.json',r)
    self.cache.pop(item['id'],None)
   threading.Thread(target=reap,daemon=True).start()
  return {'job':item,'status':'started','run_directory':str(run),'upload_authorized':False}
 def file(self,jid,relative):
  root=path_checked(self.job(jid)['root']);p=contained(root,relative)
  if not p.is_file():raise ValueError('文件不存在')
  allowed={'.json','.txt','.log','.md','.pdf','.docx','.cif','.res','.ins','.hkl','.lst','.fcf','.html'}
  if p.suffix.lower() not in allowed:raise ValueError('此类文件不在查看范围内')
  if p.suffix.lower()=='.html' and p.name!='structure_viewer.html':raise ValueError('只允许显示本地结构查看器 HTML')
  return p

def serve(console,port=8765,open_browser=False,ready_file=None):
 token=secrets.token_urlsafe(32);static=ROOT/'assets/console';code_hash=digest(__file__)
 class Handler(BaseHTTPRequestHandler):
  def log_message(self,*args):pass
  def response(self,value,code=200):
   data=json.dumps(value,ensure_ascii=False,allow_nan=False).encode('utf-8');self.send_response(code);self.send_header('Content-Type','application/json; charset=utf-8');self.send_header('Cache-Control','no-store');self.send_header('Content-Length',str(len(data)));self.end_headers();self.wfile.write(data)
  def auth(self,write=False):
   expected=f'127.0.0.1:{self.server.server_port}'
   if self.headers.get('Host')!=expected:raise ValueError('仅支持本机访问')
   checked_path=unquote(urlparse(self.path).path)
   if checked_path.startswith('/api/') or checked_path.startswith('/file/'):
    cookie=dict(x.strip().split('=',1) for x in self.headers.get('Cookie','').split(';') if '=' in x)
    if not secrets.compare_digest(cookie.get('cairystal_console',''),token):raise ValueError('请从控制台首页重新打开')
   if write:
    if self.headers.get('Origin')!='http://'+expected or not secrets.compare_digest(self.headers.get('X-Cairystal-Token',''),token):raise ValueError('请求不来自本机控制台')
  def do_GET(self):
   try:
    self.auth();parsed=urlparse(self.path);params=parse_qs(parsed.query);path=unquote(parsed.path)
    if path=='/health':return self.response({'service':'cairystal-console','pid':os.getpid(),'code_hash':code_hash,'skill_root':str(ROOT.resolve()),'workspace_hash':hashlib.sha256(str(console.workspace).casefold().encode()).hexdigest()})
    if path=='/api/jobs':return self.response({'jobs':console.registered(),'release':read_json(ROOT/'release_info.json').get('release_id'),'profile_ready':bool(console.profile),'workspace':str(console.workspace)})
    if path=='/workflow-data.json':
     data=read_json(static/'workflow-data.json');data['release']=read_json(ROOT/'release_info.json')['release_id'];return self.response(data)
    if path=='/api/snapshot':return self.response(console.snapshot(params.get('job',[''])[0]))
    if path=='/api/plans':return self.response({'plans':console.plan_list()})
    if path.startswith('/file/'):
     _,_,jid,rel=path.split('/',3);p=console.file(jid,rel);mime=mimetypes.guess_type(p.name)[0] or 'application/octet-stream'
     self.send_response(200);self.send_header('Content-Type',mime+'; charset=utf-8' if mime.startswith('text/') else mime)
     self.send_header('Cache-Control','no-store');self.send_header('X-Content-Type-Options','nosniff')
     if p.suffix=='.html':self.send_header('Content-Security-Policy',"sandbox allow-scripts; default-src 'none'; script-src 'unsafe-inline'; style-src 'unsafe-inline'; img-src data:; connect-src 'none'")
     elif p.suffix not in {'.pdf','.txt','.json','.log','.md'}:
      self.send_header('Content-Disposition',"attachment; filename=download"+p.suffix+"; filename*=UTF-8''"+quote(p.name,safe=''))
     self.send_header('Content-Length',str(p.stat().st_size));self.end_headers()
     with p.open('rb') as f:
      while chunk:=f.read(65536):self.wfile.write(chunk)
     return
    files={'/':static/'workflow.html','/workspace':static/'index.html','/workflow.js':static/'workflow.js','/workflow.css':static/'workflow.css','/workflow-data.json':static/'workflow-data.json','/app.js':static/'app.js','/app.css':static/'app.css','/app.js.LEGAL.txt':static/'app.js.LEGAL.txt','/logo.png':ROOT/'assets/Cairystal-logo.png'}
    files.update({'/automation':static/'automation.html','/automation.js':static/'automation.js','/automation.css':static/'automation.css','/ab-policy.json':ROOT/'assets/ab_policy.json'})
    if path not in files:return self.response({'error':'找不到此页面'},404)
    p=files[path];data=p.read_bytes()
    if path in {'/','/workspace'}:data=data.replace(b'__CSRF_TOKEN__',token.encode())
    self.send_response(200);self.send_header('Content-Type',mimetypes.guess_type(p.name)[0] or 'application/octet-stream');self.send_header('Content-Length',str(len(data)))
    self.send_header('Cache-Control','no-store');self.send_header('X-Content-Type-Options','nosniff')
    if path in {'/','/workspace'}:
     self.send_header('Set-Cookie',f'cairystal_console={token}; HttpOnly; SameSite=Strict; Path=/')
     self.send_header('Content-Security-Policy',"default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; connect-src 'self'; frame-src 'self'; object-src 'none'; base-uri 'none'; frame-ancestors 'none'")
    self.end_headers();self.wfile.write(data)
   except (OSError,ValueError,KeyError,TypeError) as e:self.response({'error':str(e)},400)
  def do_POST(self):
   try:
    self.auth(True);length=int(self.headers.get('Content-Length','0'))
    if not 0<length<=12000000:raise ValueError('请求内容过大或为空')
    p=json.loads(self.rfile.read(length));route=urlparse(self.path).path
    if route=='/api/register':return self.response(console.register(p['path'],p.get('label','')))
    if route=='/api/plans':return self.response(console.save_plan(p))
    if route=='/api/run-plan':return self.response(console.start_plan(p['id']))
    return self.response({'error':'不支持此操作'},404)
   except (ValueError,OSError,KeyError,TypeError,ImportError) as e:self.response({'error':str(e)},400)
 server=ThreadingHTTPServer(('127.0.0.1',port),Handler);server.daemon_threads=True
 url=f'http://127.0.0.1:{server.server_port}/'
 info={'url':url,'pid':os.getpid(),'workspace':str(console.workspace),'started_at':utc(),'release':read_json(ROOT/'release_info.json').get('release_id')}
 if ready_file:write_json(path_checked(ready_file),info)
 print(json.dumps(info,ensure_ascii=False),flush=True)
 if open_browser:webbrowser.open(url)
 try:server.serve_forever()
 finally:server.server_close()

def main():
 p=argparse.ArgumentParser(description='Cairystal 本地可视化控制台；只读取登记任务，方案另存，执行须点击开始。')
 p.add_argument('--workspace',required=True);p.add_argument('--profile');p.add_argument('--port',type=int,default=8765);p.add_argument('--open',action='store_true');p.add_argument('--register',action='append',default=[]);p.add_argument('--ready-file')
 a=p.parse_args();console=Console(a.workspace,a.profile)
 for folder in a.register:console.register(folder)
 serve(console,a.port,a.open,a.ready_file)
if __name__=='__main__':main()
