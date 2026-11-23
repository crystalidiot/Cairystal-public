"""Deterministic finish of a reviewed model; no AI calls or chemical guessing.

Explicit config -> bounded weight review -> local checks -> bilingual facts ->
optional authorized official delivery -> actual page-review checkpoint.
"""
import argparse,contextlib,io,json,math,re,shutil,sys,time
from pathlib import Path
from types import SimpleNamespace
import gemmi
from crystal_runtime import records,canonical,sha,write_json,utc_now,new_directory,regular,paired_bundle,freeze_bundle
from validation_route import validate_local as local_validation,append_local_limit
from crystal_session import logical_text
from run_crystal_stage import run as native_run
from report_preflight import review_contacts
from prepare_validation_metadata import TAGS,snapshot

def read_weights(text):
    active=next((r[1:] for r in records(text) if r[0].upper()=='WGHT'),None)
    parts=re.split(r'^\s*END\s*$',text,maxsplit=1,flags=re.M)
    matches=re.findall(r'^\s*WGHT\s+([^!\r\n]+)',parts[1] if len(parts)>1 else '',re.M)
    def pair(tokens):
        if tokens is None:raise ValueError('Active WGHT missing')
        if not 1<=len(tokens)<=2:raise ValueError('Routine weighting supports WGHT a b only')
        values=list(map(float,tokens));values+=[0.]*(2-len(values))
        if any(not math.isfinite(v) or v<0 for v in values):raise ValueError('Invalid negative/nonfinite WGHT')
        return values
    return pair(active),pair(matches[-1].split()) if matches else None

def weights_close(a,b,relative=.01):
    return b is not None and all(abs(x-y)<=max(floor,relative*max(abs(x),abs(y))) for x,y,floor in zip(a,b,[.00001,.0001]))

def weight_ins(text,new_weight,cycles=12):
    """Change WGHT and L.S. only; preserve ISO/ANI, AFIX/PART/ZERR and geometry."""
    rows=records(text);result=[];found=False;have_cycles=False
    for r in rows:
        key=r[0].upper()
        if key=='WGHT':r=['WGHT',*[f'{x:.8g}' for x in new_weight]];found=True
        if key in {'L.S.','CGLS'}:
            if have_cycles:raise ValueError('Multiple active refinement-cycle controls')
            r=['L.S.',str(cycles)];have_cycles=True
        if key=='HKLF' and not have_cycles:result.append(['L.S.',str(cycles)]);have_cycles=True
        result.append(r)
    if not found:raise ValueError('Active WGHT missing')
    # Native RES often omits output controls; adding these affects output, not the model.
    extra=[['LIST','4'],['ACTA'],['FMAP','2'],['PLAN','50']]
    result=[r for r in result if r[0].upper() not in {'LIST','ACTA','FMAP','PLAN'}]
    at=next(i for i,r in enumerate(result) if r[0].upper()=='HKLF');result[at:at]=extra
    return 'TITL bounded routine weight review\n'+logical_text(result)

def extinction_value(text):
    """EXTI is a refined scalar, not a fixed instruction value (SHELXL manual)."""
    cards=[r for r in records(text) if r[0].upper()=='EXTI']
    if not cards:return None
    if len(cards)!=1 or len(cards[0])>2:raise ValueError('Unsupported EXTI parameterization')
    value=float(cards[0][1]) if len(cards[0])==2 else 0.
    if not math.isfinite(value) or value<0:raise ValueError('Negative/nonfinite EXTI requires review')
    return value

def model_signature(text):
    from audit_occupancy import CARDS
    rows=records(text);controls=[];atoms=[];extinction_value(text)
    ignored={'WGHT','L.S.','CGLS','LIST','ACTA','FMAP','PLAN'}
    for r in rows:
        key=r[0].upper()
        if key in ignored:continue
        if key=='FVAR':controls.append(['FVAR_COUNT',len(r)-1]);continue
        if key=='EXTI':controls.append(['EXTI_REFINED_SCALAR']);continue
        if key not in CARDS and len(r)>=7:
            atoms.append([r[0].upper(),r[1],r[5],len(r)]);continue
        controls.append([v.upper() for v in r])
    return {'controls':controls,'atoms':atoms}

def movement_review(before,after,before_gate,after_gate):
    from audit_occupancy import audit
    btext=before.read_text(encoding='latin1');atext=after.read_text(encoding='latin1')
    if model_signature(btext)!=model_signature(atext):raise ValueError('Weight trial changed model parameterization or other controls')
    b=audit(before,gemmi);a=audit(after,gemmi)
    if a['unit_discrepancies'] or a['overlapping_orbit_groups']:raise ValueError('Weight trial occupancy/orbit accounting needs review')
    previous={x['label']:x for x in b['atoms']};cell=gemmi.UnitCell(*map(float,next(r[2:] for r in records(atext) if r[0].upper()=='CELL')))
    old_rows={r[0]:r for r in records(btext) if r[0] in previous};new_rows={r[0]:r for r in records(atext) if r[0] in previous}
    adp_change=[]
    for label,y in previous.items():
        if y['element'].upper() in {'H','D'}:continue
        for u,v in zip(map(float,old_rows[label][6:]),map(float,new_rows[label][6:])):
            if abs(u-v)>max(.01,.20*abs(u)):raise ValueError(f'Weight trial ADP changed materially at {label}: {u:.6g} -> {v:.6g} A^2; inspect before adoption')
            adp_change.append(abs(u-v))
    distances=[];population=[];labels=[]
    for x in a['atoms']:
        y=previous[x['label']]
        labels.append(x['label'])
        distances.append(cell.find_nearest_pbc_image(gemmi.Fractional(*x['xyz']),gemmi.Fractional(*y['xyz']),0).dist())
        population.append(abs(x['inferred_cif_occupancy']-y['inferred_cif_occupancy']))
        if not -1e-6<=x['inferred_cif_occupancy']<=1.00001:raise ValueError('Nonphysical occupancy after weight trial')
    if max(distances,default=0)>.1:
        i=max(range(len(distances)),key=distances.__getitem__)
        raise ValueError(f'Weight trial moved coordinates/populations materially: {labels[i]} shifted {distances[i]:.6f} A (limit 0.1 A); inspect before adoption')
    if max(population,default=0)>.02:
        i=max(range(len(population)),key=population.__getitem__)
        raise ValueError(f'Weight trial moved coordinates/populations materially: {labels[i]} population changed {population[i]:.6f} (limit 0.02); inspect before adoption')
    if after_gate['review_reasons'] or not after_gate['execution_complete']:raise ValueError('Weight trial numerical/control gate needs review')
    bm=before_gate['metrics'];am=after_gate['metrics']
    if am['unique']!=bm['unique']:raise ValueError('Reflection count changed during weight-only trial')
    if am['R1_observed']>bm['R1_observed']+.001:raise ValueError('R1 worsened materially during weight trial')
    return {'max_cartesian_shift_A':max(distances,default=0),'max_occupancy_change':max(population,default=0),'max_adp_component_change_A2':max(adp_change,default=0),'parameterization_unchanged':True,
            'EXTI_before':extinction_value(btext),'EXTI_after':extinction_value(atext),
            'EXTI_note':'Presence retained; refined scalar may change. This does not establish a physical extinction diagnosis.'}

def carry_metadata(source,new_cif,updates):
    """Same measured HKL/model signature was checked by caller; copy scalars only."""
    s=gemmi.cif.read_file(str(source)).sole_block();doc=gemmi.cif.read_file(str(new_cif));b=doc.sole_block();before=snapshot(doc);changed=[]
    extra=['_chemical_name_systematic','_chemical_name_common','_chemical_formula_moiety','_chemical_absolute_configuration','_exptl_absorpt_special_details','_atom_sites_solution_primary','_computing_structure_solution']
    for tag in list(TAGS)+extra:
        val=s.find_value(tag)
        # SHELXL emits 293 K when TEMP is absent. That default is not a new
        # observation. Explicit unknown/not-applicable experimental values must
        # survive continuation, including unknown temperatures absent from CIF.
        if val is None and tag in {'_cell_measurement_temperature','_diffrn_ambient_temperature'}:val='?'
        carry_unknown=tag in {'_cell_measurement_temperature','_diffrn_ambient_temperature',
            '_exptl_crystal_description','_exptl_crystal_colour','_exptl_crystal_size_min',
            '_exptl_crystal_size_mid','_exptl_crystal_size_max'}
        if val is not None and (carry_unknown or val not in {'?','.'}) and b.find_value(tag)!=val:
            changed.append({'tag':tag,'old':b.find_value(tag),'new':val,'source':'Chosen same-experiment model before weight-only continuation'})
            b.set_pair(tag,val)
    tag='_publ_section_exptl_refinement';inherited=s.find_value(tag)
    inherited=gemmi.cif.as_string(inherited) if inherited and inherited not in {'?','.'} else ''
    if updates or inherited:
        value=('Prior model refinement record (retained verbatim):\n'+inherited+'\n\n') if inherited else ''
        if updates:value+=f'Current continuation of the reviewed model: {updates} bounded suggested-WGHT updates. Chemical assignments, occupancy parameterization, hydrogen constraints and reflection set were retained. Full decisions and before/after files accompany the job. Chemical identity is not established by this automation.'
        changed.append({'tag':tag,'old':b.find_value(tag),'new':gemmi.cif.quote(value),'source':'Actual workflow ledger'});b.set_pair(tag,gemmi.cif.quote(value))
    # snapshot uses canonical lowercase CIF data names; values stay untouched.
    after=snapshot(doc);allow={x['tag'].lower() for x in changed}
    if any(after[name].get(tag)!=v for name,items in before.items() for tag,v in items.items() if tag not in allow):raise ValueError('Protected CIF token changed during metadata carry-forward')
    doc.write_file(str(new_cif));return changed

ROUTES={
 '080':('nonconvergence.md','Inspect largest shifts, parameter coupling and H constraints; do not freeze coordinates merely to hide divergence.'),
 '035':('checkcif-diagnostics.md','Report absolute-configuration method only from supported Flack/Hooft/Parsons evidence and uncertainty.'),
 '183':('experimental-metadata-preflight.md','Look for measured cell-refinement reflection count in permitted same-experiment metadata.'),
 '184':('experimental-metadata-preflight.md','Recover cell-measurement theta_min, not the refinement reflection range.'),
 '185':('experimental-metadata-preflight.md','Recover cell-measurement theta_max, not the refinement reflection range.'),
 '699':('experimental-metadata-preflight.md','Use confirmed specimen habit; unknown appearance is not a measured default.'),
 '934':('ab-alert-action-playbook.md','Inspect the actual >10-sigma HKL list, model errors and completeness before a separately recorded OMIT trial.'),
 '919':('ab-alert-action-playbook.md','Inspect the actual >10-sigma HKL list, model errors and completeness before a separately recorded OMIT trial.'),
 '939':('ab-alert-action-playbook.md','Unweighted discrepancy is not fixed by forcing weighted GoF to one; inspect sigma(I), outliers and model.'),
 '430':('ab-alert-action-playbook.md','Check valence/chemical group and possible missing H against geometry and difference density.'),
 '306':('ab-alert-action-playbook.md','An isolated O is not proof of water; check chemistry, contacts, charge balance and residual density before adding H.'),
 '234':('ab-alert-action-playbook.md','Inspect local ADPs and chemistry before justified local SIMU/RIGU restraint trials.'),
 '242':('ab-alert-action-playbook.md','Compare atom identity, occupancy and displacement against adjacent sites.'),
 '420':('ab-alert-action-playbook.md','Inspect donor-H position and alternative chemically reasonable orientations.'),
 '965':('workflow.md#weighting-review','Suggested weights remain different; retain bounded iterations and model-stability checks.')}

def decision_packet(alerts,root,reason):
    items=[]
    for alert in alerts:
        code=alert['code'].replace('PLAT','').split('_')[0];ref,action=ROUTES.get(code,('validation-evidence.md','Read the exact diagnostic and relevant native evidence; no automatic structural repair.'))
        items.append({**alert,'reference':'references/'+ref,'next_check':action})
    packet={'status':'needs_review','reason':reason,'findings':items,'evidence_root':str(root),'policy':'Findings are diagnostic routes, not diagnoses or automatic changes. Repeated alert codes remain separate.'}
    write_json(root/'decision_packet.json',packet);return packet

def factual_notes(cif,state,review):
    from bilingual_report import extract,normalized_scalars
    data=extract(cif);s=normalized_scalars(data['scalars']);formula=s.get('_chemical_formula_sum') or '?';sg=s.get('_space_group_name_h-m_alt') or '?'
    nh=[a for a in data['atoms'] if a[1].upper() not in {'H','D'}];hydrogen=len(data['atoms'])-len(nh);ani=len(data['ani']);updates=len(state['weight_trials'])
    active=state['weights']['active'];condition=state['weights']['status']
    zh={'title':'晶体学报表','summary':f'最终候选模型记录为 {formula}，空间群 {sg}。本报告由最终文件及实际运行记录自动生成；化学身份和结构解释以已记录的科学复核为准，程序不独立证明其正确性。',
        'methods':f'候选模型含 {len(nh)} 个非氢原子位点，其中 {ani} 个各向异性；氢位点 {hydrogen} 个，处理方式沿用所选模型。执行 {updates} 次有界建议权重更新，最终 WGHT a/b={active[0]:.6g}/{active[1]:.6g}。每次核对参数类型、坐标/占有率变化、反射数、收敛和 NPD；不以 GoF 接近 1 作为单独接受条件。计算细节见随附日志。',
        'provenance':'本段描述已复核候选模型的自动收尾阶段；更早的求解来源见本任务记录。实验参数从同一衍射数据对应的候选 CIF 保留，来源核验见审计记录。',
        'limitations':'权重检查：'+{'coefficients_stable':'系数已稳定','suggestion_missing':'未提供建议值','update_budget_reached':'已达到迭代上限'}.get(condition,'需复核')+'。完整警告见 IUCr 报告。'}
    en={'title':'Crystallographic Report','summary':f'The final candidate records {formula} in {sg}. This report is generated from the final files and actual execution ledger. Chemical identity and interpretation depend on the recorded scientific review; automation does not independently establish correctness.',
        'methods':f'The model contains {len(nh)} non-H sites, including {ani} anisotropic sites, and {hydrogen} H sites with the selected model treatment retained. {updates} bounded suggested-weight updates were executed; final WGHT a/b={active[0]:.6g}/{active[1]:.6g}. Each update checked parameterization, coordinate/population movement, reflection count, convergence and NPD. GoF near one was not a sole acceptance criterion. Native logs retain calculation details.',
        'provenance':'This paragraph describes automatic completion of the reviewed candidate; the origin of the earlier solution is documented in this job. Experimental scalars were retained from the candidate CIF paired to the same reflection data; see provenance audits.',
        'limitations':'Weight review: '+condition+'. See the IUCr report for all official findings.'}
    from report_method_templates import narrative_digest
    digest=narrative_digest(s)
    for lang,notes in [('zh',zh),('en',en)]:
        notes['limitations']+=' '+digest[lang]
    # Factual methods remain in the report; execution narration stays in the audit.
    zh['summary']=f'最终模型为 {formula}，空间群 {sg}。下列数值由最终 CIF 提取。'
    en['summary']=f'The final model is {formula} in {sg}. The following values are extracted from the final CIF.'
    zh['provenance']='实验参数与本次最终模型配套；来源核验见独立审计记录。'
    en['provenance']='Experimental parameters are paired with this final model; source checks are retained in the separate audit.'
    zh['methods']=f'模型包含 {len(nh)} 个非氢位点（{ani} 个各向异性）和 {hydrogen} 个氢位点。最终 WGHT a/b={active[0]:.6g}/{active[1]:.6g}。'+(f'本次完成 {updates} 次权重更新，并核对模型稳定性。' if updates else '权重系数已稳定，本次未继续迭代。')
    en['methods']=f'The model contains {len(nh)} non-H sites ({ani} anisotropic) and {hydrogen} H sites. Final WGHT a/b={active[0]:.6g}/{active[1]:.6g}. '+(f'This run performed {updates} weight updates with model-stability checks.' if updates else 'The weight coefficients were already stable; no further iteration was performed.')
    # Select method templates from actual controls, not a memorized case narrative.
    method_evidence=None
    native=Path(cif).with_suffix('.res')
    if native.exists():
        from report_method_templates import hydrogen_method_notes
        method_evidence=hydrogen_method_notes(native.read_text(encoding='latin1'))
        for lang,notes in [('zh',zh),('en',en)]:
            for key in ('methods','limitations'):notes[key]+=' '+method_evidence[lang][key]
    if state.get('solvent_mask'):
        from squeeze_bundle import bilingual_notes
        mask_notes=bilingual_notes(state['solvent_mask'])
        for lang,notes in [('zh',zh),('en',en)]:
            for key in ['methods','limitations']:notes[key]+=' '+mask_notes[lang][key]
    # Free-form scientific additions must already be supplied in both languages.
    additions=review.get('bilingual_notes',{})
    if additions and (not additions.get('zh') or not additions.get('en')):raise ValueError('Scientific free text needs equivalent zh and en notes; script does not translate')
    for lang,notes in [('zh',zh),('en',en)]:
        for key,value in additions.get(lang,{}).items():
            if key not in {'summary','methods','provenance','limitations'} or not isinstance(value,str):raise ValueError('Unsupported bilingual scientific note')
            if state.get('selected_omit') and value:
                value=('全数据基线复核记录：' if lang=='zh' else 'Full-data baseline review: ')+value
            notes[key]+=' '+value
    if state.get('selected_omit'):
        from working_omit import notes as omit_notes
        description=omit_notes(state['selected_omit'])
        zh['limitations']=zh['limitations'].replace('权重检查：需复核','权重检查：沿用全数据对照的 WGHT')
        if not updates:
            zh['methods']=zh['methods'].replace('权重系数已稳定，本次未继续迭代。','本次对照采用相同的权重系数。')
            en['methods']=en['methods'].replace('The weight coefficients were already stable; no further iteration was performed.','The two refinements used identical weighting coefficients.')
        zh['methods']+=' '+description['zh']
        en['methods']+=' '+description['en']
    return {'zh':zh,'en':en,'audit_records':{'source_narratives':digest['original_records'],'review':review,'weight_trials':state['weight_trials'],'events':state.get('events',[]),'source_hashes':state.get('source_hashes',{})},'generation':{'source_cif_sha256':data['cif_sha256'],'ai_calls':0,'factual_template':True,'hydrogen_method_evidence':method_evidence['evidence'] if method_evidence else None,'narrative_digest':digest['evidence']}}

def freeze_for_validation(audit, destination, credit_audit):
    """Embed structure factors before credit/hash validation; serialization drops comments."""
    from cif_text_preflight import add_assistance_comment
    freeze_bundle(audit,destination,'model')
    return add_assistance_comment(Path(destination)/'model.cif',credit_audit)


def report_alert_policy(local,collect_reports):
    findings=(local.get('alerts') or {}).get('alerts',[])
    pending=[x for x in findings if x['level'] in 'AB' or x['code']=='965']
    return pending,bool(pending and not collect_reports)


def finish(config,output,deliver=False,authorize=False,official_cache=None):
    from refinement_gate import assess
    root=new_directory(output);config_path=regular(config);cfg=json.loads(config_path.read_text(encoding='utf-8'));shutil.copy2(config_path,root/'config.json')
    state={'started_at':utc_now(),'status':'running','phase':'input','weight_trials':[],'events':[],'scientific_acceptance':'requires_review','ai_calls':0,'code_sha256':{p.name:sha(p) for p in Path(__file__).parent.glob('*.py')}};write_json(root/'state.json',state)
    def save():write_json(root/'state.json',state)
    def step(name,fn):
        state['phase']=name;event={'name':name,'started_at':utc_now()};state['events'].append(event);save();t=time.perf_counter()
        try:result=fn();event['status']='completed';return result
        except Exception as exc:event.update(status='failed',error=str(exc));raise
        finally:event.update(finished_at=utc_now(),seconds=round(time.perf_counter()-t,3));save()
    try:
        from model_priority import reference_provenance
        review=reference_provenance(cfg.get('review',{}))
        if review.get('chemistry_and_h_reviewed') is not True or not review.get('basis'):raise ValueError('A recorded scientific model/H review is required before routine completion')
        state['review']=review;save()
        if cfg.get('stem','model')!='model':raise ValueError('Routine finish currently requires basename model; use the general runner for other stems')
        source=Path(cfg['candidate']).resolve();audit=step('input_pairing',lambda:paired_bundle(source,'model'));write_json(root/'input_audit.json',audit)
        state['twin_handling']=audit.get('twin_handling')
        from routine_consistency import require_consistency,summary as consistency_summary
        write_json(root/'routine_consistency.json',audit['routine_checks'])
        state['routine_consistency']=consistency_summary(audit['routine_checks'])
        step('routine_consistency_gate',lambda:require_consistency(audit['routine_checks'],automatic=review.get('review_mode')=='bounded_automatic_rules'))
        if audit['gate']['review_reasons']:raise ValueError('Initial convergence/parameter controls require review: '+str(audit['gate']['review_reasons']))
        state['solvent_mask']=audit.get('solvent_mask')
        if state['solvent_mask']:
            if state['solvent_mask']['quality_flags']:raise ValueError('SQUEEZE quality flags require model/mask review')
            if not review.get('solvent_accounting_review'):raise ValueError('Record host/solvent composition, charge and formula accounting before masked-model delivery')
        state['source_hashes']=audit['source_sha256'];initial=source;current=source;current_gate=audit['gate']
        from atom_labels import renumber_ins,require_normalized,remap_notes,sort_cif
        def number_model():
            native,plan=renumber_ins((source/'model.res').read_text('latin1'))
            plan['source_sha256']=audit['source_sha256']['res']
            write_json(root/'atom_label_map.json',plan)
            if not plan['changed']:return source,current_gate,plan
            before=root/'numbered_before.res';before.write_text(native,encoding='ascii')
            destination=root/'numbered'
            args=SimpleNamespace(executable=cfg['shelxl'],ins=str(before),hkl=str(source/'model.hkl'),fab=audit['files'].get('fab'),output=str(destination),stem='model',reason='Final atom-label normalization only, followed by native full-matrix refinement. Preserve atom order, all atom parameters, SFAC, PART/AFIX, restraints and the reflection set.',timeout=cfg.get('timeout',180))
            with contextlib.redirect_stdout(io.StringIO()):rc=native_run(args)
            if rc:raise ValueError('Numbered native continuation failed; original model retained: '+str(destination/'attempt.json'))
            gate=assess(destination,'model')
            plan['continuation_stability']=movement_review(before,destination/'model.res',current_gate,gate)
            if sha(destination/'model.hkl')!=audit['source_sha256']['hkl']:raise ValueError('HKL changed during numbering')
            require_normalized((destination/'model.res').read_text('latin1'))
            plan['result_res_sha256']=sha(destination/'model.res');write_json(root/'atom_label_map.json',plan)
            return destination,gate,plan
        current,current_gate,naming=step('final_atom_numbering',number_model)
        state['atom_numbering']=naming
        review=remap_notes(review,naming['mapping']);state['effective_review']=review;save()
        max_updates=int(cfg.get('max_weight_updates',4))
        if not 0<=max_updates<=6:raise ValueError('Weight update budget must be 0..6')
        for index in range(max_updates+1):
            text=(current/'model.res').read_text(encoding='latin1');active,suggested=read_weights(text)
            if weights_close(active,suggested):stop='coefficients_stable';break
            if suggested is None:stop='suggestion_missing';break
            if index==max_updates:stop='update_budget_reached';break
            prepared=root/f'weight_{index+1:02d}.ins';prepared.write_text(weight_ins(text,suggested),encoding='ascii');destination=root/f'weight_{index+1:02d}'
            args=SimpleNamespace(executable=cfg['shelxl'],ins=str(prepared),hkl=str(initial/'model.hkl'),fab=audit['files'].get('fab'),output=str(destination),stem='model',reason='Bounded suggested-WGHT update only; preserve chemical model, hydrogen constraints, ADP types, occupancy parameterization and original reflections.',timeout=cfg.get('timeout',180))
            def run_trial():
                with contextlib.redirect_stdout(io.StringIO()):rc=native_run(args)
                if rc:raise ValueError('Native weighting job failed; see '+str(destination/'attempt.json'))
                from convergence_trend import analyse as trend
                candidate=destination;gate=assess(candidate,'model');continuations=[]
                for extra in range(2):
                    evidence=trend((candidate/'model.lst').read_text('latin1'),gate,(candidate/'model.ins').read_text('latin1'))
                    write_json(root/f'weight_{index+1:02d}_trend_{extra+1:02d}.json',evidence)
                    if not evidence['eligible']:break
                    more=root/f'weight_{index+1:02d}_continue_{extra+1:02d}'
                    restart=root/(more.name+'.ins')
                    restart.write_text(weight_ins((candidate/'model.res').read_text('latin1'),read_weights((candidate/'model.res').read_text('latin1'))[0],cycles=20),encoding='ascii')
                    extra_args=SimpleNamespace(executable=cfg['shelxl'],ins=str(restart),hkl=str(candidate/'model.hkl'),fab=str(candidate/'model.fab') if (candidate/'model.fab').is_file() else None,stem='model',output=str(more),reason='Bounded unchanged continuation: signed shift decay; same weight and model, no artificial freezing.',timeout=cfg.get('timeout',180))
                    with contextlib.redirect_stdout(io.StringIO()):extra_rc=native_run(extra_args)
                    continuations.append({'source':str(candidate),'output':str(more),'cycles':20,'trend':evidence})
                    # Persist failed attempts too; do not lose the evidence if the final gate rejects.
                    write_json(root/f'weight_{index+1:02d}_continuations.json',continuations)
                    if extra_rc:raise ValueError('Continuation failed; inspect '+str(more/'attempt.json'))
                    if read_weights((more/'model.ins').read_text('latin1'))[0]!=suggested:raise ValueError('Weight changed during unchanged continuation')
                    if sha(more/'model.hkl')!=audit['source_sha256']['hkl']:raise ValueError('Measured HKL changed during continuation')
                    candidate=more;gate=assess(candidate,'model')
                check=movement_review(current/'model.res',candidate/'model.res',current_gate,gate)
                if sha(candidate/'model.hkl')!=audit['source_sha256']['hkl']:raise ValueError('Measured HKL changed')
                return gate,check,candidate,continuations
            new_gate,check,destination,continuations=step('weight_'+str(index+1),run_trial)
            state['weight_trials'].append({'source':str(current),'output':str(destination),'active_before':active,'applied':suggested,'metrics':new_gate['metrics'],'stability':check,'unchanged_continuations':continuations});current=destination;current_gate=new_gate;save()
        state['weights']={'active':active,'suggested':suggested,'status':stop,'max_updates':max_updates};save()
        if stop!='coefficients_stable':
            state['status']='needs_weight_review';decision_packet([],root,'Weight iteration stopped: '+stop);save();return state,root
        selected=new_directory(root/'selected')
        for ext in ['ins','res','hkl','cif','fcf','lst']+(['fab'] if audit.get('solvent_mask') else []):shutil.copy2(current/f'model.{ext}',selected/f'model.{ext}')
        metadata=carry_metadata(initial/'model.cif',selected/'model.cif',len(state['weight_trials']));write_json(root/'metadata_carry_forward.json',metadata)
        if naming['changed']:
            doc=gemmi.cif.read_file(str(selected/'model.cif'));block=doc.sole_block()
            tag='_publ_section_exptl_refinement';value=block.find_value(tag)
            if value and value not in {'?','.'}:
                block.set_pair(tag,gemmi.cif.quote('Earlier narrative uses original atom labels; see accompanying atom_label_map.json for the final numbering.\n'+gemmi.cif.as_string(value)))
                doc.write_file(str(selected/'model.cif'))
        state['atom_table_order']=sort_cif(selected/'model.cif')
        shutil.copy2(root/'atom_label_map.json',selected/'atom_label_map.json')
        if cfg.get('experimental_metadata_ledger'):
            from experiment_metadata_state import synchronize
            sync=step('experimental_metadata_sync',lambda:synchronize(cfg['experimental_metadata_ledger'],selected/'model.cif',selected/'model.res',selected/'model.hkl',root/'experimental_metadata_sync',cfg.get('basis_audit')))
            state['experimental_metadata_sync']=sync
            if sync['conflicts_retained'] or sync['native_refinement_required']:raise ValueError('Experimental metadata conflicts/native temperature refinement require review')
            shutil.copy2(sync['output'],selected/'model.cif')
        contacts=review_contacts(selected/'model.cif');write_json(root/'contact_reporting_preflight.json',contacts)
        from cif_text_preflight import encode_narratives
        step('cif_text_preflight',lambda:encode_narratives(selected/'model.cif',root/'cif_text_preflight.json'))
        from cif_format_check import require as require_cif_format
        state['cif_format']=step('cif_format',lambda:require_cif_format(selected/'model.cif',require_model=True))
        write_json(root/'cif_format.json',state['cif_format'])
        chosen=paired_bundle(selected,'model');write_json(root/'selected_audit.json',chosen)
        write_json(root/'routine_consistency.json',chosen['routine_checks'])
        state['routine_consistency']=consistency_summary(chosen['routine_checks'])
        step('selected_consistency_gate',lambda:require_consistency(chosen['routine_checks'],automatic=review.get('review_mode')=='bounded_automatic_rules'))
        frozen=root/'frozen';step('freeze_for_validation',lambda:freeze_for_validation(chosen,frozen,root/'cif_assistance_credit.json'))
        shutil.copy2(root/'atom_label_map.json',frozen/'atom_label_map.json')
        local=step('local_validation',lambda:local_validation(cfg['platon'],frozen,root/'local_validation','model',cfg.get('timeout',180)))
        state['local_counts']=(local.get('alerts') or {}).get('counts');state['local_validation_available']=local.get('available',True);state['metrics']=chosen['gate']['metrics'];save()
        if chosen.get('twin_handling'):
            from twin_delivery import review_priority
            state['twin_review_policy']=review_priority(chosen['twin_handling'],
                [a['code'] for a in (local.get('alerts') or {}).get('alerts',[])])
            state['twin_review_policy']['local_validation_available']=state['local_validation_available']
            save()
        pending,stop=report_alert_policy(local,cfg.get('collect_reports_with_alerts',False))
        state['pending_alert_review']=pending
        if pending:decision_packet(pending,root,'Unresolved validation findings retained; diagnostic reports are not scientific acceptance')
        if any(a['level'] in 'AB' for a in pending) and local.get('available',True):
            from ab_auto import from_finish
            state['automatic_AB']=step('automatic_AB_tool_trials',lambda:from_finish(cfg,frozen,root/'local_validation',root/'automatic_AB'))
            write_json(root/'automatic_AB_handoff.json',state['automatic_AB'])
            selection=state['automatic_AB'].get('working_omit') or {}
            if selection.get('selected'):
                from working_omit import prepare
                branch=root/'working_omit'
                updated,updated_audit=step('prepare_working_omit',lambda:prepare(branch,frozen,selection))
                validation=step('validate_working_omit',lambda:local_validation(cfg['platon'],updated,branch/'local_validation','model',cfg.get('timeout',180)))
                findings,blocked=report_alert_policy(validation,cfg.get('collect_reports_with_alerts',False))
                expected=sorted((str(a['code']),a['level']) for a in selection['candidate_AB'])
                observed=sorted((str(a['code']),a['level']) for a in findings if a['level'] in 'AB')
                if not validation.get('available',True) or observed!=expected:
                    decision_packet(findings,root,'Working OMIT branch requires validation review')
                    state.update(status='needs_alert_review',working_omit_validation=str(branch/'local_validation'))
                    save();return state,root
                state.update(selected_omit=selection,baseline_metrics=state['metrics'],baseline_counts=state['local_counts'],
                             metrics=updated_audit['gate']['metrics'],local_counts=validation['alerts']['counts'],
                             local_validation_directory=str(branch/'local_validation'),selected=str(updated))
                state['baseline_routine_consistency']=state['routine_consistency']
                state['routine_consistency']=consistency_summary(updated_audit['routine_checks'])
                frozen,local,pending,stop=updated,validation,findings,blocked
                active,suggested=read_weights((updated/'model.res').read_text('latin1'))
                state['baseline_weights']=state['weights']
                state['weights']=dict(state['weights'],active=active,suggested=suggested,
                                      status='coefficients_stable' if weights_close(active,suggested) else 'fixed_for_omit_comparison')
                state['pending_alert_review']=pending
                write_json(branch/'paired_audit.json',updated_audit)
                # The baseline packet remains in automatic_AB. The top-level decision refers to the selected files.
                decision_packet(pending,root,'Working OMIT selection; see working_omit/selection.json and the unchanged baseline')
            elif state['automatic_AB'].get('recommended_for_review') or state['automatic_AB'].get('sensitivity_trials_for_review'):
                # Review the supported improvement before uploading the older model.
                stop=True
            save()
        if stop:
            state['status']='needs_alert_review';save();return state,root
        notes=factual_notes(frozen/'model.cif',state,review)
        from validation_route import mark_provisional
        if pending:mark_provisional(notes,pending)
        append_local_limit(notes,local);write_json(root/'reviewer_notes.json',notes)
        state.update(status='ready_for_official_delivery',selected=str(frozen),notes=str(root/'reviewer_notes.json'))
        from deliver_ready import seal_ready
        state['ready_artifacts']=seal_ready(root,state);save()
        if deliver:
            if not authorize:state['status']='official_upload_not_authorized';save();return state,root
            from crystal_delivery import run as delivery_run
            a=SimpleNamespace(input=str(frozen),stem='model',output=str(root/'delivery_run'),notes=str(root/'reviewer_notes.json'),platon=cfg['platon'],renderer=cfg['renderer'],powershell=cfg.get('powershell'),soffice=cfg.get('soffice'),pdftoppm=cfg['pdftoppm'],authorize_iucr_upload=True,official_cache=official_cache,local_cache=state.get('local_validation_directory',str(root/'local_validation')),timeout=cfg.get('timeout',180),metadata_source=None,pairing_evidence=None)
            def deliver_run():
                with contextlib.redirect_stdout(io.StringIO()) as out:rc=delivery_run(a)
                if rc:raise ValueError('Delivery failed; see '+str(root/'delivery_run/result.json')+' '+out.getvalue())
                return json.loads((root/'delivery_run/result.json').read_text(encoding='utf-8'))
            result=step('official_and_bilingual_delivery',deliver_run)
            state.update(delivery=str(root/'delivery_run/delivery'),completion=result.get('completion'),structure_viewer=result.get('structure_viewer'),status=result['status'],official_counts=result['official']['counts'],AB_alerts=result['AB_alerts'],render_manifest=str(root/'delivery_run/qa/render_manifest.json'),official_pages_manifest=str(root/'delivery_run/qa/official_pages_manifest.json'))
        state['source_unchanged']=all(sha(v)==audit['source_sha256'][ext] for ext,v in audit['files'].items())
        if not state['source_unchanged']:raise ValueError('Source bundle changed during routine finish')
        state['finished_at']=utc_now();save();return state,root
    except Exception as exc:
        state.update(status='failed',failure=str(exc),finished_at=utc_now());save();decision_packet([],root,str(exc));return state,root

def compact(state,root):
    return {k:state[k] for k in ['status','phase','metrics','local_counts','official_counts','AB_alerts','weights','failure','render_manifest','official_pages_manifest','routine_consistency','structure_viewer'] if k in state}|{'output':str(root),'full_record':str(root/'state.json'),'decision_packet':str(root/'decision_packet.json') if (root/'decision_packet.json').exists() else None,'AI_calls':0}

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--config',required=True);p.add_argument('--output',required=True);p.add_argument('--deliver',action='store_true',default=True);p.add_argument('--local-only',dest='deliver',action='store_false');p.add_argument('--authorize-iucr-upload',action='store_true');p.add_argument('--official-cache')
    a=p.parse_args();state,root=finish(a.config,a.output,a.deliver,a.authorize_iucr_upload,a.official_cache);print(json.dumps(compact(state,root),ensure_ascii=False));return 1 if state['status']=='failed' else 0
if __name__=='__main__':sys.exit(main())
