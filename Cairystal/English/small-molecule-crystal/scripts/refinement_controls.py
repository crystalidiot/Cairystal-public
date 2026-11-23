"""Audit numerical controls and prepare isolated EXTI/DAMP/resolution comparisons.

Sensitivity trials are not final models. Experimental dimensions and uncertainties
are never fabricated or shrunk by this tool.
"""
import argparse,json,math,re,time
from pathlib import Path
import gemmi
from structure_diagnostics import number,digest,newjson,res_records
from geometry_audit import scalar_error

def active_cards(text):
    rows=[]
    for line in text.splitlines():
        row=line.split('!',1)[0].split()
        if not row:continue
        if row[0].upper()=='END':break
        rows.append(row)
    return rows

def analyse(text,block):
    rows=active_cards(text);controls={}
    for row in rows:
        if row[0].upper() in {'DAMP','EXTI','BLOC','CGLS','XNPD','SHEL','OMIT','WGHT','TWIN','BASF','ABIN','SWAT'}:
            controls.setdefault(row[0].upper(),[]).append(row[1:])
    token=block.find_value('_refine_ls_extinction_coef');value=number(token);su=scalar_error(token)
    significance=abs(value)/su if value is not None and su is not None and su>0 else None
    exti=controls.get('EXTI',[])
    agreeing=bool(len(exti)==1 and len(exti[0])==1 and value is not None and number(exti[0][0]) is not None and abs(number(exti[0][0])-value)<=max(1e-7,5*(su or 0)))
    return dict(controls=controls,extinction={'cif_token':token,'value':value,'su':su,'absolute_value_over_su':significance,
        'cif_res_consistent':agreeing,'remove_trial_supported':bool(agreeing and significance is not None and significance<3.33)},
        proposals=[x for x,yes in [('release_damping',len(controls.get('DAMP',[]))==1),('remove_extinction',agreeing and significance is not None and significance<3.33)] if yes],
        restrictions=['A DAMP removal trial must converge without damping and pass the complete refinement/geometry/density/AB review.',
        'Weak EXTI significance supports a comparison, not automatic acceptance. Missing su is unknown, not zero.',
        'Resolution cutoffs are explicit sensitivity trials with changed fitted data; never rank them by lower R or fewer AB alone.',
        'SIZE/ZERR changes require a verified experimental or recalculation source; no arbitrary dimension or su reduction.'])

def audit(directory,stem='case'):
    start=time.perf_counter();d=Path(directory);paths=[d/(stem+'.res'),d/(stem+'.cif')];hashes={str(p):digest(p) for p in paths}
    value=analyse(paths[0].read_text('latin1'),gemmi.cif.read_file(str(paths[1])).sole_block())
    if any(digest(Path(p))!=h for p,h in hashes.items()):raise ValueError('Source changed during control audit')
    value.update(schema=1,status='evidence_ready',source_sha256=hashes,source_unchanged=True,model_modified=False,seconds=round(time.perf_counter()-start,4));return value

def resolution_inventory(base,d_min):
    base=Path(base);r=res_records(base/'case.res');cellrows=[v for v in r['rows'] if v[0].upper()=='CELL']
    if len(cellrows)!=1 or len(cellrows[0])!=8:raise ValueError('One complete CELL required')
    cell=gemmi.UnitCell(*map(float,cellrows[0][2:]));rows=[]
    for i,line in enumerate((base/'case.hkl').read_text('ascii').splitlines(),1):
        if not line.strip():continue
        try:
            if len(line)>=28:
                hkl=[int(line[k:k+4]) for k in (0,4,8)];fo=float(line[12:20]);sigma=float(line[20:28])
            else:
                f=line.split();hkl=list(map(int,f[:3]));fo=float(f[3]);sigma=float(f[4])
        except (ValueError,IndexError):raise ValueError('Unsupported HKLF4 record at line '+str(i))
        if hkl==[0,0,0]:break
        if not all(math.isfinite(x) for x in [fo,sigma]):raise ValueError('Nonfinite intensity')
        d=cell.calculate_d(hkl)
        if not math.isfinite(d) or d<=0:raise ValueError('Invalid reflection resolution')
        rows.append(dict(hkl=hkl,d_A=d,signal=fo/sigma if sigma>0 else None))
    retained=[r for r in rows if r['d_A']>=d_min];cut=[r for r in rows if r['d_A']<d_min]
    if not retained or not cut:raise ValueError('Cutoff must retain and exclude actual measured rows')
    return dict(measured_HKL_records=len(rows),within_requested_window=len(retained),high_angle_records_outside_window=len(cut),
        outside_record_fraction=len(cut)/len(rows),original_d_min_A=min(r['d_A'] for r in rows),requested_d_min_A=d_min,
        cutoff_shell_mean_I_over_sigma=sum(r['signal'] for r in cut if r['signal'] is not None)/sum(r['signal'] is not None for r in cut) if any(r['signal'] is not None for r in cut) else None,
        theoretical_completeness=None,actual_refined_reflections=None,
        note='Counts are measured HKL records, including equivalents. They are not unique completeness or final refinement counts; existing OMIT still applies.')

def edit(base,request):
    base=Path(base);mode=request.get('mode');allowed={'mode','basis'}|({'d_min_A'} if mode=='resolution_window' else set())
    if set(request)!=allowed or not isinstance(request.get('basis'),str) or not request['basis'].strip():raise ValueError('Explicit mode, basis and supported fields required')
    if mode not in {'remove_extinction','release_damping','resolution_window'}:raise ValueError('Unsupported control operation')
    source=(base/'case.res').read_text('latin1');rows=active_cards(source)
    if any(r[0].startswith('+') for r in rows) or any(r[0].upper() in {'BLOC','XNPD','CGLS','TWIN','BASF','ABIN','SWAT'} for r in rows):
        raise ValueError('Includes, subset/floor/CGLS/twin/mask controls require a dedicated reviewed comparison')
    hkl=[r for r in rows if r[0].upper()=='HKLF']
    if len(hkl)!=1 or hkl[0]!=['HKLF','4']:raise ValueError('Ordinary untransformed HKLF 4 required')
    block=gemmi.cif.read_file(str(base/'case.cif')).sole_block();evidence=analyse(source,block)
    card={'remove_extinction':'EXTI','release_damping':'DAMP','resolution_window':'SHEL'}[mode]
    inventory=None
    if mode=='remove_extinction' and not evidence['extinction']['remove_trial_supported']:
        raise ValueError('Paired positive su and weak (<3.33 su) EXTI evidence required')
    if mode=='release_damping' and len(evidence['controls'].get('DAMP',[]))!=1:raise ValueError('Exactly one DAMP card required')
    if mode=='resolution_window':
        cutoff=request['d_min_A']
        if isinstance(cutoff,bool) or not isinstance(cutoff,(int,float)) or not math.isfinite(cutoff) or not .5<=cutoff<=2.5:raise ValueError('Explicit d_min in 0.5..2.5 angstrom required')
        if evidence['controls'].get('SHEL'):raise ValueError('Existing SHEL needs a separately reviewed replacement; no stacked cutoffs')
        inventory=resolution_inventory(base,cutoff)
    output=[];ended=False;changes=[]
    for line in source.splitlines():
        f=line.split();key=f[0].upper() if f else ''
        if not ended and key==card and mode!='resolution_window':
            if '=' in line:raise ValueError('Continued control card requires explicit review')
            changes.append({'removed_control':line,'basis':request['basis']});continue
        if not ended and key=='HKLF' and mode=='resolution_window':
            inserted=f'SHEL 999 {request["d_min_A"]:.6f}';output.append(inserted)
            changes.append({'added_control':inserted,'basis':request['basis'],'resolution_inventory':inventory,
                'same_fitted_data':False,'ranking_allowed':False,'original_HKL_changed':False})
        output.append(line)
        if key=='END':ended=True
    if len(changes)!=1:raise ValueError('Exactly one isolated control change required')
    return '\n'.join(output)+'\n',changes

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--directory',required=True);p.add_argument('--stem',default='case');p.add_argument('--output',required=True)
    a=p.parse_args();v=audit(a.directory,a.stem);newjson(a.output,v);print(json.dumps({'status':v['status'],'proposals':v['proposals']},ensure_ascii=False))
if __name__=='__main__':main()
