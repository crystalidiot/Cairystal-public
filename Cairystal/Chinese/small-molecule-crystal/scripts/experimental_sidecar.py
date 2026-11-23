"""Whitelist-only anonymous experimental metadata, bound to exact input hashes.

Never searches for source CIFs or models. Export is a metadata source, not a
validated structure. TEMP/H review and native refinement must precede delivery.
"""
import argparse,hashlib,json,math,re
from decimal import Decimal
from pathlib import Path
import gemmi

FIELDS={'_exptl_crystal_description':None,'_diffrn_measurement_device_type':None,
 '_cell_measurement_reflns_used':'count','_cell_measurement_theta_min':'degree',
 '_cell_measurement_theta_max':'degree','_cell_measurement_temperature':'K',
 '_diffrn_ambient_temperature':'K'}
def safe(path):
 p=Path(path).absolute()
 for q in (p,*p.parents):
  if q.is_symlink() or (hasattr(q,'is_junction') and q.is_junction()):raise ValueError('Linked paths are not allowed')
 return p
def sha(path):return hashlib.sha256(safe(path).read_bytes()).hexdigest()
def read(path):return json.loads(safe(path).read_text(encoding='utf-8-sig'))
def exact(obj,keys):
 if not isinstance(obj,dict) or set(obj)!=set(keys):raise ValueError('Unexpected or missing schema keys')
def digest(value):
 if not isinstance(value,str) or not re.fullmatch('[0-9a-f]{64}',value):raise ValueError('Invalid SHA256')

def validate_fields(fields):
 exact(fields,FIELDS)
 tokens={}
 for tag,unit in FIELDS.items():
  v=fields[tag];exact(v,['raw_token','value','unit'])
  if v['unit']!=unit or not isinstance(v['raw_token'],str):raise ValueError('Invalid unit/token: '+tag)
  token=v['raw_token']
  if len(token)>4000:raise ValueError('Oversized metadata token')
  # Parse exactly one scalar: appended tags/loops/blocks cannot hide in the token.
  doc=gemmi.cif.read_string('data_metadata\n'+tag+'\n'+token+'\n')
  if len(doc)!=1:raise ValueError('Injected block in metadata')
  b=doc.sole_block();items=list(b)
  if len(items)!=1 or not items[0].pair or items[0].pair[0]!=tag:raise ValueError('Injected metadata content')
  parsed=b.find_value(tag)
  if parsed.strip()!=token.strip():raise ValueError('Extra text/comment outside metadata token')
  if parsed in {'?','.'} or not gemmi.cif.as_string(parsed).strip():raise ValueError('Unknown metadata field '+tag)
  if unit is None:
   text=gemmi.cif.as_string(parsed)
   if not isinstance(v['value'],str) or text!=v['value']:raise ValueError('Raw/value mismatch '+tag)
   if re.search(r'https?://|doi\s*:|[A-Za-z]:[\\/]|[\\/]{2}',text,re.I):raise ValueError('Path/link in anonymous metadata')
  else:
   value=gemmi.cif.as_number(parsed)
   if isinstance(v['value'],bool) or not isinstance(v['value'],(int,float)) or not math.isfinite(value) or value!=v['value']:raise ValueError('Numeric token/value mismatch '+tag)
   if unit=='K' and value<=0:raise ValueError('Kelvin must be positive')
   if unit=='count' and (value<=0 or value!=int(value)):raise ValueError('Reflection count must be positive integer')
   if unit=='degree' and not 0<=value<=90:raise ValueError('Theta out of range; do not convert 2theta implicitly')
  tokens[tag]=parsed
 if fields['_cell_measurement_theta_min']['value']>fields['_cell_measurement_theta_max']['value']:raise ValueError('Theta range reversed')
 return tokens

def load(sidecar,manifest):
 s=read(sidecar);m=read(manifest);exact(s,['schema','dataset_manifest_sha256','cases'])
 if s['schema']!=1 or s['dataset_manifest_sha256']!=sha(manifest):raise ValueError('Sidecar does not match manifest')
 expected={c['case_id']:c for c in m['cases']}
 if len(expected)!=len(m['cases']):raise ValueError('Duplicate manifest case ID')
 records={}
 for c in s['cases']:
  exact(c,['case_id','input_sha256','hkl_sha256','fields','provenance'])
  if not isinstance(c['case_id'],str) or not re.fullmatch('[A-Za-z0-9_-]+',c['case_id']):raise ValueError('Unsafe case identifier')
  if c['case_id'] in records or c['case_id'] not in expected:raise ValueError('Duplicate or unknown case ID')
  digest(c['input_sha256']);digest(c['hkl_sha256'])
  exact(c['provenance'],['source_sha256','selected_block_sha256','extraction'])
  for key in ['source_sha256','selected_block_sha256']:digest(c['provenance'][key])
  if c['provenance']['extraction']!='selected source block; whitelist only':raise ValueError('Unexpected provenance payload')
  validate_fields(c['fields']);records[c['case_id']]=c
 if set(records)!=set(expected):raise ValueError('Sidecar does not cover exactly the manifest cases')
 return records,expected

def read_case(sidecar,manifest,case_id,input_json,hkl):
 records,expected=load(sidecar,manifest)
 if case_id not in records:raise ValueError('Unknown case ID')
 item=expected[case_id];root=safe(manifest).parent;rel=Path(item['directory'])
 if rel.is_absolute() or '..' in rel.parts:raise ValueError('Invalid manifest directory')
 # Compare explicit paths, not just content hashes: prevent accidental case swaps.
 if safe(input_json)!=safe(root/rel/'input.json') or safe(hkl)!=safe(root/rel/'data.hkl'):raise ValueError('Input path does not belong to this manifest case')
 c=records[case_id]
 if sha(input_json)!=c['input_sha256'] or sha(hkl)!=c['hkl_sha256']:raise ValueError('Case input hashes differ')
 return c

def export(sidecar,manifest,input_root,output):
 sidecar,manifest,input_root=map(safe,(sidecar,manifest,input_root));out=safe(output)
 if input_root!=manifest.parent:raise ValueError('Input root must be manifest parent')
 if out==input_root or input_root in out.parents or out.exists():raise ValueError('Choose new output outside read-only inputs')
 records,expected=load(sidecar,manifest);before={str(sidecar):sha(sidecar),str(manifest):sha(manifest)}
 checked=[]
 for cid,item in expected.items():
  rel=Path(item['directory']);ip=input_root/rel/'input.json';hp=input_root/rel/'data.hkl'
  c=read_case(sidecar,manifest,cid,ip,hp);checked.append((c,ip,hp))
  before[str(ip)]=c['input_sha256'];before[str(hp)]=c['hkl_sha256']
 out.mkdir(parents=True);entries=[]
 for c,ip,hp in checked:
  cid=c['case_id']
  if not re.fullmatch('[A-Za-z0-9_-]+',cid):raise ValueError('Unsafe case identifier')
  folder=out/cid;folder.mkdir();tokens=validate_fields(c['fields'])
  d=gemmi.cif.Document();b=d.add_new_block('experimental_metadata')
  for tag,token in tokens.items():b.set_pair(tag,token)
  cf=folder/'experimental_metadata.cif';d.write_file(str(cf))
  basis='Anonymous metadata sidecar bound to the exact manifest, input.json and original HKL hashes; source identities withheld.'
  config={'hkl':str(hp),'sources':[{'path':str(cf),'kind':'cif_metadata','source_sha256':sha(cf),'hkl_sha256':c['hkl_sha256'],'same_experiment_confirmed':True,'basis':basis}]}
  (folder/'ledger_sources.json').write_text(json.dumps(config,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
  numeric=re.sub(r'\(\d+\)','',gemmi.cif.as_string(tokens['_diffrn_ambient_temperature']))
  plan={'case_id':cid,'sidecar_sha256':before[str(sidecar)],'input_sha256':c['input_sha256'],'hkl_sha256':c['hkl_sha256'],'provenance':c['provenance'],'ambient_K_token':tokens['_diffrn_ambient_temperature'],'cell_K_token':tokens['_cell_measurement_temperature'],'target_TEMP_degrees_C':format(Decimal(numeric)-Decimal('273.15'),'f'),'requires_native_review':True,'instructions':'Audit TEMP and hydrogen constraints using current native RES; if missing/mismatched, prepare a new INS and run SHELXL. Recheck H geometry, then synchronize metadata and validate the exact newly generated CIF. This file does not authorize scientific acceptance or bypass the existing upload permission.','metadata_cif_sha256':sha(cf)}
  (folder/'temperature_plan.json').write_text(json.dumps(plan,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
  entries.append({'case_id':cid,'directory':str(folder),'metadata_cif':str(cf),'metadata_cif_sha256':sha(cf),'ledger_sources':str(folder/'ledger_sources.json'),'temperature_plan':str(folder/'temperature_plan.json')})
 if any(sha(p)!=v for p,v in before.items()):raise ValueError('Input changed during export')
 result={'schema':1,'status':'exported_metadata_sources_only','case_count':len(entries),'sidecar_sha256':sha(sidecar),'manifest_sha256':sha(manifest),'entries':entries,'input_hashes_unchanged':True,'scientific_acceptance':False}
 (out/'export_manifest.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8');return result

def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--sidecar',required=True);p.add_argument('--manifest',required=True);p.add_argument('--input-root',required=True);p.add_argument('--output',required=True);a=p.parse_args()
 r=export(a.sidecar,a.manifest,a.input_root,a.output);print(json.dumps({'status':r['status'],'case_count':r['case_count'],'sidecar_sha256':r['sidecar_sha256'],'manifest':str(Path(a.output)/'export_manifest.json')},ensure_ascii=False));return 0
if __name__=='__main__':raise SystemExit(main())
