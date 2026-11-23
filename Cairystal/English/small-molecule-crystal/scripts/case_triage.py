"""Read-only diagnostic packets and a small, advisory historical route prior.

No network, LLM, model coordinates, atom reassignment or refinement mutations.
Historical actions are weak labels, not proof that an action was appropriate.
"""
import argparse, collections, hashlib, json, re, time
from pathlib import Path

METADATA_CODES = {'183', '184', '185', '196', '197', '198', '699'}
FAMILIES = {
 'symmetry': ('空间群/设置核对', 'symmetry-and-twins.md', r'centric|symmetr|twin|p21c|c2c|amm2|p1_'),
 'elements': ('元素与化学连接核对', 'chemical-model-and-density.md', r'typ|reassign|element|nitro|aryl_c|ring_n|cno_|amine_n|imidazole|triazole|perchlorate|ammonium|oxo|cage_n'),
 'hydrogens': ('加氢、质子化与方向核对', 'hydrogen-and-report-rules.md', r'hydrogen|proton|(?:^|_)h(?:_|$)|ch2|methyl|nh2|aromatic|ionic_h'),
 'water': ('水分子身份与氢方向核对', 'hydrogen-and-report-rules.md', r'water'),
 'solvent_disorder': ('溶剂、无序与占有率核对', 'disorder-occupancy.md', r'solvent|disorder|split|dmf|dcm|occup|void|fraction|special'),
 'adp': ('热参数、几何限制与参数可辨识性', 'adp-model-selection.md', r'aniso|(?:^|_)ani(?:_|$)|(?:^|_)iso(?:_|$)|rigu|simu|isor|rigid|geometry'),
 'weights': ('权重与收敛核对', 'nonconvergence.md', r'weight|wght|conver'),
 'composition': ('UNIT、化学式与Z的一致性审计', 'restraint-and-accounting-audit.md', r'unit|formula|normaliz|element_labels'),
 'data': ('数据、异常反射与系统误差诊断', 'systematic-error-diagnostics.md', r'exti|extinct|omit|reflection'),
}
ALERT_ROUTES = {
 '080':['weights'], '211':['adp','elements'], '212':['adp','elements'],
 '213':['adp','solvent_disorder'], '214':['adp','solvent_disorder'],
 '234':['elements','solvent_disorder','adp'], '241':['elements','solvent_disorder'],
 '242':['elements','solvent_disorder'], '260':['hydrogens','adp'],
 '306':['water'], '315':['solvent_disorder'], '420':['hydrogens'], '430':['hydrogens'],
 '919':['data'], '934':['data'], '939':['data','weights'],
 '910':['data'], '911':['data'], '912':['data'],
 **{str(x):['data'] for x in range(920,929)},
}

def sha(path): return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def write(path, value):
    p=Path(path);p.parent.mkdir(parents=True,exist_ok=True)
    if p.exists(): raise ValueError('Refusing to overwrite '+str(p))
    p.write_text(json.dumps(value,ensure_ascii=False,indent=2),encoding='utf-8')

def action_families(record):
    """Weak labels derived only from names of historical attempted stages."""
    labels=set()
    for trial in record.get('trials',[])+record.get('round_trials',[]):
        name=trial.get('name','').lower()
        for family,(_,_,pattern) in FAMILIES.items():
            if re.search(pattern,name): labels.add(family)
    return sorted(labels)

def fit(records):
    global_counts=collections.Counter();by_category={}
    for r in records:
        labels=action_families(r);global_counts.update(labels)
        entry=by_category.setdefault(r['category'],{'n':0,'family_counts':collections.Counter()})
        entry['n']+=1;entry['family_counts'].update(labels)
    return {'schema':1,'kind':'smoothed_historical_action_frequency',
      'n':len(records),'global_counts':dict(global_counts),'categories':by_category,
      'smoothing_case_equivalents':2,'features':['category'],
      'labels':'Attempted diagnostic families inferred from stage names; not correct actions or verified structures.',
      'limitations':['Small, retrospective sample. Earlier conversation exposure remains.',
       'Only ranks optional diagnostics; cannot authorize atom, occupancy, reflection or symmetry changes.',
       'No neural weights, reference identities, atomic coordinates, exact cells or case IDs are stored.']}

def rank(prior,category,global_only=False):
    group=prior['categories'].get(category,{'n':0,'family_counts':{}})
    n=0 if global_only else group['n'];alpha=prior['smoothing_case_equivalents']
    result=[]
    for family in FAMILIES:
        global_rate=prior['global_counts'].get(family,0)/max(1,prior['n'])
        local=0 if global_only else group['family_counts'].get(family,0)
        result.append({'family':family,'historical_frequency_score':round((local+alpha*global_rate)/(n+alpha),6),
                       'category_support_cases':n,'category_attempted_cases':local})
    return sorted(result,key=lambda x:(-x['historical_frequency_score'],x['family']))

def metric_aliases(metrics):
    m=dict(metrics or {})
    for a,b in [('R1','R1_observed'),('GoF','GooF'),('last_abs_max_shift_esd','max_shift_esd')]:
        if a in m and b not in m:m[b]=m[a]
    return {k:m.get(k) for k in ['R1_observed','R1_all','wR2','GooF','difference_density_max',
      'difference_density_min','max_shift_esd','NPD_atoms']}

def packet(record,prior,evidence_path=None,gate=None):
    start=time.perf_counter();m=metric_aliases(record.get('metrics'))
    raw=record.get('major_alerts')
    alerts=list(raw or []);ab=[dict(a) for a in alerts if a.get('level') in ('A','B')]
    for a in ab:a['code']=str(a.get('code','')).zfill(3)
    metadata=[a for a in ab if a['code'] in METADATA_CODES]
    scientific=[a for a in ab if a['code'] not in METADATA_CODES]
    unknown=[a for a in scientific if a['code'] not in ALERT_ROUTES]
    reasons=[];status=record.get('status','unknown')
    if status!='candidate_completed':reasons.append('历史模型状态不是候选完成；零A/B不能替代模型完整性审查。')
    if raw is None:reasons.append('缺少验证警告清单；不得将缺失当作零警告。')
    if any(m[k] is None for k in ('R1_observed','wR2','GooF','max_shift_esd','NPD_atoms')):
        reasons.append('关键精修指标缺失，需查原始LST/运行完成证据。')
    if m['NPD_atoms'] is not None and m['NPD_atoms']>0:reasons.append('存在NPD；先查模型、占有率和参数可辨识性。')
    if m['max_shift_esd'] is not None and abs(m['max_shift_esd'])>0.01:reasons.append('最大shift/esd超过0.01，需确认真实收敛。')
    if scientific:reasons.append('仍有结构/数据类A/B，必须逐项诊断。')
    if unknown:reasons.append('有本脚本未覆盖的警告；交给现有知识检索或人工/AI判断。')
    if gate:
        if not gate.get('execution_complete'):reasons.append('新运行未正常完成，不能引用其拟合指标宣称成功。')
        reasons.extend(gate.get('failures',[]));reasons.extend(gate.get('review_reasons',[]))
    priority=[]
    for a in scientific:
        for family in ALERT_ROUTES.get(a['code'],[]):
            if family not in priority:priority.append(family)
    if (m['NPD_atoms'] or 0)>0:
        priority=[x for x in ['adp','elements','solvent_disorder'] if x not in priority]+priority
    advisory=rank(prior,record.get('category'))[:3]
    routes=[{'family':f,'title':FAMILIES[f][0],'reference':'references/'+FAMILIES[f][1],
             'basis':'current_alert_or_numerical_evidence','automatic_model_change':False} for f in priority]
    # Keep exact alert instances (including atom names); never deduplicate by code.
    result={'schema':1,'case_id':record.get('case_id'),'category':record.get('category'),
       'historical_status':status,'metrics':m,'AB_counts':dict(collections.Counter(a['level'] for a in ab)),
       'model_data_AB':scientific,'experimental_metadata_AB':metadata,
       'unmapped_AB':unknown,'requires_scientific_review':bool(reasons),'review_reasons':reasons,
       'evidence_routes':routes,'advisory_historical_routes':advisory,
       'unresolved':record.get('unresolved',[]),'failure_analysis':record.get('failure_analysis'),
       'evidence_file':str(evidence_path) if evidence_path else None,
       'model_change_permitted':False,'scientific_correctness':'not_established',
       'official_iucr_report':record.get('official_iucr_report',False),
       'remaining_delivery_gates':['化学、对称性、无序/占有率审查','配套CIF/FCF重新验证','授权范围内IUCr官网验证','中英文Word与产物一致性复核'],
       'scope':'Read-only triage; not acceptance, solution, refinement or an official report.'}
    result['elapsed_ms']=round((time.perf_counter()-start)*1000,3)
    return result

def brief(value):
    """Smaller presentation, retaining each warning and all scientific caveats."""
    m=value['metrics'];lines=[f"{value['case_id']} | {value['category']} | {value['historical_status']}",
      '质量指标 '+json.dumps(m,ensure_ascii=False,separators=(',',':')),
      '结构正确性未确认；此摘要不接受/修改模型。']
    for key,label in [('model_data_AB','结构/数据A/B'),('experimental_metadata_AB','实验参数A/B')]:
        lines.append(label+f" ({len(value[key])})")
        lines.extend(f"{a['code']}_ALERT_{a.get('type')}_{a['level']} {a.get('text','')}" for a in value[key])
    if value['review_reasons']:lines.append('待审查：'+'；'.join(value['review_reasons']))
    if value['evidence_routes']:
        lines.append('证据优先路线：'+'；'.join(f"{r['title']} [{r['reference']}]" for r in value['evidence_routes']))
    lines.append('历史路线仅供排序：'+'、'.join(FAMILIES[r['family']][0] for r in value['advisory_historical_routes']))
    if value['unresolved']:lines.append('未解决：'+json.dumps(value['unresolved'],ensure_ascii=False,separators=(',',':')))
    if value['failure_analysis']:lines.append('失败证据：'+json.dumps(value['failure_analysis'],ensure_ascii=False,separators=(',',':')))
    lines.append('原始证据：'+str(value['evidence_file']))
    lines.append('仍需：化学/对称/占有率审查、配套CIF/FCF、IUCr官网验证、中英文Word；本摘要不替代这些步骤。')
    return '\n'.join(lines)+'\n'

def main():
    p=argparse.ArgumentParser(description=__doc__);s=p.add_subparsers(dest='command',required=True)
    a=s.add_parser('fit');a.add_argument('--training',required=True);a.add_argument('--output',required=True)
    a=s.add_parser('triage');a.add_argument('--record',required=True);a.add_argument('--prior',required=True);a.add_argument('--output',required=True)
    a=p.parse_args()
    if a.command=='fit':
        data=json.loads(Path(a.training).read_text(encoding='utf-8-sig'));v=fit(data['cases']);write(a.output,v)
        print(json.dumps({'training_cases':v['n'],'model_sha256':sha(a.output),'output':a.output}))
    else:
        r=json.loads(Path(a.record).read_text(encoding='utf-8-sig'));prior=json.loads(Path(a.prior).read_text(encoding='utf-8-sig'))
        v=packet(r,prior,a.record);write(a.output,v);print(brief(v))
if __name__=='__main__':main()
