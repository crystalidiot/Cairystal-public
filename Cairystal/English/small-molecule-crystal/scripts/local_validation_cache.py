"""Reuse local validation only for exact same CIF, FCF, executable and artifacts."""
from pathlib import Path
import json,shutil
from crystal_runtime import sha,regular,new_directory,write_json
from parse_platon_alerts import parse

def reuse(source,frozen,destination,stem,executable):
    source=Path(source);record=json.loads(regular(source/'local_validation.json').read_text(encoding='utf-8'))
    if record.get('input_sha256')!={ext:sha(regular(Path(frozen)/f'{stem}.{ext}')) for ext in ['cif','fcf']}:raise ValueError('Local cache CIF/FCF hash differs')
    if record.get('executable_sha256')!=sha(regular(executable)):raise ValueError('Local cache executable differs')
    from platon_execution import rules_context
    if record.get('rules_context') is not None and record['rules_context']!=rules_context(executable):raise ValueError('Local cache rules configuration differs')
    expected=[f'{stem}.cif',f'{stem}.fcf',f'{stem}.chk',f'{stem}.ckf','platon.out','process.log']
    if set(record.get('artifact_sha256',{}))!=set(expected):raise ValueError('Local cache lacks complete evidence manifest')
    for name,digest in record['artifact_sha256'].items():
        if sha(regular(source/name))!=digest:raise ValueError('Local cache artifact changed: '+name)
    if any(record['artifact_sha256'][f'{stem}.{ext}']!=record['input_sha256'][ext] for ext in ['cif','fcf']):raise ValueError('Local cache artifact/input mismatch')
    parsed=parse((source/f'{stem}.chk').read_text(encoding='latin1'));log=(source/'platon.out').read_text(errors='replace')
    if not parsed['report_footer_present'] or parsed['warnings'] or 'CheckCIF' not in log or 'CheckFCF' not in log or (source/f'{stem}.ckf').stat().st_size<=100:raise ValueError('Local cache completion markers absent')
    if parsed!=record.get('alerts'):raise ValueError('Local cache parsed report differs')
    target=new_directory(destination)
    for name in expected:shutil.copy2(source/name,target/name)
    result=dict(record);result.update(cache_hit=True,cache_source=str(source),reused_elapsed_s=0);write_json(target/'local_validation.json',result);return result
