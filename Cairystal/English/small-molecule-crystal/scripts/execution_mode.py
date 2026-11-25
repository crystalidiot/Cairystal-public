"""Opt-in working-model policy. Standard scientific checks stay the default.

The fast shift limit is an engineering stopping rule for a provisional model,
not a validation threshold endorsed by IUCr and not a statement of accuracy.
"""
import math

STANDARD = 'standard'
FAST = 'fast'
MODES = (STANDARD, FAST)
FAST_SHIFT_LIMIT = .1
CONVERGENCE_REASON = 'Not converged to the review threshold max shift/esd <= 0.01'


def mode(value=STANDARD):
    if value not in MODES:
        raise ValueError('execution_mode must be standard or fast')
    return value


def options(cfg):
    """Return effective settings, preserving input and existing authorization."""
    result = dict(cfg)
    selected = mode(cfg.get('execution_mode', STANDARD))
    result['execution_mode'] = selected
    if selected == FAST:
        for key, limit in [('max_candidates', 2), ('max_weight_updates', 1)]:
            value = cfg.get(key, limit)
            if type(value) is not int or value < (1 if key == 'max_candidates' else 0):
                raise ValueError('Invalid fast-mode budget: '+key)
            result[key] = min(value, limit)
    return result


def gate_reasons(gate, selected=STANDARD):
    """Only a measured small final shift may be deferred. Never hide NPD/control errors."""
    selected = mode(selected)
    reasons = list(gate.get('review_reasons', []))
    metrics = gate.get('metrics', {})
    shift = metrics.get('last_abs_max_shift_esd')
    if (selected == FAST and gate.get('execution_complete') is True
            and type(metrics.get('NPD_atoms')) is int and metrics['NPD_atoms'] == 0
            and type(shift) in (float, int) and math.isfinite(shift)
            and 0 <= shift <= FAST_SHIFT_LIMIT):
        return [r for r in reasons if r != CONVERGENCE_REASON]
    return reasons


def automatic_repairs(selected=STANDARD):
    return mode(selected) == STANDARD


def weight_stop_blocks(stop, selected=STANDARD):
    return stop != 'coefficients_stable' and mode(selected) == STANDARD


def annotate_notes(notes, state):
    """Keep provisional status in both human reports, even if there are no AB alerts."""
    if mode(state.get('execution_mode', STANDARD)) != FAST:
        return notes
    notes['provisional'] = True
    weight = state.get('weights', {}).get('status')
    updates = len(state.get('weight_trials', []))
    notes['zh']['summary'] = '快速候选模型（供查看，非充分精修定稿）。' + notes['zh']['summary']
    notes['en']['summary'] = 'Fast candidate model (provisional, not an exhaustively refined final model). ' + notes['en']['summary']
    notes['zh']['limitations'] += ' 本次使用快速模式：最多一轮权重更新，不自动逐项追消 AB 警告；余留问题和原始数值完整保留。收敛停止条件可放宽至最大位移/标准不确定度 0.1；这不是结构正确性保证或发表标准。'
    notes['en']['limitations'] += ' Fast mode allows at most one weight update and defers automatic AB repair trials. All remaining findings and measured values are retained. A maximum shift/s.u. up to 0.1 may be tolerated for this provisional model; this is neither proof of correctness nor a publication criterion.'
    if not updates and weight != 'coefficients_stable':
        notes['zh']['methods'] = notes['zh']['methods'].replace('权重系数已稳定，本次未继续迭代。', '本次未更新权重；建议系数尚未确认稳定，见限制说明。')
        notes['en']['methods'] = notes['en']['methods'].replace('The weight coefficients were already stable; no further iteration was performed.', 'No weight update was performed; coefficient stability has not been established.')
    notes.setdefault('audit_records', {})['execution_mode'] = FAST
    return notes


def preview_record(selected, local, state, started):
    """Local artifact receipt precedes optional network/Word work; no fake final files."""
    from pathlib import Path
    from crystal_runtime import sha, utc_now
    import time
    folder = Path(selected)
    return {'schema': 1, 'status': 'provisional_model_available', 'execution_mode': FAST,
            'at': utc_now(), 'seconds_to_local_model': round(time.perf_counter()-started, 4),
            'files': {ext: {'path': str(folder/('model.'+ext)), 'sha256': sha(folder/('model.'+ext))}
                      for ext in ['res','hkl','cif','fcf']},
            'metrics': state.get('metrics'), 'weights': state.get('weights'),
            'local_validation_available': local.get('available', True),
            'alerts': (local.get('alerts') or {}).get('alerts'),
            'deferred': ['automatic_AB_repair_trials', 'exhaustive_disorder_search'],
            'official_report': 'not_yet_obtained', 'bilingual_word': 'not_yet_generated',
            'scientific_acceptance': 'not_established',
            'scope': 'Local working-model milestone only; inspect final state for subsequent report delivery.'}


def live_preview(run):
    """Expose the local milestone while official/Word stages are still running."""
    import json
    from pathlib import Path
    from pipeline_intake import unlinked
    from crystal_runtime import sha
    root=unlinked(run)
    receipt=root/'pipeline/auto_finish/fast_preview.json'
    if not receipt.is_file():return None
    try:
        value=json.loads(unlinked(receipt).read_text('utf-8'))
        if value.get('execution_mode')!=FAST or value.get('status')!='provisional_model_available':return None
        folder=receipt.parent/'frozen'
        for ext in ['res','hkl','cif','fcf']:
            item=value['files'][ext];target=unlinked(item['path'])
            if target!=folder/('model.'+ext) or sha(target)!=item['sha256']:return None
        return value
    except (OSError,ValueError,KeyError,TypeError):
        return None  # A partial write or changed artifact is not an available verified preview.
