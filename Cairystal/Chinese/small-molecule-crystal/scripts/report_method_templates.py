"""Bilingual method statements grounded in actual final RES instructions."""
from collections import Counter
from crystal_runtime import records
from audit_occupancy import CARDS
import json,re

def narrative_digest(scalars):
    """Keep exact source text in the audit; render only supported bilingual facts."""
    originals={tag:scalars[tag] for tag in ('_publ_section_exptl_refinement','_exptl_absorpt_special_details') if scalars.get(tag)}
    decoded={}
    prefix='Original Unicode narrative as a JSON string with Unicode escapes; exact UTF-8 text is in the accompanying audit record:\n'
    for tag,value in originals.items():
        if value.startswith(prefix):
            try: value=json.loads(value[len(prefix):])
            except (ValueError,TypeError): pass
        decoded[tag]=value
    text='\n'.join(decoded.values());zh=[];en=[];evidence=[]
    for value in dict.fromkeys(re.findall(r'(?:spherical\s+)?mu\s*\*\s*r\s*=\s*([0-9.]+)',text,re.I)):
        value=value.rstrip('.')
        zh.append(f'原始处理记录含额外球形吸收参数 μr={value}，其适用性仍需复核。')
        en.append(f'The original processing records an additional spherical absorption parameter mu*r={value}; its applicability still needs review.')
        evidence.append({'kind':'recorded_spherical_absorption','value':value})
    match=re.search(r'Original processing transmission limits:\s*([0-9.]+)\s+to\s+([0-9.]+)',text)
    if match:
        low,high=match[1],match[2].rstrip('.')
        zh.append(f'原始透射率范围为 {low}–{high}；未为降低警告而改写数据。')
        en.append(f'The original transmission range is {low}–{high}; data were not rewritten to reduce alerts.')
        evidence.append({'kind':'recorded_transmission_limits','min':low,'max':high})
    if re.search(r'(?:needs? review|unconfirmed|unresolved|uncertain|需.*复核|未确认)',text,re.I):
        zh.append('原记录存在待复核事项；完整说明单独保留，不能仅凭低R值或无A/B警告认定已解决。')
        en.append('The source record contains review items; their full text is retained separately. Low R or no A/B alerts does not establish that these items are resolved.')
    if originals:
        zh.append('完整原文、方案及审计记录见 full_audit_records.json，计算输出见 model.lst。')
        en.append('Full source text, plans and audit records are in full_audit_records.json; native output is in model.lst.')
    return {'zh':' '.join(zh),'en':' '.join(en),'original_records':decoded,'evidence':evidence}

def hydrogen_method_notes(text):
    rows=records(text);sfac=next((r[1:] for r in rows if r[0].upper()=='SFAC'),[])
    afix=0;counts=Counter();free=0;unsupported=[];multipliers=Counter()
    for r in rows:
        key=r[0].upper()
        if key=='AFIX':afix=int(r[1]);continue
        if key=='HFIX':unsupported.append('Pending HFIX: '+' '.join(r));continue
        if key in CARDS:continue
        if len(r)<7:continue
        try:
            i=int(r[1]);xyz=list(map(float,r[2:5]));u=float(r[6])
        except ValueError:continue
        if not 1<=i<=len(sfac) or sfac[i-1].upper() not in ('H','D'):continue
        counts[afix]+=1
        if -.5>u>-5:multipliers[-u]+=1
        elif u<=-.5 or u>=5:unsupported.append('Encoded H U: '+r[0])
        if afix==0:free+=1
    zh=[];en=[]
    supported={13:'sp³ CH',23:'CH₂',43:'平面 CH/NH',137:'转动三氢基团',147:'转动 OH',163:'末端炔 CH',3:'位置相对母原子固定的骑乘 H'}
    supported_en={13:'sp3 CH',23:'CH2',43:'planar CH/NH',137:'rotating three-H groups',147:'rotating OH',163:'terminal acetylenic CH',3:'fixed-relative riding H'}
    for code,n in sorted(counts.items()):
        if code in supported:
            zh.append(f'{n} 个氢位点采用 AFIX {code}（{supported[code]}）')
            en.append(f'{n} H site'+('s use' if n!=1 else ' uses')+f' AFIX {code} ({supported_en[code]})')
        else:
            zh.append(f'{n} 个氢位点记录 AFIX {code}，自由度需结合其他指令核对')
            en.append(f'{n} H sites record AFIX {code}; degrees of freedom require checking other controls')
            unsupported.append('AFIX '+str(code))
    for k,n in sorted(multipliers.items()):
        zh.append(f'{n} 个氢的 Uiso 按母原子 Ueq 的 {k:g} 倍设置')
        en.append(f'{n} H Uiso values are set to {k:g} times the parent Ueq')
    limitations_zh='以上文字只描述最终模型的约束，不宣称氢均由差值图独立定位。'
    limitations_en='These statements describe final-model constraints and do not claim that every H was independently located in a difference map.'
    if not counts:
        zh=['最终 RES 中未识别到氢原子'];en=['No H sites were identified in the final RES']
    return {'zh':{'methods':'；'.join(zh)+'。','limitations':limitations_zh},'en':{'methods':'; '.join(en)+'.','limitations':limitations_en},
            'evidence':{'AFIX_H_site_counts':dict(counts),'relative_U_counts':dict(multipliers),'unsupported':unsupported},'ai_calls':0}
