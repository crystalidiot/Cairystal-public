"""Classify actual SHELX controls for delivery; never search for or invent twins."""
import math

INVERSION = [-1, 0, 0, 0, -1, 0, 0, 0, -1]


def classify(rows):
    cards = {}
    for row in rows:
        cards.setdefault(row[0].upper(), []).append(row[1:])
    result = {"kind": "ordinary_HKLF4", "supported_for_pairing": True,
              "new_twin_search_requested": False, "scientific_acceptance": False,
              "message_zh": "按普通模型继续；没有证据时不额外搜索孪晶方案。"}

    def decline(reason, message):
        result.update(supported_for_pairing=False, reason=reason, message_zh=message)
        return result

    hkl = cards.get('HKLF', [])
    if len(hkl) != 1 or not hkl[0]:
        return decline('ambiguous_HKLF', '反射格式记录缺失或重复，请核对原生输入。')
    if hkl[0][0] != '4':
        result['kind'] = 'HKLF5_overlap' if hkl[0][0] == '5' else 'unsupported_HKLF'
        return decline('overlap_or_nonstandard_reflection_format',
                       '当前交付核对器只支持 HKLF 4；HKLF 5 的重叠反射需要专用配对核对，不能按普通反射表放行。')
    twin, basf = cards.get('TWIN', []), cards.get('BASF', [])
    if not twin and not basf:
        return result
    try:
        factors = [float(v) for values in basf for v in values]
    except ValueError:
        return decline('invalid_BASF', 'BASF 数值格式无法读取，请检查原生指令。')
    if any(not math.isfinite(v) for v in factors):
        return decline('nonfinite_BASF', 'BASF 含有非有限数值。')
    result['BASF'] = factors
    if not twin:
        result.update(kind='HKLF4_batch_scales', message_zh='BASF 用作 HKLF 4 批次尺度参数，不按孪晶分数处理。')
        if not factors or any(v <= 0 for v in factors):
            return decline('invalid_batch_scale', '批次尺度系数需为有限正数；不会套用孪晶分数的 0–1 限制。')
        return result
    result['kind'] = 'HKLF4_twin'
    if len(twin) != 1 or len(twin[0]) not in {0, 9, 10}:
        return decline('unsupported_twin_syntax', '现有孪晶指令超出已验证的常规双组分格式，请保留模型并核对。')
    try:
        matrix = list(map(float, twin[0][:9])) if twin[0] else INVERSION[:]
        domains = float(twin[0][9]) if len(twin[0]) == 10 else 2
    except ValueError:
        return decline('invalid_twin_values', '孪晶矩阵或组分数无法读取。')
    result.update(matrix=matrix, domains=domains)
    if domains != 2 or len(factors) != 1:
        return decline('unsupported_twin_domains', '当前常规配对支持双组分 HKLF 4 孪晶；其它组分数或缺失 BASF 需单独核对。')
    if any(not math.isfinite(v) or v != int(v) for v in matrix):
        return decline('noninteger_twin_matrix', '非整数孪晶矩阵需核查反射重叠及数据处理方式。')
    square = [sum(matrix[3*i+k]*matrix[3*k+j] for k in range(3)) for i in range(3) for j in range(3)]
    identity = [1, 0, 0, 0, 1, 0, 0, 0, 1]
    if matrix == identity or square != identity:
        return decline('not_two_domain_law', '矩阵不是所支持的两次操作回到原位的双组分孪晶律。')
    # A common negative/over-one refined inversion parameter can be statistically
    # consistent with a boundary. Record it for existing scientific review; file
    # pairing is not a physical-population acceptance or a Flack interpretation.
    result.update(kind='HKLF4_inversion_twin' if matrix == INVERSION else 'HKLF4_two_domain_twin',
                  fraction_outside_unit_interval=not 0 <= factors[0] <= 1,
                  message_zh='现有双组分 HKLF 4 孪晶模型可走自动文件配对；保留孪晶律和 BASF，继续 LIST 4、AB 和官网验证。')
    return result


def check_batch_columns(route, hkl_rows):
    """Do not interpret HKLF5 negative component codes as ordinary batch IDs."""
    batches = {r[5] for r in hkl_rows}
    if any(v < 0 for v in batches):
        raise ValueError('HKLF 4 batch identifiers cannot be negative; overlap/component data require separate pairing')
    if route['kind'] == 'HKLF4_batch_scales' and max(batches) > len(route['BASF']) + 1:
        raise ValueError('HKLF 4 batch identifier exceeds the available BASF scale parameters')
    if route['kind'].endswith('_twin') and max(batches) > 1:
        raise ValueError('Combined twin and multiple batch scaling needs a separate audit; retain all controls and measured data')


def review_priority(route, alert_codes=(), other_evidence=()):
    """Explain when investigation is justified; absence of alerts is not proof."""
    import re
    known = {'033', '107', '108', '109', '850', '930', '931', '987'}
    found = []
    for value in alert_codes:
        match = re.fullmatch(r'(?:PLAT)?(\d{3})(?:_ALERT_\d_[ABCG])?', str(value))
        if match and match[1] in known:
            found.append(str(value))
    active = route['kind'] in {'HKLF4_inversion_twin', 'HKLF4_two_domain_twin', 'HKLF4_twin', 'HKLF5_overlap'}
    already_reported = [code for code in found if active and re.search(r'(?:PLAT)?931(?:_|$)', code)]
    triggers = list(other_evidence) + [code for code in found if code not in already_reported]
    return {'new_twin_search_requested': bool(triggers), 'existing_model_treatment': active,
            'triggers': triggers, 'reported_existing_twin_alerts': already_reported, 'no_alert_is_not_exclusion': True,
            'action': 'review_actual_evidence' if triggers else 'preserve_existing_model_and_continue' if active else 'ordinary_refinement_continue'}
