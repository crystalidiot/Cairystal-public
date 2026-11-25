"""Evidence-triggered bounded PLATON TwinRotMat search and isolated TWIN/BASF trials.

No model acceptance, reflection removal, overlap conversion or external upload.
Only complete, attributable PLATON matrix blocks are used, even on an early stop.
"""
import argparse
import copy
import json
import math
from pathlib import Path
import re
import shutil
import subprocess
import time

NUM = r'[+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:[Ee][+-]?\d+)?'
SIGNALS = {'033','107','108','109','850','930','987'}


def trigger(rows, alerts=(), reflection_evidence=None, reason=None):
    from twin_delivery import classify
    route = classify(rows)
    if route['kind'] != 'ordinary_HKLF4':
        return {'run':False, 'status':'existing_or_unsupported_model', 'route':route,
                'reason':'Retain existing controls; no duplicate TWIN/BASF search.'}
    codes = {str(a['code']).zfill(3) for a in alerts}
    signals = sorted(codes & SIGNALS)
    # Positive excess intensity, not beamstop-type negative residuals. This is
    # a workload trigger, not a diagnosis or a request to remove observations.
    excess = [r for r in (reflection_evidence or {}).get('weighted_outliers',[]) or []
              if r.get('status') != 'x' and (r.get('delta_over_sigmaW') or 0)>10
              and r.get('Fo2',0)>2*max(r.get('Fc2',0),0)]
    if len(excess)>=3: signals.append('at_least_3_large_positive_intensity_excesses')
    if reason: signals.append(str(reason))
    return {'run':bool(signals), 'status':'triggered' if signals else 'no_concrete_signal',
            'signals':signals,'positive_excess_count':len(excess),'route':route}


def parse_listing(text):
    """PLATON printed reciprocal mapping: column(h2,k2,l2)=M column(h1,k1,l1)."""
    total = re.search(r'N\(refl\)\s*=\s*(\d+)',text)
    rows = text.splitlines();found=[]
    for i,line in enumerate(rows):
        if 'Nr Overlap' not in line or '(h1)' not in line or i+2>=len(rows):continue
        three=rows[i:i+3];matrix=[]
        for row,axis in zip(three,['h','k','l']):
            m=re.match(r'^\s*\(\s*('+NUM+r')\s+('+NUM+r')\s+('+NUM+r')\s*\)',row)
            if not m or f'({axis}1)' not in row or f'({axis}2)' not in row:break
            matrix.extend(map(float,m.groups()))
        if len(matrix)!=9:continue
        block='\n'.join(three)
        overlap=re.search(r'Nr Overlap\s*=\s*(\d+)',block)
        fraction=re.search(r'BASF\s*=\s*('+NUM+')',block)
        delta=re.search(r'DEL-R\s*=\s*('+NUM+')',block)
        if not (overlap and fraction and delta and total):continue
        item={'matrix':matrix,'basf_estimate':float(fraction[1]),'delta_R_estimate':float(delta[1]),
              'overlap_count':int(overlap[1]),'reflection_count':int(total[1]),
              'line':i+1,'native_block':block,'matrix_convention':'h2=M*h1'}
        if all(math.isfinite(v) for v in matrix+[item['basf_estimate'],item['delta_R_estimate']]):
            if not any(x['matrix']==matrix for x in found):found.append(item)
    return sorted(found,key=lambda x:x['delta_R_estimate'])


def usable(law, cif):
    import gemmi
    from twin_delivery import classify
    m=law['matrix'];a=law['basf_estimate']
    route=classify([['HKLF','4'],['TWIN',*map(str,m)],['BASF',str(a)]])
    if not route['supported_for_pairing']:raise ValueError(route['reason'])
    if not 0<a<1 or law['delta_R_estimate']>=0:raise ValueError('No positive-population fit improvement suggested by PLATON')
    if law['reflection_count']<=0 or law['overlap_count']!=law['reflection_count']:
        raise ValueError('Partial reflection overlap: requires dedicated HKLF5/data treatment')
    b=gemmi.cif.read_file(str(cif)).sole_block()
    cell=gemmi.UnitCell(*[gemmi.cif.as_number(b.find_value('_cell_'+k)) for k in
                        ['length_a','length_b','length_c','angle_alpha','angle_beta','angle_gamma']])
    if max(abs(x) for x in m)>6:raise ValueError('Matrix outside the bounded HKLF4 route')
    for h in [(1,0,0),(0,1,0),(0,0,1),(1,1,0),(1,0,1),(0,1,1),(1,-1,1)]:
        transformed=[sum(m[3*i+j]*h[j] for j in range(3)) for i in range(3)]
        d0=cell.calculate_d(h);d1=cell.calculate_d(list(map(int,transformed)))
        if not all(math.isfinite(x) and x>0 for x in [d0,d1]) or abs(d1/d0-1)>.005:
            raise ValueError('Twin law incompatible with current reciprocal metric (0.5% screen)')
    ops=b.find_values('_space_group_symop_operation_xyz') or b.find_values('_symmetry_equiv_pos_as_xyz')
    for op in ops:
        o=gemmi.Op(gemmi.cif.as_string(op))
        cols=[o.apply_to_hkl(h) for h in [(1,0,0),(0,1,0),(0,0,1)]]
        if all(abs(m[3*i+j]-cols[j][i])<1e-8 for i in range(3) for j in range(3)):
            raise ValueError('Matrix is already a reciprocal operation of the current space group')
    return route


def search(executable, folder, seconds=20):
    """Stop own process once a complete positive block settles; never call timeout negative."""
    from native_process import hidden_kwargs
    from crystal_runtime import sha
    if not 1<=seconds<=120:raise ValueError('Search timeout must be 1..120 s')
    folder=Path(folder);command=[str(Path(executable).resolve()),'-T','case.cif']
    start=time.perf_counter();last=None;since=None;state='timeout';candidates=[]
    with (folder/'process.log').open('w') as stream:
        p=subprocess.Popen(command,cwd=folder,stdout=stream,stderr=subprocess.STDOUT,**hidden_kwargs())
        try:
            while time.perf_counter()-start<seconds:
                time.sleep(.1)
                listing=folder/'case.lis';text=listing.read_text('latin1') if listing.exists() else ''
                candidates=parse_listing(text)
                signature=json.dumps(candidates,sort_keys=True) if candidates else None
                if signature!=last:since=time.perf_counter();last=signature
                log=folder/'platon.out';native=log.read_text('latin1') if log.exists() else ''
                if re.search(r'Job ABORTED|Sorry, No Analysis|FATAL|>>> STOP:',native,re.I):
                    state='native_failure';break
                # Complete law evidence is usable for a trial even if more laws
                # were being enumerated. Do not claim the search was exhaustive.
                if candidates and since is not None and time.perf_counter()-since>=.5:
                    state='complete_candidates_early_stop';break
                if p.poll() is not None:
                    state='exited_with_candidates' if candidates else 'no_usable_candidate_output';break
        finally:
            if p.poll() is None:p.kill()
            p.wait(timeout=5)
    return {'state':state,'command':command,'returncode':p.returncode,
            'seconds':round(time.perf_counter()-start,4),'candidates':candidates,
            'search_exhaustive':False,'negative_twin_diagnosis':False,
            'artifacts':{x.name:sha(x) for x in folder.iterdir() if x.is_file()},
            'executable_sha256':sha(executable),'hidden_startup':True}


def edit(base, config):
    """Reverify the native listing and source identity before injecting two cards."""
    from crystal_runtime import sha,records
    from crystal_session import logical_text
    base=Path(base);evidence=Path(config['evidence']);report=json.loads(evidence.read_text('utf-8'))
    if sha(evidence)!=config['evidence_sha256']:raise ValueError('Twin evidence changed')
    if report.get('search_state') not in {'complete_candidates_early_stop','exited_with_candidates'}:
        raise ValueError('Native search failed or timed out; preserve raw evidence for review')
    if report['source_hashes']!={e:sha(base/f'case.{e}') for e in report['source_hashes']}:
        raise ValueError('Twin evidence belongs to another model or reflection set')
    listing=Path(report['listing'])
    if sha(listing)!=report['listing_sha256']:raise ValueError('PLATON listing changed')
    law=config['law']
    if law not in parse_listing(listing.read_text('latin1')):raise ValueError('Law absent from current native listing')
    usable(law,base/'case.cif')
    rows=records((base/'case.res').read_text('latin1'))
    if any(r[0].upper() in {'TWIN','BASF','ABIN','SWAT'} or r[0].startswith('+') for r in rows):
        raise ValueError('Existing twin/batch/mask/include controls require separate treatment')
    hk=[r for r in rows if r[0].upper()=='HKLF']
    if hk!=[['HKLF','4']]:raise ValueError('Automatic trial requires untransformed HKLF 4')
    result=[];cards=['TWIN '+' '.join(str(int(x)) for x in law['matrix']),f"BASF {law['basf_estimate']:.6f}"]
    for r in rows:
        if r[0].upper()=='HKLF':result.extend(cards)
        result.append(r)
    return logical_text(result),[{'twin_law_added':law,'evidence':str(evidence),'cards':cards}]


def compare_twin(control, trial):
    from compare_diagnostic_trials import compare
    from crystal_runtime import records
    from twin_delivery import classify
    a=copy.deepcopy(control);b=copy.deepcopy(trial)
    for obj in (a,b):
        ctx=obj.get('comparison_context')
        if ctx:ctx['frozen_controls']=[r for r in ctx['frozen_controls'] if r[0].upper() not in {'TWIN','BASF'}]
    result=compare(a,b);result['comparison_scope']='Same HKL/cell/symmetry/weights/atoms; isolated TWIN+BASF hypothesis'
    result['model_adopted']=False
    if trial.get('status')=='completed':
        res=Path(trial['diagnostic']).parent/'paired/case.res'
        result['refined_twin']=classify(records(res.read_text('latin1')))
        import gemmi
        cif=gemmi.cif.read_file(str(res.with_suffix('.cif'))).sole_block()
        value=cif.find_value('_refine_ls_abs_structure_Flack')
        result['absolute_structure_parameter']=value or None
        # Generic non-inversion BASF s.u. is in the native final parameter table,
        # not necessarily the Flack CIF field. Retain its literal evidence.
        lst=res.with_suffix('.lst').read_text('latin1')
        result['BASF_listing']=[line.strip() for line in lst.splitlines() if re.search(r'\bBASF\b',line)][-8:]
        matches=re.findall(r'^\s*\d+\s+('+NUM+r')\s+('+NUM+r')\s+('+NUM+r')\s+BASF\s+1\s*$',lst,re.M)
        result['BASF_parameter']=None
        if matches:
            value,su,shift=map(float,matches[-1])
            if all(math.isfinite(v) for v in (value,su,shift)) and su>0:
                result['BASF_parameter']={'value':value,'standard_uncertainty':su,'last_shift_over_su':shift,
                                          'ratio_to_su':value/su,'source':'last native BASF 1 parameter row'}
                if value-3*su<=0:result['flags'].append('BASF_not_significant_at_3su_screen')
        if result['BASF_parameter'] is None:result['flags'].append('BASF_uncertainty_unavailable')
        if result['refined_twin'].get('fraction_outside_unit_interval'):
            result['flags'].append('refined_fraction_outside_unit_interval')
        result['review_required']=['BASF significance/uncertainty','geometry and ADPs','density and chemistry']
    return result


def run(directory,stem,output,software,alerts=(),reason=None,execute=True,seconds=20,reflection_evidence=None):
    from crystal_runtime import paired_bundle,records,sha,write_json
    start=time.perf_counter();out=Path(output)
    if out.exists():raise FileExistsError(out)
    out.mkdir(parents=True)
    result={'status':'running','model_adopted':False,'official_upload':False,'defer_omit':False}
    audit=None
    try:
        audit=paired_bundle(directory,stem)
        rows=records(Path(audit['files']['res']).read_text('latin1'))
        if reflection_evidence is None and {str(a['code']) for a in alerts}&{'934','939'}:
            from reflection_audit import audit as reflection_audit
            reflection_evidence=reflection_audit(directory,stem)
        decision=trigger(rows,alerts,reflection_evidence,reason);result['trigger']=decision
        if not decision['run']:result['status']=decision['status'];return finish(out,result,start,audit)
        result['defer_omit']=True
        if not execute:
            result['status']='search_required_plan_only';return finish(out,result,start,audit)
        base=out/'baseline';base.mkdir()
        for ext,source in audit['files'].items():shutil.copy2(source,base/f'case.{ext}')
        source_hashes={e:sha(base/f'case.{e}') for e in ['res','hkl','cif','fcf']}
        search_dir=out/'search';search_dir.mkdir()
        for ext in ['cif','fcf','res','hkl']:shutil.copy2(base/f'case.{ext}',search_dir/f'case.{ext}')
        native=search(software['platon'],search_dir,seconds);result['search']=native
        if native['state'] not in {'complete_candidates_early_stop','exited_with_candidates'}:
            result['status']=native['state'];return finish(out,result,start,audit)
        accepted=[];rejected=[]
        for law in native['candidates']:
            try:usable(law,base/'case.cif');accepted.append(law)
            except ValueError as exc:rejected.append({'law':law,'reason':str(exc)})
        result['rejected_laws']=rejected
        if not accepted:
            result['status']='law_requires_specialist_route' if rejected else native['state']
            # A completed no-candidate search is not a proof of absence; allow
            # the other independent diagnostic work, but not an automatic OMIT.
            return finish(out,result,start,audit)
        listing=search_dir/'case.lis';evidence=out/'native_evidence.json'
        write_json(evidence,{'source_hashes':source_hashes,'listing':str(listing),'listing_sha256':sha(listing),
                             'search_state':native['state'],'search_exhaustive':False})
        law=accepted[0]  # One promising detected law, no open-ended search.
        config={'evidence':str(evidence),'evidence_sha256':sha(evidence),'law':law}
        control={'name':'control','kind':'baseline','cycles':20,'reason':'Same-data untwinned continuation',
                 'evidence':'Unchanged contemporaneous source and fixed WGHT'}
        trial={'name':'twin','kind':'diagnostic_refinement','cycles':20,'reason':'PLATON detected complete-overlap two-domain candidate',
               'evidence':str(evidence),'twin_law':config}
        from candidate_trials import build,run_plan
        preview=out/'preview';preview.mkdir()
        for plan in [control,trial]:
            text,_=build(base,plan,preview);(preview/(plan['name']+'.ins')).write_text(text,'ascii')
        job={'baseline':str(base),'output':str(out/'trials'),'software':software,
             'software_sha256':{k:sha(v) for k,v in software.items()},'trials':[control,trial],'stop_on_control_failure':True}
        write_json(out/'plan.json',job)
        trials=run_plan(out/'plan.json');result['trials']=[{'name':t['name'],'status':t['status']} for t in trials]
        if len(trials)==2 and all(t['status']=='completed' for t in trials):
            comparison=compare_twin(*trials);write_json(out/'comparison.json',comparison)
            result.update(status='twin_comparison_ready',comparison=str(out/'comparison.json'),
                          candidate=str(out/'trials/twin/paired'),control=str(out/'trials/control/paired'))
        else:result['status']='twin_refinement_failed'
    except Exception as exc:result.update(status='failed',error=str(exc),defer_omit=True)
    return finish(out,result,start,audit)


def finish(out,result,start,audit):
    from crystal_runtime import sha,write_json
    if audit:
        result['source_unchanged']=all(sha(p)==audit['source_sha256'][e] for e,p in audit['files'].items())
        if not result['source_unchanged']:result.update(status='failed',error='Source changed during twin trial',defer_omit=True)
    result['seconds']=round(time.perf_counter()-start,4)
    result['next']='Compare candidate chemistry, BASF with uncertainty, ADPs, density and A/B; use existing final validation/report path after selecting the model.'
    write_json(out/'result.json',result);return result


def main():
    p=argparse.ArgumentParser(description=__doc__)
    for key in ['directory','output','profile']:p.add_argument('--'+key,required=True)
    p.add_argument('--stem',default='case');p.add_argument('--reason');p.add_argument('--alerts')
    p.add_argument('--seconds',type=float,default=20);p.add_argument('--plan-only',action='store_true');a=p.parse_args()
    from pipeline_intake import verify_profile
    profile=json.loads(Path(a.profile).read_text('utf-8-sig'));paths=verify_profile(profile)
    alerts=json.loads(Path(a.alerts).read_text('utf-8-sig')) if a.alerts else []
    r=run(a.directory,a.stem,a.output,{k:paths[k] for k in ['shelxl','platon']},alerts,a.reason,not a.plan_only,a.seconds)
    print(json.dumps(r,ensure_ascii=False));return 2 if r['status']=='failed' else 0


if __name__=='__main__':raise SystemExit(main())
