"""Read-only whole-fragment symmetry and occupancy diagnostics.

Pair/triple exclusion bounds are necessary conditions, not a full configurational
probability solution. Short contacts are review triggers, not automatic bonds.
"""
from pathlib import Path
import argparse,itertools,json,math
import gemmi
from audit_occupancy import audit
from structure_diagnostics import structure,digest,newjson

VDW={'H':1.20,'C':1.70,'N':1.55,'O':1.52,'F':1.47,'P':1.80,'S':1.80,'CL':1.75,'BR':1.85,'I':1.98}

def occupancy_bound(states,edges,tolerance=.01):
    """Test necessary marginal-population bounds for pair/triple cliques."""
    bad=[];edge_set={frozenset(e) for e in edges}
    for size in [2,3]:
        for ids in itertools.combinations(range(len(states)),size):
            if all(frozenset(p) in edge_set for p in itertools.combinations(ids,2)):
                total=sum(states[i]['probability'] for i in ids)
                if total>1+tolerance:
                    bad.append({'states':[states[i]['id'] for i in ids],'population_sum':total,'upper_bound':1,
                        'reason':'If these short contacts imply mutual exclusion, these marginal populations cannot coexist.'})
    return bad

def site_account(q,general,multiplicity):
    if not 1<=multiplicity<=general or not math.isfinite(q):raise ValueError('Invalid site accounting')
    return {'decoded_shelx_sof':q,'general_multiplicity':general,'site_multiplicity':multiplicity,
            'physical_occupancy':general*q/multiplicity,'atoms_per_cell':general*q}

def inspect(directory,config):
    if any('probability' in g or any(isinstance(a,dict) for a in g['atoms']) for g in config['fragments']):
        from configuration_orbits import inspect_explicit
        return inspect_explicit(directory,config)
    directory=Path(directory);cif=directory/'case.cif';res=directory/'case.res'
    b,cell,ops,atoms,parsed=structure(cif,res);account=audit(res,gemmi)
    by={a['label'].upper():a for a in atoms};raw={a['label'].upper():a for a in account['atoms']}
    if len(ops)>64:raise ValueError('At most 64 explicit operations supported in this bounded diagnostic')
    groups=config['fragments']
    if not 1<=len(groups)<=4:raise ValueError('Specify 1–4 reviewed complete fragments')
    ratio=float(config.get('severe_contact_fraction',.70));tolerance=float(config.get('population_tolerance',.01))
    if not .5<=ratio<=.85 or not 0<=tolerance<=.1:raise ValueError('Unreasonable screening thresholds')
    states=[];sites=[];warnings=[]
    if len(ops)*len(groups)>128:raise ValueError('More than 128 configurations; restrict the local diagnostic')
    for g in groups:
        labels=[s.upper() for s in g['atoms']]
        if len(set(labels))!=len(labels) or not 2<=len(labels)<=20:raise ValueError('2–20 unique atoms required per fragment')
        aa=[by[k] for k in labels];rr=[raw[k] for k in labels]
        if any(a['res_context_status']!='matched' for a in aa):raise ValueError('Selected CIF/RES atoms are not uniquely paired')
        if any(a['element'].upper()=='H' for a in aa):raise ValueError('Use heavy-atom configuration footprints; audit H ownership separately')
        if any(a['element'].upper() not in VDW for a in aa):raise ValueError('Unsupported element contact radius; use specialist review')
        pops=[a['decoded_shelx_sof'] for a in rr]
        if max(pops)-min(pops)>.0001:raise ValueError('Fragment SOFs differ: declare complete configurations/shared sites using a specialist route')
        p=sum(pops)/len(pops)
        if not 0<p<=1:raise ValueError('Configuration population outside (0,1]')
        # Reject unassembled coordinates rather than moving individual atoms to arbitrary images.
        xyz=[a['xyz'] for a in aa]
        span=max(cell.orthogonalize(gemmi.Fractional(*[a[i]-c[i] for i in range(3)])).length() for a in xyz for c in xyz)
        if span>float(config.get('max_fragment_span_A',10)):raise ValueError('Fragment is not compact: supply coherently assembled representatives')
        for a in rr:
            inferred=a['general_multiplicity']*a['decoded_shelx_sof']/a['geometric_site_multiplicity']
            exported=by[a['label'].upper()]['occupancy']
            if exported is None or abs(exported-inferred)>.002:
                warnings.append(a['label']+': CIF occupancy and geometric/SHELX accounting differ; review special-position export before interpreting populations')
            sites.append({'fragment':g['id'],'label':a['label'],'element':a['element'],
                **site_account(a['decoded_shelx_sof'],a['general_multiplicity'],a['geometric_site_multiplicity']),
                'exported_cif_occupancy':by[a['label'].upper()]['occupancy']})
        keys=set()
        for oi,op in enumerate(ops):
            points=[op.apply_to_xyz(a['xyz']) for a in aa]
            key=tuple(sorted((a['element'].upper(),*[round(v%1,5) for v in pos]) for a,pos in zip(aa,points)))
            if key in keys:raise ValueError('Whole-fragment special symmetry produces duplicate configurations; requires explicit configuration normalization')
            keys.add(key)
            states.append({'id':g['id']+'@'+str(oi+1),'fragment':g['id'],'operation':op.triplet(),'probability':p,
                           'atoms':[{'label':a['label'],'element':a['element'],'xyz':pos} for a,pos in zip(aa,points)]})
    edges=[];contacts=[]
    for i,j in itertools.combinations(range(len(states)),2):
        a,b=states[i],states[j]
        ca=[sum(x['xyz'][k] for x in a['atoms'])/len(a['atoms']) for k in range(3)]
        cb=[sum(x['xyz'][k] for x in b['atoms'])/len(b['atoms']) for k in range(3)]
        center_shift=cell.find_nearest_pbc_image(gemmi.Fractional(*ca),gemmi.Fractional(*cb),0).pbc_shift
        found=[]
        for extra in itertools.product([-1,0,1],repeat=3):
            shift=[center_shift[k]+extra[k] for k in range(3)]
            # One common lattice translation for every atom in the second configuration.
            for x,y in itertools.product(a['atoms'],b['atoms']):
                delta=[y['xyz'][k]+shift[k]-x['xyz'][k] for k in range(3)]
                distance=cell.orthogonalize(gemmi.Fractional(*delta)).length()
                limit=ratio*(VDW[x['element'].upper()]+VDW[y['element'].upper()])
                if distance<limit:found.append({'atoms':[x['label'],y['label']],'distance_A':distance,'threshold_A':limit,'whole_fragment_translation':shift})
        if found:
            edges.append([i,j]);contacts.append({'states':[a['id'],b['id']],'contacts':sorted(found,key=lambda x:x['distance_A'])})
    conflicts=occupancy_bound(states,edges,tolerance)
    return {'status':'needs_review' if conflicts or warnings else 'screen_complete_not_acceptance','source_hashes':{'cif':digest(cif),'res':digest(res)},
        'settings':config,'site_accounting':sites,'configurations':states,'possible_exclusions':contacts,
        'incompatible_population_bounds':conflicts,'warnings':warnings,
        'limitations':['Requires reviewed complete compact configurations; chemistry is supplied, not inferred.',
        'A geometric short contact is evidence for review, not definitive mutual exclusion.',
        'Only pair/triple bounds checked; passing does not prove a globally feasible ensemble.',
        'No occupancy rewriting, final model adoption, hydrogen construction, or reference-model lookup.']}

def main():
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--directory',required=True,type=Path)
    ap.add_argument('--config',required=True,type=Path);ap.add_argument('--output',required=True,type=Path)
    args=ap.parse_args();result=inspect(args.directory,json.loads(args.config.read_text(encoding='utf-8')))
    newjson(args.output,result);print(json.dumps({'status':result['status'],'population_conflicts':len(result['incompatible_population_bounds']),'output':str(args.output)}))
if __name__=='__main__':main()
