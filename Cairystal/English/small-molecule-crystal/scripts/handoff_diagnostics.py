"""Attach a read-only atom packet to an existing finishing-stage handoff.

Only named files inside this run's exact finish_root are read. No directory
search, historical fallback, model mutation, upload or scientific acceptance.
"""
from pathlib import Path
import hashlib,json,shutil
from pipeline_intake import unlinked
from structure_diagnostics import analyse,brief,digest,newjson

def collect(root,pipeline_state):
 root=Path(root).absolute();value=pipeline_state.get('finish_root')
 if not value:return {'status':'not_available','reason':'No current-run finishing checkpoint; use explicit diagnostics on a paired candidate.'}
 finish=Path(value).absolute();unlinked(finish)
 if not finish.is_relative_to(root/'pipeline'):raise ValueError('Finish source outside current run')
 finish_state=finish/'state.json'
 working=finish/'working_omit' if finish_state.is_file() and json.loads(finish_state.read_text('utf-8')).get('selected_omit') else finish
 sources={name:working/'frozen'/('model.'+name) for name in ['cif','res','lst']}
 sources['chk']=working/'local_validation/model.chk'
 for p in sources.values():
  unlinked(p)
  if not p.is_file():return {'status':'not_available','reason':'Paired finishing evidence incomplete','missing':str(p)}
 before={k:digest(p) for k,p in sources.items()}
 from common_disorder import CATALOG
 implementation={p.name:digest(p) for p in [Path(__file__),Path(__file__).with_name('common_disorder.py'),CATALOG]}
 fingerprint=hashlib.sha256(json.dumps({'sources':before,'implementation':implementation},sort_keys=True).encode()).hexdigest()
 parent=root/'atom_diagnostics';unlinked(parent);parent.mkdir(exist_ok=True);folder=parent/fingerprint
 if folder.exists():
  unlinked(folder);cache=folder/'cache.json';unlinked(cache);rec=json.loads(cache.read_text(encoding='utf-8'))
  for name,sha in rec['output_hashes'].items():
   p=folder/name;unlinked(p)
   if digest(p)!=sha:raise ValueError('Diagnostic cache changed')
  if rec['source_hashes']!=before:raise ValueError('Diagnostic cache source differs')
  return dict(rec['packet'],cache_hit=True)
 folder.mkdir()
 for ext,p in sources.items():shutil.copy2(p,folder/('model.'+ext))
 result=analyse(folder,stem='model',case_status='requires_scientific_review');newjson(folder/'diagnostic.json',result)
 (folder/'diagnostic.txt').write_text(brief(result),encoding='utf-8')
 if {k:digest(p) for k,p in sources.items()}!=before:raise ValueError('Source changed during diagnostics')
 packet={'status':'ready','json':str(folder/'diagnostic.json'),'brief':str(folder/'diagnostic.txt'),'regions':len(result['regions']),'AB_count':len(result['AB_alerts']),'seconds':result['elapsed_s'],'AI_calls':0,'model_modified':False,'cache_hit':False}
 try:
  from common_disorder import detect
  common=detect(folder,stem='model');newjson(folder/'common_disorder.json',common)
  packet['common_disorder']={'status':'screened','path':str(folder/'common_disorder.json'),'sites':len(common['sites']),'AI_calls':0,'model_modified':False}
 except Exception as exc:
  packet['common_disorder']={'status':'needs_review','error':str(exc),'model_modified':False}
 newjson(folder/'cache.json',{'source_hashes':before,'output_hashes':{p.name:digest(p) for p in folder.iterdir() if p.is_file()},'packet':packet})
 return packet
