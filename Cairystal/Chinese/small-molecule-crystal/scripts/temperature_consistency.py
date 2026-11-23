"""Audit CIF/K vs SHELXL/degC; prepare a new INS from a paired temperature source.

No refinement, implicit source search, reference-model import or upload occurs.
"""
import argparse
from decimal import Decimal
import json
import math
from pathlib import Path
import re

import gemmi
from crystal_runtime import regular, sha, utc_now

AMBIENT = '_diffrn_ambient_temperature'
CELL = '_cell_measurement_temperature'
NUMBER = r'[+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:\(\d+\))?(?:[eE][+-]?\d+)?'
TOLERANCE_K = 0.51  # Screening for whole-K serialization, not measurement uncertainty.


def kelvin(token):
    if token is None or token in {'?', '.'}: return None
    text = gemmi.cif.as_string(token)
    if not re.fullmatch(NUMBER, text): raise ValueError('Invalid temperature token: '+text)
    # Strip the uncertainty only after validating syntax; retain the original token in audits.
    # Decimal handles a scientific exponent without depending on Gemmi's SU notation variants.
    number = float(Decimal(re.sub(r'\(\d+\)', '', text)))
    if not math.isfinite(number) or number <= 0: raise ValueError('Temperature must be finite and > 0 K')
    return number


def celsius_string(token):
    kelvin(token)
    numeric = re.sub(r'\(\d+\)', '', gemmi.cif.as_string(token))
    return format(Decimal(numeric)-Decimal('273.15'), 'f')


def native_info(text):
    # Lazy import: routine_consistency calls this module after its own initialization.
    from routine_consistency import active_records
    from audit_occupancy import CARDS
    rows = active_records(text)
    atoms = []
    for line, fields in rows:
        if fields[0].upper().split('_')[0] in CARDS or len(fields)<5: continue
        try:
            int(fields[1]); [float(v) for v in fields[2:5]]
            atoms.append(line)
        except ValueError: pass
    temps = [(n, f) for n,f in rows if f[0].upper()=='TEMP']
    opaque = [f for _,f in rows if f[0].startswith(('+','@')) or f[0].upper()=='FRAG']
    if len(temps)>1: raise ValueError('Multiple active TEMP instructions')
    result = {'records':rows, 'opaque':opaque, 'first_atom_line':min(atoms) if atoms else None,
              'temp_line':None, 'celsius':None, 'kelvin':None, 'late':False}
    if temps:
        line, fields = temps[0]
        if len(fields)!=2 or not re.fullmatch(r'[+-]?(?:\d+(?:\.\d*)?|\.\d+)', fields[1]):
            raise ValueError('TEMP must have one explicit numeric Celsius value')
        c = float(fields[1]); k = c+273.15
        if not math.isfinite(k) or k<=0: raise ValueError('Invalid physical TEMP value')
        result.update(temp_line=line, celsius=c, kelvin=k,
                      late=bool(atoms and line>min(atoms)))
    return result


def audit_temperature(block, native=''):
    issues=[]; values={}; info=None
    def add(code, severity, message, evidence=None):
        issues.append({'code':code, 'severity':severity, 'message_zh':message, 'evidence':evidence})
    for tag in (AMBIENT,CELL):
        token=block.find_value(tag)
        try:
            if block.find_loop(tag): raise ValueError('Temperature must be an explicitly selected scalar')
            values[tag]={'token':token, 'kelvin':kelvin(token)}
        except ValueError as exc:
            values[tag]={'token':token, 'kelvin':None}
            add('TEMPERATURE_INVALID','error','温度记录无效；不能当作实测值。',{'tag':tag,'detail':str(exc)})
    try: info=native_info(native)
    except ValueError as exc: add('TEMP_CONTROL_INVALID','error','TEMP 指令无效或重复。',str(exc))
    if info:
        if info['opaque']:
            add('TEMP_SCOPE_UNSUPPORTED','review','含外部指令或 FRAG；温度指令作用范围需复核。')
        if info['late']: add('TEMP_AFTER_ATOMS','error','TEMP 必须写在全部原子之前。')
        ambient=values[AMBIENT]['kelvin']; cell=values[CELL]['kelvin']; native_k=info['kelvin']
        if ambient is not None:
            if native_k is None:
                add('TEMP_MISSING','review','CIF 有采集温度，但 RES 缺少显式 TEMP；需按来源同步并重新精修。',{'ambient_K':ambient})
            elif abs(native_k-ambient)>TOLERANCE_K:
                add('TEMP_CIF_MISMATCH','error','RES 的 TEMP 与 CIF 采集温度不一致。',{'TEMP_K':native_k,'ambient_K':ambient})
        else:
            add('TEMPERATURE_COLLECTION_UNKNOWN','review','缺少可靠的 CIF 采集温度；未把晶胞测量温度或程序默认值当作采集温度。',{'cell_K':cell,'TEMP_K':native_k})
    return {'issues':issues, 'reported':values,
            'native':{k:v for k,v in info.items() if k!='records'} if info else None,
            'comparison_tolerance_K':TOLERANCE_K,
            'status':'failed' if any(i['severity']=='error' for i in issues) else 'needs_review' if issues else 'checks_passed',
            'limits':['Temperature consistency is not experimental provenance or PLATON validation.',
                      'Cell and diffraction collection temperatures can legitimately differ.']}


def prepare(source, res, evidence, output, tag=AMBIENT, source_block=None,
            replace_reason=None, encoding='utf-8-sig'):
    from inspect_experiment_metadata import inspect_metadata
    if tag not in (AMBIENT,CELL): raise ValueError('Unsupported temperature tag')
    source,res,evidence=map(regular,(source,res,evidence))
    output=Path(output).absolute()
    if output.exists(): raise ValueError('Use a new output directory')
    if any(p.is_symlink() or getattr(p,'is_junction',lambda:False)() for p in output.parents):
        raise ValueError('Linked output parent unsupported')
    hashes={str(p):sha(p) for p in (source,res,evidence)}
    provenance=json.loads(evidence.read_text(encoding='utf-8-sig'))
    for field in ('same_experiment_confirmed','collection_temperature_confirmed'):
        if provenance.get(field) is not True: raise ValueError('Missing explicit provenance: '+field)
    if not str(provenance.get('basis','')).strip(): raise ValueError('Document the pairing/measurement basis')
    if provenance.get('source_sha256')!=hashes[str(source)] or provenance.get('res_sha256')!=hashes[str(res)]:
        raise ValueError('Provenance must identify these exact source and native files')
    if tag==CELL and provenance.get('cell_temperature_is_collection_temperature') is not True:
        raise ValueError('Cell temperature alone does not establish diffraction temperature')
    extracted=inspect_metadata(source,encoding)
    blocks=[b for b in extracted['blocks'] if source_block is None or b['block']==source_block]
    if len(blocks)!=1: raise ValueError('Select exactly one source block')
    entry=blocks[0]['fields'].get(tag)
    if not entry or entry['state']!='present_unverified': raise ValueError('Selected scalar temperature is missing')
    token=entry['token']; target_k=kelvin(token); temp=celsius_string(token)
    # Even explicitly confirmed fallback may not override a different recorded ambient temperature.
    if tag==CELL:
        ambient=blocks[0]['fields'].get(AMBIENT)
        ambient_k=kelvin(ambient['token']) if ambient else None
        if ambient_k is not None and abs(ambient_k-target_k)>TOLERANCE_K:
            raise ValueError('Cell fallback conflicts with source ambient temperature')
    raw=res.read_bytes(); text=raw.decode('latin1'); info=native_info(text)
    if info['opaque'] or not info['first_atom_line']: raise ValueError('Unsupported native scope or no atom records')
    if not any(f[0].upper()=='HKLF' for _,f in info['records']): raise ValueError('Missing HKLF')
    old=info['kelvin']
    if old is not None and abs(old-target_k)>TOLERANCE_K and not (replace_reason and replace_reason.strip()):
        raise ValueError('Existing TEMP conflicts: retain it or document an explicit replacement reason')
    lines=text.splitlines(keepends=True); newline='\r\n' if b'\r\n' in raw else '\n'
    if info['temp_line'] and '=' in lines[info['temp_line']-1].split('!',1)[0]:
        raise ValueError('Continued TEMP instruction requires separate review')
    changed=[]
    for n,line in enumerate(lines,1):
        if n==info['first_atom_line']: changed.append('TEMP '+temp+newline)
        if n!=info['temp_line']: changed.append(line)
    rendered=''.join(changed)
    from routine_consistency import active_records
    before=[f for _,f in active_records(text) if f[0].upper()!='TEMP']
    after=[f for _,f in active_records(rendered) if f[0].upper()!='TEMP']
    if before!=after: raise ValueError('Unexpected non-TEMP instruction/atom change')
    new_info=native_info(rendered)
    if new_info['late'] or abs(new_info['kelvin']-target_k)>1e-7: raise ValueError('TEMP round-trip failed')
    if any(sha(p)!=h for p,h in hashes.items()): raise ValueError('Input changed during preparation')
    output.mkdir(parents=True)
    ins=output/'model.ins'; ins.write_bytes(rendered.encode('latin1'))
    record={'created_at':utc_now(),'status':'prepared_not_refined','scientific_acceptance':False,
            'ai_calls':0,'input_hashes':hashes,'provenance':provenance,
            'source_block':blocks[0]['block'],'source_tag':tag,'source_token':token,
            'temperature_K':target_k,'TEMP_C':temp,'previous_TEMP_K':old,
            'replacement_reason':replace_reason,'inputs_unchanged':True,
            'other_active_records_unchanged':True,'output':str(ins),'output_sha256':sha(ins),
            'required_next_steps':['Refine with unchanged paired HKL; inspect temperature-sensitive H geometry.',
                                   'Regenerate paired RES/FCF/CIF; recheck source temperatures and A/B.',
                                   'Generate authorized official checkCIF and bilingual reports for the new files.']}
    (output/'temperature_audit.json').write_text(json.dumps(record,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    return record


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--source',required=True); p.add_argument('--res',required=True)
    p.add_argument('--evidence',required=True); p.add_argument('--output',required=True)
    p.add_argument('--tag',choices=[AMBIENT,CELL],default=AMBIENT)
    p.add_argument('--source-block'); p.add_argument('--replace-reason'); p.add_argument('--encoding',default='utf-8-sig')
    a=p.parse_args()
    try: r=prepare(a.source,a.res,a.evidence,a.output,a.tag,a.source_block,a.replace_reason,a.encoding)
    except (OSError,ValueError,RuntimeError) as exc:
        print(json.dumps({'status':'blocked','reason':str(exc)},ensure_ascii=False)); return 2
    print(json.dumps(r,ensure_ascii=False)); return 0


if __name__=='__main__': raise SystemExit(main())
