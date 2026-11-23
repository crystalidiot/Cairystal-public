"""Diagnose data/parameter warnings; never misroute PLAT088 as nonconvergence."""
import argparse,json,time
from pathlib import Path
import gemmi
from structure_diagnostics import structure,number,digest,newjson
from audit_occupancy import audit as occupancy_audit

def audit(directory,stem='case'):
    start=time.perf_counter();d=Path(directory);cif=d/(stem+'.cif');res=d/(stem+'.res')
    hashes={str(p):digest(p) for p in [cif,res]}
    b,cell,ops,atoms,parsed=structure(cif,res)
    account=occupancy_audit(res,gemmi)
    groups={}
    for a in account['atoms']:groups.setdefault(a['label'].upper(),[]).append(a)
    p=number(b.find_value('_refine_ls_number_parameters'));n=number(b.find_value('_refine_ls_number_reflns'))
    restraints=number(b.find_value('_refine_ls_number_restraints'))
    for value in (p,n,restraints):
        if value is not None and (value<0 or not float(value).is_integer()):raise ValueError('Invalid native parameter/reflection/restraint count')
    sg=gemmi.find_spacegroup_by_name(account['space_group']) if account['space_group'] else None
    zmax=max((gemmi.Element(a['element']).atomic_number for a in atoms),default=None)
    centro=sg.is_centrosymmetric() if sg else None
    target=10 if centro is True else (7 if zmax<=18 else 8) if centro is False and zmax else None
    constrained={v.upper() for row in parsed['rows'] if row[0].upper() in {'EXYZ','EADP'} for v in row[1:]}
    free=[];riding=[];uncertain=[]
    for a in parsed['atoms']:
        if a['element']!='H':continue
        context=groups.get(a['label'].upper(),[])
        row={'label':a['label'],'AFIX':a['afix'],'PART':a['part'],'U_field':a['adp_raw']}
        if a['afix']:riding.append(row);continue
        if len(context)!=1 or a['part'] or abs(context[0]['inferred_cif_occupancy']-1)>1e-5 or context[0]['geometric_site_multiplicity']!=context[0]['general_multiplicity'] or a['label'].upper() in constrained:
            uncertain.append(dict(row,reason='Special/partial/disordered/constrained or ambiguous H; no generic parameter reduction'));continue
        free.append(row)
    result=dict(schema=1,status='evidence_ready',problem_family='data_parameter_budget',
        alerts=['PLAT088','PLAT089','PLAT090','PLAT904','REFNR01'],source_sha256=hashes,
        counts={'native_refined_parameters':p,'native_refined_reflections':n,'native_restraints':restraints},
        native_reflection_parameter_ratio=n/p if n is not None and p and p>0 else None,
        centrosymmetric=centro,largest_atomic_number=zmax,reference_PLAT_target=target,
        exact_PLAT_ratio=None,
        free_general_H=free,AFIX_H=riding,H_requiring_special_review=uncertain,
        controls_to_review=[r for r in parsed['controls'] if r.split()[0].upper() in {'SHEL','OMIT','BLOC','DAMP','EXYZ','EADP'}],
        next_actions=['Check an adequate measured resolution/completeness and the actual reflection selection.',
                      'For chemically justified C-H, compare an appropriate riding model; special positions, neutron/HAR and donor H need separate treatment.',
                      'Do not count restraints as new measured reflections or fix arbitrary heavy-atom coordinates to improve this ratio.'],
        limitations=['The native refinement ratio is not necessarily the PLATON ratio; non-centrosymmetric PLAT089/090 use Laue-averaged data. No exact PLAT ratio is fabricated.',
                     'An AFIX code alone does not count independent parameters: free variables, constraints and special positions matter.',
                     'This tool makes no atom edits and does not establish chemical correctness.'],model_modified=False)
    result['source_unchanged']=all(digest(Path(p))==h for p,h in hashes.items())
    if not result['source_unchanged']:raise ValueError('Source changed during audit')
    result['seconds']=round(time.perf_counter()-start,4);return result

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--directory',required=True);p.add_argument('--stem',default='case');p.add_argument('--output',required=True)
    a=p.parse_args();value=audit(a.directory,a.stem);newjson(a.output,value)
    print(json.dumps({k:value[k] for k in ['status','native_reflection_parameter_ratio','reference_PLAT_target']},ensure_ascii=False))
if __name__=='__main__':main()
