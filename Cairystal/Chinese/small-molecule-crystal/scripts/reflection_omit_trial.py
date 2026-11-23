"""Explicit fixed-list reflection selection trial; never edit raw HKL or iterate pruning."""
from pathlib import Path
from crystal_runtime import records
from crystal_session import logical_text
from reflection_audit import audit


def validate_list(values):
    if not isinstance(values,list) or not 1<=len(values)<=20:raise ValueError('One fixed list of 1..20 reflections required')
    for hkl in values:
        if not isinstance(hkl,list) or len(hkl)!=3 or any(type(x)!=int or abs(x)>999 for x in hkl) or hkl==[0,0,0]:
            raise ValueError('Each reflection must be three finite bounded integer indices')
    if len({tuple(x) for x in values})!=len(values):raise ValueError('Duplicate OMIT indices')
    return values


def edit(base,config):
    if set(config)!={'hkls','basis'} or not isinstance(config['basis'],str) or not config['basis'].strip():
        raise ValueError('Explicit fixed hkl list and investigation basis required')
    selected=validate_list(config['hkls']);evidence=audit(base)
    if evidence['weighted_outliers'] is None:raise ValueError('Actual weighted-reflection evidence unavailable')
    eligible={tuple(r['hkl']):r for r in evidence['weighted_outliers'] if r['status']!='x'}
    if any(tuple(x) not in eligible for x in selected):raise ValueError('Every selected reflection must be a current active >10 sigmaW outlier')
    rows=records((Path(base)/'case.res').read_text('latin1'));index=next(i for i,r in enumerate(rows) if r[0].upper()=='HKLF')
    if rows[index]!=['HKLF','4']:raise ValueError('This OMIT comparison supports ordinary HKLF 4 only')
    if any(r[0].upper() in {'TWIN','BASF','ABIN','SWAT','EXTI'} for r in rows):raise ValueError('Twin/mask/extinction corrections need dedicated reflection interpretation')
    old={tuple(map(int,r[1:])) for r in rows if r[0].upper()=='OMIT' and len(r)==4}
    if any(tuple(x) in old for x in selected):raise ValueError('Reflection already omitted')
    edited=rows[:index]+[['OMIT',*map(str,hkl)] for hkl in selected]+rows[index:]
    return logical_text(edited),[{'reflection_omit':{'hkls':selected,'basis':config['basis'],
        'weighted_evidence':[eligible[tuple(h)] for h in selected], 'raw_HKL_modified':False,
        'selection_changed':True,'automatic_model_adoption':False,
        'warning':'Refinement R values use different reflection selections; no direct winner ranking. Check native completeness and retained/excluded fit separately.'}}]
