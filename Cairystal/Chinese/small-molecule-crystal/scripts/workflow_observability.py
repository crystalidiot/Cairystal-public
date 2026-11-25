"""Reason-coded handoff intervals. Waiting is never reported as AI/token time."""
from datetime import datetime, timezone
import hashlib
import json

REASONS = {
    'chemical_assignment': ('元素、连接或质子化待判断', 'Inspect current-model decision queue'),
    'candidate_selection': ('候选模型或空间群待比较', 'Compare evidence for current candidates'),
    'disorder_model': ('无序或特殊位置待比较', 'Compare complete components and occupancy'),
    'model_review': ('结构证据待复核', 'Inspect atom-specific findings'),
    'solver_fallback': ('备用求解待核查', 'Inspect solver output'),
    'report_review': ('报告检查未通过', 'Inspect failed report checks'),
    'upload_consent': ('官网上传授权待核对', 'Reuse applicable consent or ask once'),
    'environment_or_execution': ('程序或环境报错', 'Inspect exact error/log'),
    'input_or_version_changed': ('输入或版本指纹变化', 'Verify current input/version'),
    'uncertain_action': ('中断操作结果待确认', 'Recover checkpoint without replay'),
    'diagnostic_unavailable': ('初解检查未生成', 'Resolve the diagnostic failure'),
    'unclassified': ('尚未分类', 'Preserve original category and evidence'),
}

def now():
    return datetime.now(timezone.utc).isoformat()

def elapsed(start, end):
    try:
        value = (datetime.fromisoformat(end) - datetime.fromisoformat(start)).total_seconds()
        return round(value, 6) if value >= 0 else None
    except (ValueError, TypeError):
        return None

def classify(packet):
    category = packet.get('category')
    fixed = {'chemical_graph_required':'chemical_assignment', 'solver_fallback_review':'solver_fallback',
             'report_review':'report_review', 'upload_authorization_required':'upload_consent',
             'execution_error':'environment_or_execution', 'integrity_error':'input_or_version_changed',
             'interrupted_action':'uncertain_action', 'initial_model_review_unavailable':'diagnostic_unavailable'}
    if category in fixed:
        return fixed[category]
    if category == 'scientific_decision':
        models = packet.get('first_models') or []
        if len(models) > 1:
            return 'candidate_selection'
        queues = [q for m in models for q in m.get('decision_queue', [])]
        if any(q.get('problem') in {'disorder_or_motion', 'occupancy_or_symmetry'} for q in queues):
            return 'disorder_model'
        return 'model_review'
    return 'unclassified'

def close_wait(state, action, at=None):
    at = at or now()
    for item in reversed(state.get('wait_episodes', [])):
        if item['status'] == 'open':
            item.update(status='closed', ended_at=at, resume_action=action,
                        duration_s=elapsed(item['started_at'], at))
            return item
    return None

def record_wait(state, packet, at=None):
    at = at or now()
    code = classify(packet)
    # Hash meaningful checkpoint evidence, excluding runtime timestamps/support paths.
    evidence = {k:packet.get(k) for k in ['category','reason','pipeline_status','first_models','AB_alerts','pipeline_failure']}
    evidence['last_action'] = {k:(packet.get('last_action') or {}).get(k) for k in ['action','status','returncode']}
    signature = hashlib.sha256(json.dumps(evidence,sort_keys=True,default=str).encode()).hexdigest()
    episodes = state.setdefault('wait_episodes', [])
    if episodes and episodes[-1]['status']=='open' and episodes[-1]['evidence_sha256']==signature:
        item=episodes[-1];item['observations']+=1;item['last_seen_at']=at
        return item
    close_wait(state, 'evidence_or_reason_changed', at)
    item={'id':len(episodes)+1, 'reason_code':code, 'reason_zh':REASONS[code][0],
          'original_category':packet.get('category'), 'detail':packet.get('reason'),
          'owner':(packet.get('next_step') or {}).get('owner'), 'evidence_sha256':signature,
          'started_at':at, 'last_seen_at':at, 'ended_at':None, 'duration_s':None,
          'status':'open', 'observations':1,
          'time_scope':'Elapsed handoff interval; includes waiting/offline work, not measured AI time.'}
    episodes.append(item)
    return item

def summarize_waits(state, at=None):
    at=at or now();groups={};rows=[]
    for original in state.get('wait_episodes', []):
        row=dict(original)
        row['open_age_s']=elapsed(row['started_at'],at) if row['status']=='open' else None
        rows.append(row)
        group=groups.setdefault(row['reason_code'], {'reason_code':row['reason_code'],
            'reason_zh':row['reason_zh'],'episodes':0,'repeated_observations':0,
            'closed_seconds':0.0,'open_episodes':0,'unknown_durations':0})
        group['episodes']+=1;group['repeated_observations']+=max(0,row['observations']-1)
        if row['status']=='open':group['open_episodes']+=1
        elif row['duration_s'] is None:group['unknown_durations']+=1
        else:group['closed_seconds']+=row['duration_s']
    ranked=sorted(groups.values(),key=lambda g:(-g['closed_seconds'],-g['episodes'],g['reason_code']))
    return {'schema':1,'status':'recorded' if rows else 'not_recorded', 'episodes':rows,
            'by_reason':ranked, 'priority_reasons':ranked[:3], 'AI_time_s':None,'token_count':None,
            'scope':'Closed handoff intervals only. Open waits are separate; no historical gaps inferred; do not add nested pipeline time.'}
