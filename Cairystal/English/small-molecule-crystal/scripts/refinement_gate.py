"""Read-only SHELXL output gate: completion is separate from model acceptance."""
from pathlib import Path
import argparse,json,re
from audit_occupancy import CARDS,logical_lines

def duplicate_atom_labels(text):
    """Case-insensitive SHELX identities: RESI scopes names; PART does not.

    Accept native punctuation in labels so suffix exhaustion such as H00$ is
    actually checked. Ignore comments, fragments, and post-HKLF peak lists.
    """
    seen=set();duplicates=[];residue='0';fragment=False
    for line in logical_lines(text):
        f=line.split();key=f[0].upper()
        if key in {'END','HKLF'}:break
        if key=='FRAG':fragment=True;continue
        if key=='FEND':fragment=False;continue
        if fragment:continue
        if key=='RESI':
            numbers=[v for v in f[1:] if re.fullmatch(r'[+-]?\d+',v)]
            if len(numbers)!=1:raise ValueError('RESI without a unique explicit number needs atom-label review')
            residue=str(int(numbers[0]));continue
        if key in CARDS or len(f)<7 or not re.match(r'^[A-Za-z]',f[0]):continue
        try:int(f[1]);list(map(float,f[2:7]))
        except ValueError:continue
        identity=(residue,key)
        if identity in seen:duplicates.append({'residue':residue,'label':f[0]})
        seen.add(identity)
    return duplicates

def parameter_controls(text):
    """Read requested controls only; a run log must establish what was applied."""
    controls=[]
    for line in logical_lines(text):
        fields=line.split()
        if fields[0].upper()=='END':break
        if fields[0].upper() in {'BLOC','XNPD'}:
            controls.append((fields[0].upper(),fields[1:]))
    return controls

def assess(stage,stem):
    process=stage/'process.log';lst=stage/f'{stem}.lst';res=stage/f'{stem}.res'
    logs='\n'.join(p.read_text(encoding='latin1') for p in (process,lst) if p.exists())
    failures=[];review=[]
    for p in (res,lst):
        if not p.exists() or not p.stat().st_size:failures.append('Missing or empty '+p.name)
    banner=bool(re.search(r'finished at .*Total elapsed time:',logs))
    if not banner:failures.append('Normal SHELXL completion banner absent')
    fatal=[r'INPUT INSTRUCTION .*IS LONGER THAN',r'CANNOT OPEN',r'NO REFLECTION',r'REFLECTION\s+\d+\s+HAS WRONG FORMAT',r'\*\*.*(?:ERROR|INVALID|UNRECOGNI[ZS]ED)',r'SINGULAR']
    for pattern in fatal:
        if re.search(pattern,logs,re.I):failures.append('Error/singularity marker: '+pattern)
    summary=re.findall(r'wR2 =\s*([\d.]+), GooF = S =\s*([\d.]+).*?R1 =\s*([\d.]+) for\s*(\d+) Fo > 4sig\(Fo\) and\s*([\d.]+) for all\s*(\d+) data',logs,re.S)
    metrics={}
    if summary:
        wr,s,r,nobs,rall,nall=summary[-1]
        metrics.update(wR2=float(wr),GooF=float(s),R1_observed=float(r),R1_all=float(rall),observed=int(nobs),unique=int(nall))
    else:failures.append('Final R1/wR2 summary absent')
    counts=re.findall(r'(\d+)\s+atoms NPD',logs)
    if counts:
        metrics['NPD_atoms']=int(counts[-1])
        if metrics['NPD_atoms']:review.append('Non-positive-definite displacement parameters; do not accept on R1 improvement')
    shifts=re.findall(r'Mean shift/esd =\s*([\d.]+)\s+Maximum =\s*(-?[\d.]+)',logs)
    if shifts:
        metrics['last_mean_shift_esd']=float(shifts[-1][0]);metrics['last_abs_max_shift_esd']=abs(float(shifts[-1][1]))
        if metrics['last_abs_max_shift_esd']>0.01:review.append('Not converged to the review threshold max shift/esd <= 0.01')
    else:review.append('Convergence statistics absent')
    if res.exists() and res.stat().st_size:
        text=res.read_text(encoding='latin1').split('\nEND')[0]
        try:
            duplicates=duplicate_atom_labels(text)
            metrics['duplicate_atom_labels']=duplicates
            if duplicates:failures.append('Duplicate atom identities in native RES: '+str(duplicates))
        except ValueError as e:review.append('Atom-label audit incomplete: '+str(e))
        ins=stage/f'{stem}.ins'
        control_text=ins.read_text(encoding='latin1').split('\nEND')[0] if ins.exists() else text
        # INS can already belong to the next attempt. Inspect both artifacts,
        # without treating their controls as proof of the completed run identity.
        requested=[]
        try:
            for source in (control_text,text):
                for card,args in parameter_controls(source):
                    item={'card':card,'arguments':args}
                    if item not in requested:requested.append(item)
        except ValueError:
            review.append('Incomplete parameter-control syntax; inspect the exact input/output pair')
        if requested:metrics['parameter_controls_requiring_context']=requested
        if any(v['card']=='BLOC' for v in requested):
            review.append('BLOC parameter subsets requested: inspect actual cycle/block coverage; small shifts do not establish convergence of frozen coordinates or a full-model uncertainty calculation')
        for item in requested:
            if item['card']!='XNPD':continue
            try:
                lower=float(item['arguments'][0]) if item['arguments'] else .001
                if lower>0:
                    review.append('Positive XNPD floor requested: zero reported NPD atoms is not independent evidence of unconstrained positive displacement parameters; verify exact run controls')
            except ValueError:
                review.append('XNPD instruction needs manual interpretation')
        # A no-shift covariance job is not evidence that a moving model converged.
        for match in re.finditer(r'^\s*DAMP\s+([^!\r\n]+)',control_text,re.M|re.I):
            try:
                parameters=list(map(float,match[1].split()))
                if len(parameters)>=2 and parameters[0]==0 and parameters[1]==0:
                    review.append('DAMP 0 0 no-shift uncertainty calculation is not independent convergence evidence; inspect preceding moving refinement')
                    metrics['no_shift_uncertainty_job']=True
            except ValueError:review.append('DAMP instruction needs manual interpretation')
        if re.search(r'^\s*TWIN\s+',text,re.M) or re.search(r'^\s*HKLF\s+5(?:\s|$)',text,re.M):
            basf=re.search(r'^BASF\s+([^\n]+)',text,re.M)
            if basf:
                try:
                    fractions=[float(v) for v in basf[1].split()]
                    metrics['twin_BASF']=fractions
                    if any(v<0 or v>1 for v in fractions) or sum(fractions)>1:review.append('Twin fraction outside physical range')
                except ValueError:review.append('BASF needs manual interpretation')
            lattice=re.search(r'^LATT\s+(-?\d+)',text,re.M)
            twin=re.search(r'^TWIN\s+([^\n]+)',text,re.M)
            if lattice and twin and int(lattice[1])>0:
                try:
                    matrix=list(map(float,twin[1].split()[:9]))
                    if matrix==[-1,0,0,0,-1,0,0,0,-1]:
                        review.append('Inversion twin is not identifiable in this centrosymmetric model; verify symmetry/law rather than interpreting BASF as a measured population')
                except ValueError:pass
        # Verify actual output parameterization, not merely the presence of an ANIS card.
        logical=[];pending=''
        for raw in text.splitlines():
            line=(pending+' '+raw.strip()) if pending else raw.strip()
            if line.endswith('='):pending=line[:-1];continue
            pending='';logical.append(line.split())
        sfac=next((f[1:] for f in logical if f and f[0].upper()=='SFAC'),[])
        anis_count=iso_count=0
        for f in logical:
            if f and f[0].upper() in CARDS:continue
            if len(f)<7 or not re.fullmatch(r'[A-Za-z][A-Za-z0-9]{0,3}',f[0]):continue
            try:idx=int(f[1]);list(map(float,f[2:7]))
            except ValueError:continue
            if not 1<=idx<=len(sfac) or sfac[idx-1].upper() in {'H','D'}:continue
            if f[0].upper() in {'ZERR','UNIT','SFAC','TWIN','BASF','CELL'}:continue
            if len(f)>=12:anis_count+=1
            else:iso_count+=1
        metrics['anisotropic_nonH_atoms']=anis_count;metrics['isotropic_nonH_atoms']=iso_count
        ins=stage/f'{stem}.ins'
        if ins.exists() and re.search(r'^\s*ANIS\s*$',ins.read_text(encoding='latin1'),re.M) and iso_count:
            review.append('Global ANIS requested but isotropic non-H atoms remain; check instruction placement and actual output')
    return {'stage':str(stage.resolve()),'execution_complete':not failures,
        'status':'failed_execution' if failures else 'needs_review' if review else 'numerically_converged_requires_chemical_validation',
        'metrics':metrics,'failures':failures,'review_reasons':review,
        'limitation':'This gate does not establish correct chemistry, symmetry, disorder, experiment metadata or official validation.'}

def main():
    parser=argparse.ArgumentParser();parser.add_argument('stage',type=Path);parser.add_argument('--stem',default='case')
    args=parser.parse_args(); result=assess(args.stage,args.stem)
    print(json.dumps(result,ensure_ascii=False,indent=2))
    return 0 if result['execution_complete'] else 1
if __name__=='__main__':raise SystemExit(main())
