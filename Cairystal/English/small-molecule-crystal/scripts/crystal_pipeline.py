"""One headless entry: intake, solve, reviewed plans, finish, QA seal and summary.

No LLM calls. Chemical changes require explicit recorded plans; no hidden answers.
"""
import argparse,contextlib,io,json,re,shutil,sys,time,html,os
from pathlib import Path
from types import SimpleNamespace
from datetime import datetime
from crystal_runtime import new_directory,regular,sha,write_json,utc_now
from pipeline_intake import build_profile,verify_profile,inspect,unlinked,bootstrap

def read(path):return json.loads(regular(path).read_text(encoding='utf-8-sig'))
def stamp():return {p.name:sha(p) for p in Path(__file__).parent.glob('*.py')}
def identifier(value):
    if not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_-]{0,60}',value):raise ValueError('Use a short ASCII stage identifier without paths')
    return value
def save(root,state):write_json(root/'pipeline.json',state)

@contextlib.contextmanager
def run_lock(root):
    path=root/'pipeline.lock'
    try:
        with path.open('x',encoding='utf-8') as f:json.dump({'pid':os.getpid(),'created_at':utc_now()},f)
    except FileExistsError:raise ValueError('Another action or interrupted action owns this run; inspect pipeline.lock and process state before an explicit recovery')
    digest=sha(path)
    try:yield
    finally:
        if path.exists() and sha(path)==digest:path.unlink()

def checked(root,state):
    if state['skill_sha256']!=stamp():raise ValueError('Skill scripts changed during this run; preserve it and create a new fixed-version run')
    if state['profile_sha256']!=sha(root/'runtime_profile.json'):raise ValueError('Run profile changed')
    for item in state.get('intake',{}).get('inputs',{}).values():
        if sha(regular(unlinked(item['path'])))!=item['sha256']:raise ValueError('Original input changed: '+item['path'])
    return verify_profile(read(root/'runtime_profile.json'))

def timed(root,state,name,fn,arguments):
    event={'stage':name,'started_at':utc_now(),'status':'running','arguments':arguments};state['events'].append(event);state.update(status='running',active_stage=name);save(root,state)
    clock=time.perf_counter();buffer=io.StringIO()
    try:
        with contextlib.redirect_stdout(buffer):result=fn()
        event['status']='completed';return result
    except Exception as exc:event.update(status='failed',error=str(exc));raise
    finally:
        event.update(seconds=round(time.perf_counter()-clock,4),finished_at=utc_now());state.pop('active_stage',None);(root/'logs').mkdir(exist_ok=True)
        logfile=root/'logs'/(f'{len(state["events"]):02d}_'+identifier(name)+'.stdout.txt');logfile.write_text(buffer.getvalue(),encoding='utf-8');event['stdout_log']=str(logfile);save(root,state)

def register_summary(root,state,summary_path):
    from crystal_session import compact_candidates
    from candidate_packet import make_packet
    payload=read(summary_path);full=dict(payload,full_record=str(summary_path));compact=dict(compact_candidates(payload),full_record=str(summary_path))
    old=json.dumps(full,ensure_ascii=False);new=json.dumps(compact,ensure_ascii=False)
    state['context_measurements'].append({'source':str(summary_path),'full_characters':len(old),'compact_characters':len(new),'scope':'Equivalent candidate stdout only; not billing or total conversation tokens'})
    packet=make_packet(root/'session',payload);write_json(root/'decision_packet.json',packet)
    state['candidates']=packet['candidates'];state['status']='needs_scientific_review'
    if payload.get('solver_handoff'):state['solver_handoff']=payload['solver_handoff']
    from pipeline_metadata import sync_summary
    try:
        sync_summary(root,state,payload);state.pop('metadata_sync_error',None)
    except (ValueError,OSError,RuntimeError) as exc:state['metadata_sync_error']=str(exc)
    save(root,state)

def start(a):
    root=new_directory(unlinked(a.output));profile_source=regular(unlinked(a.profile));shutil.copy2(profile_source,root/'runtime_profile.json')
    state={'schema':1,'created_at':utc_now(),'status':'starting','events':[],'context_measurements':[],'skill_sha256':stamp(),'profile_sha256':sha(root/'runtime_profile.json'),
           'ai_api_calls':0,'prior_model_files_read':False,'prior_conversation_exposure':bool(a.prior_conversation_exposure),'scope':'Original HKL/P4P route; chemistry and final visual acceptance remain explicit review checkpoints.'}
    save(root,state)
    try:
        tools=timed(root,state,'environment',lambda:verify_profile(read(root/'runtime_profile.json')),{'profile':str(profile_source)})
        intake=timed(root,state,'intake',lambda:inspect(a.data_dir,a.elements,a.stem,a.specimen),{'data_directory':a.data_dir,'stem':a.stem,'elements':a.elements,'specimen':a.specimen})
        state['data_directory']=str(unlinked(a.data_dir));state['intake']=intake;write_json(root/'intake.json',intake);save(root,state)
        from crystal_session import start as native_start
        inputs={k:v['path'] for k,v in intake['inputs'].items()}
        args=SimpleNamespace(**{k:inputs.get(k) for k in ['hkl','p4p','integration_log','absorption_log','specimen']},output=str(root/'session'),elements=intake['elements'],shelxt=tools['shelxt'],shelxl=tools['shelxl'],prior_conversation_exposure=a.prior_conversation_exposure,detail=False,solver_fallback=getattr(a,'solver_fallback',None),shelxd=tools.get('shelxd'),expected_hashes={k:v['sha256'] for k,v in intake['inputs'].items()})
        if 'laue_screen' in intake['metadata']:
            args.checked_laue = dict(p4p=intake['inputs']['p4p']['sha256'], hkl=intake['inputs']['hkl']['sha256'],
                                     screen=intake['metadata']['laue_screen'], seed=intake['laue_seed'])
        timed(root,state,'fresh_solution',lambda:native_start(args),vars(args))
        register_summary(root,state,root/'session/start_summary.json')
    except Exception as exc:
        state.update(status='blocked',failure=str(exc))
        if hasattr(exc, 'evidence'):
            state['laue_review'] = exc.evidence
        save(root,state)
    render_summary(root,state);return root,state

def load_run(path):
    root=unlinked(path);state=read(root/'pipeline.json');return root,state

def step(root,state,a):
    checked(root,state)
    if state['status']=='complete':raise ValueError('Completed delivery is sealed; create a new run for further changes')
    source=root/'session/stages'/identifier(a.source)/'model.res';regular(source)
    name=identifier(a.name);plan=read(regular(unlinked(a.plan)))
    if not isinstance(plan.get('reason'),str) or not plan['reason'].strip():raise ValueError('A reason supported by current evidence is required')
    plans=root/'session/plans';plans.mkdir(exist_ok=True);target=plans/(name+'.json')
    if target.exists() or (root/'session/stages'/name).exists():raise ValueError('Stage/plan name already used; preserve it and use a new name')
    write_json(target,plan)
    from crystal_session import refine
    args=SimpleNamespace(job=str(root/'session'),source=str(source),plan=str(target),name=name,detail=False)
    timed(root,state,'step_'+name,lambda:refine(args),vars(args))
    register_summary(root,state,root/'session'/(name+'_summary.json'))

def match(root,state,a):
    from graph_assignment import run_pipeline
    run_pipeline(root,state,a)

def autofinish(root,state,a):
    import pdfplumber  # Fail before native/network work when the optional QA dependency is unavailable.
    from scientific_report_rules import review_current
    from report_autoqa import run as automated_qa
    checked(root,state);folder=root/(identifier(a.name)+'_rules');folder.mkdir(exist_ok=False)
    evidence,path=timed(root,state,'scientific_rules',lambda:review_current(root,state,a.source,folder),{'source':a.source})
    state['rule_review']={'status':evidence['status'],'record':str(folder/'scientific_rules.json'),'findings':evidence['findings']}
    if path is None:state['status']='needs_scientific_review';save(root,state);return
    a.review=str(path);finish(root,state,a)
    complete_report_qa(root,state,a)

def complete_report_qa(root,state,a):
    from report_autoqa import run as automated_qa
    if state['status']!='awaiting_visual_review':return
    dr=Path(state['finish_root'])/'delivery_run';qa_path=dr/'automatic_qa.json'
    qa=timed(root,state,'automated_report_qa',lambda:automated_qa(dr,qa_path),{'delivery':str(dr)})
    state['automatic_report_qa']={'status':qa['status'],'record':str(qa_path),'flagged_pages':{lang:[p['number'] for p in v['pages'] if p['issues']] for lang,v in qa['documents'].items()},'findings':qa['findings']}
    if qa['status']!='automatic_checks_passed':state['status']='needs_report_review';save(root,state);return
    state['status']='awaiting_visual_review';a.automatic_qa=str(qa_path);a.review_note='Automated exact-file consistency and measured PDF/DOCX layout rules passed. No actual visual inspection claimed; scientific identity and original processing validity remain unestablished.'
    a.reviewed_zh=a.reviewed_en=a.reviewed_official=False
    finalize(root,state,a)

def solution_notes(session):
    path=Path(session)/'session.json'
    program=read(path).get('solution_program') if path.is_file() else None
    if program in {'SHELXT','SHELXD'}:
        return (f'本次运行记录的初解程序为 {program}。所用衍射数据及元素、氢和空间群的选择依据见本次记录。',
                f'The recorded phasing program was {program}. The current run records the diffraction input and the basis for element, H and space-group assignments.')
    return ('本次记录未确认初解程序。衍射输入和模型选择依据见运行记录。',
            'The phasing program is unconfirmed in this run. See the run record for diffraction inputs and model selection.')

def finish(root,state,a):
    tools=checked(root,state);name=identifier(a.name);review=read(regular(unlinked(a.review)))
    if review.get('chemistry_and_h_reviewed') is not True or not review.get('basis'):raise ValueError('A supported chemistry/H review and selection basis are required')
    stage=root/'session/stages'/identifier(a.source);regular(stage/'model.res')
    if (root/name).exists():raise ValueError('Finish label exists; do not overwrite previous validation')
    reviewed=root/(name+'_review.json');write_json(reviewed,review)
    from candidate_packet import factual_annotations
    annotations=factual_annotations(root/'session',review['basis']);extra=review.get('annotations',{})
    allowed={'_chemical_formula_moiety','_computing_cell_refinement','_computing_data_reduction','_computing_molecular_graphics'}
    if set(extra)-allowed:raise ValueError('Only approved non-model annotations are accepted')
    annotations.update(extra);notes=root/'session'/(name+'_annotations.json');write_json(notes,annotations)
    from crystal_session import prepare
    args=SimpleNamespace(job=str(root/'session'),stage=str(stage),name='selected_'+name,annotations=str(notes))
    timed(root,state,'prepare_'+name,lambda:prepare(args),vars(args))
    profile=read(root/'runtime_profile.json')
    zh,en=solution_notes(root/'session')
    if review.get('review_mode')=='bounded_automatic_rules':
        zh+=' 科学说明由限定范围的规则生成，报告排版使用自动检测；不声明已人工逐页查看。'
        en+=' Scientific statements use bounded rules and report layout uses automatic checks; no manual page-by-page inspection is claimed.'
    if state['prior_conversation_exposure']:
        zh+=' 存在先前聊天信息，不属于完全未知样品盲测。';en+=' Prior conversational exposure prevents describing this as a fully naive blind test.'
    config={'collect_reports_with_alerts':True,'candidate':str(root/'session'/args.name),'stem':'model',**tools,'renderer':profile['renderer'],'timeout':a.timeout,'max_weight_updates':a.max_weight_updates,
            'review':{'chemistry_and_h_reviewed':True,'basis':review['basis'],'review_mode':review.get('review_mode'),'bilingual_notes':{'zh':{'provenance':zh},'en':{'provenance':en}}}}
    raw_hkl=state.get('intake',{}).get('inputs',{}).get('hkl',{}).get('path')
    data_dir=state.get('data_directory') or (str(Path(raw_hkl).parent) if raw_hkl else None)
    if data_dir:config['data_dir']=data_dir
    # Scientific additions are copied without inferred translation.
    if getattr(a,'ab_policy',None):
        from ab_auto import load_policy
        source_policy=regular(unlinked(a.ab_policy));load_policy(source_policy)
        frozen_policy=root/(name+'_ab_policy.json');shutil.copy2(source_policy,frozen_policy)
        config['ab_policy']=str(frozen_policy)
    if review.get('solvent_accounting_review'):config['review']['solvent_accounting_review']=review['solvent_accounting_review']
    additions=review.get('bilingual_notes',{})
    if additions and (not additions.get('zh') or not additions.get('en')):raise ValueError('Scientific additional notes need both zh and en')
    for lang in ['zh','en']:
        for key,value in additions.get(lang,{}).items():
            if key not in {'summary','methods','provenance','limitations'} or not isinstance(value,str):raise ValueError('Unsupported scientific note')
            config['review']['bilingual_notes'][lang][key]=config['review']['bilingual_notes'][lang].get(key,'')+' '+value
    if state.get('metadata_sync_error'):raise ValueError('Resolve experimental metadata audit before final delivery: '+state['metadata_sync_error'])
    if state.get('experimental_metadata_ledger'):config['experimental_metadata_ledger']=state['experimental_metadata_ledger']
    config_path=root/(name+'_config.json');write_json(config_path,config)
    from routine_finish import finish as routine_finish
    def invoke():
        result,_=routine_finish(config_path,root/name,a.deliver,a.authorize_iucr_upload)
        if result['status']=='failed':raise ValueError('Routine finish failed: '+result.get('failure','See retained state.json'))
        return result
    result=timed(root,state,'finish_'+name,invoke,{'config':str(config_path),'deliver':a.deliver,'upload_authorized':a.authorize_iucr_upload})
    state.update(status=result['status'],finish_root=str(root/name),metrics=result.get('metrics'),official_counts=result.get('official_counts'),local_counts=result.get('local_counts'),AB_alerts=result.get('AB_alerts') or result.get('pending_alert_review'),automatic_AB=result.get('automatic_AB'))
    if (root/name/'decision_packet.json').exists():shutil.copy2(root/name/'decision_packet.json',root/'decision_packet.json')
    if result.get('render_manifest'):state['render_manifest']=result['render_manifest'];state['official_pages_manifest']=result['official_pages_manifest']
    if result.get('delivery'):state.update(delivery=result['delivery'],completion=result.get('completion'),structure_viewer=result.get('structure_viewer'))
    save(root,state)

def deliver(root,state,a):
    checked(root,state)
    if state['status'] not in {'ready_for_official_delivery','official_upload_not_authorized'}:raise ValueError('No intact locally finished checkpoint waiting for delivery')
    from deliver_ready import run as deliver_checkpoint
    finish_root=Path(state['finish_root'])
    result=timed(root,state,'resume_official_delivery',lambda:deliver_checkpoint(finish_root,a.authorize_iucr_upload),{'finish_root':str(finish_root),'authorize':a.authorize_iucr_upload})
    state.update(status=result['status'],official_counts=result.get('official_counts'),AB_alerts=result.get('AB_alerts'))
    if result.get('delivery'):state.update(delivery=result['delivery'],completion=result.get('completion'),structure_viewer=result.get('structure_viewer'))
    for key in ['render_manifest','official_pages_manifest']:
        if result.get(key):state[key]=result[key]
    save(root,state)
    if result['status']=='failed':raise ValueError(result.get('failure','Delivery failed'))
    if result.get('review',{}).get('review_mode')=='bounded_automatic_rules':complete_report_qa(root,state,a)


def finalize(root,state,a):
    checked(root,state)
    automatic=getattr(a,'automatic_qa',None)
    if state['status']=='needs_report_review' and not automatic:
        qa=read(Path(state['finish_root'])/'delivery_run/automatic_qa.json')
        if qa.get('status')!='needs_review' or set(qa.get('documents',{}))!={'zh','en'} or set(qa['findings'])-{'Official A/B requires scientific review'}:
            raise ValueError('Report QA integrity or official validation needs repair before manual sign-off')
        if any(doc.get('global_issues') for doc in qa['documents'].values()):
            raise ValueError('Report content or page count needs repair before manual sign-off')
    elif state['status']!='awaiting_visual_review':
        raise ValueError('No complete delivery waiting for actual page review')
    if not automatic and not(a.reviewed_zh and a.reviewed_en and a.reviewed_official and a.review_note):raise ValueError('Actual review of both Word files and official PDF is required without exact-file automated QA')
    finish_root=Path(state['finish_root']);delivery=finish_root/'delivery_run'
    from crystal_delivery import finalize as seal
    args=SimpleNamespace(run=str(delivery),data_dir=state.get('data_directory') or str(Path(state['intake']['inputs']['hkl']['path']).parent),reviewed_zh=a.reviewed_zh,reviewed_en=a.reviewed_en,reviewed_official=a.reviewed_official,review_note=a.review_note,automatic_qa=automatic)
    timed(root,state,'seal_delivery',lambda:seal(args),vars(args))
    result=read(delivery/'result.json');state.update(status='complete',finished_at=utc_now(),delivery=result['customer_delivery']['directory'],working_delivery=str(delivery/'delivery'),customer_delivery=result['customer_delivery'],customer_notice=result['customer_notice'],zip=result['zip'],baseline_seconds=a.baseline_seconds)
    state['original_inputs_unchanged']=True;state['skill_unchanged']=True
    f=read(finish_root/'state.json');f.update(status=result['status'],review_record='delivery_run/'+('automatic_review.json' if automatic else 'visual_review.json'),finalized_at=result['finalized_at']);write_json(finish_root/'state.json',f)
    save(root,state)

def make_summary(root,state):
    end=state.get('finished_at',utc_now());elapsed=(datetime.fromisoformat(end)-datetime.fromisoformat(state['created_at'])).total_seconds()
    full=sum(x['full_characters'] for x in state['context_measurements']);small=sum(x['compact_characters'] for x in state['context_measurements'])
    native=[]
    for p in sorted((root/'session/stages').glob('*/attempt.json')):
        x=read(p);native.append({'stage':p.parent.name,'seconds':x.get('elapsed_s'),'command':x.get('command'),'metrics':x.get('gate',{}).get('metrics'),'log':x.get('log')})
    delivery=None;routine=None
    if state.get('finish_root'):
        fp=Path(state['finish_root']);routine=read(fp/'state.json')
        for trial in routine['weight_trials']:
            p=Path(trial['output'])/'attempt.json';x=read(p);native.append({'stage':p.parent.name,'seconds':x.get('elapsed_s'),'command':x.get('command'),'metrics':x.get('gate',{}).get('metrics'),'log':x.get('log')})
        if (fp/'delivery_run/result.json').exists():delivery=read(fp/'delivery_run/result.json')
    return {'status':state['status'],'elapsed_wall_s':round(elapsed,3),'timed_actions_s':round(sum(x.get('seconds',0) for x in state['events']),3),
            'between_actions_s':round(max(0,elapsed-sum(x.get('seconds',0) for x in state['events'])),3),'events':state['events'],'native_attempts':native,
            'native_elapsed_s':round(sum(x['seconds'] or 0 for x in native),3),'routine_events':routine['events'] if routine else None,
            'completion':state.get('completion'),'delivery':state.get('delivery'),'customer_delivery':state.get('customer_delivery'),'customer_notice':state.get('customer_notice'),'delivery_timings_s':delivery.get('timings_s') if delivery else None,'official_counts':state.get('official_counts'),'metrics':state.get('metrics'),
            'token_usage':{'exact_total':None,'exact_saving':None,'reason':'No billed per-turn token telemetry. Character counterfactual covers candidate stdout only, not all context, reasoning, images or arguments.',
                           'full_candidate_characters':full,'compact_candidate_characters':small,'character_reduction_percent':round(100*(1-small/full),1) if full else None},
            'script_ai_calls':0,'support_report':state.get('support_report'),'graph_matching':state.get('graph_matching'),'rule_review':state.get('rule_review'),'automatic_report_qa':state.get('automatic_report_qa'),'baseline_seconds':state.get('baseline_seconds'),'scientific_correctness':'not_established_by_automation'}

def render_summary(root,state):
    if state.get('status') in {'blocked','failed'} or state.get('last_command_error'):
        from support_report import try_record
        state['support_report']=try_record(root,'execution_error',state.get('failure') or str(state.get('last_command_error')),'workflow')
        save(root,state)
    elif state.get('status') in {'needs_scientific_review','needs_alert_review','needs_weight_review','needs_report_review'}:
        from support_report import try_record
        kind='report_review' if state['status']=='needs_report_review' else 'scientific_decision'
        state['support_report']=try_record(root,kind,state['status'],'workflow');save(root,state)
    result=make_summary(root,state);write_json(root/'result.json',result)
    rows=''.join(f'<tr><td>{html.escape(e["stage"])}</td><td>{e.get("seconds",0):.3f}</td><td>{html.escape(e["status"])}</td></tr>' for e in state['events'])
    links=['<a href="pipeline.json">完整运行记录</a>','<a href="result.json">耗时及输出统计</a>']
    if state.get('support_report',{}).get('report'):links.append('<a href="'+html.escape(Path(state['support_report']['report']).as_uri(),quote=True)+'">处理说明与反馈包</a>')
    if (root/'decision_packet.json').exists():links.append('<a href="decision_packet.json">候选/诊断材料</a>')
    if state.get('graph_matching'):links.append(f'<a href="{Path(state["graph_matching"]["record"]).relative_to(root).as_posix()}">二维图匹配与元素指认对照</a>')
    if state.get('zip'):links.append(f'<a href="{Path(state["zip"]["path"]).relative_to(root).as_posix()}">结构和报告完整包</a>')
    if state.get('delivery'):
        folder=Path(state['delivery'])
        for name in ['model.res','model.hkl','model.cif','IUCr_checkCIF.pdf','晶体学报表_中文.docx','Crystallographic_Report_EN.docx','structure_viewer.html']:
            if (folder/name).is_file():links.append(f'<a href="{html.escape((folder/name).as_uri(),quote=True)}">{html.escape(name)}</a>')
    if state.get('customer_notice'):links.append('<p>'+html.escape(state['customer_notice'])+'</p>')
    payload=html.escape(json.dumps(state.get('official_counts') or state.get('local_counts'),ensure_ascii=False));failure=html.escape(state.get('failure',''))
    page=f'''<!doctype html><html lang="zh-CN"><meta charset="utf-8"><title>自动单晶工作流</title><style>body{{font:17px/1.7 system-ui;max-width:1050px;margin:35px auto;padding:20px;color:#23364b}}table{{border-collapse:collapse;width:100%}}td,th{{border:1px solid #ddd;padding:8px;text-align:left}}a{{display:inline-block;margin:7px 16px 7px 0;color:#1464a0}}pre{{white-space:pre-wrap}}.box{{background:#f3f6f9;padding:20px;border-radius:10px}}</style><h1>自动单晶工作流</h1><div class="box"><b>状态：{html.escape(state['status'])}</b><p>总墙钟 {result['elapsed_wall_s']:.2f} 秒；脚本动作 {result['timed_actions_s']:.2f} 秒；动作间隔 {result['between_actions_s']:.2f} 秒。间隔包括科学判断、调用准备及页面复核，不能当作软件计算时间。</p><p>警告计数：{payload}。以本次官网 PDF 为正式验证结果；本地预检单独保存。</p><p>{failure}</p></div><p>{''.join(links)}</p><h2>各动作耗时</h2><table><tr><th>动作</th><th>秒</th><th>状态</th></tr>{rows}</table><h2>资源统计</h2><pre>{html.escape(json.dumps(result['token_usage'],ensure_ascii=False,indent=2))}</pre><p>脚本内部 AI 调用为 0。没有读取旧模型；先前聊天信息标记：{state['prior_conversation_exposure']}。低 R、收敛和零 A/B 不证明结构正确。原始强度、所有候选及实验限制均需保留。</p></html>'''
    page=page.replace('</html>','<footer style="margin-top:28px;font-size:12px;color:#707070">本流程由 Cairystal 协助执行 · Assisted by Cairystal</footer></html>')
    (root/'index.html').write_text(page,encoding='utf-8')

def compact(root,state):
    result={'run':str(root),'status':state['status'],'summary':str(root/'index.html'),'record':str(root/'pipeline.json'),'support_report':state.get('support_report')}
    for key in ['metrics','official_counts','local_counts','failure','last_command_error','active_stage','render_manifest','official_pages_manifest','delivery','zip','graph_matching','rule_review','automatic_report_qa','structure_viewer','customer_delivery','customer_notice']:
        if key in state:result[key]=state[key]
    if state['status']=='needs_scientific_review':
        result['candidates']=[{'stage':c['stage'],'R1':c['metrics'].get('R1_observed'),'formula':c['formula_as_recorded'],'hydrogen_sites':c['hydrogen_sites']} for c in state['candidates']]
        result['next']='Read decision_packet.json; provide a supported step plan or reviewed selection. No automatic chemical acceptance.'
    elif state['status'] in {'awaiting_visual_review','needs_report_review'}:result['next']='Inspect official alerts, flagged pages and both reports. Correct content/integrity failures. After actual review use finalize (or autorun review for a coordinated run) with all three review flags and the review note.'
    elif state['status'] in {'blocked','failed','needs_alert_review','needs_weight_review'}:result['next']='Inspect retained failure/decision evidence; no automatic destructive retry.'
    return result

def main():
    p=argparse.ArgumentParser(description=__doc__);sub=p.add_subparsers(dest='cmd',required=True)
    s=sub.add_parser('profile');s.add_argument('--software-dir',required=True);s.add_argument('--renderer',choices=['word','libreoffice'],required=True);s.add_argument('--pdftoppm',required=True);s.add_argument('--powershell');s.add_argument('--soffice');s.add_argument('--module-dir',action='append',default=[]);s.add_argument('--output',required=True)
    s=sub.add_parser('start')
    for k in ['data-dir','profile','output']:s.add_argument('--'+k,required=True)
    s.add_argument('--elements',nargs='+',required=True);s.add_argument('--stem');s.add_argument('--specimen');s.add_argument('--solver-fallback');s.add_argument('--prior-conversation-exposure',action='store_true')
    s=sub.add_parser('step')
    for k in ['run','source','plan','name']:s.add_argument('--'+k,required=True)
    s=sub.add_parser('match')
    for k in ['run','source','graph']:s.add_argument('--'+k,required=True)
    s.add_argument('--name',default='02_graph');s.add_argument('--max-candidates',type=int,default=6);s.add_argument('--add-hydrogens',action='store_true');s.add_argument('--donor-basis',default='')
    s=sub.add_parser('finish')
    for k in ['run','source','review']:s.add_argument('--'+k,required=True)
    s.add_argument('--name',default='finish_01');s.add_argument('--deliver',action='store_true',default=True);s.add_argument('--local-only',dest='deliver',action='store_false');s.add_argument('--authorize-iucr-upload',action='store_true');s.add_argument('--timeout',type=float,default=180);s.add_argument('--max-weight-updates',type=int,default=4)
    s.add_argument('--ab-policy')
    s=sub.add_parser('autofinish')
    for k in ['run','source']:s.add_argument('--'+k,required=True)
    s.add_argument('--name',default='finish_01');s.add_argument('--deliver',action='store_true',default=True);s.add_argument('--local-only',dest='deliver',action='store_false');s.add_argument('--authorize-iucr-upload',action='store_true');s.add_argument('--timeout',type=float,default=180);s.add_argument('--max-weight-updates',type=int,default=4);s.add_argument('--baseline-seconds',type=float)
    s.add_argument('--ab-policy')
    s=sub.add_parser('deliver');s.add_argument('--run',required=True);s.add_argument('--authorize-iucr-upload',action='store_true');s.add_argument('--baseline-seconds',type=float)
    s=sub.add_parser('finalize');s.add_argument('--run',required=True);s.add_argument('--review-note',required=True);s.add_argument('--baseline-seconds',type=float)
    for k in ['zh','en','official']:s.add_argument('--reviewed-'+k,action='store_true')
    s=sub.add_parser('status');s.add_argument('--run',required=True)
    a=p.parse_args();command_failed=False
    try:
        if a.cmd=='profile':
            path=unlinked(a.output)
            if path.exists():raise ValueError('Profile exists; choose a new version, do not overwrite')
            value=build_profile(a.software_dir,a.renderer,a.pdftoppm,a.powershell,a.soffice,a.module_dir);path.parent.mkdir(parents=True,exist_ok=True);write_json(path,value)
            print(json.dumps({'profile':str(path),'status':'files_and_modules_ready','execution_verified':False},ensure_ascii=False));return 0
        if a.cmd=='start':root,state=start(a)
        else:
            root,state=load_run(a.run)
            if a.cmd!='status':
                with run_lock(root):
                    # Reload under the lock so a previous action cannot leave a stale state.
                    state=read(root/'pipeline.json');bootstrap(read(root/'runtime_profile.json'));previous_status=state['status'];previous_events=len(state['events'])
                    try:
                        globals()[a.cmd](root,state,a);state.pop('last_command_error',None);state.pop('failure',None);save(root,state)
                    except Exception as exc:
                        command_failed=True;state['last_command_error']={'action':a.cmd,'at':utc_now(),'error':str(exc)}
                        state['status']='failed' if len(state['events'])>previous_events else previous_status
                        if state['status']=='failed':state['failure']=str(exc)
                        save(root,state)
                    render_summary(root,state)
        print(json.dumps(compact(root,state),ensure_ascii=False));return 1 if command_failed or state['status'] in {'blocked','failed'} else 0
    except Exception as exc:
        from support_report import try_record
        support=try_record(root,'execution_error',str(exc),'workflow',exc) if 'root' in locals() else {'status':'no_verified_run_directory'}
        print(json.dumps({'status':'failed','error':str(exc),'support_report':support},ensure_ascii=False));return 1

if __name__=='__main__':sys.exit(main())
