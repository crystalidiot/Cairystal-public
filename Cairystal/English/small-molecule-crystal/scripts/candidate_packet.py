"""Small deterministic review packets; diagnostics are not automatic chemistry."""
import json,statistics
from pathlib import Path
from crystal_runtime import write_json

def make_packet(session,summary):
    candidates=[]
    for item in summary['candidates']:
        stage=Path(item['stage']);review=item.get('review') or json.loads((stage/'model_review.json').read_text(encoding='utf-8'))
        atoms=review['atoms'];by_label={a['label']:a for a in atoms};issues=[];centers=[]
        for a in atoms:
            if a['element'].upper() in {'H','D'}:continue
            neighbors=[n for n in a['neighbors'] if n[1].upper() not in {'H','D'}]
            ratios=[by_label[n[0]]['Ueq'] for n in neighbors if by_label[n[0]]['Ueq']>0]
            ratio=a['Ueq']/statistics.median(ratios) if ratios else None
            if ratio is not None and (ratio<.5 or ratio>2.5):issues.append({'site':a['label'],'issue':'ADP ratio to nearby sites needs interpretation','ratio':round(ratio,3),'element':a['element']})
            if a['element'].upper() in {'CL','P','S'} and len(neighbors)==4:
                centers.append({'center':a['label'],'element':a['element'],'neighbors':neighbors,'interpretation':'Four close sites; inspect chemical group and elemental assignments. Connectivity alone does not establish an oxyanion.'})
        metrics=item['metrics']
        candidates.append({'stage':stage.name,'space_group':review['space_group'],'formula_as_recorded':review['formula'],'metrics':metrics,'residual_density':review['difference_density'],'atom_sites':len(atoms),'hydrogen_sites':sum(a['element'].upper() in {'H','D'} for a in atoms),'local_adp_flags':issues,'four_neighbor_centers':centers,'full_atom_review':str(stage/'model_review.json'),'native_log':str(stage/'model.lst')})
    for source,candidate in zip(summary['candidates'],candidates):
        if 'initial_review' in source:candidate['initial_review']=source['initial_review']
    ordered=sorted(candidates,key=lambda c:float('inf') if c['metrics'].get('R1_observed') is None else c['metrics']['R1_observed'])
    return {'status':'needs_scientific_review','candidates':candidates,'numerical_rank_only':[x['stage'] for x in ordered],'automatic_selection':False,'limitation':'No atom identities, H positions, space group or chemical correctness are established by numerical ranking. Plans require a recorded reason. Full geometry remains on disk.'}

def factual_annotations(session,selection_basis):
    m=json.loads((session/'session.json').read_text(encoding='utf-8'));plans=[]
    # This explicitly generated directory contains only this job's action plans.
    for p in sorted((session/'plans').glob('*.json')):
        value=json.loads(p.read_text(encoding='utf-8'));plans.append({'file':p.name,'reason':value.get('reason'),'element_changes':value.get('element_changes',{}),'hydrogens':value.get('hydrogens',[]),'variants':value.get('variants',[])})
    events=[x['name'] for x in m['events'] if x['status']=='completed']
    pieces=['Fresh phasing in this job from the explicitly recorded original HKL/P4P. No earlier model is loaded by this workflow. Recorded Laue seed: '+m['laue_basis'],
            'Completed native stages: '+', '.join(events)+'.',
            'Reviewer selection basis (source statement): '+selection_basis]
    for p in plans:pieces.append('Recorded plan '+p['file']+': '+str(p['reason']))
    if 'absorption_log' in m['inputs']:
        import re
        log=Path(m['inputs']['absorption_log']['copy']).read_text(encoding='latin1')
        extra=re.search(r'Additional spherical absorption correction applied with mu\*r\s*=\s*([.\d]+)',log)
        transmission=re.search(r'Estimated minimum and maximum transmission:\s*([.\d]+)\s+([.\d]+)',log)
        if extra:pieces.append('Original absorption processing records an additional spherical mu*r='+extra[1]+'. Physical applicability needs review; original reflections are retained.')
        if transmission:pieces.append('Original processing transmission limits: '+transmission[1]+' to '+transmission[2]+'.')
    if m['prior_conversation_exposure']:pieces.append('Prior conversation exposure is recorded; do not call this a fully naive blind test.')
    pieces.append('Subsequent weight-only continuation is separately logged. Numerical convergence and zero A/B do not establish chemical identity.')
    return {'_publ_section_exptl_refinement':'\n\n'.join(pieces)}
