"""Turn current-model screening into evidence-linked work; never choose chemistry by R."""
from pathlib import Path
import json
import math
import shutil

NO_H_NOTE = 'No modeled hydrogen atoms; chemistry may be incomplete'

def occupancy_holds(review):
    # This note is expected before element assignment/H construction, not an occupancy defect.
    return [w for w in review.get('occupancy_warnings',[]) if w != NO_H_NOTE]

def decision_queue(review):
    queue=[]
    def add(problem, tool, atoms, evidence, automatic, next_action):
        queue.append({'id':len(queue)+1,'problem':problem,'tool':tool,'atoms':sorted(set(atoms)),
                      'evidence':evidence,'execution':'script' if automatic else 'assistant_review',
                      'next_action':next_action,'scientific_acceptance':False})
    findings=review.get('findings',[])
    broken=[f['atom'] for f in findings if f['code']=='cif_res_pairing_unresolved']
    if broken:
        add('input_pairing','initial-review',broken,{'findings':[f for f in findings if f['code']=='cif_res_pairing_unresolved']},False,
            'Resolve CIF/RES pairing before generating model changes.')
        return queue
    if occupancy_holds(review):
        add('occupancy_or_symmetry','occupancy',[],{'warnings':occupancy_holds(review)},True,
            'Run the occupancy audit on the current RES; compare physical and SHELX occupancies.')
    outside=[f for f in findings if f['code']=='element_outside_input']
    if outside:
        add('element_outside_input','initial-review',[f['atom'] for f in outside],{'findings':outside},False,
            'Resolve the supplied element list versus current scattering types; do not infer stoichiometry.')
    for site in review.get('sites',[]):
        flags=set(site.get('flags',[]));label=site['label']
        evidence={k:site.get(k) for k in ['scattering_element','relative_Ueq','occupancy','part','flags']}
        evidence['review_site']=label
        evidence['contact_count']=len(site.get('geometric_contacts',[]))
        evidence['reported_Q_peak_count']=len(site.get('nearby_reported_Q_peaks',[]))
        if flags & {'very_short_contact','too_many_close_nonmetal_contacts_review_connectivity'}:
            add('connectivity_or_overlap','geometry-audit',[label],evidence,True,
                'Inspect contacts and PART/symmetry before element changes or restraints.')
        if flags & {'elongated_ADP','non_positive_ADP'} or (flags & {'high_relative_Ueq'} and site.get('nearby_reported_Q_peaks')):
            add('disorder_or_motion','adp-directions',[label],evidence,True,
                'Inspect ADP and density directions, then use density-disorder on an established complete fragment.')
        if flags & {'low_relative_Ueq','high_relative_Ueq'}:
            add('element_assignment','initial-review',[label],evidence,True,
                'Prepare bounded element contrasts; H, constraints and occupancy conflicts are deferred explicitly.')
        if 'isolated_site_check_symmetry_coordination_or_solvent' in flags:
            add('isolated_site_identity','occupancy',[label],evidence,False,
                'Check symmetry/coordination and solvent identity; isolation alone does not establish water.')
    if not queue:
        add('chemical_review','initial-review',[],{'screen_status':review.get('status')},False,
            'Screening found no routed issue. Check connectivity, composition and protonation; do not invent a graph.')
    directory=review.get('source_directory');stem=review.get('stem','model')
    if directory:
        for item in queue:
            if item['tool']=='occupancy':item['argv']=[str(Path(directory)/(stem+'.res'))]
            elif item['tool'] in {'adp-directions','geometry-audit'}:
                item['argv']=['--directory',directory,'--stem',stem,'--output','NEW_DIAGNOSTIC.json']
                if item['tool']=='adp-directions':item['argv']+=['--atoms',*item['atoms']]
            elif item['problem']=='element_assignment':
                item['argv']=['--directory',directory,'--stem',stem,'--elements',*review['allowed_elements'],
                    '--output','NEW_REVIEW.json','--trial-output','NEW_TRIAL_DIRECTORY','--profile','LOCAL_PROFILE.json','--run-trials']
    return queue

def element_options(review, parsed, max_sites=2, max_trials=4):
    """One-site C/N/O contrasts only; all other coordinates/data/weights stay paired."""
    if not 1<=max_sites<=4 or not 1<=max_trials<=8:
        raise ValueError('Bounded max_sites 1..4 and max_trials 1..8 required')
    trials=[];deferred=[];sites=0
    atoms={a['label'].upper():a for a in parsed['atoms']}
    duplicate=len(atoms)!=len(parsed['atoms'])
    # Existing H parentage is conservatively held; changing a parent can change protonation.
    has_h=any(a['element'].upper()=='H' for a in parsed['atoms'])
    global_holds=[]
    if duplicate:global_holds.append('duplicate_atom_labels')
    if occupancy_holds(review):global_holds.append('occupancy_audit_unresolved')
    if any(f['code']=='cif_res_pairing_unresolved' for f in review.get('findings',[])):
        global_holds.append('pairing_unresolved')
    for site in review.get('sites',[]):
        flags=set(site.get('flags',[]))
        if not flags & {'low_relative_Ueq','high_relative_Ueq'}:continue
        label=site['label'];atom=atoms.get(label.upper());holds=list(global_holds)
        if atom is None:holds.append('missing_RES_atom')
        else:
            if atom.get('part')!=0 or atom.get('residue')!='0' or atom.get('encoded_sof')!=11 or site.get('occupancy')!=1:
                holds.append('partial_or_special_or_existing_disorder')
            if atom.get('afix')!=0:holds.append('AFIX_target')
        if has_h:holds.append('existing_H_requires_parent_and_protonation_review')
        if flags & {'very_short_contact','too_many_close_nonmetal_contacts_review_connectivity','non_positive_ADP'}:
            holds.append('connectivity_or_ADP_must_be_resolved_first')
        if any(r[0].upper() in {'EXYZ','EADP'} and label.upper() in [s.upper() for s in r[1:]] for r in parsed['rows']):
            holds.append('constrained_target')
        candidates=[e for e in review['allowed_elements'] if e in {'C','N','O'} and e!=site['scattering_element'] and e.upper() in [s.upper() for s in parsed['sfac']]]
        if not candidates:holds.append('no_alternative_in_allowed_SFAC')
        if sites>=max_sites:holds.append('site_budget')
        if holds:
            deferred.append({'atom':label,'reasons':holds});continue
        sites+=1
        for element in candidates:
            if len(trials)>=max_trials:
                deferred.append({'atom':label,'element':element,'reasons':['trial_budget']});continue
            trials.append({'name':f'type_{len(trials)+1}_{element}','kind':'diagnostic_refinement','cycles':20,
                'reason':'Current-model relative U contrast; alternative identity remains a hypothesis',
                'evidence':{'atom':label,'flags':sorted(flags),'relative_Ueq':site.get('relative_Ueq'),'source_hashes':review.get('source_hashes')},
                'element_changes':{label:element},'focus':[label]})
    return trials,deferred

def prepare_element_trials(directory, stem, review, output, profile, max_sites=2, max_trials=4):
    from crystal_runtime import paired_bundle, write_json
    from structure_diagnostics import res_records, digest
    from candidate_trials import build
    from pipeline_intake import unlinked
    base=unlinked(directory);out=unlinked(output)
    if out.exists():raise FileExistsError(str(out))
    # A fresh review is calculated by the caller; binding is checked again before copying.
    for ext in ['res','cif']:
        if review.get('source_hashes',{}).get(stem+'.'+ext) != digest(base/(stem+'.'+ext)):
            raise ValueError('Review/model hash mismatch: '+ext)
    audit=paired_bundle(base,stem);parsed=res_records(base/(stem+'.res'))
    trials,deferred=element_options(review,parsed,max_sites,max_trials)
    out.mkdir(parents=True);frozen=out/'baseline';frozen.mkdir()
    for ext,p in audit['files'].items():shutil.copy2(p,frozen/('case.'+ext))
    plans=[{'name':'control','kind':'baseline','cycles':20,'reason':'Unmodified same-cycle control','evidence':'Same HKL and starting weight controls'}]
    for trial in trials:
        work=out/'prepared'/trial['name'];work.mkdir(parents=True)
        try:
            text,edits=build(frozen,trial,work)
        except (ValueError,KeyError,TypeError) as exc:
            deferred.append({'atom':trial['focus'][0],'reasons':['editor_requires_review'],'detail':str(exc)});continue
        (work/'case.ins').write_text(text,encoding='ascii');write_json(work/'edits.json',edits);plans.append(trial)
    profile=json.loads(Path(profile).read_text('utf-8-sig'))
    plan={'baseline':str(frozen),'output':str(out/'trials'),
          'software':{k:profile['tools'][k]['path'] for k in ['shelxl','platon']},
          'trials':plans,'stop_on_control_failure':True}
    write_json(out/'plan.json',plan)
    result={'status':'prepared' if len(plans)>1 else 'needs_review','plan':str(out/'plan.json'),
            'trial_count':len(plans)-1,'deferred':deferred,'scientific_acceptance':False,
            'next_tool':'trials' if len(plans)>1 else None,'source_hashes':review['source_hashes']}
    write_json(out/'preparation.json',result);return result
