"""Execute explicit bounded SHELXL diagnostic plans; never choose a final model.

Each trial restarts from the same baseline. Raw HKL and weights are frozen.
Explicit reflection_omit trials change fitted selection and cannot be ranked as same-data fits.
Accepted edit operations are deliberately narrower than a general INS editor.
"""
from pathlib import Path
import argparse,collections,json,re,shutil,time,traceback,hashlib
import gemmi
from crystal_runtime import records,run_command,local_validation
from crystal_session import logical_text
from audit_occupancy import audit
from prepare_validation_metadata import TAGS,require_identity
from structure_diagnostics import analyse,brief,digest,newjson,res_records,number
from refinement_gate import assess

ALLOWED_RESTRAINTS={'RIGU','DELU','SIMU','ISOR','DFIX','DANG','SADI','FLAT'}
IMMUTABLE={'CELL','LATT','SYMM','HKLF','WGHT','OMIT','SHEL','MERG','TWIN','BASF','ABIN','SWAT','EXTI','TEMP'}

def controls(text,keys):return [r for r in records(text) if r[0].upper() in keys]
def build(base,plan,workspace):
 base=Path(base);workspace=Path(workspace);source=(base/'case.res').read_text(encoding='latin1')
 allowed={'name','kind','reason','evidence','expected','focus','cycles','element_changes','rename','isotropic','omit_atoms','add_restraints','remove_restraints','geometry_checks','expected_unresolved','split_fragment','common_disorder','hydrogen_riding','water_orientation','reflection_omit','control_change','occupancy_start','twin_law'}
 if set(plan)-allowed:raise ValueError('Unknown plan fields: '+str(set(plan)-allowed))
 if not re.fullmatch(r'[A-Za-z0-9_-]{1,60}',plan.get('name','')):raise ValueError('Safe unique name required')
 if not plan.get('reason') or not plan.get('evidence'):raise ValueError('Explicit hypothesis and evidence required')
 kind=plan.get('kind','diagnostic_refinement');cycles=plan.get('cycles',20)
 if kind not in {'baseline','diagnostic_refinement','omit_map'}:raise ValueError('Unsupported kind')
 h_edits=[]
 special=[k for k in ['hydrogen_riding','water_orientation','reflection_omit','control_change','occupancy_start','twin_law'] if plan.get(k)]
 if special:
  if len(special)!=1 or kind!='diagnostic_refinement' or any(plan.get(k) for k in ['element_changes','rename','isotropic','omit_atoms','add_restraints','remove_restraints','split_fragment','common_disorder']):raise ValueError('One isolated special trial operation required')
  if special[0]=='twin_law':
   from twin_quick import edit as twin_edit
   source,h_edits=twin_edit(base,plan['twin_law'])
  elif special[0]=='occupancy_start':
   from population_stability import edit as population_edit
   source,h_edits=population_edit(base,plan['occupancy_start'])
  elif special[0]=='control_change':
   from refinement_controls import edit as control_edit
   source,h_edits=control_edit(base,plan['control_change'])
  elif special[0]=='water_orientation':
   from water_h_trial import edit as water_edit
   source,h_edits=water_edit(base,plan['water_orientation'])
  elif special[0]=='reflection_omit':
   from reflection_omit_trial import edit as omit_edit
   source,h_edits=omit_edit(base,plan['reflection_omit'])
 if plan.get('hydrogen_riding'):
  if kind!='diagnostic_refinement' or any(plan.get(k) for k in ['element_changes','rename','isotropic','omit_atoms','add_restraints','remove_restraints','split_fragment','common_disorder']):raise ValueError('Existing H operation must be an isolated diagnostic branch')
  from hydrogen_riding_trial import edit
  source,h_edits=edit(base,plan['hydrogen_riding'])
 if not isinstance(cycles,int) or not 0<=cycles<=100 or (cycles==0 and kind!='omit_map'):raise ValueError('Invalid cycle request')
 parsed=res_records(base/'case.res');labelcounts=collections.Counter(a['label'].upper() for a in parsed['atoms'])
 if any(n>1 for n in labelcounts.values()):raise ValueError('This edit route requires unique labels across PART/RESI; use qualified-atom editor for duplicates')
 atommap={a['label'].upper():a for a in parsed['atoms']};symbols=parsed['sfac'];rows=records(source)
 if any(r[0].startswith('+') for r in rows):raise ValueError('Includes need an audited resolved input')
 if any(r[0].upper() in {'BLOC','XNPD'} for r in rows):raise ValueError('Parameter floors/subset blocks require a separate reviewed route')
 changes={k.upper():v for k,v in plan.get('element_changes',{}).items()}
 rename={k.upper():v for k,v in plan.get('rename',{}).items()}
 iso={x.upper() for x in plan.get('isotropic',[])};omit={x.upper() for x in plan.get('omit_atoms',[])}
 omitted_children=[];parent=None
 if omit:
  for atom in parsed['atoms']:
   if atom['element'].upper()!='H' and atom['afix']==0:parent=atom
   elif atom['element'].upper()=='H' and atom['afix'] and parent and parent['label'].upper() in omit:
    if atom['part']!=parent['part'] or atom['residue']!=parent['residue']:raise ValueError('Ambiguous H parent across PART/RESI')
    omit.add(atom['label'].upper());omitted_children.append({'atom':atom['label'],'parent':parent['label'],'reason':'Riding H cannot remain after parent omission'})
 targets=set(changes)|set(rename)|iso|omit
 if not targets<=set(atommap):raise ValueError('Unknown atom target: '+str(targets-set(atommap)))
 if len(targets)>30:raise ValueError('Too many targets for local diagnostic route')
 if omit and kind!='omit_map':raise ValueError('Atom omission permitted only in declared map-only branch')
 if kind=='omit_map' and (changes or iso or rename or plan.get('add_restraints')):raise ValueError('Do not mix map omission with repair changes')
 if iso and any(r[0].upper()=='ANIS' for r in rows):raise ValueError('Explicit ANIS would override ISO; review/remove the precise instruction in a separate input')
 if any(a['afix'] and a['label'].upper() in iso|omit|set(changes) and not (kind=='omit_map' and a['element'].upper()=='H' and a['label'].upper() in omit) for a in parsed['atoms']):raise ValueError('Targets inside AFIX require reviewed geometry/children handling')
 for r in rows:
  if r[0].upper() in {'EADP','EXYZ'} and any(x.upper() in targets for x in r[1:]):raise ValueError('Constrained target requires separate reviewed mapping')
 names={s.upper():i+1 for i,s in enumerate(symbols)}
 for el in changes.values():
  if el.upper() not in names:raise ValueError('Element not in supplied SFAC list: '+el)
 finalnames=[rename.get(a['label'].upper(),a['label']) for a in parsed['atoms'] if a['label'].upper() not in omit]
 if len(set(x.upper() for x in finalnames))!=len(finalnames) or any(not re.fullmatch(r'[A-Za-z][A-Za-z0-9]{0,3}',x) for x in finalnames):raise ValueError('Rename creates collisions or unsupported labels')
 cb=gemmi.cif.read_file(str(base/'case.cif')).sole_block();ueqs={gemmi.cif.as_string(row[0]).upper():number(row[1]) for row in cb.find(['_atom_site_label','_atom_site_U_iso_or_equiv'])}
 split=None
 if plan.get('split_fragment') or plan.get('common_disorder'):
  if plan.get('split_fragment') and plan.get('common_disorder'):raise ValueError('One fragment generator per trial')
  if targets or kind!='diagnostic_refinement':raise ValueError('Do not combine split seed with other atom edits')
  if plan.get('common_disorder'):
   from common_disorder import generate
   split=generate(parsed,cb,plan['common_disorder'])
  else:
   from split_fragment_seed import generate
   split=generate(parsed,cb,plan['split_fragment'])
  for row in rows:
   if row[0].upper() in atommap:continue
   if any(x.upper() in split['selected'] for x in row[1:]):raise ValueError('Existing instructions reference split targets; supply a separately reviewed constraint mapping')
 remove={' '.join(x.split()).upper() for x in plan.get('remove_restraints',[])};seen_remove=set();edits=([{'auto_omitted_riding_children':omitted_children}] if omitted_children else [])+h_edits;output=[]
 if split:edits.append({'split_fragment':{k:v for k,v in split.items() if k!='rows'}})
 last_fvar=max((i for i,r in enumerate(rows) if r[0].upper()=='FVAR'),default=-1)
 remove_afix=set()
 for i,row in enumerate(rows):
  if row[0].upper()!='AFIX' or int(row[1])==0:continue
  stop=next((j for j in range(i+1,len(rows)) if rows[j][0].upper() in {'AFIX','HKLF'}),len(rows))
  group={v[0].upper() for v in rows[i+1:stop] if v[0].upper() in atommap}
  if split and group.intersection(split['selected']):
   if not group<=set(split['selected']) or any(atommap[k]['element'].upper()!='H' for k in group):raise ValueError('Partial AFIX fragment split needs review')
   remove_afix.add(i)
  if group.intersection(omit):
   if not group<=omit:raise ValueError('Partial AFIX group omission would leave broken geometry')
   remove_afix.add(i)
 for i,row in enumerate(rows):
  row=list(row);key=row[0].upper();canonical=' '.join(row).upper()
  if split and key in split['selected']:continue
  if split and i==last_fvar:row.append(str(split['free_variable_start']))
  if i in remove_afix:edits.append({'removed_empty_AFIX_group':row});continue
  if canonical in remove:
   if key not in ALLOWED_RESTRAINTS:raise ValueError('Only specified restraint removal allowed')
   seen_remove.add(canonical);edits.append({'removed_instruction':row});continue
  if key in {'L.S.','CGLS','ACTA','LIST','FMAP','PLAN'}:continue
  if key in ALLOWED_RESTRAINTS and any(x.upper() in omit for x in row[1:]):
   edits.append({'removed_for_omit_map':row});continue
  if key in atommap:
   if key in omit:edits.append({'omitted_atom_for_map':key});continue
   if key in changes:edits.append({'atom':key,'old_element':atommap[key]['element'],'new_element':changes[key]});row[1]=str(names[changes[key].upper()])
   if key in iso:
    u=ueqs.get(key)
    if u is None or u<=0:raise ValueError('Positive paired CIF Ueq required for ISO start: '+key)
    edits.append({'atom':key,'adp_change':'ANI to ISO','start_Uiso':u,'source':'paired CIF Ueq'});row=row[:6]+[f'{u:.8f}']
  if key=='HKLF':
   if split:output+=split['rows']
   for instruction in plan.get('add_restraints',[]):
    if not isinstance(instruction,str) or '\n' in instruction or '\r' in instruction:raise ValueError('One instruction per string')
    card=instruction.split()[0].upper()
    if card not in ALLOWED_RESTRAINTS:raise ValueError('Unsupported injected instruction: '+card)
    output.append(instruction);edits.append({'added_instruction':instruction})
   output+=['L.S. '+str(cycles)]+(['LIST 6','FMAP 2','PLAN 100'] if kind=='omit_map' else ['LIST 4','ACTA','FMAP 2','PLAN 100'])
  output.append([rename.get(v.upper(),v) for v in row])
 if remove!=seen_remove:raise ValueError('Requested restraint not found')
 text='TITL Cairystal explicit diagnostic candidate '+plan['name']+'\n'+logical_text(output)
 # Derive bookkeeping only after an atom-type/removal change; no chemical identity claim.
 if changes or omit:
  tmp=workspace/'unit_accounting_input.res';tmp.write_text(text,encoding='ascii');account=audit(tmp,gemmi)
  composition={k.upper():v for k,v in account['modeled_unit_cell_composition'].items()}
  text=re.sub(r'^UNIT\s+[^\r\n]+', 'UNIT '+' '.join(f'{composition.get(s.upper(),0):.6f}' for s in symbols),text,flags=re.M)
  edits.append({'UNIT_updated_from_modelled_atoms':composition,'chemical_formula_confirmed':False})
 if controls(source,IMMUTABLE)!=controls(text,IMMUTABLE):raise ValueError('Frozen cell/symmetry/data/weight controls changed')
 return text,edits

def metadata_copy(base,native,target):
 doc=gemmi.cif.read_file(str(native/'case.cif'));dst=doc.sole_block();src=gemmi.cif.read_file(str(base/'case.cif')).sole_block()
 from crystal_runtime import compare_cell_tokens,canonical
 if digest(base/'case.hkl')!=digest(native/'case.hkl'):raise ValueError('Metadata overlay requires unchanged HKL')
 cell_controls=lambda p:[r for r in canonical(p.read_text('latin1')) if r[0] in {'CELL','LATT','SYMM'}]
 if cell_controls(base/'case.res')!=cell_controls(native/'case.res'):raise ValueError('Metadata overlay requires unchanged CELL and symmetry controls')
 compare_cell_tokens(src,dst)
 from crystal_runtime import number as cif_number,cif_tolerance
 tag='_diffrn_radiation_wavelength';a=src.find_value(tag);b=dst.find_value(tag)
 if abs(cif_number(a)-cif_number(b))>cif_tolerance(a)+cif_tolerance(b):raise ValueError('Wavelength mismatch in metadata overlay')
 changes=[]
 # The same immutable HKL/RES lineage establishes specimen identity for this comparison.
 for tag in TAGS:
  old=dst.find_value(tag);new=src.find_value(tag)
  if new is not None and old!=new:dst.set_pair(tag,new);changes.append({'tag':tag,'native':old,'same_experiment':new})
 # A cell s.u. and its volume s.u. form one experimental record. Do not retain
 # a freshly calculated volume s.u. from placeholder ZERR values.
 tag='_cell_volume';old=dst.find_value(tag);new=src.find_value(tag)
 if new not in (None,'?','.'):
  volume=gemmi.cif.as_number(new)
  values=[gemmi.cif.as_number(src.find_value(t)) for t in ['_cell_length_a','_cell_length_b','_cell_length_c','_cell_angle_alpha','_cell_angle_beta','_cell_angle_gamma']]
  calculated=gemmi.UnitCell(*values).volume
  if not 0<volume or abs(volume-calculated)>max(.1,calculated*.001):raise ValueError('Source cell volume conflicts with source cell')
 else:
  new=new or '?'
 if old!=new:dst.set_pair(tag,new);changes.append({'tag':tag,'native':old,'same_experiment':new})
 target.mkdir()
 for tag in ['_cell_length_a','_cell_length_b','_cell_length_c','_cell_angle_alpha','_cell_angle_beta','_cell_angle_gamma']:
  # Carry audited uncertainties (including their absence), not placeholder ZERR precision.
  old=dst.find_value(tag);new=src.find_value(tag)
  if new is not None and old!=new:dst.set_pair(tag,new);changes.append({'tag':tag,'native':old,'same_experiment':new})
 doc.write_file(str(target/'case.cif'));shutil.copy2(native/'case.fcf',target/'case.fcf')
 newjson(target/'metadata_lineage.json',{'source_CIF_sha256':digest(base/'case.cif'),'native_CIF_sha256':digest(native/'case.cif'),
  'HKL_unchanged':digest(base/'case.hkl')==digest(native/'case.hkl'),'changes':changes,'structural_fields_copied':False})

def execute(base,output,plan,software,baseline_diag=None,dedup=None,resources=None):
 start=time.perf_counter();base=Path(base);out=Path(output)
 if out.exists():raise FileExistsError(str(out))
 out.mkdir(parents=True);newjson(out/'plan.json',plan)
 sourcehash={x.name:digest(x) for x in base.iterdir() if x.is_file()}
 result={'name':plan['name'],'kind':plan.get('kind','diagnostic_refinement'),'status':'running','scientific_status':'not_accepted',
  'plan':str(out/'plan.json'),'source_hashes':sourcehash,'hypothesis':plan['reason'],'evidence':plan['evidence'],
  'official_validation':False,'model_adopted':False,'AB':None,'errors':[]}
 try:
  native=out/'native';native.mkdir();text,edits=build(base,plan,out)
  (native/'case.ins').write_text(text,encoding='ascii');shutil.copy2(base/'case.hkl',native/'case.hkl')
  implementation={p.name:digest(p) for p in [Path(__file__),*[Path(__file__).with_name(n) for n in ['structure_diagnostics.py','split_fragment_seed.py','crystal_runtime.py','prepare_validation_metadata.py','platon_execution.py','parse_platon_alerts.py']]]}
  if plan.get('common_disorder'):
   from common_disorder import CATALOG
   implementation['common_disorder.py']=digest(Path(__file__).with_name('common_disorder.py'))
   implementation['common_disorder_solvents.json']=digest(CATALOG)
  if plan.get('hydrogen_riding'):implementation['hydrogen_riding_trial.py']=digest(Path(__file__).with_name('hydrogen_riding_trial.py'))
  if plan.get('occupancy_start'):implementation['population_stability.py']=digest(Path(__file__).with_name('population_stability.py'))
  if plan.get('twin_law'):
   implementation['twin_quick.py']=digest(Path(__file__).with_name('twin_quick.py'))
   implementation['twin_evidence']=digest(Path(plan['twin_law']['evidence']))
  if plan.get('water_orientation'):
   for n in ['water_h_trial.py','donor_audit.py']:implementation[n]=digest(Path(__file__).with_name(n))
  if plan.get('reflection_omit'):
   for n in ['reflection_omit_trial.py','reflection_audit.py']:implementation[n]=digest(Path(__file__).with_name(n))
  if plan.get('control_change'):
   for n in ['refinement_controls.py','geometry_audit.py']:implementation[n]=digest(Path(__file__).with_name(n))
   result['control_change']=plan['control_change']
   if plan['control_change']['mode']=='resolution_window':result['same_fitted_data']=False;result['ranking_allowed']=False
  result['implementation_hashes']=implementation
  from native_resources import effective
  selected_resources=effective(**(resources or {}));result['native_resources']=selected_resources
  result['comparison_context']={'hkl_sha256':digest(base/'case.hkl'),
   'frozen_controls':controls(text,IMMUTABLE),'SFAC':controls(text,{'SFAC'})}
  fingerprint=hashlib.sha256(json.dumps({'records':records(text),'hkl':digest(base/'case.hkl'),
    'metadata':digest(base/'case.cif'),'fab':digest(base/'case.fab') if (base/'case.fab').exists() else None,
    'software':{k:digest(p) for k,p in software.items()},'implementation':implementation,'native_resources':selected_resources},sort_keys=True).encode()).hexdigest()
  result['configuration_fingerprint']=fingerprint
  if dedup is not None and fingerprint in dedup:
   result.update(status='skipped_identical_configuration',reuse_evidence=dedup[fingerprint],elapsed_s=round(time.perf_counter()-start,4),source_unchanged=True)
   newjson(out/'result.json',result);return result
  from squeeze_bundle import companion_fab
  fab=companion_fab(base/'case.res')
  if fab:shutil.copy2(fab,native/'case.fab')
  result['edits']=edits;result['command']=run_command([software['shelxl'],'case',f"-t{selected_resources['threads']}",f"-b{selected_resources['matrix_parameters']}"],native,native/'process.log',600)
  result['software_sha256']={k:digest(p) for k,p in software.items()}
  if plan.get('kind')=='omit_map':
   log=(native/'process.log').read_text(encoding='latin1')
   gate=assess(native,'case')
   if not gate['execution_complete'] or not (native/'case.fcf').exists():
    raise ValueError('Map-only run incomplete or native warning/error; inspect process.log')
   mapdata=res_records(native/'case.res')
   result.update(status='completed_map',scientific_status='map_only_not_a_model_candidate',
    difference_peak_list=mapdata['peaks'],map_fcf=str(native/'case.fcf'),native_gate=gate,
    native_warning_lines=re.findall(r'^\s*\*\*.*$',log,re.M),
    map_limitation='L.S. 0 without ACTA: phase-biased omit-map diagnostic, no model refinement/convergence/acceptance or model checkCIF claim.',
    elapsed_s=round(time.perf_counter()-start,4),source_unchanged=all(digest(base/name)==value for name,value in sourcehash.items()))
   newjson(out/'result.json',result)
   if dedup is not None:dedup[fingerprint]=str(out/'result.json')
   return result
  result['native_gate']=assess(native,'case')
  if not result['native_gate']['execution_complete']:raise ValueError('Native refinement failed/incomplete: '+str(result['native_gate']['failures'])+'; inspect '+str(native/'process.log'))
  if any(not (native/('case.'+ext)).is_file() or not (native/('case.'+ext)).stat().st_size for ext in ['cif','res','fcf']):raise ValueError('Native output missing/empty; inspect '+str(native/'process.log'))
  metadata_copy(base,native,out/'validation_inputs')
  val=local_validation(software['platon'],out/'validation_inputs',out/'validation','case',120)
  # A paired evidence directory, with a documented experimental metadata overlay.
  paired=out/'paired';paired.mkdir()
  for ext in ['res','lst','ins','hkl']+(['fab'] if fab else []):shutil.copy2(native/('case.'+ext),paired/('case.'+ext))
  shutil.copy2(native/'process.log',paired/'process.log')
  for ext in ['cif','fcf','chk','ckf']:shutil.copy2(out/'validation'/('case.'+ext),paired/('case.'+ext))
  v=analyse(paired,focus=plan.get('focus'),case_status='diagnostic_candidate')
  newjson(out/'diagnostic.json',v);(out/'diagnostic.txt').write_text(brief(v),encoding='utf-8')
  result.update(status='completed',diagnostic=str(out/'diagnostic.json'),metrics=v['gate']['metrics'],
   difference_density=v['difference_density'],parameters=v['parameter_count'],restraints=v['restraint_count'],
   gate=v['gate']['status'],AB=v['AB_alerts'],local_validation_seconds=val['elapsed_s'],
   occupancy_warnings=v['occupancy_audit'].get('warnings',[]),
   geometry_results=[])
  result['restraint_tension']=v['restraint_tension']
  result['model_sha256']=digest(paired/'case.cif')
  if plan.get('hydrogen_riding') or plan.get('water_orientation'):
   from hydrogen_riding_trial import environment
   hconfig=plan.get('hydrogen_riding') or plan['water_orientation']
   result['hydrogen_geometry']={'before':environment(base,hconfig['parent']),'after':environment(paired,hconfig['parent'])}
  result['diagnostic_priorities']=v.get('diagnostic_priorities')
  result['ADP_summary']={'non_H_atoms':v['heavy_atom_count'],
   'max_Ueq':max((a['Ueq'] for a in v['all_atoms'] if a['element']!='H' and a['Ueq'] is not None),default=None),
   'max_principal_rms_ratio':max((a['principal_rms_axis_ratio'] for a in v['all_atoms'] if a['element']!='H' and a['principal_rms_axis_ratio'] is not None),default=None)}
  atommap={a['label'].upper():a for a in v['all_atoms']};cell=gemmi.UnitCell(*v['cell'])
  for g in plan.get('geometry_checks',[]):
   a,b=[atommap[x.upper()] for x in g['atoms']]
   distance=cell.find_nearest_pbc_image(gemmi.Fractional(*a['xyz']),gemmi.Fractional(*b['xyz']),0).dist()
   lo,hi=g['range'];result['geometry_results'].append(dict(g,distance=distance,within_declared_range=lo<=distance<=hi))
  result['review_reasons']=list(v['gate']['failures'])+list(v['gate']['review_reasons'])
  result['review_reasons']+=['Geometry outside explicit hypothesis: '+str(g['atoms']) for g in result['geometry_results'] if not g['within_declared_range']]
  result['review_reasons']+=plan.get('expected_unresolved',[])
  result['review_reasons'].append('No automatic chemical/symmetry/disorder acceptance; compare complete evidence and controls.')
  if baseline_diag:
   before=baseline_diag['gate']['metrics'];after=v['gate']['metrics'];result['comparison']={}
   for k in ['R1_observed','wR2','GooF','NPD_atoms','last_abs_max_shift_esd']:
    a=before.get(k);b=after.get(k);result['comparison'][k]={'baseline':a,'candidate':b,'delta':b-a if a is not None and b is not None else None}
   result['comparison']['difference_density']={'baseline':baseline_diag['difference_density'],'candidate':v['difference_density']}
  if plan.get('kind')=='omit_map':result['scientific_status']='map_only_not_a_model_candidate'
 except Exception as exc:
  result['status']='failed';result['errors'].append({'error':str(exc),'traceback':traceback.format_exc(),'log_directory':str(out)})
  failure=out/'validation/local_validation.json'
  if failure.is_file():
   validation=json.loads(failure.read_text('utf-8'));result['validation_complete']=validation.get('validation_complete',False)
   result['validation_state']=validation.get('state');result['validation_record']=str(failure)
 result['source_unchanged']=all(digest(base/name)==value for name,value in sourcehash.items())
 result['elapsed_s']=round(time.perf_counter()-start,4);newjson(out/'result.json',result)
 if dedup is not None and result['status']=='completed':dedup[fingerprint]=str(out/'result.json')
 return result

def run_plan(path):
 from trial_checkpoint import context,verified_previous,validate_names,Checkpoint
 from crystal_runtime import write_json
 path=Path(path);job=json.loads(path.read_text(encoding='utf-8'));base=Path(job['baseline']);output=Path(job['output'])
 if output.exists():raise FileExistsError(str(output))
 validate_names(job['trials']);ctx=context(job);reuse,counts=verified_previous(job,ctx)
 job=dict(job,shelxl_resources=ctx['native_resources'])
 output.mkdir(parents=True);newjson(output/'job.json',job);baseline_diag=analyse(base,focus=job.get('focus'),case_status='partial_model')
 newjson(output/'baseline_diagnostic.json',baseline_diag);result=[];dedup={};checkpoint=Checkpoint(output,ctx,job,counts)
 try:
  for plan in job['trials']:
   name=plan['name'];reused=name in reuse
   if reused:
    saved=reuse[name];shutil.copytree(saved['directory'],output/name)
    v=dict(saved['result'],resume_reuse={'source':saved['directory'],'native_rerun':False})
    if v['status']=='completed' and v.get('configuration_fingerprint'):dedup[v['configuration_fingerprint']]=str(output/name/'result.json')
   else:
    checkpoint.begin(name);v=execute(base,output/name,plan,job['software'],baseline_diag,dedup,ctx['native_resources'])
   result.append(v);checkpoint.finish(v,reused)
   write_json(output/'results.json',{'cases':result,'pending':checkpoint.value['pending'],'native_attempts_this_run':checkpoint.value['native_attempts_this_run'],'reused_trials':checkpoint.value['reused_trials']})
   from trial_summary import update as update_summary
   update_summary(output)
   print(json.dumps({'name':name,'status':v['status'],'reused':reused,'R1':(v.get('metrics') or {}).get('R1_observed'),'gate':v.get('gate'),'original_trial_seconds':v['elapsed_s']},ensure_ascii=False),flush=True)
   if job.get('stop_on_control_failure') and len(result)==1 and v['status']!='completed':break
  checkpoint.close('completed' if not checkpoint.value['pending'] else 'stopped_control_failure')
  update_summary(output)
 except BaseException as exc:
  checkpoint.close('interrupted',str(exc) or type(exc).__name__);raise
 return result
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('plan');a=p.parse_args();run_plan(a.plan)
