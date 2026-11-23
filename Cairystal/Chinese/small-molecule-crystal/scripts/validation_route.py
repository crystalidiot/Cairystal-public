"""Record a proven missing local rule file separately from official validation."""
from pathlib import Path
import json,re,shutil
from crystal_runtime import regular,new_directory,sha,write_json

def missing_rules_evidence(folder):
 rows=[]
 for name in ['platon.out','process.log']:
  p=Path(folder)/name
  if not p.is_file():continue
  text=p.read_text('latin1')
  for line in text.splitlines():
   if re.search(r'check[.]def',line,re.I) and re.search(r'not\s+found|missing|cannot\s+(?:open|find)|can\s*not\s+(?:open|find)|unable\s+to\s+(?:open|find)|no\s+(?:file|check)|could\s+not\s+(?:open|find)',line,re.I):rows.append({'log':name,'line':line.strip()[:600]})
 return rows

def validate_local(executable,frozen,destination,stem,timeout=120):
 from crystal_runtime import local_validation
 try:
  result=local_validation(executable,frozen,destination,stem,timeout);return dict(result,available=True)
 except ValueError:
  folder=Path(destination);evidence=missing_rules_evidence(folder)
  if not evidence:raise  # malformed reports, inconsistent counts and other failures still stop.
  files={p.name:sha(p) for p in folder.iterdir() if p.is_file() and p.name!='local_unavailable.json'}
  result={'available':False,'state':'unavailable_missing_check_def','official':False,'alerts':None,'reason':'PLATON explicitly reported a missing check.def; no local pass or zero-alert result is inferred.','evidence':evidence,'input_sha256':{ext:sha(regular(Path(frozen)/f'{stem}.{ext}')) for ext in ['cif','fcf']},'executable_sha256':sha(regular(executable)),'artifact_sha256':files,'cache_hit':False}
  write_json(folder/'local_unavailable.json',result);return result

def reuse_local(source,frozen,destination,stem,executable):
 source=Path(source)
 if not (source/'local_unavailable.json').is_file():
  from local_validation_cache import reuse
  return dict(reuse(source,frozen,destination,stem,executable),available=True)
 r=json.loads(regular(source/'local_unavailable.json').read_text('utf-8'))
 if r.get('available') is not False or r.get('state')!='unavailable_missing_check_def':raise ValueError('Unknown local-unavailable record')
 if r['input_sha256']!={e:sha(regular(Path(frozen)/f'{stem}.{e}')) for e in ['cif','fcf']} or r['executable_sha256']!=sha(regular(executable)):raise ValueError('Local-unavailable evidence belongs to other inputs/program')
 for name,h in r['artifact_sha256'].items():
  if Path(name).name!=name or sha(regular(source/name))!=h:raise ValueError('Local-unavailable evidence changed')
 if missing_rules_evidence(source)!=r.get('evidence'):raise ValueError('Missing-rule log evidence changed')
 target=new_directory(destination)
 for name in r['artifact_sha256']:shutil.copy2(source/name,target/name)
 result=dict(r,cache_hit=True,cache_source=str(source));write_json(target/'local_unavailable.json',result);return result

def append_local_limit(notes,local):
 if local.get('available',True):return notes
 texts={'zh':'本地 PLATON 明确报告缺少 check.def，本地完整验证未完成；此限制单独保留，不记为零警告。官网验证状态见所附报告。','en':'Local PLATON reported a missing check.def, so complete local validation was unavailable and was not recorded as zero alerts. The official validation status is documented separately.'}
 for lang,text in texts.items():
  prior=notes.setdefault(lang,{}).get('limitations','')
  if text not in prior:notes[lang]['limitations']=prior+' '+text
 notes.setdefault('audit_records',{})['local_validation_unavailable']=local
 return notes

def mark_provisional(notes,findings):
 texts={'zh':'这是用于诊断和修复的候选模型报告，仍有待审查的验证警告，不代表结构已通过科学审核。','en':'This is a diagnostic candidate report with unresolved validation findings; it does not establish scientific acceptance.'}
 for lang,text in texts.items():
  prior=notes.setdefault(lang,{}).get('limitations','')
  if text not in prior:notes[lang]['limitations']=prior+' '+text
 notes.setdefault('audit_records',{})['pending_validation_findings']=findings
 return notes
