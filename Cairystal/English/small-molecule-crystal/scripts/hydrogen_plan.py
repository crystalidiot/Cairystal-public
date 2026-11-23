"""Generate bounded HFIX plans from an explicit chemical graph and current RES.

No image recognition, protonation guessing, coordinate changes or model acceptance.
The generated plan feeds crystal_pipeline.py step; normal validation remains required.
"""
import argparse, hashlib, json, math, re, sys
from pathlib import Path


def rule(atom, orders, donor_basis=''):
    """Return (HFIX, H count, reason). None code means no H, not unknown H."""
    e=atom['element'].upper(); q=atom.get('formal_charge')
    if type(q) is not int:raise ValueError('Explicit integer formal_charge required')
    h=atom.get('hydrogens'); n=len(orders); val=sum(orders)
    if h is None and e=='C' and q==0:
        h=4-val
        if not float(h).is_integer():raise ValueError('Ambiguous carbon valence')
        h=int(h)
    if type(h) is not int or not 0<=h<=4:raise ValueError('Explicit/derivable integer H count required')
    if e=='C':
        if q!=0 or abs(val+h-4)>1e-8:raise ValueError('Charged or non-tetravalent carbon needs review')
        if h==0:return None,0,'no H in carbon valence'
        if orders==[1] and h==3:return 137,h,'methyl rotating group'
        if n==2 and orders==[1,1] and h==2:return 23,h,'sp3 methylene riding group'
        if n==3 and orders==[1,1,1] and h==1:return 13,h,'sp3 methine riding group'
        if n==2 and sorted(orders) in ([1,2],[1.5,1.5]) and h==1:return 43,h,'sp2 CH external-bisector riding group'
        if orders==[3] and h==1:return 163,h,'terminal acetylenic CH'
        raise ValueError('Carbon H geometry outside implemented rules')
    if e=='N':
        if q not in (0,1) or abs(val+h-(3+q))>1e-8:raise ValueError('Nitrogen valence/charge conflict')
        if h==0:return None,0,'no H in explicit nitrogen valence'
        if not donor_basis.strip():raise ValueError('N-H protonation basis required')
        if q==1 and h==3 and orders==[1]:return 137,h,'confirmed terminal ammonium rotating group'
        if q==0 and h==1 and orders==[1,1] and atom.get('geometry')=='planar':return 43,h,'explicitly planar neutral NH'
        raise ValueError('N-H geometry/protonation requires separate treatment')
    if e=='O':
        if q not in (-1,0,1) or abs(val+h-(2+q))>1e-8:raise ValueError('Oxygen valence/charge conflict')
        if h==0:return None,0,'no H in explicit oxygen valence'
        if not donor_basis.strip():raise ValueError('O-H protonation basis required')
        if q==0 and h==1 and orders==[1]:return 147,h,'confirmed OH rotating group; orientation still needs density/contact checks'
        raise ValueError('Water or charged O-H requires separate orientation treatment')
    if h:raise ValueError('Hydrogens on this element are outside implemented rules')
    return None,0,'no H on this graph site'


def parse_graph(graph):
    atoms=graph['atoms']; ids=[a['id'] for a in atoms]
    if not ids or len(ids)!=len(set(ids)):raise ValueError('Graph IDs empty/duplicated')
    byid={a['id']:a for a in atoms}; adjacent={k:{} for k in ids}
    for a in atoms:
        if not re.fullmatch(r'[A-Z][a-z]?',a['element']) or a['element'] in ('H','D'):
            raise ValueError('Heavy-atom graph with H counts required')
    for x,y,order in graph['bonds']:
        if x==y or x not in byid or y not in byid or y in adjacent[x]:raise ValueError('Invalid/duplicated graph bond')
        if type(order) not in (int,float) or order not in (1,1.5,2,3):raise ValueError('Unsupported bond order')
        adjacent[x][y]=order;adjacent[y][x]=order
    return byid,adjacent


def acceptor_exclusion(atom,neighbors,byid):
    if atom['element']=='N' and type(atom.get('formal_charge')) is int and atom['formal_charge']>0:
        return 'positively charged nitrogen in supplied graph'
    if atom['element'] in {'Cl','Br','I'} and sum(byid[j]['element']=='O' for j in neighbors)>=3:
        return 'central oxohalogen site; free halide acceptors are retained'
    return None


def hydrogen_scope(graph):
    """Classify requested H treatment using the same valence rules as the actual plan."""
    byid,adjacent=parse_graph(graph)
    donors=[]
    total=0
    for key,atom in byid.items():
        # This dry run only asks whether supporting a donor would require evidence.
        # The actual H plan still calls rule() with the user's recorded basis.
        _,count,_=rule(atom,list(adjacent[key].values()),'classify requested geometry')
        total+=count
        if atom['element'] in ('N','O') and count:
            donors.append(key)
    return total,donors


def generate(graph, mapping, model_atoms, nearby, donor_basis=''):
    byid,adjacent=parse_graph(graph)
    mapping={k:str(v).upper() for k,v in mapping.items()}
    current={a['label'].upper():a for a in model_atoms}
    if len(current)!=len(model_atoms):raise ValueError('Duplicate model labels')
    if any(a['element'].upper() in ('H','D') for a in model_atoms):raise ValueError('Existing H present; do not add duplicate H or replace previous treatment')
    if set(mapping)!=set(byid) or len(set(mapping.values()))!=len(mapping) or set(mapping.values())!=set(current):
        raise ValueError('Complete one-to-one graph/current-model mapping required')
    findings=[];decisions=[];commands=[];expected=0
    for key,a in byid.items():
        label=mapping[key];m=current[label]
        try:
            if m['element'].upper()!=a['element'].upper():raise ValueError('Graph/model element mismatch; correct and refine atom typing first')
            if m.get('part',0)!=0 or m.get('residue','0')!='0':raise ValueError('PART/RESI needs explicit component handling')
            if abs(m['inferred_cif_occupancy']-1)>1e-5:raise ValueError('Partial population needs explicit H occupancy handling')
            if m['geometric_site_multiplicity']!=m['general_multiplicity']:raise ValueError('Special position needs symmetry-aware H treatment')
            if set(nearby[label])!={mapping[x] for x in adjacent[key]}:raise ValueError('Current geometric neighborhood disagrees with graph (including possible coordination/polymer contact)')
            code,h,why=rule(a,list(adjacent[key].values()),donor_basis)
            if code and h>1 and len(label)>=4:
                raise ValueError('Multi-H HFIX on a four-character parent risks native H-label collisions. Renumber the current heavy model with labels, update graph mapping, and regenerate this plan; do not reuse old H coordinates. Native output identities must still be checked.')
            expected+=h
            if code:commands.append(f'HFIX {code} {label}')
            decisions.append({'graph_id':key,'parent':label,'element':a['element'],'hydrogens':h,'hfix':code,'reason':why})
        except ValueError as exc:findings.append({'graph_id':key,'parent':label,'reason':str(exc)})
    from scientific_report_rules import excluded_acceptors
    return {'status':'ready_for_refinement' if not findings else 'needs_review','decisions':decisions,'findings':findings,'excluded_acceptors':excluded_acceptors(graph,mapping),
            'expected_H_sites_for_accepted_rules':expected,'commands':commands,'donor_protonation_basis':donor_basis,
            'meaning':'A reproducible proposal, not structural acceptance. Refine, inspect residuals/contacts and validate A/B afterwards.'}


def model_geometry(path,*,require_h=True):
    import gemmi
    from audit_occupancy import audit
    from crystal_runtime import records
    rows=records(path.read_text(encoding='latin1'))
    forbidden={'NEUT','RESI','TWIN','BASF','ABIN','EXYZ','FRAG','BIND','FREE','CONN'}
    if any(r[0].upper() in forbidden or r[0].startswith('+') for r in rows):raise ValueError('Special model/connectivity controls need dedicated handling')
    if any(r[0].upper()=='HFIX' or (r[0].upper()=='AFIX' and int(r[1])!=0) for r in rows):raise ValueError('Existing HFIX/nonzero AFIX; review current model before generating H')
    if require_h and not any(r[0].upper()=='TEMP' for r in rows):raise ValueError('Measured TEMP required for temperature-aware native X-H distances')
    sfac=next(r[1:] for r in rows if r[0].upper()=='SFAC')
    if require_h and 'H' not in [x.upper() for x in sfac]:raise ValueError('Explicit SFAC must already include H')
    evidence=audit(path,gemmi)
    if evidence['overlapping_orbit_groups'] or evidence['unit_discrepancies']:raise ValueError('Occupancy/UNIT audit must be resolved first')
    if not evidence['space_group']:raise ValueError('Unrecognized symmetry setting')
    cell=gemmi.UnitCell(*map(float,next(r[2:] for r in rows if r[0].upper()=='CELL')))
    ops=gemmi.SpaceGroup(evidence['space_group']).operations()
    sites=[]
    for atom in evidence['atoms']:
        radius=gemmi.Element(atom['element']).covalent_r
        if not radius or not math.isfinite(radius):raise ValueError('No covalent radius for graph consistency check')
        xyz=atom['xyz']
        images=[gemmi.Fractional(*op.apply_to_xyz(xyz)) for op in ops]
        sites.append((atom['label'].upper(),radius,gemmi.Fractional(*xyz),images))
    return evidence,sfac,cell,sites


def model_context(path,*,require_h=True):
    evidence,_,cell,sites=model_geometry(path,require_h=require_h)
    atoms=evidence['atoms']
    nearby={label:set() for label,_,_,_ in sites}
    for label,ra,origin,_ in sites:
        for other,rb,_,images in sites:
            cutoff=ra+rb+.35
            if any(.4<cell.find_nearest_pbc_image(origin,pos,0).dist()<cutoff for pos in images):
                nearby[label].add(other)
    return atoms,nearby,evidence


def plan_from_decisions(result):
    if result.get('status')!='ready_for_refinement':raise ValueError('Unresolved H findings cannot produce an executable plan')
    return {'reason':'Deterministic graph-valence H rules; parent decisions and hashes are recorded alongside this plan. H orientations generated anew by SHELXL; validate density, occupancy, contacts and A/B before acceptance.',
            'hydrogens':result['commands'],'riding_h_counts':{d['parent']:d['hydrogens'] for d in result['decisions'] if d['hfix']},
            'cycles':16,'post':['HTAB'],'discover_hbonds':True,'excluded_acceptors':result.get('excluded_acceptors',{})}


def predicted_unit_h(counts,commands,account):
    """Count only the explicit, supported riding groups on audited full general sites."""
    per_code={13:1,23:2,43:1,137:3,147:1,163:1}
    declared={}
    for line in commands:
        fields=line.split()
        if len(fields)!=3 or fields[0].upper()!='HFIX' or int(fields[1]) not in per_code or fields[2].upper() in declared:
            raise ValueError('Unsupported or duplicated HFIX group for UNIT accounting')
        declared[fields[2].upper()]=per_code[int(fields[1])]
    if counts!=declared or any(type(n) is not int for n in counts.values()):
        raise ValueError('HFIX counts do not match the recorded parent decisions')
    parents={a['label'].upper():a for a in account['atoms']}
    if any(a['element'].upper() in {'H','D'} for a in account['atoms']):
        raise ValueError('Refusing to count riding H on top of existing hydrogen sites')
    total=0
    for label,n in counts.items():
        a=parents.get(label)
        if (not a or a['part'] or a['residue']!='0' or a['geometric_site_multiplicity']!=a['general_multiplicity']
                or abs(a['inferred_cif_occupancy']-1)>1e-5):
            raise ValueError('HFIX parent requires occupancy/symmetry review: '+label)
        total+=a['unit_cell_contribution']*n
    return total

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--model',required=True);p.add_argument('--graph',required=True);p.add_argument('--mapping',required=True)
    p.add_argument('--output',required=True);p.add_argument('--donor-protonation-basis',default='');p.add_argument('--dependency-dir')
    a=p.parse_args()
    if a.dependency_dir:sys.path.insert(0,a.dependency_dir)
    from pipeline_intake import unlinked
    from crystal_runtime import regular,sha,write_json
    out=unlinked(a.output);out.mkdir(exist_ok=False)
    try:
        paths=[regular(unlinked(x)) for x in (a.model,a.graph,a.mapping)]
        hashes={str(x):sha(x) for x in paths}
        graph=json.loads(paths[1].read_text('utf-8-sig'));mapping=json.loads(paths[2].read_text('utf-8-sig'))
        atoms,nearby,evidence=model_context(paths[0],require_h=bool(hydrogen_scope(graph)[0]));result=generate(graph,mapping,atoms,nearby,a.donor_protonation_basis)
        result.update(input_hashes=hashes,ai_calls=0,source_unchanged=all(sha(x)==hashes[str(x)] for x in paths))
        if not result['source_unchanged']:raise ValueError('Inputs changed during plan generation')
        write_json(out/'decisions.json',result)
        if result['status']=='ready_for_refinement':
            plan=plan_from_decisions(result)
            write_json(out/'plan.json',plan)
        print(json.dumps({'status':result['status'],'plan':str(out/'plan.json') if (out/'plan.json').exists() else None,'decisions':str(out/'decisions.json'),'H_sites':result['expected_H_sites_for_accepted_rules'],'findings':result['findings']},ensure_ascii=False))
        return 0 if result['status']=='ready_for_refinement' else 2
    except (ValueError,OSError,KeyError,TypeError,StopIteration) as exc:
        write_json(out/'decisions.json',{'status':'needs_review','failure':str(exc),'ai_calls':0})
        print(json.dumps({'status':'needs_review','failure':str(exc),'output':str(out)},ensure_ascii=False));return 2

if __name__=='__main__':raise SystemExit(main())
