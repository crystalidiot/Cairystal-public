"""Read-only arithmetic and SHELX control checks. No model edits or LLM calls."""
import argparse
from collections import Counter
import json
import math
from pathlib import Path
import re
import time

import gemmi
from audit_occupancy import CARDS
from crystal_runtime import regular, sha, utc_now

NUM = r'[+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:\(\d+\))?(?:[Ee][+-]?\d+)?'
CELL_TAGS = ['_cell_length_a', '_cell_length_b', '_cell_length_c',
             '_cell_angle_alpha', '_cell_angle_beta', '_cell_angle_gamma']


def parse_formula(text):
    """Only a flat CIF sum formula; no guessed parentheses, charge or adducts."""
    if not text or text in {'?', '.'}:
        raise ValueError('Formula sum is missing')
    # Ignore whitespace between element tokens, but not inside a numeric count.
    pattern = re.compile(r'\s*([A-Z][a-z]?)(\d+(?:\.\d+)?|\.\d+)?')
    counts = Counter(); pos = 0
    while pos < len(text):
        if not text[pos:].strip(): break
        m = pattern.match(text, pos)
        if not m: raise ValueError('Unsupported formula syntax near '+repr(text[pos:pos+24]))
        element = gemmi.Element(m[1])
        if element.atomic_number == 0 or element.name != m[1]:
            raise ValueError('Unrecognized element: '+m[1])
        count = float(m[2]) if m[2] else 1.0
        if not math.isfinite(count) or count <= 0: raise ValueError('Nonpositive/nonfinite element count')
        counts[m[1]] += count; pos = m.end()
    if not counts: raise ValueError('Empty formula')
    return dict(counts)


def active_records(text):
    """Respect END, comments and continuation; never follow include paths."""
    result = []; pending = ''; start = None
    for number, raw in enumerate(text.splitlines(), 1):
        if not pending and raw[:1].isspace(): continue  # standalone indented SHELX comments
        line = raw.split('!', 1)[0].rstrip()
        if not line.strip(): continue
        if pending: line = pending+' '+line.strip()
        else: start = number
        if line.endswith('='):
            pending = line[:-1]; continue
        pending = ''; fields = line.split()
        if fields[0].upper() == 'END': break
        if fields[0].upper() not in {'TITL', 'REM'}: result.append((start, fields))
    if pending: raise ValueError('Unfinished SHELX continuation')
    return result


def issue(items, code, severity, zh, evidence=None):
    items.append({'code':code, 'severity':severity, 'message_zh':zh, 'evidence':evidence})


def check_instructions(text):
    issues = []
    try: rows = active_records(text)
    except ValueError as exc:
        issue(issues, 'SHELX_PARSE', 'error', 'SHELX 续行不完整。', str(exc))
        return {'status':'failed', 'issues':issues, 'checks':[], 'active_records':[]}
    by = {}
    for line, fields in rows: by.setdefault(fields[0].upper().split('_')[0], []).append((line, fields))
    checks = []
    if any(f[0].startswith(('+', '@')) for _, f in rows):
        issue(issues, 'INCLUDE_NOT_READ', 'review', '含外部指令文件；未读取或展开，指令检查不完整。')
    if 'FRAG' in by: issue(issues, 'FRAG_SCOPE', 'review', 'FRAG 模板需要专门解析；未将模板内容当作最终原子模型。')
    if 'EXTI' in by and 'SWAT' in by:
        issue(issues, 'EXTI_SWAT_CONFLICT', 'error', 'EXTI 与 SWAT 同时出现；必须检查模型意图，不能直接并用。', {'EXTI':by['EXTI'], 'SWAT':by['SWAT']})
    list_rows = by.get('LIST', [])
    values = [f[1:] for _, f in list_rows]
    if not values and 'ACTA' in by:
        checks.append({'code':'LIST4', 'status':'passed', 'basis':'ACTA implies LIST 4 when LIST is absent'})
    elif values == [['4']]: checks.append({'code':'LIST4', 'status':'passed', 'basis':'explicit LIST 4'})
    else: issue(issues, 'LIST4_REVIEW', 'review', '未能确认唯一有效的 LIST 4 输出设置。', values)
    omissions = []; unexpanded = []
    for line, f in by.get('OMIT', []):
        if len(f) == 4 and all(re.fullmatch(r'[+-]?\d+', v) for v in f[1:]):
            omissions.append(tuple(map(int, f[1:])))
        else: unexpanded.append({'line':line, 'record':f})
    duplicates = [{'hkl':list(k), 'occurrences':v} for k,v in Counter(omissions).items() if v>1]
    if duplicates: issue(issues, 'DUPLICATE_OMIT', 'review', '发现重复的显式 OMIT 指标；未去重或删点。', duplicates)
    if unexpanded: issue(issues, 'OMIT_SCOPE', 'review', '含角度/阈值/其他 OMIT 形式；不能用显式指标数代表实际剔除数。', unexpanded)
    checks.append({'code':'OMIT_INVENTORY', 'status':'recorded', 'explicit_records':len(omissions),
                   'distinct_literal_hkl':len(set(omissions)), 'other_forms':unexpanded,
                   'coverage_not_computed':True, 'symmetry_equivalents_not_merged':True})
    # SAME hydrogen checks are only inferred from actual simple-SFAC atom records.
    sfacs = by.get('SFAC', [])
    valid = len(sfacs)==1 and all(re.fullmatch(r'[A-Z][a-z]?', e) and gemmi.Element(e).atomic_number for e in sfacs[0][1][1:])
    types = {}
    if valid and 'FRAG' not in by:
        sfac = sfacs[0][1][1:]
        for _, f in rows:
            if f[0].upper().split('_')[0] in CARDS or len(f)<7: continue
            try:
                idx=int(f[1]); [float(x) for x in f[2:7]]
                if 1<=idx<=len(sfac): types.setdefault(f[0].upper(),set()).add(sfac[idx-1])
            except ValueError: pass
    for line, f in by.get('SAME', []):
        hydrogens = [a for a in f[1:] if types.get(a.upper().split('_')[0]) and types[a.upper().split('_')[0]] <= {'H','D'}]
        if hydrogens:
            issue(issues, 'SAME_IGNORES_H', 'review', 'SAME 中列出的氢不受该指令约束；检查是否误以为已限制水氢。', {'line':line,'hydrogens':hydrogens,'record':f})
        checks.append({'code':'SAME_MAPPING', 'status':'not_evaluated', 'line':line,
                       'reason':'Chemical correspondence, connectivity and residue-specific expansion need review'})
        issue(issues, 'SAME_MAPPING_REVIEW', 'review', 'SAME 的原子对应关系尚未自动验证。', {'line':line,'record':f})
    for card in ['CHIV','FLAT']:
        if card in by: checks.append({'code':card+'_SCOPE', 'status':'not_evaluated', 'records':by[card], 'reason':'No chemical planarity or stereochemistry inferred'})
    return {'status':'failed' if any(i['severity']=='error' for i in issues) else 'needs_review' if issues else 'checks_passed',
            'issues':issues, 'checks':checks, 'active_records':[{'line':n,'fields':f} for n,f in rows if f[0].upper().split('_')[0] in {'EXTI','SWAT','LIST','ACTA','OMIT','SAME','CHIV','FLAT','WGHT'}]}


def check_cif(block, native_text=''):
    issues=[]; checks=[]; values={}; computed={}
    def value(tag):
        raw=block.find_value(tag)
        if raw is None or raw in {'?','.'}: return None
        return gemmi.cif.as_string(raw)
    def numeric(tag, positive=False):
        raw=value(tag); values[tag]=raw
        if raw is None:
            issue(issues,'MISSING_VALUE','review','缺少数值，未编造或补写。',{'tag':tag});return None
        if not re.fullmatch(NUM,raw):
            issue(issues,'INVALID_NUMBER','error','CIF 数值格式无效。',{'tag':tag,'value':raw});return None
        n=gemmi.cif.as_number(raw)
        if not math.isfinite(n) or (positive and n<=0):
            issue(issues,'INVALID_NUMBER','error','CIF 数值不在有效范围。',{'tag':tag,'value':raw});return None
        return n
    def compare(code, actual, expected, tolerance, severity='error', basis=None):
        if actual is None or expected is None: return
        delta=actual-expected
        checks.append({'code':code,'status':'passed' if abs(delta)<=tolerance else 'mismatch',
                       'reported':actual,'calculated':expected,'difference':delta,'tolerance':tolerance,'basis':basis})
        if abs(delta)>tolerance: issue(issues,code,severity,'数值不一致，需要核对来源；未自动修正。',checks[-1])
    formula=value('_chemical_formula_sum'); values['_chemical_formula_sum']=formula
    try:
        counts=parse_formula(formula);computed['formula_counts']=counts
        computed['formula_weight']=sum(gemmi.Element(e).weight*n for e,n in counts.items())
        computed['formula_electrons']=sum(gemmi.Element(e).atomic_number*n for e,n in counts.items())
    except ValueError as exc:
        issue(issues,'FORMULA_UNSUPPORTED','review','分子式缺失或超出简单元素计数语法，未猜测展开。',str(exc));counts=None
    cell=[numeric(t,True) for t in CELL_TAGS]
    volume=numeric('_cell_volume',True);z=numeric('_cell_formula_units_Z',True)
    mr=numeric('_chemical_formula_weight',True);density=numeric('_exptl_crystal_density_diffrn',True)
    f000=numeric('_exptl_crystal_F_000')
    if all(x is not None for x in cell):
        a,b,c,alpha,beta,gamma=cell
        cosines=[math.cos(math.radians(t)) for t in cell[3:]]
        ca,cb,cg=cosines;factor=1+2*ca*cb*cg-ca*ca-cb*cb-cg*cg
        if any(t>=180 for t in cell[3:]) or factor<=0:
            issue(issues,'INVALID_CELL','error','晶胞度量不是有效的正定晶胞。',cell)
        else:
            computed['cell_volume']=a*b*c*math.sqrt(factor)
            compare('CELL_VOLUME',volume,computed['cell_volume'],max(.02,.001*computed['cell_volume']))
    compare('FORMULA_WEIGHT',mr,computed.get('formula_weight'),max(.05,.0005*computed.get('formula_weight',0)),basis='Gemmi standard atomic weights; explicit D supported, isotope/charge notation not guessed')
    if all(x is not None for x in [volume,z,mr]):
        computed['density_from_reported_Mr']=1.66053906660*z*mr/volume
        compare('DENSITY',density,computed['density_from_reported_Mr'],max(.002,.002*computed['density_from_reported_Mr']),basis='Reported formula weight, Z and cell volume')
    tags=[]
    for item in block:
        if item.pair: tags.append(item.pair[0].lower())
        if item.loop: tags.extend(t.lower() for t in item.loop.tags)
    special=any(t.startswith(('_platon_squeeze','_smtbx_masks','_olex2_solvent')) for t in tags)
    try:
        native=active_records(native_text) if native_text else []
        special=special or any(f[0].upper() in {'ABIN','SWAT','DISP','NEUT'} or (f[0].upper()=='SFAC' and len(f)>2 and any(re.search(r'\d',s) for s in f[1:])) for _,f in native)
    except ValueError: special=True
    if f000 is not None and f000<0: issue(issues,'INVALID_F000','error','F(000) 不应为负。',f000)
    if counts and z is not None:
        computed['neutral_electron_F000']=z*computed['formula_electrons']
        if special: issue(issues,'F000_CONVENTION','review','检测到掩膜/特殊散射/溶剂项；未把简单电子计数当作 F(000) 的确定标准。')
        else: compare('F000_ELECTRON_COUNT',f000,computed['neutral_electron_F000'],max(.51,.0005*computed['neutral_electron_F000']),severity='review',basis='Neutral-atom electron count only; a mismatch needs the actual scattering/mask convention checked')
    return {'issues':issues,'checks':checks,'reported':values,'computed':computed,
            'limits':['Internal arithmetic only; no atomic identity or composition established',
                      'Not a coordinate/orbit/occupancy audit; use audit_occupancy and paired_bundle',
                      'Numerical tolerances are screening thresholds, not experimental uncertainties']}


def audit_files(cif, res=None):
    started=time.perf_counter();cif=regular(cif);res=regular(res) if res is not None else None
    paths={'cif':cif};
    if res: paths['res']=res
    hashes={k:sha(p) for k,p in paths.items()};issues=[]
    native=res.read_text(encoding='latin1') if res else ''
    result={'schema':1,'created_at':utc_now(),'ai_calls':0,'inputs':{k:{'path':str(p),'sha256':hashes[k]} for k,p in paths.items()},'implementation_sha256':sha(__file__)}
    try:
        doc=gemmi.cif.read_file(str(cif))
        if len(doc)!=1: raise ValueError('Exactly one explicitly selected datablock required')
        block=doc.sole_block()
        if not native and block.find_value('_shelx_res_file'):
            native=gemmi.cif.as_string(block.find_value('_shelx_res_file'))
            result['native_source']='embedded_RES'
        elif native:result['native_source']='explicit_RES'
        else:result['native_source']='not_supplied'
        result['cif_checks']=check_cif(block,native);issues.extend(result['cif_checks']['issues'])
        from temperature_consistency import audit_temperature
        result['temperature_checks']=audit_temperature(block,native)
        result['temperature_checks']['implementation_sha256']=sha(Path(__file__).with_name('temperature_consistency.py'))
        issues.extend(result['temperature_checks']['issues'])
    except (ValueError,RuntimeError) as exc:
        issue(issues,'CIF_PARSE','error','CIF 无法完成指定数据块检查。',str(exc))
    if native:
        result['instruction_checks']=check_instructions(native);issues.extend(result['instruction_checks']['issues'])
    else:result['instruction_checks']={'status':'not_evaluated','reason':'No RES supplied or embedded'}
    unchanged=all(sha(p)==hashes[k] for k,p in paths.items())
    if not unchanged:issue(issues,'INPUT_CHANGED','error','检查期间输入文件哈希改变。')
    result.update(issues=issues,inputs_unchanged=unchanged,seconds=round(time.perf_counter()-started,6),
                  status='failed' if any(i['severity']=='error' for i in issues) else 'needs_review' if issues else 'checks_passed')
    return result


def require_consistency(report, automatic=False):
    """Definite contradictions stop delivery; uncertain checks stop auto-acceptance."""
    selected=[i for i in report['issues'] if i['severity']=='error' or automatic]
    if selected:raise ValueError('Routine consistency: '+', '.join(dict.fromkeys(i['code'] for i in selected))+'; see routine_consistency.json')


def summary(report):
    return {'status':report['status'],'issue_codes':list(dict.fromkeys(i['code'] for i in report['issues'])),
            'full_record':'routine_consistency.json'}


def write_audit(report, directory):
    out=Path(directory).absolute()
    if out.exists():raise ValueError('Use a new audit directory')
    # New output may not replace either input; following directory junctions is avoided.
    if any(p.is_symlink() or getattr(p,'is_junction',lambda:False)() for p in out.parents):raise ValueError('Linked output parent unsupported')
    out.mkdir(parents=True)
    (out/'routine_consistency.json').write_text(json.dumps(report,ensure_ascii=False,indent=2,allow_nan=False)+'\n',encoding='utf-8')
    lines=['常规一致性检查：'+report['status'],'输入保持不变：'+str(report['inputs_unchanged']),'AI 调用：0',f"耗时：{report['seconds']:.6f} 秒",'']
    lines += [i['code']+'：'+i['message_zh'] for i in report['issues']] or ['未发现已检查范围内的数值矛盾。']
    lines += ['','只核对数值和指令，不证明结构正确；没有修改模型、反射或原始文件。']
    (out/'检查摘要.txt').write_text('\n'.join(lines)+'\n',encoding='utf-8')


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--cif',required=True,type=Path);p.add_argument('--res',type=Path);p.add_argument('--output',required=True,type=Path)
    a=p.parse_args();report=audit_files(a.cif,a.res);write_audit(report,a.output)
    print(json.dumps({'status':report['status'],'issue_codes':[i['code'] for i in report['issues']],'seconds':report['seconds'],'output':str(a.output),'ai_calls':0},ensure_ascii=False))
    return 1 if report['status']=='failed' else 2 if report['status']=='needs_review' else 0


if __name__=='__main__':raise SystemExit(main())
