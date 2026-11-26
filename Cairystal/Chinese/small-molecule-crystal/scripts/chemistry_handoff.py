"""Current-run element contrasts and reviewed-graph H continuation, without an LLM.

Only the selected run is read. No reference structures or structure identities.
Contrasts are hypotheses; a ranked fit is never a chemical acceptance decision.
"""
import argparse
import json
import math
import time
from collections import Counter
from pathlib import Path
from types import SimpleNamespace
import crystal_pipeline as cp
from crystal_runtime import sha, write_json, utc_now


def safe_atoms(atoms):
    if any(a['element'].upper() in {'H', 'D'} for a in atoms):
        raise ValueError('Use the current H-free model; do not silently remove H')
    for a in atoms:
        if (a.get('part', 0) or a.get('residue', '0') != '0'
                or abs(a['inferred_cif_occupancy']-1) > 1e-5
                or a['geometric_site_multiplicity'] != a['general_multiplicity']):
            raise ValueError('PART, partial occupancy or special position needs its dedicated route')


def short_labels(atoms):
    """Complete simultaneous permutation, including collision-free old/new overlaps."""
    counts = Counter()
    rename = {}
    for atom in sorted(atoms, key=lambda a: (a['element'].upper(), a['label'].upper())):
        e = atom['element'].upper()
        counts[e] += 1
        target = e+str(counts[e])
        if len(target) > 4 or (e in {'C', 'N', 'O'} and len(target) > 3):
            raise ValueError('Too many sites for supported short H-parent labels')
        rename[atom['label'].upper()] = target
    if len(set(rename.values())) != len(atoms):
        raise ValueError('Duplicate input labels or proposed targets')
    return rename


def propose_changes(atoms, near, view, allowed, mode):
    allowed = {e.upper() for e in allowed}
    by = {a['label'].upper(): a for a in atoms}
    measured = {a['label'].upper(): a for a in view['atoms']}
    proposals = []
    anchored = set()
    from model_strategy import classify
    context = classify({'all_atoms':[dict(a,label=a['label'].upper()) for a in atoms], 'regions':[
        dict(a,label=a['label'].upper(),neighbors=[{'label':n,'element':by[n]['element'],'part_compatible':True,
                          'within_covalent_radius_screen':True} for n in near[a['label'].upper()]])
        for a in atoms]}, [e.capitalize() for e in allowed])
    cage_sites = {x.upper() for x in context['possible_cage_sites']}
    # Tetrahedral terminal short-bond oxoanion hypotheses, never auto adopted.
    # This deliberately does not treat all tetrahedral P-C groups as oxygen.
    for center, a in by.items():
        if a['element'].upper() not in {'P', 'S', 'CL'} or 'O' not in allowed:
            continue
        ligands = sorted(near[center])
        distances = {x[0].upper(): x[2] for x in measured[center]['neighbors']}
        if (len(ligands) != 4 or any(near[x] != {center} for x in ligands)
                or any(by[x]['element'].upper() not in {'C','N','O'} for x in ligands)
                or any(not 1.30 <= distances.get(x, 99) <= 1.65 for x in ligands)):
            continue
        anchored.update(ligands)
        changes = {x:'O' for x in ligands if by[x]['element'].upper() != 'O'}
        if changes and mode in {'motifs', 'all'}:
            proposals.append(dict(id='oxo_'+center, element_changes=changes,
                reason=f'Current short terminal tetrahedral group around {center}: compare O ligands. This is an oxoanion hypothesis, not an identity or charge assignment.',
                evidence={'center':center,'distances':{x:distances[x] for x in ligands}}))
    if mode in {'light', 'all'}:
        for a in atoms:
            label=a['label'].upper(); e=a['element'].upper()
            if e not in {'C','N','O'} or label in anchored or label in cage_sites:
                continue
            for alternative in sorted(allowed & {'C','N','O'} - {e}):
                proposals.append(dict(id=label+'_'+alternative, element_changes={label:alternative},
                    reason=f'One-site current-run contrast {label}: {e} to {alternative}. Same reflections, weight and cycles; assess chemistry and density before selection.'))
    return proposals, sorted(anchored)


def run_step(root, state, folder, source, name, plan):
    target=folder/(name+'_plan.json'); write_json(target, plan)
    cp.step(root,state,SimpleNamespace(source=source, name=name, plan=str(target)))
    return name


def screen(root, state, a):
    from hydrogen_plan import model_context
    from refinement_gate import assess
    cp.checked(root,state)
    source=root/'session/stages'/cp.identifier(a.source)/'model.res'
    digest=sha(source)
    atoms,near,_=model_context(source,require_h=False); safe_atoms(atoms)
    allowed=state['intake']['elements']
    view=cp.read(source.parent/'model_review.json')
    proposals,anchored=propose_changes(atoms,near,view,allowed,a.mode)
    folder=root/cp.identifier(a.name);folder.mkdir(exist_ok=False)
    result=dict(status='running',started_at=utc_now(),source=a.source,source_sha256=digest,
                allowed_elements=allowed,original_view=view,anchored_oxo_ligands=anchored,
                proposals=proposals,trials=[],budget=a.max_trials,AI_calls=0,
                local_AB_per_trial=None,meaning='Screen only; final selected model must receive local and official validation.')
    begin=time.perf_counter()
    try:
        if len(proposals)>a.max_trials:
            result.update(status='needs_review',reason='Candidate count exceeds budget; nothing was silently truncated')
            return result
        if not proposals:
            result.update(status='no_candidates',reason='No supported candidate in requested mode')
            return result
        for i,proposal in enumerate([dict(id='baseline',element_changes={},reason='Equal-cycle unchanged reference for this element batch')]+proposals):
            name=a.name+'_'+str(i)
            try:
                run_step(root,state,folder,a.source,name,dict(reason=proposal['reason'],element_changes=proposal['element_changes'],cycles=a.cycles,anisotropic=True))
                stage=root/'session/stages'/name
                gate=assess(stage,'model')
                result['trials'].append(dict(id=proposal['id'],stage=name,element_changes=proposal['element_changes'],
                    execution_complete=gate['execution_complete'],metrics=gate['metrics'],review_reasons=gate['review_reasons'],
                    view=cp.read(stage/'model_review.json')))
            except (ValueError,OSError,RuntimeError) as exc:
                result['trials'].append(dict(id=proposal['id'],stage=name,execution_complete=False,error=str(exc),metrics=None))
            write_json(folder/'result.json',result)
        base=result['trials'][0].get('metrics') or {}
        for t in result['trials']:
            m=t.get('metrics') or {}; value=m.get('R1_observed'); initial=base.get('R1_observed')
            t['delta_R1']=value-initial if isinstance(value,(float,int)) and isinstance(initial,(float,int)) else None
        result.update(status='needs_chemical_selection',ranking_is_not_acceptance=True)
        result['compact_trials']=[{k:t.get(k) for k in ['id','stage','element_changes','execution_complete','metrics','delta_R1','error']} for t in result['trials']]
        return result
    finally:
        result.update(seconds=time.perf_counter()-begin,finished_at=utc_now(),source_unchanged=sha(source)==digest)
        write_json(folder/'result.json',result)
        state['element_screen']={'status':result['status'],'record':str(folder/'result.json')}
        state['status']='needs_scientific_review';cp.save(root,state)


def hydrogen(root,state,a):
    from hydrogen_plan import model_context, generate, hydrogen_scope, plan_from_decisions
    from audit_occupancy import audit
    from refinement_gate import assess
    import gemmi
    cp.checked(root,state)
    graphpath=cp.regular(cp.unlinked(a.graph));mappingpath=cp.regular(cp.unlinked(a.mapping))
    graph=cp.read(graphpath);mapping={k:v.upper() for k,v in cp.read(mappingpath).items()}
    if not a.basis.strip():raise ValueError('Record the present chemical/protonation basis before continuing')
    source=root/'session/stages'/cp.identifier(a.source)/'model.res'
    digest=sha(source);expected,_=hydrogen_scope(graph)
    atoms,near,_=model_context(source,require_h=bool(expected));safe_atoms(atoms)
    # Check complete bijection before writing/refining anything.
    if set(mapping)!= {x['id'] for x in graph['atoms']} or set(mapping.values()) != {x['label'].upper() for x in atoms} or len(set(mapping.values()))!=len(mapping):
        raise ValueError('Complete current graph/model mapping required')
    folder=root/cp.identifier(a.name);folder.mkdir(exist_ok=False)
    write_json(folder/'chemical_graph.json',graph)
    result=dict(status='running',source=a.source,source_sha256=digest,started_at=utc_now(),AI_calls=0,
                graph_origin=a.graph_origin,chemical_basis=a.basis,graph_sha256=sha(graphpath),mapping_input_sha256=sha(mappingpath))
    begin=time.perf_counter()
    try:
        rename=short_labels(atoms);write_json(folder/'rename.json',rename)
        selected=a.source
        if any(k!=v for k,v in rename.items()):
            selected=run_step(root,state,folder,a.source,a.name+'_labels',dict(reason='Normalize current heavy labels before native H generation; coordinates and atom identities are preserved.',rename=rename,cycles=6))
        mapping={k:rename[v] for k,v in mapping.items()};write_json(folder/'mapping.json',mapping)
        model=root/'session/stages'/selected/'model.res'
        atoms,near,_=model_context(model,require_h=bool(expected))
        h=generate(graph,mapping,atoms,near,a.basis);write_json(folder/'hydrogen_decisions.json',h)
        if h['status']!='ready_for_refinement':
            result.update(status='needs_review',findings=h['findings']);return result
        final=selected
        if expected:
            final=run_step(root,state,folder,selected,a.name+'_H',plan_from_decisions(h))
            if (root/'session/stages'/(final+'_hbonds')/'model.res').is_file():final+='_hbonds'
        built=audit(root/'session/stages'/final/'model.res',gemmi)
        actual=sum(x['element'].upper()=='H' for x in built['atoms'])
        gate=assess(root/'session/stages'/final,'model')
        result.update(selected_stage=selected,hydrogen_stage=final,finish_stage=final,
                      native_h_check=dict(expected=expected,actual=actual,unit_discrepancies=built['unit_discrepancies']),metrics=gate['metrics'])
        if expected!=actual or built['unit_discrepancies'] or not gate['execution_complete']:
            result.update(status='needs_review',reason='Native H count, UNIT or execution check failed');return result
        result.update(status='ready_for_model_review',hydrogen_handling='refined' if expected else 'none_in_complete_graph')
        return result
    finally:
        result.update(seconds=time.perf_counter()-begin,finished_at=utc_now(),source_unchanged=sha(source)==digest)
        write_json(folder/'result.json',result)
        state['hydrogen_workflow']={k:result.get(k) for k in ['status','selected_stage','hydrogen_stage','finish_stage','hydrogen_handling','graph_origin','chemical_basis']}
        state['hydrogen_workflow']['record']=str(folder/'result.json')
        state['status']='needs_scientific_review';cp.save(root,state)


def main():
    p=argparse.ArgumentParser(description=__doc__);sub=p.add_subparsers(dest='cmd',required=True)
    s=sub.add_parser('screen')
    for k in ['run','source','name']:s.add_argument('--'+k,required=True)
    s.add_argument('--mode',choices=['motifs','light','all'],default='all');s.add_argument('--max-trials',type=int,default=32);s.add_argument('--cycles',type=int,default=12)
    h=sub.add_parser('hydrogen')
    for k in ['run','source','name','graph','mapping','basis']:h.add_argument('--'+k,required=True)
    h.add_argument('--graph-origin',choices=['supplied_2d','current_run_inferred'],required=True)
    h.add_argument('--finish',action='store_true');h.add_argument('--authorize-iucr-upload',action='store_true')
    h.add_argument('--execution-mode',choices=['standard','fast'],default='standard')
    h.add_argument('--max-weight-updates',type=int,default=4);h.add_argument('--timeout',type=float,default=180)
    a=p.parse_args();root,state=cp.load_run(a.run)
    if a.cmd=='screen' and not(1<=a.max_trials<=64 and 1<=a.cycles<=30):p.error('Trial budget 1..64 and cycles 1..30 required')
    from pipeline_intake import bootstrap
    bootstrap(cp.read(root/'runtime_profile.json'))
    with cp.run_lock(root):
        state=cp.read(root/'pipeline.json')
        try:
            result=globals()[a.cmd](root,state,a)
            if a.cmd=='hydrogen' and a.finish and result['status']=='ready_for_model_review':
                args=SimpleNamespace(source=result['finish_stage'],name=a.name+'_finish',deliver=True,authorize_iucr_upload=a.authorize_iucr_upload,execution_mode=a.execution_mode,max_weight_updates=a.max_weight_updates,timeout=a.timeout,baseline_seconds=None)
                cp.autofinish(root,state,args)
            cp.render_summary(root,state)
            print(json.dumps({'status':state['status'],'operation':result['status'],'record':str(root/a.name/'result.json'),'seconds':result['seconds'],'trials':result.get('compact_trials'),'delivery':state.get('delivery'),'rule_review':state.get('rule_review')},ensure_ascii=False))
            return 0 if result['status'] in {'ready_for_model_review','needs_chemical_selection','no_candidates'} else 2
        except Exception as exc:
            state.update(status='needs_attention',last_command_error={'action':a.cmd,'error':str(exc),'at':utc_now()});cp.save(root,state)
            print(json.dumps({'status':'needs_attention','error':str(exc),
                'next_action_owner':'assistant',
                'continuation':'If this helper is outside its supported chemistry, retain the model and use model-strategy, native stage, then complete with a current-model review. Do not fabricate a graph or discard B/metal sites to fit this helper.',
                'reference':'references/adaptive-science.md'},ensure_ascii=False));return 1


if __name__=='__main__':raise SystemExit(main())
