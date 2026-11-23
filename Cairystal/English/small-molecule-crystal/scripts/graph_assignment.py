"""Bounded 2D graph matching and competing C/N/O assignment trials; no reference models."""
import json,math,time
from pathlib import Path
from collections import Counter
from hydrogen_plan import parse_graph,rule,model_context,model_geometry,generate,plan_from_decisions,hydrogen_scope,acceptor_exclusion
from crystal_runtime import write_json,sha

LIGHT={'C','N','O'}

def enumerate_assignments(graph,atoms,neighbors,distances,max_classes=6,max_nodes=200000):
    byid,adj=parse_graph(graph);current={a['label'].upper():dict(a,element=a['element'][0].upper()+a['element'][1:].lower()) for a in atoms}
    if len(current)!=len(atoms) or len(byid)!=len(atoms):
        return {'status':'needs_review','reason':'Graph/current heavy-atom counts differ or duplicate labels; missing sites/solvents are not invented.','candidates':[]}
    if any(c in graph.get('smiles','') for c in ('@','/','\\')) or any(k in graph for k in ('stereochemistry','stereo')) or any(any(k in a for k in ('stereo','chirality','chiral_tag')) for a in byid.values()):
        return {'status':'needs_review','reason':'Explicit stereochemistry needs a dedicated check; unsupported by this matcher.','candidates':[]}
    roles={}
    for k,a in byid.items():
        code,h,why=rule(a,list(adj[k].values()),'Protonation explicitly declared by the supplied graph')
        roles[k]=(a['element'],h,code,bool(acceptor_exclusion(a,adj[k],byid)))
    for label,a in current.items():
        if a['element'].upper() in ('H','D') or a.get('part',0)!=0 or a.get('residue','0')!='0' or abs(a.get('inferred_cif_occupancy',1)-1)>1e-5 or a.get('geometric_site_multiplicity',1)!=a.get('general_multiplicity',1):
            return {'status':'needs_review','reason':'Existing H, disorder, partial occupancy or special position requires dedicated handling.','candidates':[]}
    domains={k:[label for label,a in current.items() if len(neighbors[label])==len(adj[k]) and (a['element']==v['element'] or {a['element'],v['element']}<=LIGHT)] for k,v in byid.items()}
    # For one connected molecule, keep the original search and avoid loading the
    # equivalence machinery. BFS is also the first component of a disconnected graph.
    first=next(iter(byid))
    connected={first};pending=[first]
    while pending:
        unseen=adj[pending.pop()].keys()-connected
        connected.update(unseen);pending.extend(unseen)
    copies=[]
    if len(connected)!=len(byid):
        from graph_components import components,restrict_copies
        parts=[sorted(connected)]+components({k:v for k,v in adj.items() if k not in connected})
        copies=restrict_copies(byid,adj,current,neighbors,domains,LIGHT,sorted(parts))
    if any(not d for d in domains.values()):return {'status':'needs_review','reason':'No complete graph match under fixed non-C/N/O anchors and observed connectivity.','candidates':[]}
    # Terminal sites with the same parent, bond order, charge and H treatment
    # can exchange labels without changing a refinement plan. The smallest
    # mapping in each such family assigns model labels in graph-ID order.
    terminal_groups={}
    for key, bonds in adj.items():
        if len(bonds)==1:
            parent, order=next(iter(bonds.items()))
            group=(parent,order,byid[key]['formal_charge'],roles[key])
            terminal_groups.setdefault(group,[]).append(key)
    siblings={}
    multiplicity=math.prod(group['label_permutations'] for group in copies)
    for group in terminal_groups.values():
        if len(group)>1:
            siblings.update((key,group) for key in group)
            multiplicity*=math.factorial(len(group))
    classes={};mapping={};nodes=0;total=0;truncated=False
    def search(remaining):
        nonlocal nodes,total,truncated
        nodes+=1
        if nodes>max_nodes or len(classes)>max_classes:truncated=True;return
        if not remaining:
            total+=multiplicity
            # Quotient is limited to identical element/H-control effects. Formal
            # Lewis resonance label permutations remain recorded as degeneracy.
            signature=tuple(sorted((label,*roles[k]) for k,label in mapping.items()))
            native_changes=sum(current[label]['element']!=byid[k]['element'] for k,label in mapping.items())
            key=(native_changes,tuple(sorted(mapping.items())))
            if signature not in classes:classes[signature]={'key':key,'mapping':dict(mapping),'label_permutations':multiplicity}
            else:
                item=classes[signature];item['label_permutations']+=multiplicity
                if key<item['key']:item.update(key=key,mapping=dict(mapping))
            return
        k=min(remaining,key=lambda key:(len(remaining[key]),-sum(j in mapping for j in adj[key]),-len(adj[key]),key))
        for label in remaining[k]:
            next_domains={}
            for j, labels in remaining.items():
                if j==k:continue
                bonded=j in adj[k]
                choices=[other for other in labels if other!=label and (other in neighbors[label])==bonded]
                if j in siblings.get(k,()):
                    choices=[other for other in choices if (j<k)==(other<label)]
                if not choices:break
                next_domains[j]=choices
            else:
                mapping[k]=label
                search(next_domains)
                del mapping[k]
            if truncated:return
    search({k:sorted(labels) for k,labels in domains.items()})
    result={'status':'candidates_ready','search_nodes':nodes,'complete_label_mappings':total,'assignment_classes':len(classes),'search_truncated':truncated,'candidates':[],'equivalent_fragment_groups':copies,
            'equivalence':'Same element, H count, HFIX and acceptor exclusion at each current site; graph labeling within a class is arbitrary. No stereochemical acceptance.',
            'scope':'Only C/N/O may change; non-C/N/O assignments are fixed anchors. All heavy sites must match.'}
    if truncated:result.update(status='needs_review',reason='Search/class budget reached; candidates incomplete, no automatic choice.');return result
    if not classes:result.update(status='needs_review',reason='No exact connectivity match; inspect missing sites, contacts, symmetry or chemical prior.');return result
    for number,item in enumerate(sorted(classes.values(),key=lambda x:x['key']),1):
        original=item['mapping'];counts=Counter();newmap={};rename={};changes={}
        for k,atom in byid.items():
            el=atom['element'];counts[el]+=1;label=el.upper()+str(counts[el])
            if len(label)>4:raise ValueError('Generated labels exceed supported SHELX label length')
            newmap[k]=label;rename[original[k]]=label
            if current[original[k]]['element']!=el:changes[original[k]]=el
        result['candidates'].append({'id':f'c{number:02d}','original_mapping':original,'mapping':newmap,'label_permutations':item['label_permutations'],
            'plan':{'reason':'2D graph/current-model exact connectivity match; competing C/N/O assignments are separately refined. Coordinates originate only from this run. Equivalent element/H-control label permutations are collapsed; no stereochemical acceptance. See graph-matching evidence alongside this plan.','element_changes':changes,'rename':rename,'cycles':20}})
    return result

def geometry(path,graph):
    import gemmi
    evidence,sfac,cell,sites=model_geometry(path,require_h=bool(hydrogen_scope(graph)[0]))
    atoms=evidence['atoms']
    if any(a['geometric_site_multiplicity']!=a['general_multiplicity'] for a in atoms):raise ValueError('Special position requires dedicated matching')
    expected={a['element'].upper() for a in graph['atoms']}
    if not expected<={s.upper() for s in sfac}:raise ValueError('Graph contains elements absent from the explicitly configured SFAC')
    domains={a['label'].upper():(LIGHT & {v['element'] for v in graph['atoms']} if a['element'] in LIGHT else {a['element']}) for a in atoms}
    if any(not els for els in domains.values()):
        raise ValueError('A light scattering site has no allowed C/N/O assignment in the supplied graph')
    radii={label:max(gemmi.Element(el).covalent_r for el in els) for label,els in domains.items()}
    distances={};near={a['label'].upper():set() for a in atoms};sensitivity=[]
    for i,(la,_,origin,_) in enumerate(sites):
        for j,(lb,_,_,images) in enumerate(sites[i:],i):
            ds=[]
            for target in images:
                distance=cell.find_nearest_pbc_image(origin,target,0).dist()
                if i==j and distance<.001:continue
                ds.append(distance)
            if not ds:continue
            d=min(ds);cutoff=radii[la]+radii[lb]+.25
            if d<.65:raise ValueError('Overlapping/too-close model sites need review')
            if abs(d-cutoff)<.05:sensitivity.append([la,lb,d,cutoff])
            if d<cutoff:
                if i==j or sum(x<cutoff for x in ds)>1:raise ValueError('Self/symmetry-multiple connectivity needs polymer/special-site handling')
                near[la].add(lb);near[lb].add(la)
            if i!=j:distances[tuple(sorted((la,lb)))]=d
    if sensitivity:raise ValueError('Connectivity changes near radius cutoff; ambiguous contacts: '+str(sensitivity[:6]))
    return atoms,near,distances,{'space_group':evidence['space_group'],'bond_rule':'maximum allowed C/N/O covalent-radius sum +0.25 A; +/-0.05 A boundary is ambiguous','radii_source':'Installed Gemmi covalent_r','distance_sensitivity_findings':sensitivity}

def propose(model,graph,max_classes=6):
    atoms,near,distances,evidence=geometry(model,graph)
    result=enumerate_assignments(graph,atoms,near,distances,max_classes=max_classes)
    result['geometry']=evidence;result['neighbors']={k:sorted(v) for k,v in near.items()}
    return result

def select_trial(trials):
    if not trials or any(not x.get('execution_complete') for x in trials):
        return {'status':'needs_review','reason':'One or more competing trials did not finish; no automatic acceptance.'}
    for trial in trials:
        metrics=trial.get('metrics') or {}
        for key in ('R1_observed','wR2','GooF','last_abs_max_shift_esd'):
            value=metrics.get(key)
            if type(value) not in (int,float) or not math.isfinite(value) or value<0:
                return {'status':'needs_review','reason':f'Missing or invalid {key} for comparison: {trial.get("id")}'}
        for key,minimum in [('NPD_atoms',0),('unique',1)]:
            if type(metrics.get(key)) is not int or metrics[key]<minimum:
                return {'status':'needs_review','reason':f'Missing or invalid {key} for comparison: {trial.get("id")}'}
    viable=[t for t in trials if not t.get('review_reasons') and t.get('graph_H_check')=='ready_for_refinement'
            and t['metrics']['NPD_atoms']==0 and t['metrics']['last_abs_max_shift_esd']<=.01
            and t['metrics']['R1_observed']<=.12 and .5<=t['metrics']['GooF']<=2]
    if not viable:return {'status':'needs_review','reason':'No trial passes convergence, ADP, graph/H and broad fit checks.'}
    viable.sort(key=lambda t:t['metrics']['R1_observed']);best=viable[0]
    others=[t for t in trials if t is not best]
    gap=min((t['metrics']['R1_observed']-best['metrics']['R1_observed'] for t in others),default=None)
    required=max(.003,.05*best['metrics']['R1_observed'])
    if gap is not None and gap<required:return {'status':'needs_review','reason':'Competing assignments are too close, or lower-R alternative needs scientific review.','R1_gap':gap,'required_gap':required}
    if any(t['metrics'].get('unique') is None for t in trials) or len({t['metrics']['unique'] for t in trials})!=1:return {'status':'needs_review','reason':'Competing trials used different or unknown reflection counts.'}
    return {'status':'ready_for_model_review','selected_id':best['id'],'selected_stage':best['stage'],'R1_gap':gap,'required_gap':required,'reason':'Provisional choice under an explicit chemical graph; all bounded candidates retained. R1 margin is an engineering review threshold, not a correctness probability.'}

def run_pipeline(root,state,a):
    import crystal_pipeline as cp
    from types import SimpleNamespace
    from refinement_gate import assess
    cp.checked(root,state)
    if state['status']=='complete':raise ValueError('Completed run is sealed; use a new run')
    if not 1<=a.max_candidates<=6:raise ValueError('Candidate budget must be 1..6')
    name=cp.identifier(a.name);folder=root/name
    folder.mkdir(exist_ok=False)
    graphpath=cp.regular(cp.unlinked(a.graph));graph=cp.read(graphpath);write_json(folder/'chemical_graph.json',graph)
    model=root/'session/stages'/cp.identifier(a.source)/'model.res'
    result={'graph_sha256':sha(graphpath),'model_sha256':sha(model),'ai_calls':0,'trials':[]}
    try:
        proposal=cp.timed(root,state,name+'_enumerate',lambda:propose(model,graph,a.max_candidates),{'model':str(model),'graph':str(graphpath),'max_classes':a.max_candidates})
        write_json(folder/'proposal.json',proposal);result['proposal_status']=proposal['status']
        if proposal['status']!='candidates_ready':result.update(status='needs_review',reason=proposal.get('reason'));return result
        expected_h,_=hydrogen_scope(graph)
        for candidate in proposal['candidates']:
            stage=name+'_'+candidate['id'];plan=folder/(candidate['id']+'_plan.json');write_json(plan,candidate['plan'])
            cp.step(root,state,SimpleNamespace(source=a.source,plan=str(plan),name=stage))
            current=root/'session/stages'/stage;gate=assess(current,'model')
            try:
                atoms,near,_=model_context(current/'model.res',require_h=bool(expected_h));h=generate(graph,candidate['mapping'],atoms,near,a.donor_basis)
            except (ValueError,KeyError) as exc:h={'status':'needs_review','failure':str(exc)}
            trial={'id':candidate['id'],'stage':stage,'metrics':gate['metrics'],'execution_complete':gate['execution_complete'],'review_reasons':gate['review_reasons'],'graph_H_check':h['status'],'H_decisions':h,'mapping':candidate['mapping']}
            result['trials'].append(trial);write_json(folder/'result.json',result)
        result.update(select_trial(result['trials']))
        if result['status']=='ready_for_model_review':
            selected=next(t for t in result['trials'] if t['id']==result['selected_id']);write_json(folder/'mapping.json',selected['mapping'])
            cp.register_summary(root,state,root/'session'/(selected['stage']+'_summary.json'))
            if a.add_hydrogens:
                h=selected['H_decisions'];h['input_hashes']={str(graphpath):sha(graphpath),str(folder/'mapping.json'):sha(folder/'mapping.json'),str(root/'session/stages'/selected['stage']/'model.res'):sha(root/'session/stages'/selected['stage']/'model.res')};h['ai_calls']=0
                write_json(folder/'hydrogen_decisions.json',h)
                if not expected_h and not h['commands'] and h['expected_H_sites_for_accepted_rules']==0:
                    result.update(hydrogen_handling='none_in_complete_graph',finish_stage=selected['stage'])
                else:
                    plan=folder/'hydrogen_plan.json';write_json(plan,plan_from_decisions(h))
                    stage=name+'_H';cp.step(root,state,SimpleNamespace(source=selected['stage'],plan=str(plan),name=stage))
                    result['hydrogen_stage']=stage+'_hbonds' if (root/'session/stages'/(stage+'_hbonds')/'model.res').exists() else stage
                    import gemmi
                    from audit_occupancy import audit
                    built=audit(root/'session/stages'/result['hydrogen_stage']/'model.res',gemmi)
                    actual=sum(atom['element'].upper()=='H' for atom in built['atoms'])
                    result['native_h_check']=dict(expected_asu_h=expected_h,actual_asu_h=actual,
                                                   unit_discrepancies=built['unit_discrepancies'])
                    if actual!=expected_h or built['unit_discrepancies']:
                        result.update(status='needs_review',reason='Native hydrogen sites or UNIT disagree with the recorded plan')
                        return result
                    result.update(hydrogen_handling='refined',finish_stage=result['hydrogen_stage'])
        return result
    except (ValueError,KeyError,TypeError) as exc:
        result.update(status='needs_review',reason=str(exc));return result
    finally:
        result['source_model_unchanged']=sha(model)==result['model_sha256'];result['graph_unchanged']=sha(graphpath)==result['graph_sha256']
        write_json(folder/'result.json',result);state['graph_matching']={k:result.get(k) for k in ('status','selected_stage','hydrogen_stage','finish_stage','hydrogen_handling','reason')}
        state['graph_matching']['record']=str(folder/'result.json')
        state['status']='needs_scientific_review';cp.save(root,state)
