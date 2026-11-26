"""Continue the same specimen from a reviewed native model, without graph replay.

This is a route change, not a model builder or scientific approval. Keep the
original coordinator checkpoint and bind the new branch to the same raw HKL.
"""
from pathlib import Path
import shutil,time
from crystal_runtime import paired_bundle,sha,write_json,utc_now,check_stem
from pipeline_intake import unlinked

def _call(root,state,action,command,runner):
    import crystal_autorun as ar
    if any(x['action']==action for x in state['actions']):
        raise ValueError('This branch action was already attempted; inspect its checkpoint rather than replaying it')
    log=root/'logs'/(action.replace(':','_')+'.log')
    event={'action':action,'command':command,'log':str(log),'started_at':utc_now(),'status':'running'}
    state['actions'].append(event);state.update(status='running',pending=action);ar.save(root,state)
    started=time.perf_counter()
    try:
        event['returncode']=runner(command,log);event['status']='checkpointed'
        state['completed_actions'].append(action);state.pop('pending',None)
    except Exception as exc:
        event.update(status='uncertain',error=str(exc))
        raise
    finally:
        event.update(seconds=round(time.perf_counter()-started,4),finished_at=utc_now());ar.save(root,state)

def continue_native(root,state,candidate,review,name,stem='model',runner=None):
    import crystal_autorun as ar
    ar.verify(root,state)
    if state.get('pending'):raise ValueError('A process outcome is still uncertain; inspect it before starting another branch')
    name=ar.identifier(name);stem=check_stem(stem);candidate=unlinked(candidate)
    destination=unlinked(root/'native_branches'/name)
    if destination.exists():raise ValueError('Keep the previous branch; use a new branch name')
    audit=paired_bundle(candidate,stem)
    expected=ar.specimen_identity(root,state)['hkl_sha256']
    if not expected or audit['source_sha256']['hkl']!=expected:
        raise ar.WrongSpecimen('Native candidate HKL differs from this specimen. Record any transformed-data lineage in a separate explicit job; do not substitute another data set.')
    reviewed=ar.read(review)
    if reviewed.get('chemistry_and_h_reviewed') is not True or not str(reviewed.get('basis','')).strip():
        raise ValueError('Record the actual current-model chemistry/H assessment before final completion; stage remains available for ongoing modelling')
    model_hash=audit['source_sha256']['cif']
    if reviewed.get('model_sha256') not in (None,model_hash):raise ValueError('Review belongs to a different CIF')
    from model_priority import reference_provenance
    reviewed=reference_provenance(reviewed)
    reviewed['model_sha256']=model_hash
    destination.mkdir(parents=True);write_json(destination/'previous_coordinator.json',state)
    snapshot=destination/'input';snapshot.mkdir()
    for ext,path in audit['files'].items():shutil.copy2(path,snapshot/('model.'+ext))
    if any(sha(snapshot/('model.'+ext))!=h for ext,h in audit['source_sha256'].items()):raise ValueError('Candidate changed during snapshot')
    write_json(destination/'review.json',reviewed);write_json(destination/'source_audit.json',audit)
    record={'name':name,'directory':str(destination),'source':str(candidate),'model_sha256':model_hash,
            'input_hashes':ar.seal(snapshot),'review_sha256':sha(destination/'review.json'),
            'prior_graph_not_replayed':True,'scientific_acceptance':'not_established_by_route_change'}
    state.setdefault('native_branches',[]).append(record);state['native_branch']=record
    state.setdefault('interventions',[]).append({'at':utc_now(),'changes':{'native_branch':name},'basis':reviewed['basis']})
    cfg=state['options'];python=ar.read(cfg['profile'])['python']
    command=[python,'-B',str(Path(__file__).with_name('complete_candidate.py')),
             '--input',str(snapshot),'--review',str(destination/'review.json'),
             '--profile',cfg['profile'],'--output',str(destination/'completion'),
             '--data-dir',cfg['data_dir'],'--timeout',str(cfg['timeout']),
             '--max-weight-updates',str(cfg['max_weight_updates'])]
    if not cfg['deliver']:command.append('--local-only')
    if cfg['deliver'] and cfg['authorize_iucr_upload']:command.append('--authorize-iucr-upload')
    _call(root,state,'native_finish:'+name,command,runner or ar.default_runner)
    return refresh_native(root,state,runner or ar.default_runner)

def _verified_delivery(folder):
    import crystal_autorun as ar
    from delivery_contract import require
    contract=require(folder,'model');data=ar.read(folder/'result.json')
    receipt=ar.read(folder/'customer_delivery.json')
    if receipt.get('status')!='exported' or receipt!=data.get('customer_delivery'):
        raise ValueError('Native delivery has no matching customer export receipt')
    target=unlinked(receipt['directory'])
    for name,h in receipt['exported_hashes'].items():
        if Path(name).name!=name or sha(unlinked(target/name))!=h:raise ValueError('Exported native delivery changed')
    data['official_counts']=contract['official_counts']
    return data

def local_report(root,state):
    """Never show an earlier graph branch's alert counts as the native result."""
    import crystal_autorun as ar
    try:
        record=state['native_branch'];folder=unlinked(record['directory'])
        if folder!=root/'native_branches'/ar.identifier(record['name']):raise ValueError('Wrong native branch path')
        finish=folder/'completion/finish';ready=ar.read(finish/'state.json')
        model=unlinked(ready.get('selected') or finish/'frozen');model.relative_to(finish)
        validation=unlinked(ready.get('local_validation_directory') or finish/'local_validation');validation.relative_to(finish)
        path=validation/'local_validation.json';data=ar.read(path)
        if data.get('validation_complete') is not True:raise ValueError('Native local validation is incomplete')
        for ext in ['cif','fcf']:
            if data['input_sha256'][ext]!=sha(model/('model.'+ext)):raise ValueError('Native validation belongs to a different model')
        alerts=[a for a in data['alerts']['alerts'] if a['level'] in ('A','B')]
        if any(not all(isinstance(a.get(k),str) for k in ['code','text']) for a in alerts):raise ValueError('Invalid native alert record')
        counts=data['validated_counts']
        if any(type(counts[k]) is not int or counts[k]!=sum(a['level']==k for a in alerts) for k in ['A','B']):raise ValueError('Native alert counts disagree')
        return {'status':'verified_checkpoint','counts':{k:counts[k] for k in ['A','B']},'alerts':alerts,'record':str(path),'branch':record['name']}
    except (OSError,ValueError,KeyError,TypeError) as exc:
        return {'status':'unavailable','counts':None,'reason':str(exc),'branch':'native'}

def refresh_native(root,state,runner=None,allow_delivery=False):
    import crystal_autorun as ar
    record=state['native_branch'];folder=unlinked(record['directory'])
    if folder!=root/'native_branches'/ar.identifier(record['name']):raise ValueError('Native branch path differs from this run')
    if ar.seal(folder/'input')!=record['input_hashes'] or sha(folder/'review.json')!=record['review_sha256']:
        raise ValueError('Reviewed native snapshot changed; preserve it and prepare a new candidate branch')
    result_path=folder/'completion/result.json';finish=folder/'completion/finish';dr=finish/'delivery_run'
    result=ar.read(result_path) if result_path.is_file() else {}
    ready=ar.read(finish/'state.json') if (finish/'state.json').is_file() else {}
    delivery=ar.read(dr/'result.json') if (dr/'result.json').is_file() else {}
    state['native_completion']={'record':str(result_path),'status':result.get('status'),'finish_status':ready.get('status'),
                                'metrics':result.get('metrics'),'next_tool':result.get('next_tool'),
                                'continuation':delivery.get('continuation') or result.get('continuation')}
    if delivery.get('status')=='delivery_complete_needs_scientific_review':
        data=_verified_delivery(dr)
        for key in ['reason','category','stopped_at','next_step']:state.pop(key,None)
        state.update(status='complete',finished_at=utc_now(),delivery=data['customer_delivery']['directory'],
                     customer_delivery=data['customer_delivery'],customer_notice=data.get('customer_notice'),
                     zip=data.get('zip'),official_counts=data['official_counts'])
        ar.save(root,state);return state
    cfg=state['options'];ready_status=ready.get('status') in {'ready_for_official_delivery','official_upload_not_authorized'}
    if ready_status and not cfg['deliver']:
        from deliver_ready import verify_ready
        verify_ready(finish,ready)
        for key in ['category','stopped_at','next_step']:state.pop(key,None)
        state.update(status='local_ready',reason='Native local refinement and validation complete; official and bilingual delivery not requested.')
        ar.save(root,state);return state
    if ready_status and cfg['deliver'] and cfg['authorize_iucr_upload'] and allow_delivery:
        python=ar.read(cfg['profile'])['python']
        command=[python,'-B',str(Path(__file__).with_name('deliver_ready.py')),'--run',str(finish),'--data-dir',cfg['data_dir'],'--authorize-iucr-upload']
        _call(root,state,'native_delivery:'+record['name'],command,runner or ar.default_runner)
        return refresh_native(root,state,runner)
    category='upload_authorization_required' if ready_status and not cfg['authorize_iucr_upload'] else 'native_continuation_review'
    reason=('Native local result retained; resume delivery when this specimen upload is authorized.' if ready_status else
            'Continue from the native completion/delivery checkpoint; inspect its specific result and continuation. Do not rerun solution or require an organic graph.')
    return ar.stop(root,state,category,reason,{'status':result.get('status'),'native_completion':state['native_completion']})
