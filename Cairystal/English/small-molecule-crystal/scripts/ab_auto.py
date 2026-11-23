"""Automatically route A/B evidence to bounded native trials, never accept an unreviewed model."""
import argparse
import copy
import hashlib
import json
import math
from pathlib import Path
import re
import shutil
import time

ROOT=Path(__file__).resolve().parent.parent
METADATA={'035','183','184','185','196','197','198','699','881'}

def load_policy(path=None):
    default=json.loads((ROOT/'assets/ab_policy.json').read_text('utf-8'))
    if path:
        changes=json.loads(Path(path).read_text('utf-8-sig'))
        allowed={'automatic_candidates','automatic_reflection_trials','allow_automatic_reflection_omission','max_hypotheses','cycles','adp_sigma','adp_terminal_sigma','oh_angles'}
        if not isinstance(changes,dict) or set(changes)-allowed:raise ValueError('Only bounded job policy overrides are accepted: '+str(sorted(allowed)))
        default.update(changes)
    if type(default['automatic_candidates']) is not bool:raise ValueError('automatic_candidates must be boolean')
    if type(default.get('automatic_reflection_trials',False)) is not bool:raise ValueError('automatic_reflection_trials must be boolean')
    if type(default['allow_automatic_reflection_omission']) is not bool:raise ValueError('allow_automatic_reflection_omission must be boolean')
    for key,lo,hi in [('max_hypotheses',1,20),('cycles',1,100)]:
        value=default[key]
        if type(value) is not int or not lo<=value<=hi:raise ValueError(key+' outside supported range')
    for key in ['adp_sigma','adp_terminal_sigma']:
        x=default[key]
        if isinstance(x,bool) or not isinstance(x,(int,float)) or not math.isfinite(x) or not .01<=x<=.2:raise ValueError('Invalid '+key)
    angles=default['oh_angles']
    if not isinstance(angles,list) or not 1<=len(angles)<=8 or any(isinstance(x,bool) or not isinstance(x,(int,float)) or not math.isfinite(x) or not -360<=x<=360 for x in angles):raise ValueError('Invalid OH candidate angles')
    return default

def generate_requests(packet,parsed,policy):
    """Diagnostic packet -> explicit hypotheses. Missing prerequisites remain unresolved."""
    from route_problem import select_routes
    routes=json.loads((ROOT/'assets/console/workflow-data.json').read_text('utf-8'))
    atoms={a['label'].upper():a for a in packet['all_atoms']}
    regions={a['label'].upper():a for a in packet['regions']}
    parents={};last=None
    for a in parsed['atoms']:
        if a['element']=='H' and a['afix'] and last:parents[a['label'].upper()]=last
        elif a['element']!='H':last=a['label'].upper()
        else:last=None
    findings=[];requests=[];seen=set()
    codes={str(a['code']) for a in packet['AB_alerts']}
    severe_global=bool(codes&{'112','113','211'}) or bool((packet.get('restraint_tension') or {}).get('needs_review'))
    def local_guard(labels):
        if severe_global:raise ValueError('Symmetry/NPD/restraint conflict must be diagnosed before local restraints')
        for key in labels:
            a=atoms[key]
            if a.get('res_context_status')!='matched':raise ValueError('Atom mapping to RES is ambiguous')
            if a.get('part')!=0 or a.get('occupancy') is None or abs(a['occupancy']-1)>.0001:raise ValueError('Partial/disordered site needs a model comparison before automatic ADP restraint')
            region=regions.get(key,{})
            if any(p['height']>.5 and .25<p['distance']<1.2 for p in region.get('nearby_reported_Q_peaks',[])):
                raise ValueError('Nearby residual density suggests unresolved model/disorder; restraint alone is not the first automatic trial')
            if any(n.get('part_compatible') is not False and n['element']!='H' and n['distance']<.9 for n in region.get('neighbors',[])):
                raise ValueError('Unusually short heavy-atom contact requires topology/disorder review')
            if any(str(x['code']) in {'241','242','411','412','413'} and key in [v.upper() for v in x.get('atom_labels',[])] for x in packet['AB_alerts']):
                raise ValueError('Possible atom-type/geometry issue takes precedence over an ADP restraint')
    for index,alert in enumerate(packet['AB_alerts']):
        code=str(alert['code']);selected=select_routes(routes,[code])
        route_ids=[r['id'] for r in selected['routes']]
        tools=list(dict.fromkeys(t for r in selected['routes'] for t in r['tools']))
        finding={'alert':alert,'category':'experimental_metadata' if code in METADATA else 'model_or_data',
                 'routes':route_ids,'tools':tools,'status':'needs_evidence','reason':None}
        labels=list(dict.fromkeys(x.upper() for x in alert.get('atom_labels',[]) if x.upper() in atoms))
        req=None
        try:
            if code in METADATA:raise ValueError('Use same-experiment metadata tools/provenance; never invent values to remove an alert')
            if code in {'213','214'}:
                if len(labels)!=1:raise ValueError('Exactly one unambiguous atom label required')
                local_guard(labels);req={'recipe':'adp_local','parameters':{'atoms':[atoms[labels[0]]['res_label']],'methods':['ISOR'],'sigma':policy['adp_sigma'],'terminal_sigma':policy['adp_terminal_sigma']}}
            elif code=='234':
                if len(labels)!=2:raise ValueError('Two explicit atom labels required')
                local_guard(labels)
                a,b=[atoms[x] for x in labels]
                if (a['part'],a['residue'])!=(b['part'],b['residue']):raise ValueError('Cross-PART/RESI pair')
                neighbors=regions.get(labels[0],{}).get('neighbors',[])
                if not any(n['label'].upper()==labels[1] and n['part_compatible'] is True and n['within_covalent_radius_screen'] and n['symmetry']=='x,y,z' and n['translation']==[0,0,0] for n in neighbors):raise ValueError('Pair is not a gathered same-part geometric bond candidate')
                req={'recipe':'adp_local','parameters':{'atoms':[a['res_label'],b['res_label']],'methods':['RIGU','SIMU'],'sigma':policy['adp_sigma'],'terminal_sigma':policy['adp_terminal_sigma']}}
            elif code in {'241','242'}:
                if len(labels)!=1 or atoms[labels[0]]['element'] not in {'C','N','O'}:raise ValueError('One uniquely identified C/N/O site required')
                a=atoms[labels[0]]
                if a['res_context_status']!='matched' or a['part']!=0 or a['occupancy'] is None or abs(a['occupancy']-1)>.0001:raise ValueError('Type versus occupancy/disorder is ambiguous')
                bonded=[n for n in regions.get(labels[0],{}).get('neighbors',[]) if n.get('within_covalent_radius_screen') and n.get('part_compatible') is True and n.get('element')!='H']
                if any(n.get('part',0)!=0 or (n.get('occupancy') is not None and abs(n['occupancy']-1)>.0001) for n in bonded):
                    raise ValueError('Bonded neighbors are disordered/partial: compare the local disorder model before changing a full-occupancy atom type from Ueq alone')
                choices=[e for e in policy['element_alternatives'] if e in parsed['sfac']]
                req={'recipe':'element_scan','parameters':{'atom':a['res_label'],'elements':choices}}
            elif code in {'919','934','939'}:
                if not policy.get('automatic_reflection_trials',False):raise ValueError('Automatic OMIT sensitivity trials disabled by job policy')
                if codes&{'112','113','211'} or (packet.get('gate',{}).get('metrics',{}).get('NPD_atoms') or 0)>0:
                    raise ValueError('Resolve symmetry or non-positive ADPs before selecting reflections')
                if any(row[0].upper()=='OMIT' and len(row)==4 for row in parsed.get('rows',[])):
                    raise ValueError('A fixed list of excluded reflections already exists; no iterative selection')
                if code=='939' and severe_global:raise ValueError('Global fit and restraint conflict requires review')
                evidence=packet.get('reflection_evidence')
                if not evidence or evidence.get('weighted_outliers') is None:raise ValueError('Verified active weighted-reflection evidence required')
                outliers=[r for r in evidence['weighted_outliers'] if r.get('status')!='x']
                if len(outliers)>20:raise ValueError('More than 20 active weighted outliers: inspect the whole dataset')
                if code=='919' and '934' in codes:raise ValueError('Covered by the complete PLAT934 list')
                if code=='919':outliers=[r for r in outliers if r.get('theta_degrees') is not None and r['theta_degrees']<3 and r['delta_over_sigmaW']<-10]
                if not 1<=len(outliers)<=20:raise ValueError('Automatic fixed-list OMIT trial is limited to 1..20 eligible reflections')
                if any(not math.isfinite(r['delta_over_sigmaW']) or abs(r['delta_over_sigmaW'])<=10 for r in outliers):
                    raise ValueError('Every active fixed-list reflection must exceed 10 sigmaW')
                printed=re.search(r'(\d+)\s+Check\b',alert.get('text',''),re.I)
                if code=='934' and printed and int(printed[1])!=len(outliers):
                    raise ValueError('PLAT934 count differs from the reconstructed weighted outlier list')
                req={'recipe':'reflection_omit','parameters':{'hkls':[r['hkl'] for r in outliers],
                    'basis':'Fixed list from the paired weighted residuals; retain all-data control. Instrumental cause is unconfirmed.'}}
            elif code=='420':
                if severe_global:raise ValueError('Resolve symmetry/NPD/restraint conflict before an automatic hydrogen orientation trial')
                from auto_water import request as water_request
                try:
                    req=water_request(packet,labels)
                except ValueError:
                    req=None
                labels=list(dict.fromkeys(parents.get(x,x) for x in labels))
                donors=[x for x in labels if x in atoms and atoms[x]['element']=='O']
                if req is None:
                    if len(donors)!=1:raise ValueError('One existing OH donor required; N-H and incomplete/ambiguous water need scientific review')
                    donor=donors[0];a=atoms[donor]
                    anchors=list(dict.fromkeys(n['label'].upper() for n in regions.get(donor,{}).get('neighbors',[]) if n['element']=='C' and n['within_covalent_radius_screen'] and n['part_compatible'] is True and n['symmetry']=='x,y,z' and n['translation']==[0,0,0]))
                    if len(anchors)!=1:raise ValueError('Neither a supported complete water orientation nor a gathered C-O-H anchor was established')
                    req={'recipe':'oh_rotate','parameters':{'parent':a['res_label'],'anchor':atoms[anchors[0]]['res_label'],'angles':policy['oh_angles']}}
            elif code=='031':
                controls=packet.get('refinement_control_evidence') or {}
                if not controls.get('extinction',{}).get('remove_trial_supported'):raise ValueError('Paired weak EXTI with positive uncertainty required; no automatic extinction removal from alert alone')
                req={'recipe':'remove_extinction','parameters':{'basis':'Paired CIF/RES EXTI agrees and its magnitude is <3.33 su. Compare removal without changing reflections; do not automatically accept.'}}
            elif code in {'936','731','732'}:
                controls=packet.get('refinement_control_evidence') or {}
                if 'release_damping' not in controls.get('proposals',[]):raise ValueError('Exactly one existing DAMP required for a release-and-convergence comparison')
                req={'recipe':'release_damping','parameters':{'basis':'Current numerical-control audit found one DAMP; recheck full-matrix convergence without damping. No forced freezing or automatic acceptance.'}}
            elif code in {'080','SHFSU01'}:
                shifts=packet.get('last_shifts',[])
                if not shifts:raise ValueError('No last-cycle shift/esd target found')
                tokens=re.findall(r'\b[A-Za-z][A-Za-z0-9]{0,3}\b',str(shifts[-1][2]).upper())
                hydrogens=[t for t in tokens if t in parents]
                if len(hydrogens)!=1:raise ValueError('Nonconvergence not uniquely attributable to an existing riding H; do not freeze heavy atoms blindly')
                parent=parents[hydrogens[0]]
                req={'recipe':'h_freeze','parameters':{'parent':atoms[parent]['res_label']}}
            elif not tools:raise ValueError('No executable route matched; preserve this alert and consult its official explanation with current-case evidence.')
            else:raise ValueError('Route located; automatic chemical parameters are not established. Use the listed tool with current evidence.')
            req.update(reason='Automatic bounded hypothesis for PLAT'+code+'; cause not assumed',
                       evidence=[{'alert':alert,'source':'current paired local validation and atom diagnostic','atom_labels':labels}],cycles=policy['cycles'])
            key=json.dumps({k:req[k] for k in ('recipe','parameters','cycles')},sort_keys=True)
            if key not in seen:seen.add(key);requests.append(req)
            finding.update(status='hypothesis_ready',reason='Executor will validate exact recipe preconditions before native execution',recipe=req['recipe'])
        except (ValueError,KeyError,TypeError) as exc:finding['reason']=str(exc)
        findings.append(finding)
    return requests,findings

def rank_rows(rows):
    """Chemical evidence first; A then B only within the same evidence tier."""
    from model_priority import assessment,rank_key
    for r in rows:
        r['eligible_for_priority']=bool(r.get('status')=='completed' and isinstance(r.get('AB'),list) and r.get('comparison_context_verified') and not r.get('flags') and r.get('source_unchanged') is True)
        alerts=r.get('AB')
        r['AB_priority']=[sum(a['level']==level for a in alerts) for level in 'AB'] if isinstance(alerts,list) and r.get('status')=='completed' else None
        r['scientific_acceptance']=False
        r['chemical_priority']=assessment(r)
        if r['chemical_priority']['status'] in {'needs_review','contradicted'}:
            r['eligible_for_priority']=False
    return sorted(rows,key=rank_key)

def review_candidate(ranked):
    """A supported chemical improvement may deserve review despite more alerts."""
    for row in ranked:
        if (row.get('status')=='completed' and row.get('source_unchanged') is True
                and row.get('comparison_context_verified')
                and row['chemical_priority']['status']=='supported'):
            return row
        if row['eligible_for_priority'] and row.get('classification')=='alert_reduced_scientific_review_required':
            return row
    return None

def sensitivity_handoff(rows,plans,trials_root):
    names={p['name'] for p in plans if p.get('reflection_omit') or (p.get('control_change') or {}).get('mode')=='resolution_window'}
    return [{'name':x['name'],'classification':x.get('classification'),'flags':x.get('flags'),'paired':str(Path(trials_root)/x['name']/'paired')} for x in rows if x.get('status')=='completed' and x['name'] in names]

def non_model_alert_route(checked,policy):
    """No atom scanning/trial plan for verified no-AB or metadata-only reports.

    Pairing, native gate and report hashes are still checked by resolve first.
    Metadata alerts remain unresolved, never converted to scientific approval.
    """
    alerts=[dict(a,atom_labels=[]) for a in checked['alerts'] if a['level'] in 'AB']
    if any(str(a['code']) not in METADATA for a in alerts):return None
    requests,findings=generate_requests({'AB_alerts':alerts,'all_atoms':[],'regions':[]},{'atoms':[]},policy)
    for finding in findings:finding['evidence_tools']=[]
    return {'status':'needs_evidence' if alerts else 'no_AB_in_verified_local_report',
        'findings':findings,'evidence_tools':[],'prepared_hypotheses':0,'native_attempts':0,
        'baseline_AB':{level:sum(a['level']==level for a in alerts) for level in 'AB'},
        'skipped_work':['atom_neighborhood_scan','unchanged_control_plan'],
        'routing_scope':'verified_metadata_only' if alerts else 'verified_no_AB',
        'scientific_acceptance':'not_established','model_adopted':False}


def resolve(directory,stem,validation,output,software,policy=None,execute=True):
    from crystal_runtime import paired_bundle,sha,new_directory,write_json
    from structure_diagnostics import analyse,structure
    from parse_platon_alerts import parse
    from repair_plan import compile_trials
    from candidate_trials import build,run_plan
    from compare_diagnostic_trials import compare
    policy=policy or load_policy();out=new_directory(output);start=time.perf_counter();result={'schema':1,'status':'running','model_adopted':False,'AI_calls':0,'official_upload':False,'findings':[]}
    write_json(out/'policy.json',policy)
    try:
        audit=paired_bundle(directory,stem);v=Path(validation)
        log=json.loads((v/'local_validation.json').read_text('utf-8'))
        if log.get('official') is not False or not log.get('input_sha256'):raise ValueError('Verified local validation provenance required')
        for ext in ['cif','fcf']:
            if log['input_sha256'].get(ext)!=sha(Path(directory)/(stem+'.'+ext)):raise ValueError('Local validation belongs to different model/reflections')
        for name,h in log.get('artifact_sha256',{}).items():
            if Path(name).name!=name or sha(v/name)!=h:raise ValueError('Local validation artifact changed')
        if stem+'.chk' not in log.get('artifact_sha256',{}):raise ValueError('Validation CHK hash missing')
        checked=parse((v/(stem+'.chk')).read_text('latin1'))
        if checked['warnings'] or not checked['report_footer_present']:raise ValueError('Incomplete/inconsistent PLATON alert report')
        lightweight=non_model_alert_route(checked,policy)
        if lightweight is not None:
            result.update(lightweight)
            write_json(out/'requests.json',[])
            write_json(out/'alert_routing.json',lightweight)
        else:
            base=out/'baseline';base.mkdir()
            for ext,source in audit['files'].items():shutil.copy2(source,base/('case.'+ext))
            shutil.copy2(v/(stem+'.chk'),base/'case.chk')
            packet=analyse(base);write_json(out/'diagnostic.json',packet)
            _,_,_,_,parsed=structure(base/'case.cif',base/'case.res')
            # A donor alert may name only H. Include its existing parent in the local
            # geometry packet; otherwise a valid OH anchor would falsely look absent.
            parent_map={};parent=None
            for atom in parsed['atoms']:
                if atom['element']=='H' and atom['afix'] and parent:parent_map[atom['label'].upper()]=parent
                elif atom['element']!='H':parent=atom['label'].upper()
                else:parent=None
            needed={parent_map[x.upper()] for a in packet['AB_alerts'] if str(a['code'])=='420' for x in a.get('atom_labels',[]) if x.upper() in parent_map}
            existing_regions={a['label'].upper() for a in packet['regions']}
            if needed-existing_regions:
                packet=analyse(base,focus=sorted(needed));write_json(out/'diagnostic.json',packet)
            from ab_evidence_tools import collect
            result['evidence_tools']=collect(base,packet['AB_alerts'],out/'evidence')
            for tool,key in [('reflection-audit','reflection_evidence'),('donor-audit','donor_evidence'),('refinement-controls','refinement_control_evidence')]:
                evidence=next((x for x in result['evidence_tools'] if x['tool']==tool and x['status']=='evidence_ready'),None)
                if evidence:packet[key]=json.loads(Path(evidence['path']).read_text('utf-8'))
            requests,findings=generate_requests(packet,parsed,policy);result['findings']=findings
            for finding in findings:
                finding['evidence_tools']=[x for x in result['evidence_tools'] if x['tool'] in finding['tools']]
            write_json(out/'requests.json',requests);result['baseline_AB']={level:sum(a['level']==level for a in packet['AB_alerts']) for level in 'AB'}
            proposals=[];preview=out/'preview';preview.mkdir()
            for i,request in enumerate(requests):
                try:
                    trials=compile_trials(base,request)[1:]
                    if len(proposals)+len(trials)>policy['max_hypotheses']:
                        result.setdefault('deferred',[]).append({'recipe':request['recipe'],'reason':'Hypothesis budget reached; no endless repeated edits'});continue
                    # Build all variants before accepting a recipe, so partial preconditions cannot leak through.
                    checked_trials=[]
                    for j,trial in enumerate(trials):
                        trial['name']=f'r{i+1:02d}_{j+1:02d}_{trial["name"]}'
                        text,edits=build(base,trial,preview)
                        (preview/(trial['name']+'.ins')).write_text(text,encoding='ascii');write_json(preview/(trial['name']+'.json'),edits)
                        checked_trials.append(trial)
                    proposals.extend(checked_trials)
                except (ValueError,KeyError,TypeError) as exc:
                    result.setdefault('deferred',[]).append({'recipe':request['recipe'],'parameters':request['parameters'],'reason':str(exc)})
            control={'name':'control','kind':'baseline','cycles':policy['cycles'],'reason':'Shared unchanged contemporaneous control for every automatic hypothesis','evidence':'Same frozen model/HKL/WGHT and setting'}
            software={k:str(Path(software[k]).absolute()) for k in ['shelxl','platon']}
            job={'baseline':str(base),'output':str(out/'trials'),'software':software,'software_sha256':{k:sha(p) for k,p in software.items()},'trials':[control]+proposals,'stop_on_control_failure':True}
            write_json(out/'native_plan.json',job);result['prepared_hypotheses']=len(proposals)
            if not packet['AB_alerts']:result['status']='no_AB_in_verified_local_report'
            elif not proposals:result['status']='needs_evidence'
            elif not execute or not policy['automatic_candidates']:result['status']='prepared_not_executed'
            else:
                # Fresh process validation before running; runtime profile has already pinned paths in the caller.
                if any(sha(p)!=job['software_sha256'][k] for k,p in software.items()):raise ValueError('Executable changed')
                trials=run_plan(out/'native_plan.json');result['native_attempts']=len(trials)
                if trials[0]['status']!='completed':
                    result['status']='control_failed';result['trial_statuses']=[{'name':x['name'],'status':x['status']} for x in trials]
                else:
                    rows=[compare(trials[0],r) for r in trials[1:]]
                    for row in rows:
                        if row.get('status')!='completed':row['AB']=None;row['AB_counts']=None
                    ranked=rank_rows(rows);write_json(out/'comparison.json',{'candidates':ranked,'model_adopted':False,'objective':policy['objective']})
                    result['comparison']=str(out/'comparison.json')
                    result['sensitivity_trials_for_review']=sensitivity_handoff(ranked,proposals,out/'trials')
                    best=review_candidate(ranked)
                    result['recommended_for_review']=None if best is None else {'name':best['name'],'AB':best['AB_priority'],'chemical_priority':best['chemical_priority'],'remaining_flags':best.get('flags',[]),'paired':str(out/'trials'/best['name']/'paired')}
                    result['status']='candidate_comparison_ready' if best else ('sensitivity_comparison_ready' if result['sensitivity_trials_for_review'] else 'no_supported_improvement')
                    if policy['allow_automatic_reflection_omission'] and result['sensitivity_trials_for_review']:
                        from working_omit import select
                        result['working_omit']=select(trials,ranked,proposals,packet,out/'trials')
                        if result['working_omit']['selected']:
                            result['status']='working_omit_selected'
        result['source_unchanged']=all(sha(p)==audit['source_sha256'][ext] for ext,p in audit['files'].items())
        if not result['source_unchanged']:raise ValueError('Original source changed')
    except Exception as exc:result.update(status='failed',error=str(exc))
    result['release']=json.loads((ROOT/'release_info.json').read_text('utf-8'))['release_id']
    result['implementation_sha256']={n:sha(ROOT/'scripts'/n) for n in ['ab_auto.py','auto_water.py','ab_evidence_tools.py','repair_plan.py','candidate_trials.py','compare_diagnostic_trials.py','model_priority.py']}
    result.update(seconds=round(time.perf_counter()-start,3),next='Review specific unresolved evidence or the recommended candidate, then refine/revalidate the chosen model before official delivery. Never declare zero AB as structure correctness.')
    write_json(out/'result.json',result);return result

def from_finish(cfg,frozen,validation,output):
    policy=load_policy(cfg.get('ab_policy'))
    return resolve(frozen,'model',validation,output,{k:cfg[k] for k in ['shelxl','platon']},policy,cfg.get('automatic_ab_trials',True))

def main():
    p=argparse.ArgumentParser(description=__doc__)
    for name in ['baseline','validation','profile','output']:p.add_argument('--'+name,required=True)
    p.add_argument('--stem',default='model');p.add_argument('--policy');p.add_argument('--plan-only',action='store_true');a=p.parse_args()
    from pipeline_intake import verify_profile
    tools=verify_profile(json.loads(Path(a.profile).read_text('utf-8-sig')))
    r=resolve(a.baseline,a.stem,a.validation,a.output,tools,load_policy(a.policy),not a.plan_only)
    print(json.dumps(r,ensure_ascii=False));return 2 if r['status']=='failed' else 0
if __name__=='__main__':raise SystemExit(main())
