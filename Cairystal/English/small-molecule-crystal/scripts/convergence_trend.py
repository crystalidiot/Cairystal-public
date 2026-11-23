"""Read-only SHELXL convergence evidence; never a chemical acceptance gate."""
import argparse,json,math,re
from pathlib import Path

RECORD=re.compile(r'Mean shift/esd\s*=\s*([+\-\d.Ee]+)\s+Maximum\s*=\s*([+\-\d.Ee]+)\s+for\s+([^\r\n]+)')
ONLY_REASON='Not converged to the review threshold max shift/esd <= 0.01'

def analyse(text,gate,ins_text):
    rows=[]
    for m in RECORD.finditer(text):
        try: mean,value=float(m[1]),float(m[2])
        except ValueError: continue
        if not all(math.isfinite(v) for v in (mean,value)): continue
        rows.append(dict(mean=mean,signed_max=value,parameter=' '.join(m[3].split())))
    result=dict(schema=1,cycles=rows,eligible=False,suggested_extra_cycles=0,
                scientific_acceptance=False,reason='Insufficient or unsuitable evidence')
    def stop(reason):result['reason']=reason;return result
    metrics=gate.get('metrics',{})
    if not gate.get('execution_complete') or gate.get('failures'):return stop('Native execution or other numerical failure')
    if metrics.get('NPD_atoms')!=0:return stop('NPD count is nonzero or unknown')
    if gate.get('review_reasons')!=[ONLY_REASON]:return stop('Not a convergence-only review condition')
    # Read echoed/current execution INS, never infer benign controls from RES alone.
    if re.search(r'^\s*(?:BLOC|XNPD|DAMP|CGLS)\b',ins_text,re.M|re.I):return stop('Subset, floor, damping or CGLS requires explicit review')
    if len(rows)<4:return stop('Fewer than four cycle records')
    tail=rows[-4:];values=[abs(r['signed_max']) for r in tail]
    final=metrics.get('last_abs_max_shift_esd')
    if final is None or not math.isfinite(final) or abs(final-values[-1])>.00051:return stop('Gate and final LST record do not agree')
    if not .01<values[-1]<=.2:return stop('Shift outside bounded continuation range')
    if len({r['parameter'] for r in tail})!=1:return stop('Dominant parameter changes; cannot infer its trajectory')
    if len({r['signed_max']>0 for r in tail})!=1:return stop('Signed shifts oscillate')
    if any(b>=a for a,b in zip(values,values[1:])) or values[-1]/values[0]>.8:return stop('Decay is too slow, stalled or increasing')
    from parameter_correlations import parse_lst
    correlation=parse_lst(text)
    result['correlation_parse_status']=correlation['status']
    result['max_reported_correlation']=correlation['max_absolute']
    if correlation['status']=='partial_parse':return stop('Incomplete correlation parsing; inspect the printed parameter pairs')
    if result['max_reported_correlation'] is not None and result['max_reported_correlation']>=.9:return stop('Large reported parameter correlation')
    result.update(eligible=True,suggested_extra_cycles=20,reason='Same signed parameter decays consistently; try unchanged continuation, then recheck full gate')
    return result

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--directory',required=True);p.add_argument('--stem',default='model');p.add_argument('--output',required=True)
    a=p.parse_args()
    from crystal_runtime import check_stem
    from refinement_gate import assess
    stem=check_stem(a.stem);d=Path(a.directory);out=Path(a.output)
    value=analyse((d/(stem+'.lst')).read_text('latin1'),assess(d,stem),(d/(stem+'.ins')).read_text('latin1'))
    with out.open('x',encoding='utf-8') as f:json.dump(value,f,ensure_ascii=False,indent=2)
    print(json.dumps({k:value[k] for k in ['eligible','reason','suggested_extra_cycles']},ensure_ascii=False))
if __name__=='__main__':main()
