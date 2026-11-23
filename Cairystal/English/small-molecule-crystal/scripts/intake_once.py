"""One questionnaire, persisted unknowns, reusable specimen/config exports. No LLM calls."""
import argparse,json,math,re,shutil,sys,unicodedata,base64,binascii,io
from pathlib import Path
from crystal_runtime import new_directory,regular,sha,utc_now,write_json
from pipeline_intake import normalize_elements,unlinked
from interface_language import selected as selected_language,message as local_message

FIELDS=['data_dir','elements','chemistry','solvents','diagram_path','smiles','colour','transparency','habit','dimensions_mm','temperature','instrument','radiation','absolute_configuration','purpose','squeeze','iucr_upload']
COLOURS={'无色':'colourless','黄色':'yellow','红色':'red','橙色':'orange','棕色':'brown','绿色':'green','蓝色':'blue','紫色':'purple','黑色':'black','白色':'white'}
HABITS={'块状':'block','针状':'needle','片状':'plate','柱状':'prism','球状':'sphere'}

def dimensions(value):
 """Three measured lengths in mm; never infer a volume or silently change units."""
 if value is None:return None
 if isinstance(value,str):
  value=unicodedata.normalize('NFKC',value).strip()
  if value.casefold() in {'','不清楚','未知','不知道','unknown','?','.'}:return None
  value=re.sub(r'\s*(?:mm|毫米)\s*$','',value,flags=re.I)
  value=[x for x in re.split(r'[\sxX×*,，]+',value) if x]
  if not value:raise ValueError('尺寸未包含长度数值；不清楚可留空。')
 if not isinstance(value,list) or any(isinstance(v,bool) for v in value):
  raise ValueError('尺寸请填三个长度，例如 0.050 × 0.052 × 0.054 mm；不清楚可留空。')
 if not value:return None
 try:
  if any(isinstance(v,str) and not re.fullmatch(r'[+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d+)?',v) for v in value):raise ValueError()
  result=[float(v) for v in value]
  if len(result)!=3 or any(not math.isfinite(v) or v<=0 for v in result):raise ValueError()
 except (ValueError,TypeError):raise ValueError('尺寸请填三个正数，单位 mm，例如 0.050 × 0.052 × 0.054；不要填体积或其他单位。')
 return result

def path_text(value):
 """Accept Explorer's Copy as path without interpreting shell syntax."""
 value=value.strip()
 for left,right in [('"','"'),("'","'"),('“','”')]:
  if len(value)>=2 and value.startswith(left) and value.endswith(right):return value[1:-1].strip()
 return value

def temperature_kelvin(record):
 if record is None:return None
 if not isinstance(record,dict):raise ValueError('Temperature must contain value and unit')
 value=record.get('value')
 if value is None or (isinstance(value,str) and value.strip().casefold() in {'','?','.','unknown','不清楚','未知','不知道'}):return None
 if isinstance(value,bool):raise ValueError('Temperature must be numeric, not boolean')
 unit=record.get('unit','K')
 if unit not in ('K','C'):raise ValueError('温度单位只能为 K 或 C')
 kelvin=float(value)+(273.15 if unit=='C' else 0)
 if not math.isfinite(kelvin) or kelvin<=0:raise ValueError('温度必须大于绝对零度')
 return kelvin


def normalized(raw):
 if not isinstance(raw,dict):raise ValueError('Intake must be a JSON object')
 if raw.get('schema')!=1:raise ValueError('Unsupported intake schema')
 d={k:raw.get(k) for k in FIELDS};errors=[]
 if not isinstance(d['data_dir'],str) or not d['data_dir'].strip():errors.append('数据目录未提供')
 else:
  d['data_dir']=path_text(d['data_dir'])
  if not d['data_dir']:errors.append('数据目录未提供')
 values=d['elements']
 if isinstance(values,str):values=[x for x in re.split(r'[\s,，;；/]+',values.strip()) if x]
 try:d['elements']=normalize_elements(values)
 except (ValueError,TypeError) as e:errors.append('元素范围未明确：'+str(e));d['elements']=[]
 for k in FIELDS:
  if k not in {'elements','dimensions_mm','temperature'} and d[k] is not None and not isinstance(d[k],str):raise ValueError(k+' must be a string or null')
 for k in ['colour','transparency','habit','chemistry','solvents','diagram_path','smiles','instrument','radiation','absolute_configuration']:
  if d[k] is None or d[k].strip().casefold() in {'','不清楚','未知','不知道','unknown','not known','not provided','?','.'}:d[k]=None
 d['dimensions_mm']=dimensions(d['dimensions_mm'])
 d['temperature_K']=temperature_kelvin(d['temperature'])
 if d['temperature_K'] is None:d['temperature']=None
 d['purpose']=d['purpose'] or 'host_priority'
 if d['purpose'] not in ['host_priority','full_composition']:raise ValueError('Unknown scientific purpose')
 d['squeeze']=d['squeeze'] or 'undecided'
 if d['squeeze'] not in ['allow_if_justified','never','undecided']:raise ValueError('Unknown SQUEEZE preference')
 d['iucr_upload']=d['iucr_upload'] or 'not_answered'
 if d['iucr_upload'] not in ['allow','deny','not_answered']:raise ValueError('Unknown IUCr upload preference')
 if raw.get('observations_confirmed') is not None and not isinstance(raw['observations_confirmed'],bool):raise ValueError('observations_confirmed must be boolean')
 d['observations_confirmed']=raw.get('observations_confirmed') is True
 d['schema']=1;d['blocking_items']=errors
 return d

def extract_uploaded_diagram(raw):
 """Validate a local image attached to the questionnaire; never upload it."""
 value=raw.get('diagram_image_data_url')
 if value in (None,''):return None
 if not isinstance(value,str) or len(value)>12000000:raise ValueError('Structure image is too large (limit 8 MiB)')
 match=re.fullmatch(r'data:image/(png|jpeg|webp);base64,([A-Za-z0-9+/=]+)',value)
 if not match:raise ValueError('Structure image must be PNG, JPEG or WebP')
 try:data=base64.b64decode(match.group(2),validate=True)
 except (binascii.Error,ValueError):raise ValueError('Invalid structure image encoding')
 if len(data)>8*1024*1024:raise ValueError('Structure image is too large (limit 8 MiB)')
 from PIL import Image
 try:
  with Image.open(io.BytesIO(data)) as image:
   if image.format != {'png':'PNG','jpeg':'JPEG','webp':'WEBP'}[match.group(1)]:raise ValueError('Structure image type does not match content')
   if image.width*image.height>40000000:raise ValueError('Structure image dimensions exceed limit')
   image.verify()
 except (OSError,Image.DecompressionBombError) as exc:raise ValueError('Structure image cannot be read') from exc
 return data,{'png':'.png','jpeg':'.jpg','webp':'.webp'}[match.group(1)]

def export(raw_path,output,profile=None,language=None):
 raw_path=regular(unlinked(raw_path));raw=json.loads(raw_path.read_text('utf-8-sig'));data=normalized(raw);image=extract_uploaded_diagram(raw)
 if image and data.get('diagram_path'):raise ValueError('Choose an uploaded structure image or a local image path, not both')
 if isinstance(data.get('data_dir'),str) and data['data_dir'].strip():
  input_path=Path(data['data_dir'].strip()).expanduser()
  data['data_dir']=str(unlinked(input_path if input_path.is_absolute() else raw_path.parent/input_path))
  if not Path(data['data_dir']).is_dir():data['blocking_items'].append('找不到数据文件夹，请检查路径；无需重新填写其他信息。')
 from intake_metadata import prepare,export_fields
 if raw.get('metadata_ledger'):data['metadata_ledger']=raw['metadata_ledger']
 previous_plan=raw.get('question_plan')
 if isinstance(previous_plan,dict):
  prior_unknown=previous_plan.get('answered_unknown_fields',[])
  if isinstance(prior_unknown,list):
   data['_previous_asked_fields']=[field for field in ('colour','habit','dimensions_mm') if field in prior_unknown]
 data,question_plan,metadata=prepare(data,language=selected_language(language))
 data['temperature_K']=temperature_kelvin(data.get('temperature'))
 if question_plan['conflicts']:
  data['blocking_items'].append('实验文件与已有记录存在冲突，仅需核实：'+', '.join(question_plan['conflicts']))
 out=new_directory(unlinked(output));shutil.copy2(raw_path,out/'submitted_intake.json')
 if image:
  image_path=out/('uploaded_structure'+image[1]);image_path.write_bytes(image[0]);data['diagram_path']=str(image_path)
 state={'schema':1,'created_at':utc_now(),'source':str(raw_path),'source_sha256':sha(raw_path),'data':data,
 'questionnaire_completed':True,'asked_once_fields':FIELDS,'unknown_fields':[k for k in FIELDS if data.get(k) in [None,'',[]]],
 'followup_policy':'Do not repeat known/unknown appearance questions. Only consolidate genuinely new scientific conflicts or blocking missing inputs; reuse current-sample authorization.',
 'pending_questions':data['blocking_items'],'status':'needs_input' if data['blocking_items'] else 'ready_for_raw_data_inspection','ai_calls':0,
 'question_plan':question_plan,'metadata_reuse':metadata}
 fields=export_fields(metadata,data)
 if data['observations_confirmed']:
  if data['colour'] and 'colour' not in question_plan['conflicts']:fields['_exptl_crystal_colour']=COLOURS.get(data['colour'],data['colour'])
  if data['habit'] and 'habit' not in question_plan['conflicts']:fields['_exptl_crystal_description']=HABITS.get(data['habit'],data['habit'])
  if data['dimensions_mm'] and 'dimensions_mm' not in question_plan['conflicts']:
   for key,val in zip(['min','mid','max'],sorted(data['dimensions_mm'])):fields['_exptl_crystal_size_'+key]=val
  if data['instrument'] and 'instrument' not in question_plan['conflicts']:fields['_diffrn_measurement_device_type']=data['instrument']
  if data['radiation'] and 'radiation' not in question_plan['conflicts']:fields['_diffrn_radiation_type']=data['radiation']
  if data['temperature_K'] is not None and 'temperature' not in question_plan['conflicts']:fields['_diffrn_ambient_temperature']=data['temperature_K']
 provenance='Current-specimen user form; explicitly confirmed entered observations. Unknown fields are omitted.'
 if metadata:provenance='Paired experiment-file observations reused after hash checks; any additional confirmed user observations are from the current-specimen form. See metadata_reuse in intake_state.json.'
 specimen={'schema':1,'confirmed':True,'provenance':provenance,'basis':provenance,'cif_fields':fields,'source_sha256':sha(raw_path)}
 if metadata:specimen['metadata_ledger']=data['metadata_ledger'];specimen['file_field_provenance']=metadata['provenance']
 write_json(out/'specimen.json',specimen)
 write_json(out/'intake_state.json',state)
 if not data['observations_confirmed']:
  write_json(out/'observations.pending.json',{'confirmed':False,'allow_official_export':False,'data':{k:data[k] for k in ['colour','habit','dimensions_mm','temperature_K','instrument']},'reason':'Entered information was not confirmed as belonging to this specimen.'})
 if profile and not data['blocking_items']:
  cfg={'schema':1,'data_dir':data['data_dir'],'profile':str(regular(unlinked(profile))),'elements':data['elements'],'specimen':str(out/'specimen.json'),'intake_state':str(out/'intake_state.json'),'deliver':data['iucr_upload']!='deny','authorize_iucr_upload':data['iucr_upload']=='allow'}
  if metadata:cfg['stem']=Path(metadata['hkl']).stem
  write_json(out/'autorun_config.json',cfg)
 return state,out

def paired_form_sources(hkl,records,basis):
 """Build the existing collector config from explicitly paired instrument files."""
 if not hkl or not basis or not basis.strip():
  raise ValueError('Paired records require --hkl and a documented --pairing-basis for this experiment')
 hkl=regular(unlinked(hkl))
 if hkl.suffix.lower()!='.hkl':raise ValueError('Select a reflection file ending in .hkl')
 entries=[]
 digest=sha(hkl)
 for record in records:
  source=unlinked(record)
  if source.parent not in (hkl.parent,hkl.parent/'olex2'):
   raise ValueError('Instrument record belongs to a different specimen directory')
  anonymous=source.name.casefold()=='cif_od'
  if not anonymous and (source.suffix.casefold() not in {'.pcf','.cif_od'} or source.stem.casefold()!=hkl.stem.casefold()):
   raise ValueError('Instrument record does not match the selected HKL stem. Use an audited ledger for other naming conventions.')
  if anonymous and any(p!=hkl and p.suffix.lower()=='.hkl' for p in hkl.parent.iterdir()):
   raise ValueError('Unqualified cif_od in a multi-sample directory needs an audited pairing ledger')
  if any(item['path']==str(source) for item in entries):continue
  entries.append(dict(path=str(source),kind='cif_metadata',source_sha256=sha(regular(source)),
                      hkl_sha256=digest,same_experiment_confirmed=True,basis=basis.strip()))
 return {'hkl':str(hkl),'sources':entries}


def form(output,known=None,language=None,metadata_ledger=None,data_dir=None,hkl=None,paired_records=(),pairing_basis=None):
 language=selected_language(language)
 assets=Path(__file__).resolve().parent.parent/'assets'
 asset=assets/('intake_form.en.html' if language=='en' else 'intake_form.html')
 template=asset.read_text('utf-8')
 data=json.loads(regular(known).read_text('utf-8-sig')) if known else {'schema':1}
 if 'data' in data:data=dict(data['data'],_previous_asked_fields=data.get('asked_once_fields',[]))
 if hkl:
  hkl=regular(unlinked(hkl))
  if data_dir and unlinked(data_dir)!=hkl.parent:raise ValueError('Selected HKL belongs to a different specimen directory')
  data_dir=hkl.parent
  previous=(data.get('metadata_ledger') or {}).get('hkl')
  if previous and unlinked(previous)!=hkl:raise ValueError('Known intake belongs to a different HKL')
 if data_dir:
  if data.get('data_dir') and unlinked(path_text(data['data_dir']))!=unlinked(data_dir):raise ValueError('Known intake belongs to a different specimen directory')
  data['data_dir']=str(unlinked(data_dir))
 from intake_metadata import prepare
 if pairing_basis and not paired_records:raise ValueError('--pairing-basis requires --paired-record')
 if paired_records:
  if metadata_ledger or data.get('metadata_ledger'):raise ValueError('Choose paired records or an existing metadata ledger')
  sources=paired_form_sources(hkl,paired_records,pairing_basis)
  from experiment_metadata_state import collect
  out=new_directory(unlinked(output))
  config=out/'paired_sources.json'
  write_json(config,sources)
  collect(config,out/'ledger')
  metadata_ledger=out/'ledger/metadata_ledger.json'
 elif hkl and not (metadata_ledger or data.get('metadata_ledger')):
  raise ValueError('Use --hkl with --paired-record or --metadata-ledger')
 data,plan,metadata=prepare(data,metadata_ledger,language,hkl)
 if not paired_records:out=new_directory(unlinked(output))
 write_json(out/'question_plan.json',plan)
 if metadata:write_json(out/'metadata_reuse.json',metadata)
 encoded=json.dumps(data,ensure_ascii=False).replace('<','\\u003c').replace('>','\\u003e').replace('&','\\u0026')
 text=template.replace('INTAKE_PREFILL_JSON',encoded)
 (out/'index.html').write_text(text,encoding='utf-8')
 logo=asset.parent/'Cairystal-logo.png'
 if logo.exists():shutil.copy2(logo,out/logo.name)
 return out

def main():
 p=argparse.ArgumentParser(description=__doc__);sub=p.add_subparsers(dest='command',required=True)
 f=sub.add_parser('form');f.add_argument('--output',required=True);f.add_argument('--known');f.add_argument('--language',choices=['zh-CN','en']);f.add_argument('--metadata-ledger');f.add_argument('--data-dir')
 f.add_argument('--hkl',help='Intended reflections for this metadata-backed questionnaire')
 f.add_argument('--paired-record',action='append',default=[],help='Explicitly paired PCF or cif_od instrument record, repeatable')
 f.add_argument('--pairing-basis',help='Evidence that the specified records belong to this experiment')
 e=sub.add_parser('accept');e.add_argument('--input',required=True);e.add_argument('--output',required=True);e.add_argument('--profile');e.add_argument('--language',choices=['zh-CN','en'])
 a=p.parse_args()
 language=a.language or 'zh-CN'
 try:
  language=selected_language(a.language)
  if a.command=='form':
   out=form(a.output,a.known,language,a.metadata_ledger,a.data_dir,a.hkl,a.paired_record,a.pairing_basis)
   print(json.dumps({'form':str(out/'index.html'),'question_plan':str(out/'question_plan.json'),'interface_language':language},ensure_ascii=False))
  else:
   state,out=export(a.input,a.output,a.profile,language);print(json.dumps({'output':str(out),'status':state['status'],'pending_questions':[local_message(x,language) for x in state['pending_questions']],'interface_language':language,'ai_calls':0},ensure_ascii=False))
   if state['pending_questions']:return 2
  return 0
 except (OSError,ValueError,TypeError) as exc:
  print(json.dumps({'status':'needs_input_correction','message':'Your original JSON is preserved. Correct the reported issue and import it again.' if language=='en' else '填写结果已保留在原 JSON 中，请仅修正下列问题后重新导入。','error':local_message(str(exc),language),'ai_calls':0},ensure_ascii=False));return 2
if __name__=='__main__':raise SystemExit(main())
