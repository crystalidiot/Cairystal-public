"""Explicit complete configurations for fragment-orbits.

The caller supplies chemistry, images and configuration probabilities. This
module checks geometry/population bookkeeping; it never constructs an INS.
"""
import itertools,math
from pathlib import Path
import gemmi

def norm_operation(op):
    return tuple(v for row in op.rot for v in row),tuple(v%op.DEN for v in op.tran)

def equivalent_configuration(cell,a,b,tolerance=.015):
    """One lattice shift for the whole configuration; element-preserving bijection."""
    if len(a)!=len(b):return False
    ca=[sum(x['xyz'][k] for x in a)/len(a) for k in range(3)]
    cb=[sum(x['xyz'][k] for x in b)/len(b) for k in range(3)]
    shift=cell.find_nearest_pbc_image(gemmi.Fractional(*ca),gemmi.Fractional(*cb),0).pbc_shift
    edges=[]
    for x in a:
        options=[]
        for j,y in enumerate(b):
            if x['element'].upper()!=y['element'].upper():continue
            delta=[y['xyz'][k]+shift[k]-x['xyz'][k] for k in range(3)]
            if cell.orthogonalize(gemmi.Fractional(*delta)).length()<tolerance:options.append(j)
        if not options:return False
        edges.append(options)
    assigned={}
    def match(i,seen):
        for j in edges[i]:
            if j in seen:continue
            seen.add(j)
            if j not in assigned or match(assigned[j],seen):assigned[j]=i;return True
        return False
    return all(match(i,set()) for i in range(len(a)))

def unique_configurations(cell,atoms,ops,group,probability):
    states=[]
    for op in ops:
        points=[dict(a,xyz=op.apply_to_xyz(a['xyz'])) for a in atoms]
        old=next((s for s in states if equivalent_configuration(cell,s['atoms'],points)),None)
        if old is not None:old['equivalent_operations'].append(op.triplet());continue
        states.append({'id':group+'@'+str(len(states)+1),'fragment':group,'operation':op.triplet(),
                       'probability':probability,'atoms':points,'equivalent_operations':[op.triplet()]})
    return states

def predicted_site_population(cell,xyz,element,states):
    population=0.
    for state in states:
        hits=sum(x['element'].upper()==element.upper() and cell.find_nearest_pbc_image(
            gemmi.Fractional(*xyz),gemmi.Fractional(*x['xyz']),0).dist()<.015 for x in state['atoms'])
        if hits>1:raise ValueError('A complete configuration contains duplicate coincident sites')
        population+=hits*state['probability']
    return population

def audit_fragment_hydrogens(parsed,cif_by,raw_by,selected):
    """Follow existing riding-group parents; do not infer/rebuild hydrogen chemistry."""
    items=[];warnings=[];parent=None
    for a in parsed['atoms']:
        if a['element'].upper()!='H':parent=a;continue
        if parent is None or parent['label'].upper() not in selected:continue
        if a['afix'] not in {3,13,23,33,43,83,93,123,133,137,147,163}:continue
        key=a['label'].upper();r=raw_by.get(key);cif=cif_by.get(key)
        item={'label':a['label'],'parent':parent['label'],'afix':a['afix'],'part':a['part'],'parent_part':parent['part']}
        if parent['part'] and a['part']!=parent['part']:
            warnings.append(a['label']+': existing riding H PART differs from its nonzero-PART parent; review the whole group')
        if r and cif:
            physical=r['general_multiplicity']*r['decoded_shelx_sof']/r['geometric_site_multiplicity']
            item.update(physical_occupancy=physical,exported_cif_occupancy=cif['occupancy'])
            if cif['res_context_status']!='matched':warnings.append(a['label']+': H CIF/RES context is not uniquely paired')
            if cif['occupancy'] is None or abs(cif['occupancy']-physical)>.002:
                warnings.append(a['label']+': H CIF occupancy and geometric/SHELX accounting disagree')
        else:warnings.append(a['label']+': hydrogen site accounting unavailable')
        items.append(item)
    return items,warnings

def inspect_explicit(directory,config):
    # Deferred import keeps the simple-mode public arithmetic helpers compatible.
    from fragment_orbits import VDW,occupancy_bound,site_account
    from structure_diagnostics import structure,digest
    from audit_occupancy import audit
    d=Path(directory);b,cell,ops,atoms,parsed=structure(d/'case.cif',d/'case.res')
    account=audit(d/'case.res',gemmi);by={a['label'].upper():a for a in atoms};raw={a['label'].upper():a for a in account['atoms']}
    if len(ops)>64:raise ValueError('At most 64 space-group operations supported')
    groups=config['fragments']
    if not 1<=len(groups)<=4:raise ValueError('Specify 1–4 complete configurations')
    if len({g['id'] for g in groups})!=len(groups):raise ValueError('Configuration ids must be unique')
    ratio=float(config.get('severe_contact_fraction',.70));tolerance=float(config.get('population_tolerance',.01))
    if not .5<=ratio<=.85 or not 0<=tolerance<=.1:raise ValueError('Unreasonable screening thresholds')
    allowed={norm_operation(op) for op in ops};states=[];selected={};warnings=[];norm=[]
    for group in groups:
        p=float(group['probability'])
        if not math.isfinite(p) or not 0<p<=1:raise ValueError('Explicit configuration probability must be in (0,1]')
        entries=group['atoms']
        if not 2<=len(entries)<=20:raise ValueError('2–20 heavy-atom entries required')
        points=[]
        for entry in entries:
            if isinstance(entry,str):entry={'label':entry}
            key=entry['label'].upper();a=by[key];r=raw[key]
            if a['res_context_status']!='matched':raise ValueError('CIF/RES atoms are not uniquely paired')
            if a['element'].upper() not in VDW or a['element'].upper()=='H':raise ValueError('Use supported heavy atoms')
            op=gemmi.Op(entry.get('symmetry','x,y,z'))
            if norm_operation(op) not in allowed:raise ValueError('Requested image is not an operation of this CIF space group')
            points.append({'label':a['label'],'element':a['element'],'xyz':op.apply_to_xyz(a['xyz'])})
            selected[key]=(a,r)
        if any(cell.orthogonalize(gemmi.Fractional(*[a['xyz'][k]-z['xyz'][k] for k in range(3)])).length()<.015 for a,z in itertools.combinations(points,2)):
            raise ValueError('Duplicate coincident atoms in a supplied complete configuration')
        span=max(cell.orthogonalize(gemmi.Fractional(*[a['xyz'][k]-z['xyz'][k] for k in range(3)])).length() for a,z in itertools.combinations(points,2))
        if span>float(config.get('max_fragment_span_A',10)):raise ValueError('Configuration not coherently assembled or larger than supported span')
        ss=unique_configurations(cell,points,ops,group['id'],p);states.extend(ss)
        norm.append({'id':group['id'],'space_group_operations':len(ops),'unique_configurations':len(ss),
                     'stabilizer_orders':[len(s['equivalent_operations']) for s in ss],
                     'supplied_configuration_probability':p,'expected_atoms_per_cell':len(ss)*p*len(points)})
    if len(states)>128:raise ValueError('More than 128 unique configurations; restrict to a local diagnostic')
    sites=[]
    for key,(a,r) in selected.items():
        actual=site_account(r['decoded_shelx_sof'],r['general_multiplicity'],r['geometric_site_multiplicity'])
        predicted=predicted_site_population(cell,a['xyz'],a['element'],states)
        sites.append({'label':a['label'],'element':a['element'],**actual,'exported_cif_occupancy':a['occupancy'],
                      'configuration_predicted_occupancy':predicted,'population_difference':predicted-actual['physical_occupancy']})
        if abs(predicted-actual['physical_occupancy'])>.002:warnings.append(a['label']+': explicit configurations do not reproduce the refined site population')
        if a['occupancy'] is None or abs(a['occupancy']-actual['physical_occupancy'])>.002:warnings.append(a['label']+': CIF and SHELX/site-multiplicity populations disagree')
    hydrogen,hwarnings=audit_fragment_hydrogens(parsed,by,raw,selected)
    warnings.extend(hwarnings)
    edges=[];contacts=[]
    for i,j in itertools.combinations(range(len(states)),2):
        a,z=states[i],states[j];ca=[sum(x['xyz'][k] for x in a['atoms'])/len(a['atoms']) for k in range(3)];cz=[sum(x['xyz'][k] for x in z['atoms'])/len(z['atoms']) for k in range(3)]
        shift=cell.find_nearest_pbc_image(gemmi.Fractional(*ca),gemmi.Fractional(*cz),0).pbc_shift
        found=[]
        for extra in itertools.product([-1,0,1],repeat=3):
            trans=[shift[k]+extra[k] for k in range(3)]
            for x,y in itertools.product(a['atoms'],z['atoms']):
                dist=cell.orthogonalize(gemmi.Fractional(*[y['xyz'][k]+trans[k]-x['xyz'][k] for k in range(3)])).length()
                limit=ratio*(VDW[x['element'].upper()]+VDW[y['element'].upper()])
                if dist<limit:found.append({'atoms':[x['label'],y['label']],'distance_A':dist,'threshold_A':limit,'whole_fragment_translation':trans,'coincident_shared_site':dist<.015})
        if found:edges.append([i,j]);contacts.append({'states':[a['id'],z['id']],'contacts':sorted(found,key=lambda x:x['distance_A'])})
    conflicts=occupancy_bound(states,edges,tolerance)
    return {'status':'needs_review' if conflicts or warnings else 'screen_complete_not_acceptance','mode':'explicit_complete_configurations',
            'source_hashes':{'cif':digest(d/'case.cif'),'res':digest(d/'case.res')},'settings':config,
            'normalization':norm,'site_accounting':sites,'hydrogen_accounting':hydrogen,'configurations':states,'possible_exclusions':contacts,
            'incompatible_population_bounds':conflicts,'warnings':warnings,
            'limitations':['Complete molecule/atom images and probabilities are supplied by a reviewer; chemical identity is not inferred.',
             'Whole-molecule symmetry duplicates are merged before probability counting; source atoms are never rewritten.',
             'Severe contacts, including shared atom positions, prompt configuration review; they are not proof of chemical bonding or exclusion.',
             'Only pair/triple clique bounds are tested. Passing is not proof of a globally feasible or correct model.']}
