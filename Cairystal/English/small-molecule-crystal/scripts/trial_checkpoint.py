"""Verified continuation of a diagnostic comparison in a new output directory."""
from pathlib import Path
import ctypes,hashlib,json,os,shutil,time
from crystal_runtime import sha,write_json,check_stem

def hashes(directory):
    root=Path(directory)
    if not root.is_dir() or root.is_symlink():raise ValueError('Expected ordinary evidence directory: '+str(root))
    found={}
    for p in sorted(root.rglob('*')):
        if p.is_symlink():raise ValueError('Redirected evidence unsupported: '+str(p))
        if p.is_file():found[p.relative_to(root).as_posix()]=sha(p)
    return found

def context(job):
    from native_resources import effective
    # All script sources and scientific JSON resources are pinned, including
    # transitive helpers which a short per-recipe import list can miss.
    scripts=Path(__file__).parent;assets=scripts.parent/'assets'
    return {'baseline':hashes(job['baseline']),
        'software':{k:{'path':str(Path(p).resolve()),'sha256':sha(p)} for k,p in job['software'].items()},
        'implementation':{p.name:sha(p) for p in sorted(scripts.glob('*.py'))},
        'resources':{p.relative_to(assets).as_posix():sha(p) for p in sorted(assets.rglob('*.json'))},
        'trials':job['trials'],'focus':job.get('focus'),'native_resources':effective(**job.get('shelxl_resources',{}))}

def alive(pid):
    if type(pid)!=int or pid<=0:return True
    if os.name=='nt':
        kernel=ctypes.WinDLL('kernel32',use_last_error=True)
        kernel.OpenProcess.argtypes=[ctypes.c_ulong,ctypes.c_int,ctypes.c_ulong];kernel.OpenProcess.restype=ctypes.c_void_p
        kernel.WaitForSingleObject.argtypes=[ctypes.c_void_p,ctypes.c_ulong];kernel.WaitForSingleObject.restype=ctypes.c_ulong
        kernel.CloseHandle.argtypes=[ctypes.c_void_p]
        handle=kernel.OpenProcess(0x00100000,False,pid)
        if not handle:return ctypes.get_last_error()!=87  # Access denied is not proof of exit.
        try:return kernel.WaitForSingleObject(handle,0)!=0
        finally:kernel.CloseHandle(handle)
    try:os.kill(pid,0);return True
    except ProcessLookupError:return False
    except PermissionError:return True

def validate_names(trials):
    if not isinstance(trials,list) or not trials:raise ValueError('Nonempty trial plan required')
    names=[]
    for item in trials:names.append(check_stem(item['name']).casefold())
    if len(set(names))!=len(names):raise ValueError('Repeated trial name (case-insensitive)')

def verified_previous(job,ctx):
    spec=job.get('resume_from')
    if not spec:return {},{}
    old=Path(spec['output']);saved=json.loads((old/'checkpoint.json').read_text('utf8'))
    if sha(old/'checkpoint.json')!=spec['checkpoint_sha256']:raise ValueError('Previous checkpoint changed; it may still be running')
    lock=old/'running.json'
    if lock.is_file() and alive(json.loads(lock.read_text('utf8')).get('pid')):raise ValueError('Previous comparison is still running; do not resume concurrently')
    if saved['context']!=ctx:raise ValueError('Baseline, software, code, resources or trial definitions changed; prepare a new comparison')
    reuse={};counts=saved.get('attempt_counts',{})
    for row in saved['finished']:
        name=row['name'];check_stem(name);directory=old/name
        if hashes(directory)!=row['artifact_sha256']:raise ValueError('Previous trial artifacts changed: '+name)
        result=json.loads((directory/'result.json').read_text('utf8'))
        if result.get('name')!=name or result.get('status')!=row['status']:raise ValueError('Checkpoint/result mismatch: '+name)
        if spec.get('retry_failed') and result['status']=='failed':
            if counts.get(name,1)>=2:raise ValueError('Failed trial already retried once; diagnose or prepare a changed hypothesis: '+name)
            continue
        reuse[name]={'directory':str(directory),'result':result,'artifact_sha256':row['artifact_sha256']}
    return reuse,counts

class Checkpoint:
    def __init__(self,output,ctx,job,counts):
        self.out=Path(output);self.started=time.perf_counter()
        self.value={'schema':1,'state':'running','context':ctx,'finished':[],
            'pending':[p['name'] for p in job['trials']],'attempt_counts':dict(counts),
            'native_attempts_this_run':0,'started_trials_this_run':0,'reused_trials':0,'job':job}
        write_json(self.out/'running.json',{'pid':os.getpid()});self.save()
    def save(self):
        self.value['wall_seconds_this_run']=round(time.perf_counter()-self.started,4)
        write_json(self.out/'checkpoint.json',self.value)
    def begin(self,name):
        self.value['active']=name;self.value['started_trials_this_run']+=1
        self.value['attempt_counts'][name]=self.value['attempt_counts'].get(name,0)+1;self.save()
    def finish(self,result,reused=False):
        name=result['name'];self.value['finished'].append({'name':name,'status':result['status'],'artifact_sha256':hashes(self.out/name)})
        self.value['pending'].remove(name);self.value.pop('active',None)
        self.value['reused_trials']+=int(reused)
        self.value['native_attempts_this_run']+=int(not reused and bool(result.get('command')))
        self.save()
    def close(self,state,error=None):
        self.value['state']=state
        if error:self.value['error']=str(error)
        self.save();(self.out/'running.json').unlink(missing_ok=True)

def prepare_resume(plan,output,retry_failed=False):
    """Prepare a new repair-plan directory, preserving all previous artifacts."""
    if type(retry_failed)!=bool:raise ValueError('retry_failed must be boolean')
    path=Path(plan);job=json.loads(path.read_text('utf8'));old=Path(job['output'])
    if job.get('schema')!=1 or not job.get('recipe'):raise ValueError('Use a prepared repair-plan job')
    checkpoint=old/'checkpoint.json'
    if not checkpoint.is_file():raise ValueError('No verifiable checkpoint from this version; do not reuse unverified legacy results')
    out=Path(output)
    if out.exists():raise FileExistsError(str(out))
    if out.resolve().is_relative_to(old.resolve()):raise ValueError('New resume directory must be outside previous trial outputs')
    saved=json.loads(checkpoint.read_text('utf8'))
    # Dynamic RAM/affinity recommendations are not a reason to silently change
    # resources partway through the same comparison. Explicit user changes still fail.
    if not job.get('shelxl_resources'):
        pinned=saved.get('context',{}).get('native_resources')
        if not pinned:raise ValueError('Checkpoint has no pinned native resources; prepare a new comparison')
        job=dict(job,shelxl_resources=pinned)
    ctx=context(job);spec={'output':str(old.resolve()),'checkpoint_sha256':sha(checkpoint),'retry_failed':retry_failed}
    temporary=dict(job,resume_from=spec);reuse,counts=verified_previous(temporary,ctx)
    control=reuse.get(job['trials'][0]['name'])
    if control and control['result']['status']!='completed':raise ValueError('Control did not complete; diagnose first, then explicitly use --retry-failed if a rerun is justified')
    if all(p['name'] in reuse for p in job['trials']):raise ValueError('All trial records already exist; nothing to continue')
    out.mkdir(parents=True);shutil.copytree(job['baseline'],out/'baseline')
    shutil.copy2(path.parent/'request.json',out/'request.json')
    previous_plan=out/'previous_plan.json';shutil.copy2(path,previous_plan)
    new=dict(job,baseline=str((out/'baseline').resolve()),output=str((out/'trials').resolve()),resume_from=spec)
    new['stop_on_control_failure']=True
    write_json(out/'plan.json',new)
    result={'status':'prepared','plan':str(out/'plan.json'),'reused_trials':list(reuse),
        'pending_trials':[p['name'] for p in job['trials'] if p['name'] not in reuse],
        'retry_failed':retry_failed,'previous_outputs_modified':False,'model_adopted':False}
    write_json(out/'resume_preparation.json',result);return result
