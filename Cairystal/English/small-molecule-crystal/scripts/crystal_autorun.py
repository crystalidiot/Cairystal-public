"""Checkpointed, exception-only dispatcher for the existing bounded pipeline.

Runs start -> graph/H match -> autofinish without model API calls. Never chooses
between multiple space groups by R, repeats a failed stage, or replays an uncertain upload.
"""
import argparse
import contextlib
import html
import json
import os
from pathlib import Path
import subprocess
import sys
import time

from crystal_runtime import new_directory, regular, sha, utc_now, write_json, flags
from pipeline_intake import unlinked
from crystal_pipeline import identifier, stamp


def read(path): return json.loads(regular(unlinked(path)).read_text(encoding='utf-8-sig'))


def seal(folder):
    """Only this run; links are rejected before traversal/read."""
    result={}
    def visit(p):
        for q in sorted(p.iterdir()):
            unlinked(q)
            if q.is_dir():visit(q)
            elif q.is_file():result[q.relative_to(folder).as_posix()]=sha(q)
    if folder.exists():visit(folder)
    return result


@contextlib.contextmanager
def lock(root):
    p=root/'autorun.lock'
    try:
        with p.open('x',encoding='utf-8') as f:json.dump({'pid':os.getpid(),'created_at':utc_now()},f)
    except FileExistsError:raise ValueError('Active/interrupted coordinator lock exists; inspect process and retained pending action before explicit recovery')
    digest=sha(p)
    try:yield
    finally:
        if p.exists() and sha(p)==digest:p.unlink()


def save(root,state):write_json(root/'autorun.json',state)


class WrongSpecimen(ValueError):
    pass


def specimen_identity(root,state):
    binding=state.get('intake_hkl') or state.get('source_hkl')
    if not binding and (root/'pipeline/pipeline.json').is_file():
        binding=read(root/'pipeline/pipeline.json').get('intake',{}).get('inputs',{}).get('hkl')
    cfg=state.get('options',{})
    return {'case_id':cfg.get('case_id') or Path(cfg.get('data_dir') or root).name,
            'run':str(root.absolute()), 'hkl_sha256':binding['sha256'] if binding else None}


def check_expected(root,state,expected):
    actual=specimen_identity(root,state)['hkl_sha256']
    if not actual or sha(regular(unlinked(expected)))!=actual:
        raise WrongSpecimen('Selected checkpoint does not confirm the expected specimen HKL. Check the run path.')


def selected_raw_hkl(directory,stem=None):
    """Bind specimen identity without requiring a particular vendor's cell file.

    Only immediate filenames and the selected HKL are read. This does not
    infer cell/space group or certify readiness of a raw-data solve helper.
    """
    folder=unlinked(directory)
    if stem and (Path(stem).name!=stem or '/' in stem or '\\' in stem):
        raise ValueError('Stem must be a basename')
    candidates=[p for p in folder.iterdir() if p.is_file() and p.suffix.lower()=='.hkl'
                and (not stem or p.stem.lower()==stem.lower())]
    return regular(unlinked(candidates[0])) if len(candidates)==1 else None


def capture(root,state,source,role):
    source=regular(unlinked(source))
    if role=='graph':
        from local_assist import verify_reviewed_graph
        verify_reviewed_graph(source)
    target=root/'inputs'/(role+source.suffix.lower())
    if target.exists():raise ValueError('Input role already frozen: '+role)
    target.write_bytes(source.read_bytes())
    item={'source':str(source),'copy':str(target),'sha256':sha(source)}
    if sha(target)!=item['sha256']:raise ValueError('Input changed during snapshot')
    state['bindings'][role]=item;return str(target)


def create(config,output,execution_mode=None):
    config=regular(unlinked(config));cfg=read(config)
    if execution_mode is not None:cfg['execution_mode']=execution_mode
    allowed={'schema','case_id','data_dir','profile','elements','stem','specimen','graph','donor_basis','deliver','authorize_iucr_upload','prior_conversation_exposure','max_candidates','max_weight_updates','timeout','intake_state','ab_policy','solver_fallback','execution_mode'}
    from execution_mode import options
    cfg=options(cfg)
    if set(cfg)-allowed:raise ValueError('Unknown config keys: '+str(sorted(set(cfg)-allowed)))
    if 'case_id' in cfg and (not isinstance(cfg['case_id'],str) or not cfg['case_id'].strip() or len(cfg['case_id'])>160):
        raise ValueError('case_id must be a nonempty specimen label of at most 160 characters')
    if cfg.get('schema',1)!=1:raise ValueError('Unsupported config schema')
    if not all(k in cfg for k in ['data_dir','profile','elements']):raise ValueError('data_dir, profile and elements are required')
    if not isinstance(cfg['elements'],list) or not cfg['elements']:raise ValueError('Explicit element list is required')
    if cfg.get('donor_basis') is not None and not isinstance(cfg['donor_basis'],str):
        raise ValueError('The H/protonation basis must be text')
    for k in ['deliver','authorize_iucr_upload','prior_conversation_exposure']:
        if k in cfg and not isinstance(cfg[k],bool):raise ValueError(k+' must be a boolean')
    for k,default,lo,hi in [('max_candidates',6,1,6),('max_weight_updates',4,0,6)]:
        value=cfg.get(k,default)
        if isinstance(value,bool) or not isinstance(value,int) or not lo<=value<=hi:raise ValueError(k+' out of bounded range')
        cfg[k]=value
    timeout=cfg.get('timeout',180)
    if isinstance(timeout,bool) or not isinstance(timeout,(int,float)) or not 1<=timeout<=3600:raise ValueError('timeout must be 1..3600 seconds per supported native/network operation')
    cfg['timeout']=timeout
    for k in ['data_dir','profile','specimen','graph','intake_state','ab_policy','solver_fallback']:
        if cfg.get(k):
            p=Path(cfg[k]);cfg[k]=str(unlinked(p if p.is_absolute() else config.parent/p))
    if cfg.get('ab_policy'):
        from ab_auto import load_policy
        load_policy(cfg['ab_policy'])
    receipts = []
    if cfg.get('intake_state'):
        intake=read(cfg['intake_state']);data=intake.get('data',{})
        if intake.get('questionnaire_completed') is not True:raise ValueError('Intake questionnaire record is incomplete')
        if unlinked(data.get('data_dir',''))!=Path(cfg['data_dir']) or data.get('elements')!=cfg['elements']:
            raise ValueError('Saved intake belongs to a different input directory or element scope')
        if data.get('metadata_ledger'):receipts.append(data['metadata_ledger'])
    if cfg.get('specimen'):
        receipt=read(cfg['specimen']).get('metadata_ledger')
        if receipt and receipt not in receipts:receipts.append(receipt)
    reflection_binding=None
    for receipt in receipts:
        from intake_metadata import read_ledger
        target=Path(cfg['data_dir'])/(cfg['stem']+'.hkl') if cfg.get('stem') else receipt.get('hkl')
        metadata=read_ledger(receipt['path'],cfg['data_dir'],target)
        if metadata['sha256']!=receipt['sha256'] or receipt.get('hkl_sha256',metadata['hkl_sha256'])!=metadata['hkl_sha256']:
            raise ValueError('Paired metadata changed since specimen intake')
        cfg['stem']=Path(metadata['hkl']).stem
        reflection_binding={'path':metadata['hkl'],'sha256':metadata['hkl_sha256']}
    if cfg.get('intake_state'):
        choice = intake['data'].get('iucr_upload')
        if choice == 'deny':
            if cfg.get('authorize_iucr_upload'):
                raise ValueError('Upload setting conflicts with the recorded choice for this specimen')
            cfg['deliver'] = False
        elif (choice == 'allow' and reflection_binding and data.get('metadata_ledger')
              and 'authorize_iucr_upload' not in cfg):
            # Reuse the submitted answer, bound to this HKL, when importing an intake.
            submitted = unlinked(Path(cfg['intake_state']).with_name('submitted_intake.json'))
            if submitted.is_file() and sha(submitted) == intake.get('source_sha256'):
                raw = read(submitted)
                if raw.get('iucr_upload') == 'allow' and raw.get('metadata_ledger') == data['metadata_ledger']:
                    cfg['authorize_iucr_upload'] = True
    if cfg.get('graph'):
        from local_assist import verify_reviewed_graph
        verify_reviewed_graph(cfg['graph'])
    root=unlinked(output)
    if root==Path(cfg['data_dir']) or Path(cfg['data_dir']) in root.parents:raise ValueError('Output must be outside the original input directory')
    root=new_directory(root);(root/'inputs').mkdir();(root/'logs').mkdir()
    state={'schema':1,'created_at':utc_now(),'status':'ready','actions':[],'completed_actions':[],
           'bindings':{},'pipeline_seal':{},'skill_sha256':stamp(),'ai_calls':0,'interventions':[],
           'scientific_correctness':'not_established_by_automation'}
    capture(root,state,config,'config')
    if reflection_binding:state['intake_hkl']=reflection_binding
    else:
        from pipeline_intake import discover
        try:
            paths,_=discover(cfg['data_dir'],cfg.get('stem'))
        except (OSError,ValueError) as exc:
            paths={}
            hkl=selected_raw_hkl(cfg['data_dir'],cfg.get('stem'))
            if hkl:paths['hkl']=hkl
            state['raw_helper_note']={'message':str(exc),'meaning':'This vendor-specific raw helper is unavailable; a reviewed same-HKL native candidate can still continue. No cell or experimental fields were invented.'}
        if 'hkl' in paths:
            state['source_hkl']={'path':str(paths['hkl']),'sha256':sha(paths['hkl'])}
    for role in ['profile','specimen','graph','intake_state','ab_policy','solver_fallback']:
        if cfg.get(role):cfg[role]=capture(root,state,cfg[role],role)
    cfg.setdefault('deliver',True);cfg.setdefault('authorize_iucr_upload',False);cfg.setdefault('prior_conversation_exposure',False)
    state['options']=cfg;save(root,state);return root,state


def verify(root,state,check_pipeline=True,check_version=True):
    if check_version and state['skill_sha256']!=stamp():raise ValueError('Skill code changed; start a new fixed-version run')
    for role,item in state['bindings'].items():
        for kind in ['source','copy']:
            if sha(regular(unlinked(item[kind])))!=item['sha256']:raise ValueError('Frozen input changed: '+role+' / '+kind)
    if 'graph' in state['bindings']:
        from local_assist import verify_reviewed_graph
        verify_reviewed_graph(state['bindings']['graph']['source'])
    if check_pipeline and state.get('pipeline_seal') and seal(root/'pipeline')!=state['pipeline_seal']:
        raise ValueError('Checkpoint files changed; do not silently adopt outside model edits')
    p=root/'pipeline/pipeline.json'
    target=state.get('intake_hkl') or state.get('source_hkl')
    if target and not p.exists() and sha(regular(unlinked(target['path'])))!=target['sha256']:
        raise ValueError('Paired HKL changed after questionnaire acceptance')
    if p.exists():
        ps=read(p)
        current=ps.get('intake',{}).get('inputs',{}).get('hkl')
        if target and current and (Path(current['path'])!=Path(target['path']) or current['sha256']!=target['sha256']):
            raise ValueError('Pipeline HKL differs from the questionnaire binding')
        for item in ps.get('intake',{}).get('inputs',{}).values():
            if sha(regular(unlinked(item['path'])))!=item['sha256']:raise ValueError('Original diffraction/metadata input changed')


def first_model_handoff(root,candidates):
    """Point directly to each current candidate and its already computed review."""
    entries=[]
    for candidate in candidates:
        stage=identifier(candidate['stage'])
        folder=unlinked(root/'pipeline/session/stages'/stage)
        entry={'stage':stage,'space_group':candidate.get('space_group'),'metrics':candidate.get('metrics'),
               'model':str(folder/'model.res') if (folder/'model.res').is_file() else None}
        review=candidate.get('initial_review') or {}
        path=unlinked(folder/'initial_review.json')
        if not path.is_file() or not review.get('sha256') or sha(path)!=review['sha256']:
            entry['status']='missing_or_unverified_review'
        else:
            data=read(path)
            findings=data.get('findings',[])
            entry.update(status=data['status'],review=str(path),finding_count=len(findings),
                         first_findings=findings[:3],review_sha256=review['sha256'],
                         decision_queue=data.get('decision_queue',[]),model_strategy=data.get('model_strategy'))
        entries.append(entry)
    return entries


def stop(root,state,category,reason,ps=None):
    state.update(status='needs_attention',category=category,reason=reason,stopped_at=utc_now())
    ps=ps or {}
    packet={'schema':1,'specimen':specimen_identity(root,state),'status':'needs_attention','category':category,'reason':reason,
            'pipeline_status':ps.get('status'),'graph_matching':ps.get('graph_matching'),
            'rule_review':ps.get('rule_review'),'automatic_report_qa':ps.get('automatic_report_qa'),
            'AB_alerts':ps.get('AB_alerts'),'automatic_AB':ps.get('automatic_AB'),'pipeline_failure':ps.get('failure') or ps.get('last_command_error'),
            'last_action':state['actions'][-1] if state['actions'] else None,
            'native_branch':state.get('native_branch'),'native_completion':state.get('native_completion'),
            'evidence':{'coordinator':str(root/'autorun.json'),'pipeline':str(root/'pipeline/pipeline.json'),
                        'decision_packet':str(root/'pipeline/decision_packet.json') if (root/'pipeline/decision_packet.json').is_file() else None},
            'boundary':'Preserve current data, provenance and reported uncertainty. A script applicability limit is not a structural failure: use native candidate comparisons when templates do not apply. Never invent measurements or imply unsupported chemical certainty.'}
    if category in {'chemical_graph_required','scientific_decision','initial_model_review_unavailable'} and ps.get('candidates') and not ps.get('finish'):
        try:
            packet['first_models']=first_model_handoff(root,ps['candidates'])
        except (ValueError,KeyError,OSError) as exc:
            packet['first_model_error']=str(exc)
    if category in {'scientific_decision','report_review'}:
        try:
            from handoff_diagnostics import collect
            packet['atom_diagnostics']=collect(root,ps)
        except Exception as exc:
            packet['atom_diagnostics']={'status':'unavailable','error':str(exc),'model_modified':False}
    index=os.environ.get('CAIRYSTAL_KNOWLEDGE_INDEX')
    if index:
        try:
            from local_knowledge import search
            query=(str(packet.get('AB_alerts') or '')+' '+reason+' '+str(packet.get('pipeline_failure') or ''))[:1500]
            guidance=search(index,query,top=3,max_chars=4800)
            write_json(root/'local_knowledge.json',guidance)
            packet['local_knowledge']={'path':str(root/'local_knowledge.json'),'hits':len(guidance['hits']),'AI_calls':0}
        except Exception as exc:packet['knowledge_error']=str(exc)
    upload_choice = None
    if category != 'integrity_error' and state.get('options',{}).get('intake_state'):
        intake=read(state['options']['intake_state'])
        upload_choice = intake.get('data',{}).get('iucr_upload')
        packet['intake_context']={'path':state['options']['intake_state'],'asked_once_fields':intake.get('asked_once_fields',[]),'unknown_fields':intake.get('unknown_fields',[]),'followup_policy':intake.get('followup_policy'),'squeeze_preference':intake.get('data',{}).get('squeeze'),'purpose':intake.get('data',{}).get('purpose')}
    if category=='scientific_decision':
        packet['solvent_branch_guidance']={'script':'squeeze_request.py','when':'Only after current-run review establishes a reliable host and separate challenging solvent; not inferred from AB counts alone.','actions':['prepare a model-specific request, reusing current-specimen intake','record a real customer choice once','execute the preserved comparison after consent'],'reference':'references/squeeze-workflow.md','automatic_scientific_approval':False}
    from customer_status import next_step
    state['next_step'] = packet['next_step'] = next_step(category, upload_choice)
    from model_strategy import handoff_routes
    native_routes=handoff_routes(root,category,packet.get('first_models'))
    if native_routes:
        for candidate in native_routes['candidates']:
            args=candidate['finish']['arguments']
            args[args.index('--profile')+1]=str(state.get('options',{}).get('profile','CURRENT_PROFILE.json'))
            candidate['finish'].pop('profile_lookup',None)
        packet['native_continuation']=native_routes
    from workflow_observability import record_wait
    packet['wait_episode']=record_wait(state,packet)
    from support_report import try_record
    state['support_report']=try_record(root,category,reason,state['actions'][-1]['action'] if state['actions'] else 'autorun')
    packet['support_report']=state['support_report']
    write_json(root/'handoff.json',packet);save(root,state);return state


def default_runner(command,log):
    env=os.environ.copy();env.update(PYTHONUTF8='1',PYTHONDONTWRITEBYTECODE='1')
    with log.open('x',encoding='utf-8') as f:
        p=subprocess.run(command,stdout=f,stderr=subprocess.STDOUT,env=env,creationflags=flags(),shell=False)
    return p.returncode


def arguments(root,state,action,source=None):
    cfg=state['options'];python=read(cfg['profile'])['python']
    cmd=[python,'-B',str(Path(__file__).with_name('crystal_pipeline.py'))]
    if action=='solve':
        cmd+=['start','--profile',cfg['profile'],'--data-dir',cfg['data_dir'],'--elements',*cfg['elements'],'--output',str(root/'pipeline')]
        for k in ['stem','specimen','solver_fallback']:
            if cfg.get(k):cmd+=['--'+k.replace('_','-'),cfg[k]]
        if cfg['prior_conversation_exposure']:cmd+=['--prior-conversation-exposure']
    elif action=='match':
        cmd+=['match','--run',str(root/'pipeline'),'--source',source,'--graph',cfg['graph'],'--name','auto_graph','--max-candidates',str(cfg['max_candidates']),'--add-hydrogens']
        if cfg.get('donor_basis'):cmd+=['--donor-basis',cfg['donor_basis']]
    elif action=='finish':
        cmd+=['autofinish','--run',str(root/'pipeline'),'--source',source,'--name','auto_finish','--max-weight-updates',str(cfg['max_weight_updates']),'--timeout',str(cfg['timeout'])]
        if cfg.get('execution_mode')=='fast':cmd+=['--execution-mode','fast']
        if cfg.get('ab_policy'):cmd+=['--ab-policy',cfg['ab_policy']]
        if not cfg['deliver']:cmd+=['--local-only']
        if cfg['deliver'] and cfg['authorize_iucr_upload']:
            cmd+=['--deliver']
            if cfg['authorize_iucr_upload']:cmd+=['--authorize-iucr-upload']
    elif action=='deliver':
        cmd+=['deliver','--run',str(root/'pipeline'),'--authorize-iucr-upload']
    elif action=='review':
        cmd+=['finalize','--run',str(root/'pipeline'),'--reviewed-zh','--reviewed-en','--reviewed-official','--review-note',source]
    else:raise ValueError('Unknown dispatcher action')
    return cmd


def execute(root,state,action,runner,source=None):
    if action in [a['action'] for a in state['actions']]:raise ValueError('Action already attempted; preserve it instead of retrying under the same name')
    cmd=arguments(root,state,action,source);log=root/'logs'/(action+'.log')
    from workflow_observability import close_wait
    close_wait(state,action)
    event={'action':action,'command':cmd,'log':str(log),'started_at':utc_now(),'status':'running'}
    state['actions'].append(event);state.update(status='running',pending=action);save(root,state)
    print(json.dumps({'event':'stage_started','stage':action,'log':str(log)},ensure_ascii=False),flush=True)
    started=time.perf_counter()
    try:rc=runner(cmd,log)
    except Exception as exc:
        event.update(error=str(exc),status='uncertain',seconds=round(time.perf_counter()-started,4));save(root,state)
        return stop(root,state,'interrupted_action','The action outcome is uncertain; it will not be replayed automatically.')
    event.update(returncode=rc,seconds=round(time.perf_counter()-started,4),finished_at=utc_now(),status='returned')
    state.pop('pending',None)
    state['pipeline_seal']=seal(root/'pipeline');save(root,state)
    p=root/'pipeline/pipeline.json';ps=read(p) if p.exists() else {}
    if rc or not ps or ps.get('status') in {'blocked','failed','running','starting'}:
        return stop(root,state,'execution_error','Pipeline action did not reach a usable checkpoint. No automatic retry.',ps)
    event['status']='checkpointed';state['completed_actions'].append(action);save(root,state)
    return None


def drive(root,state,runner=default_runner):
    if state.get('pending'):return stop(root,state,'interrupted_action','A previously started action has no recorded completion; do not replay it.')
    from coordinator_completion import reconcile
    try:
        if reconcile(root,state):return state
    except Exception as exc:return stop(root,state,'delivery_integrity_error',str(exc))
    try:verify(root,state)
    except Exception as exc:return stop(root,state,'integrity_error',str(exc))
    if state.get('native_branch'):
        from native_continuation import refresh_native
        return refresh_native(root,state,runner,allow_delivery=True)
    if state['status'] in {'complete','local_ready'}:return state
    if any(a['status']!='checkpointed' for a in state['actions']):
        return stop(root,state,'execution_error','An earlier attempted action requires inspection; automatic repetition is disabled.')
    if 'solve' not in state['completed_actions']:
        result=execute(root,state,'solve',runner)
        if result:return result
    ps=read(root/'pipeline/pipeline.json');cfg=state['options']
    if ps.get('solver_handoff') and not ps.get('candidates'):
        state['solver_handoff']=ps['solver_handoff'];save(root,state)
        return stop(root,state,'solver_fallback_review','Automatic fallback completed or identified missing inputs; inspect solver_handoff and raw candidate paths before chemical assignment/refinement.',ps)
    if 'match' not in state['completed_actions']:
        candidates=ps.get('candidates') or []
        source=cfg.get('selected_source')
        if not source:
            if len(candidates)!=1:return stop(root,state,'scientific_decision','Candidate space groups/models need an evidence-based choice; R ranking is not selection.',ps)
            source=identifier(candidates[0]['stage'])
        elif source not in {c['stage'] for c in candidates}:
            return stop(root,state,'scientific_decision','Selected source is not in this run candidate list.',ps)
        selected=next(c for c in candidates if c['stage']==source)
        if selected.get('initial_review',{}).get('status')=='review_unavailable':
            return stop(root,state,'initial_model_review_unavailable','Post-solution screening failed; inspect the recorded diagnostic rather than treating it as checked.',ps)
        if not cfg.get('graph'):return stop(root,state,'chemical_graph_required','No complete graph supplied. Continue current-model chemistry review; choose graph-based tools when applicable or the native stage/complete route for clusters, coordination, disorder or unknown chemistry. Do not ask the user to invent a graph.',ps)
        if not isinstance(cfg.get('donor_basis'),str) or not cfg['donor_basis'].strip():
            from hydrogen_plan import hydrogen_scope
            try:
                _,donors=hydrogen_scope(read(cfg['graph']))
            except (ValueError,TypeError,KeyError) as exc:
                return stop(root,state,'scientific_decision','Review the supplied graph and H treatment: '+str(exc),ps)
            if donors:
                return stop(root,state,'chemical_graph_required','N-H/O-H protonation basis needed for graph sites: '+', '.join(map(str,donors)),ps)
        result=execute(root,state,'match',runner,source)
        if result:return result
        ps=read(root/'pipeline/pipeline.json')
    graph=ps.get('graph_matching',{})
    finish_source=graph.get('finish_stage') or graph.get('hydrogen_stage')
    if graph.get('status')!='ready_for_model_review' or not finish_source:
        return stop(root,state,'scientific_decision','Graph matching/H construction is ambiguous, incomplete or unsupported.',ps)
    if 'finish' not in state['completed_actions']:
        result=execute(root,state,'finish',runner,identifier(finish_source))
        if result:return result
        ps=read(root/'pipeline/pipeline.json')
    if ps.get('fast_preview'):state['fast_preview']=ps['fast_preview'];save(root,state)
    if cfg['deliver'] and ps.get('status') in {'ready_for_official_delivery','official_upload_not_authorized'}:
        if not cfg['authorize_iucr_upload']:
            return stop(root,state,'upload_authorization_required','Local refinement, weights and AB checks are complete; official upload awaits authorization. Resume reuses this checkpoint.',ps)
        result=execute(root,state,'deliver',runner)
        if result:return result
        ps=read(root/'pipeline/pipeline.json')
    if ps.get('fast_preview'):state['fast_preview']=ps['fast_preview'];save(root,state)
    if cfg['deliver'] and ps.get('status')=='complete':
        try:reconcile(root,state)
        except Exception as exc:return stop(root,state,'delivery_integrity_error',str(exc))
    elif not cfg['deliver'] and ps.get('status')=='ready_for_official_delivery':
        for key in ['category','stopped_at']:state.pop(key,None)
        state.update(status='local_ready',finished_at=utc_now(),reason='Local preparation finished; official checkCIF and Word delivery were not requested.')
    else:
        if ps.get('delivery'):state.update(delivery=ps['delivery'],official_counts=ps.get('official_counts'))
        category='report_review' if ps.get('status') in {'awaiting_visual_review','needs_report_review'} else 'scientific_decision'
        return stop(root,state,category,'Automatic scientific/alert/weight/report checks need review.',ps)
    state.pop('next_step', None)
    from workflow_observability import close_wait
    close_wait(state,state['status'])
    save(root,state);return state


def amend(root,state,graph=None,donor_basis=None,source=None,basis=None,authorize=False):
    verify(root,state)
    if state.get('pending') or state['status'] in {'complete','local_ready'}:raise ValueError('Cannot amend a running/finished coordinator')
    cfg=state['options'];record={'at':utc_now(),'changes':{}}
    # Validate the whole amendment before changing a snapshot or state.
    if any([graph,donor_basis is not None,source]) and 'match' in [a['action'] for a in state['actions']]:
        raise ValueError('Chemical inputs/source cannot change after matching began; use a new run')
    if graph:
        if cfg.get('graph'):raise ValueError('Graph already frozen; use a new run')
        regular(unlinked(graph))
    if donor_basis is not None and (not isinstance(donor_basis,str) or not donor_basis.strip()):raise ValueError('H/protonation basis cannot be empty')
    if source:
        identifier(source)
        if not basis or not basis.strip():raise ValueError('Candidate choice requires evidence basis')
        ps=read(root/'pipeline/pipeline.json')
        if source not in {c['stage'] for c in ps.get('candidates',[])}:raise ValueError('Source is not a current-run candidate')
    if graph:
        if 'match' in [a['action'] for a in state['actions']]:raise ValueError('Cannot replace a graph after matching began; use a new run')
        if cfg.get('graph'):raise ValueError('Graph already frozen; use a new run for a different chemical prior')
        cfg['graph']=capture(root,state,graph,'graph');record['changes']['graph']=cfg['graph']
    if donor_basis is not None:
        if 'match' in [a['action'] for a in state['actions']]:raise ValueError('Cannot change protonation basis after matching began')
        cfg['donor_basis']=donor_basis;record['changes']['donor_basis']=donor_basis
    if source:
        if 'match' in [a['action'] for a in state['actions']]:raise ValueError('Source already used')
        if not basis or not basis.strip():raise ValueError('Candidate choice requires evidence basis')
        cfg['selected_source']=identifier(source);record['changes'].update(source=source,basis=basis)
    if authorize:
        cfg['authorize_iucr_upload']=True;record['changes']['authorize_iucr_upload']=True
    if record['changes']:state['interventions'].append(record);save(root,state)

def review_reports(root,state,args,runner=default_runner):
    if not (args.reviewed_zh and args.reviewed_en and args.reviewed_official and args.review_note.strip()):
        raise ValueError('Record the actual review of both Word reports and the official PDF, with a note.')
    verify(root,state)
    if state.get('pending') or state.get('category')!='report_review':
        raise ValueError('No report-review checkpoint is awaiting sign-off')
    result=execute(root,state,'review',runner,args.review_note.strip())
    return result if result else drive(root,state,runner)


def local_report_at_checkpoint(root,state):
    """Summarize the local validation paired to the CIF/FCF in the recorded checkpoint."""
    if state.get('native_branch'):
        from native_continuation import local_report
        return local_report(root,state)
    frozen=state.get('pipeline_seal') or {}
    if not any(k.endswith('/local_validation/local_validation.json') for k in frozen):
        return None
    pipeline=root/'pipeline'
    try:
        finish=unlinked(read(pipeline/'pipeline.json')['finish_root'])
        rel=finish.relative_to(pipeline.absolute())
        saved=finish/'state.json'
        if saved.is_file():
            if sha(saved)!=frozen.get((rel/'state.json').as_posix()):
                raise ValueError('Finish selection differs from checkpoint')
            selected=read(saved)
            model=unlinked(selected.get('selected') or finish/'frozen')
            model_rel=model.relative_to(finish)
            if selected.get('selected_omit') and model_rel!=Path('working_omit/frozen'):
                raise ValueError('Working OMIT selection has no matching frozen model')
            validation=unlinked(selected.get('local_validation_directory') or model.parent/'local_validation')
            report=rel/validation.relative_to(finish)/'local_validation.json'
        else:
            model_rel=Path('frozen')
            report=rel/'local_validation/local_validation.json'
        path=regular(unlinked(pipeline/report))
        if sha(path)!=frozen.get(report.as_posix()):
            raise ValueError('Local verification record differs from checkpoint')
        data=read(path)
        if data.get('validation_complete') is not True:
            raise ValueError('Incomplete local validation')
        for ext in ('cif','fcf'):
            key=(rel/model_rel/('model.'+ext)).as_posix()
            if not frozen.get(key) or data['input_sha256'][ext]!=frozen[key]:
                raise ValueError('Validation inputs differ from the frozen checkpoint')
        counts=data['validated_counts']
        alerts=[a for a in data['alerts']['alerts'] if a['level'] in ('A','B')]
        if any(not all(isinstance(a.get(k),str) for k in ('code','text')) for a in alerts):
            raise ValueError('Invalid individual alert record')
        if any(type(counts[k]) is not int or counts[k]!=sum(a['level']==k for a in alerts) for k in ('A','B')):
            raise ValueError('Local counts and individual alerts disagree')
        return dict(status='verified_checkpoint',counts={k:counts[k] for k in ('A','B')},alerts=alerts,record=str(path))
    except (OSError,ValueError,TypeError,KeyError) as exc:
        return dict(status='unavailable',counts=None,reason=str(exc))


def summary(root,state):
    from customer_status import describe
    from workflow_observability import summarize_waits
    from execution_mode import live_preview
    preview=live_preview(root) if state.get('options',{}).get('execution_mode')=='fast' else None
    return {'run':str(root),'specimen':specimen_identity(root,state),'status':state['status'],'completed_actions':state['completed_actions'],
            'execution_mode':state.get('options',{}).get('execution_mode','standard'),'fast_preview':preview,
            'customer_summary':describe(state),'support_report':state.get('support_report'),
            'next_step':state.get('next_step') if state['status']=='needs_attention' else None,
            'reason':state.get('reason'),'category':state.get('category'),'ai_calls':0,
            'handoff':str(root/'handoff.json') if state['status']=='needs_attention' else None,
            'delivery':state.get('delivery'),'customer_delivery':state.get('customer_delivery'),'customer_notice':state.get('customer_notice'),'zip':state.get('zip'),'official_counts':state.get('official_counts'),
            'local_validation':local_report_at_checkpoint(root,state),
            'action_seconds':{a['action']:a.get('seconds') for a in state['actions']},
            'handoff_timing':summarize_waits(state),
            'native_branch':state.get('native_branch'),'native_completion':state.get('native_completion'),
            'token_usage':{'exact_total':None,'exact_saving':None}}


def publish(root,state):
    s=summary(root,state);write_json(root/'result.json',s)
    actions={'solve':'初始结构求解','match':'元素匹配与加氢','finish':'精修与验证','deliver':'官网验证及报告','review':'报表复核与交付'}
    stages={'running':'正在运行','returned':'已返回，待检查','checkpointed':'本步骤已完成','uncertain':'结果待确认'}
    table=''.join('<tr><td>'+html.escape(actions.get(a['action'],a['action']))+'</td><td>'+html.escape(stages.get(a['status'],a['status']))+'</td><td>'+str(a.get('seconds',''))+'</td></tr>' for a in state['actions'])
    links='<a href="pipeline/index.html">本次晶体流程与交付</a>' if (root/'pipeline/index.html').exists() else ''
    if s['handoff']:links+=' · <a href="handoff.json">异常接手信息</a>'
    if (s.get('support_report') or {}).get('report'):
        links+=' · <a href="'+html.escape(Path(s['support_report']['report']).as_uri(),quote=True)+'">处理说明与反馈包</a>'
    if s.get('customer_delivery'):
        links+='<p>'+html.escape(s['customer_notice'])+'</p>'
        for label,path in s['customer_delivery']['files'].items():links+='<a href="'+html.escape(Path(path).as_uri(),quote=True)+'">'+html.escape(Path(path).name)+'</a> · '
    customer=s['customer_summary']
    intro='<h2>'+html.escape(customer['title'])+'</h2><p>'+html.escape(customer['explanation'])+'</p><p>接下来由谁处理：'+html.escape(customer['next_action_owner'])+'</p>'
    local=s.get('local_validation')
    if local and local['counts'] is not None:
        counts=local['counts']
        intro+=f"<h2>本地 PLATON 验证</h2><p>本次记录有 {counts['A']} 条 A 级、{counts['B']} 条 B 级警告。</p>"
        if local['alerts']:
            intro+='<ul>'+''.join('<li>'+html.escape(f"{a['level']} · {a['code']} · {a['text']}")+'</li>' for a in local['alerts'])+'</ul>'
    elif local:
        intro+='<p>本地验证记录尚未核实，A/B 数量未知。</p>'
    page='<!doctype html><html lang="zh"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Cairystal 任务进度</title><style>body{font:17px/1.7 system-ui;max-width:1000px;margin:40px auto;padding:20px}table{border-collapse:collapse}td,th{border:1px solid #bbc;padding:8px}pre{white-space:pre-wrap;overflow-wrap:anywhere}details{margin-top:24px}</style><h1>Cairystal 任务进度</h1>'+intro+'<p>'+links+'</p><table><tr><th>步骤</th><th>执行状态</th><th>秒</th></tr>'+table+'</table><details><summary>技术记录与完整路径</summary><pre>'+html.escape(json.dumps(s,ensure_ascii=False,indent=2))+'</pre></details></html>'
    (root/'index.html').write_text(page,encoding='utf-8')
    return s


def main():
    p=argparse.ArgumentParser(description=__doc__);sub=p.add_subparsers(dest='cmd',required=True)
    a=sub.add_parser('run');a.add_argument('--config',required=True);a.add_argument('--output',required=True);a.add_argument('--execution-mode',choices=['standard','fast'])
    a=sub.add_parser('resume');a.add_argument('--run',required=True);a.add_argument('--graph');a.add_argument('--donor-basis');a.add_argument('--source');a.add_argument('--basis');a.add_argument('--authorize-iucr-upload',action='store_true')
    a=sub.add_parser('status');a.add_argument('--run',required=True)
    a=sub.add_parser('sync-delivery',help='Verify an already completed child delivery and repair coordinator state, including older jobs; no computation or upload')
    a.add_argument('--run',required=True)
    a=sub.add_parser('continue-native',help='Continue a reviewed current candidate without replaying graph matching or solution')
    for name in ('run','candidate','review','name'):a.add_argument('--'+name,required=True)
    a.add_argument('--stem',default='model');a.add_argument('--authorize-iucr-upload',action='store_true')
    a=sub.add_parser('review',help='Finalize after actual report review');a.add_argument('--run',required=True);a.add_argument('--review-note',required=True)
    for lang in ('zh','en','official'):a.add_argument('--reviewed-'+lang,action='store_true',required=True)
    for mode in ('resume','status','review','continue-native','sync-delivery'):
        sub.choices[mode].add_argument('--expected-hkl',help='Original HKL of the requested specimen; reject a different checkpoint')
    args=p.parse_args()
    try:
        if args.cmd=='run':root,state=create(args.config,args.output,args.execution_mode)
        else:
            root=unlinked(args.run);state=read(root/'autorun.json')
            if args.expected_hkl:check_expected(root,state,args.expected_hkl)
        if args.cmd!='status':
            with lock(root):
                state=read(root/'autorun.json')
                if getattr(args,'expected_hkl',None):check_expected(root,state,args.expected_hkl)
                from coordinator_completion import reconcile
                synchronized=reconcile(root,state,explicit=args.cmd=='sync-delivery')
                if args.cmd=='sync-delivery' and not synchronized:raise ValueError('No completed child delivery is available; no computation was started')
                if not synchronized and args.cmd=='resume' and any([args.graph,args.donor_basis is not None,args.source,args.authorize_iucr_upload]):
                    amend(root,state,args.graph,args.donor_basis,args.source,args.basis,args.authorize_iucr_upload)
                if synchronized:pass
                elif args.cmd=='continue-native':
                    if args.authorize_iucr_upload:amend(root,state,authorize=True)
                    from native_continuation import continue_native
                    continue_native(root,state,args.candidate,args.review,args.name,args.stem)
                elif args.cmd=='review':
                    if state.get('native_branch'):raise ValueError('Review/finalize the recorded native delivery_run, then resume this coordinator; do not review the earlier graph branch')
                    review_reports(root,state,args)
                else:drive(root,state)
                result=publish(root,state)
        else:
            from coordinator_completion import reconcile
            if (root/'autorun.lock').exists() or (root/'pipeline/pipeline.lock').exists():result=summary(root,state)
            else:
                with lock(root):
                    state=read(root/'autorun.json')
                    if args.expected_hkl:check_expected(root,state,args.expected_hkl)
                    if reconcile(root,state):result=publish(root,state)
                    else:result=summary(root,state)
        print(json.dumps(result,ensure_ascii=False),flush=True)
        return 0 if state['status'] in {'complete','local_ready'} else 2
    except WrongSpecimen as exc:
        print(json.dumps({'status':'wrong_specimen','error':str(exc)}));return 1
    except Exception as exc:
        from support_report import try_record
        support=try_record(root,'execution_error',str(exc),'autorun',exc) if 'root' in locals() else {'status':'no_verified_run_directory'}
        print(json.dumps({'status':'command_rejected','error':str(exc),'support_report':support,'ai_calls':0},ensure_ascii=False),flush=True);return 1


if __name__=='__main__':raise SystemExit(main())
