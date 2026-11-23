"""SHELXT -> bounded SHELXD fallback, with explicit search hypotheses and logs.

Only coordinate-free input headers are accepted. Peak models require subsequent
refinement and chemical review; no R/CC threshold certifies a solved structure.
"""
import argparse,contextlib,io,json,math,re,shutil,time
from pathlib import Path
from types import SimpleNamespace
import gemmi
from crystal_runtime import records,sha
from structure_diagnostics import newjson
from shelx_input_preflight import validate_native_input,render_records
from run_crystal_stage import run as native_run

HEADERS={'TITL','REM','CELL','ZERR','LATT','SYMM','SFAC','UNIT','TREF','HKLF','END','TEMP'}

def header(text):
    rows=records(text);extra={r[0].upper() for r in rows}-HEADERS
    if extra:raise ValueError('Coordinate-free solution header required; unsupported records: '+str(sorted(extra)))
    validate_native_input(text)
    def one(key):
        found=[r for r in rows if r[0].upper()==key]
        if len(found)!=1:raise ValueError('Exactly one '+key+' required')
        return found[0]
    c=one('CELL');l=one('LATT');sf=one('SFAC');u=one('UNIT');hk=one('HKLF')
    if hk!=['HKLF','4']:raise ValueError('Ordinary HKLF 4 required')
    if any(not re.fullmatch('[A-Za-z]{1,2}',s) or gemmi.Element(s).atomic_number<=0 for s in sf[1:]):raise ValueError('Explicit simple SFAC elements required')
    cell=gemmi.UnitCell(*map(float,c[2:]));wave=float(c[1]);latt=int(l[1])
    if any(not math.isfinite(v) for v in cell.parameters) or any(v<=0 for v in cell.parameters[:3]) or any(not 0<v<180 for v in cell.parameters[3:]) or cell.volume<=0 or not math.isfinite(cell.volume) or not 0<wave<10:raise ValueError('Invalid cell or wavelength')
    if not 1<=abs(latt)<=7:raise ValueError('Invalid LATT')
    return dict(rows=rows,cell=cell,wavelength=wave,sfac=sf[1:],unit=list(map(float,u[1:])),latt=latt)

def default_hypotheses(text):
    h=header(text)
    # Only triclinic primitive symmetry is inferred without an extinction study.
    # Higher Laue seeds do not establish a SHELXD space group.
    if abs(h['latt'])!=1 or any(r[0].upper()=='SYMM' for r in h['rows']):return []
    n=sum(v for e,v in zip(h['sfac'],h['unit']) if e.upper() not in {'H','D'})
    if not math.isfinite(n) or n<=0:return []
    result=[]
    for sg,mult in [('P -1',2),('P 1',1)]:
        estimate=max(2,round(.75*n/mult))
        if estimate>200:continue
        result.append(dict(space_group=sg,find=estimate,ntry=30,
            basis='Primitive triclinic alternatives; FIND is 0.75 times the input search UNIT non-H count per general ASU. UNIT is only a phasing hypothesis, not established composition.'))
    return result

def configuration(text,config=None):
    config={} if config is None else config
    if not isinstance(config,dict) or set(config)-{'hypotheses','timeout_seconds','primary_timeout_seconds'}:raise ValueError('Fallback config accepts hypotheses and watchdog times only')
    timeout=config.get('timeout_seconds',600)
    if isinstance(timeout,bool) or not isinstance(timeout,(int,float)) or not math.isfinite(timeout) or not 1<=timeout<=3600:raise ValueError('Per-process watchdog must be 1..3600 seconds')
    primary=config.get('primary_timeout_seconds',timeout)
    if isinstance(primary,bool) or not isinstance(primary,(int,float)) or not math.isfinite(primary) or not 1<=primary<=3600:raise ValueError('Primary watchdog must be 1..3600 seconds')
    hypotheses=config.get('hypotheses',default_hypotheses(text))
    if not isinstance(hypotheses,list) or len(hypotheses)>6:raise ValueError('At most six explicit fallback hypotheses')
    for v in hypotheses:make_ins(text,v)
    return dict(timeout_seconds=timeout,primary_timeout_seconds=primary,hypotheses=hypotheses)

def make_ins(text,hypothesis):
    h=header(text);v=hypothesis
    if not isinstance(v,dict) or set(v)-{'space_group','find','ntry','basis','unit'} or not {'space_group','find','ntry','basis'}<=set(v):raise ValueError('Explicit space_group, find, ntry and basis required')
    if not isinstance(v['basis'],str) or not v['basis'].strip():raise ValueError('Space-group and composition search basis required')
    if type(v['find'])!=int or not 2<=v['find']<=500 or type(v['ntry'])!=int or not 1<=v['ntry']<=200:raise ValueError('Bounded FIND 2..500 and NTRY 1..200 required')
    sg=gemmi.find_spacegroup_by_name(v['space_group'])
    if sg is None or not h['cell'].is_compatible_with_spacegroup(sg):raise ValueError('Space-group hypothesis incompatible with metric cell')
    lattice={'P':1,'I':2,'R':3,'F':4,'A':5,'B':6,'C':7}.get(sg.centring_type())
    if lattice is None:raise ValueError('Unsupported centring setting')
    ops=sg.operations();centro=sg.is_centrosymmetric()
    primitive=[op for op in ops.sym_ops if op.triplet()!='x,y,z' and (not centro or op.det_rot()>0)]
    units=v.get('unit',h['unit'])
    if not isinstance(units,list) or len(units)!=len(h['sfac']) or any(isinstance(x,bool) or not isinstance(x,(float,int)) or not math.isfinite(x) or x<0 for x in units):raise ValueError('UNIT hypothesis must match SFAC with nonnegative counts')
    if not any(x>0 for e,x in zip(h['sfac'],units) if e.upper() not in {'H','D'}):raise ValueError('No non-H search content')
    rows=[['TITL','Cairystal','SHELXD','hypothesis'],next(r for r in h['rows'] if r[0].upper()=='CELL')]
    rows += [r for r in h['rows'] if r[0].upper()=='ZERR']
    rows += [['LATT',str(lattice if centro else -lattice)]]+[['SYMM',op.triplet().upper()] for op in primitive]
    rows += [['SFAC',*h['sfac']],['UNIT',*[f'{x:.8g}' for x in units]],['FIND',str(v['find'])],['NTRY',str(v['ntry'])],['MIND','1.0','-0.1'],['HKLF','4'],['END']]
    return render_records(rows)

def candidate(path,expected_cell,allowed_elements,expected_wavelength=None):
    try:
        from structure_diagnostics import res_records
        parsed=res_records(path);cs=[r for r in parsed['rows'] if r[0].upper()=='CELL']
        if len(cs)!=1 or len(cs[0])!=8:raise ValueError('Complete CELL wavelength and six parameters required')
        values=list(map(float,cs[0][1:]))
        if any(not math.isfinite(x) for x in values) or values[0]<=0:raise ValueError('Nonfinite or invalid candidate CELL/wavelength')
        if any(abs(x-y)>max(.0006,abs(y)*1e-6) for x,y in zip(values[1:],expected_cell.parameters)):raise ValueError('Cell change requires an explicit reciprocal-index transformation audit')
        if expected_wavelength is not None and abs(values[0]-expected_wavelength)>max(1e-6,abs(expected_wavelength)*1e-5):raise ValueError('Candidate wavelength differs from solution input')
        if not parsed['atoms']:raise ValueError('No recognised atom records')
        if not set(x.upper() for x in parsed['sfac'])<=set(x.upper() for x in allowed_elements):raise ValueError('Solver introduced an element outside input SFAC')
        if any(any(not math.isfinite(v) for v in a['xyz']) for a in parsed['atoms']):raise ValueError('Nonfinite coordinates')
        return dict(status='candidate_requires_refinement',path=str(path.resolve()),sites=len(parsed['atoms']),sha256=sha(path))
    except Exception as exc:return dict(status='unusable_output',path=str(path.resolve()),reason=str(exc))

def run_attempt(program,executable,text,hkl,out,timeout,runner=native_run):
    out=Path(out);prepared=out.parent/(out.name+'.ins');prepared.write_text(text,encoding='ascii')
    a=SimpleNamespace(executable=str(executable),ins=str(prepared),hkl=str(hkl),output=str(out),stem='model',reason='Fresh coordinate-free '+program+' hypothesis',timeout=timeout,fab=None)
    try:
        with contextlib.redirect_stdout(io.StringIO()):runner(a)
        result=json.loads((out/'attempt.json').read_text('utf8'))
    except Exception as exc:result={'success':False,'error':str(exc)}
    result['program']=program;result['directory']=str(out)
    result['failure_class']=('input_or_environment' if result.get('error') else 'timeout' if result.get('process_state')=='timeout' else 'native_process_error' if result.get('returncode') not in {0,None} else 'no_inspectable_candidate') if not result.get('success') else None
    return result

def fallback_reason(attempt,usable_count):
    if usable_count:return None
    if attempt.get('error') or attempt.get('failure_class') in {'input_or_environment','native_process_error'}:return 'blocked_environment_or_input'
    if attempt.get('returncode') not in {0,None} and attempt.get('process_state')!='timeout':return 'blocked_environment_or_input'
    return 'try_supported_SHELXD_hypotheses'

def run_fallback(text,hkl,shelxd,output,config=None,runner=native_run):
    start=time.perf_counter();h=header(text);cfg=configuration(text,config);out=Path(output);out.mkdir(parents=True,exist_ok=False)
    frozen=out/'input.hkl';shutil.copy2(hkl,frozen);hash0=sha(hkl)
    result=dict(schema=1,status='running',source_hkl=str(hkl),source_hkl_sha256=hash0,config=cfg,attempts=[],candidates=[],model_adopted=False,scientific_acceptance=False)
    def save():
        result['seconds']=round(time.perf_counter()-start,4);result['source_unchanged']=sha(hkl)==hash0 and sha(frozen)==hash0
        (out/'fallback.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf8')
    if not cfg['hypotheses']:
        result.update(status='input_insufficient',missing=['Evidence-based SHELXD space-group/FIND hypotheses for this non-triclinic input']);save();return result
    if shelxd is None or not Path(shelxd).is_file():
        result.update(status='software_environment_failure',error='SHELXD unavailable; no download or guessed executable');save();return result
    result['software']={'path':str(shelxd),'sha256':sha(shelxd)};save()
    for i,hyp in enumerate(cfg['hypotheses']):
        attempt=run_attempt('shelxd',shelxd,make_ins(text,hyp),frozen,out/f'd_{i+1}',cfg['timeout_seconds'],runner);attempt['hypothesis']=hyp
        result['attempts'].append(attempt)
        if attempt.get('success'):
            checks=[candidate(out/f'd_{i+1}'/n,h['cell'],h['sfac'],h['wavelength']) for n in attempt.get('candidate_outputs',[])]
            attempt['output_screening']=checks;result['candidates'] += [dict(c,program='SHELXD',hypothesis=hyp) for c in checks if c['status']=='candidate_requires_refinement']
        save()
        if attempt.get('failure_class') in {'input_or_environment','native_process_error'}:
            result.update(status='software_environment_failure',error='Shared input/native failure; stop repeated attempts');break
    else:result['status']='candidates_require_refinement_and_review' if result['candidates'] else 'solution_failed'
    if not result['source_unchanged']:result.update(status='integrity_failure')
    save();return result

def cascade(ins,hkl,shelxt,shelxd,output,config=None,runner=native_run):
    text=Path(ins).read_text('latin1');h=header(text);cfg=configuration(text,config);out=Path(output);out.mkdir(parents=True,exist_ok=False)
    hashes={str(p):sha(p) for p in [Path(ins),Path(hkl)]};frozen=out/'input.hkl';shutil.copy2(hkl,frozen)
    attempt=run_attempt('shelxt',shelxt,text,frozen,out/'shelxt',cfg['primary_timeout_seconds'],runner)
    checks=[candidate(out/'shelxt'/n,h['cell'],h['sfac'],h['wavelength']) for n in attempt.get('candidate_outputs',[])] if attempt.get('success') else []
    usable=[dict(c,program='SHELXT') for c in checks if c['status']=='candidate_requires_refinement'];decision=fallback_reason(attempt,len(usable))
    result=dict(schema=1,primary=attempt,primary_output_screening=checks,decision=decision,candidates=usable,source_sha256=hashes,model_adopted=False)
    if decision=='try_supported_SHELXD_hypotheses':
        result['fallback']=run_fallback(text,frozen,shelxd,out/'shelxd',cfg,runner);result['candidates']=result['fallback']['candidates'];result['status']=result['fallback']['status']
    else:result['status']='candidates_require_refinement_and_review' if usable else 'software_environment_failure'
    result['source_unchanged']=all(sha(Path(p))==v for p,v in hashes.items());newjson(out/'cascade.json',result);return result

def main():
    p=argparse.ArgumentParser(description=__doc__)
    for name in ['ins','hkl','shelxt','output']:p.add_argument('--'+name,required=True)
    p.add_argument('--shelxd');p.add_argument('--config');a=p.parse_args()
    cfg=json.loads(Path(a.config).read_text('utf-8-sig')) if a.config else None
    v=cascade(a.ins,a.hkl,a.shelxt,a.shelxd,a.output,cfg);print(json.dumps({'status':v['status'],'candidates':len(v['candidates']),'record':str(Path(a.output)/'cascade.json')}))
    return 0 if v['candidates'] else 2
if __name__=='__main__':raise SystemExit(main())
