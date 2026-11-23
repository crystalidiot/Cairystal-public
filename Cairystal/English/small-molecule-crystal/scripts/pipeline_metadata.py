"""Connect explicit session inputs and regenerated candidates to the metadata ledger."""
import json
from pathlib import Path
from crystal_runtime import sha,write_json
from experiment_metadata_state import collect,synchronize

def initialize(session,output):
 session=Path(session);out=Path(output);out.mkdir(exist_ok=True)
 existing=out/'ledger/metadata_ledger.json'
 if existing.exists():
  current=json.loads((session/'session.json').read_text('utf-8'))['inputs']
  config=json.loads((out/'sources.json').read_text('utf-8'))
  if config.get('session_input_bindings')!=current:raise ValueError('Existing metadata ledger belongs to different session inputs')
  previous=json.loads(existing.read_text('utf-8'))
  if previous.get('conflicts') or previous.get('validation_errors'):raise ValueError('Existing metadata ledger still needs review')
  if any(sha(p)!=h for p,h in previous['input_hashes'].items()):raise ValueError('Existing metadata source changed')
  return existing
 manifest=json.loads((session/'session.json').read_text('utf-8'));inputs=manifest['inputs']
 hkl=Path(inputs['hkl']['copy']);sources=[]
 for kind,key in [('p4p','p4p'),('sadabs_log','absorption_log')]:
  if key not in inputs:continue
  item=inputs[key];p=Path(item['copy'])
  if sha(p)!=item['sha256'] or sha(hkl)!=inputs['hkl']['sha256']:raise ValueError('Session input changed before metadata collection')
  entry={'path':str(p),'kind':kind,'source_sha256':sha(p),'hkl_sha256':sha(hkl),'same_experiment_confirmed':True,'basis':'Explicit session input pairing from the raw-data intake; original input hashes retained.'}
  if kind=='p4p':entry['temperature_scope']='diffraction'
  sources.append(entry)
 if 'specimen' in inputs:
  item=inputs['specimen'];p=Path(item['copy']);record=json.loads(p.read_text('utf-8-sig'))
  if record.get('cif_fields') and record.get('confirmed') is True:
   if sha(p)!=item['sha256']:raise ValueError('Confirmed specimen source changed')
   sources.append({'path':str(p),'kind':'confirmed_json','source_sha256':sha(p),'hkl_sha256':sha(hkl),'same_experiment_confirmed':True,'basis':record.get('basis') or record.get('provenance')})
 if not sources:raise ValueError('No supported experimental sources in session')
 cfg=out/'sources.json';write_json(cfg,{'hkl':str(hkl),'sources':sources,'session_input_bindings':inputs});m=collect(cfg,out/'ledger')
 if m['conflicts'] or m['validation_errors']:raise ValueError('Experimental source conflicts require review')
 return out/'ledger/metadata_ledger.json'

def sync_summary(root,state,payload):
 root=Path(root)
 if not state.get('experimental_metadata_ledger'):
  state['experimental_metadata_ledger']=str(initialize(root/'session',root/'experimental_metadata'))
 rows=[]
 for candidate in payload['candidates']:
  stage=Path(candidate['stage']).resolve()
  stage.relative_to((root/'session/stages').resolve())
  target=root/'metadata_sync'/stage.name;attempt=1
  while target.exists():
   attempt+=1;target=root/'metadata_sync'/(stage.name+'_'+str(attempt))
  result=synchronize(state['experimental_metadata_ledger'],stage/'model.cif',stage/'model.res',stage/'model.hkl',target)
  rows.append({'stage':str(stage),'cif':result['output'],'status':result['status'],'native_refinement_required':result['native_refinement_required']})
 state.setdefault('metadata_sync_history',[]).extend(rows)
 return rows
