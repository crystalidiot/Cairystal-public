"""Read-only atom-centred evidence from explicitly paired CIF/RES/LST/CHK.

Symmetry contacts are observations, not automatically assigned chemical bonds.
Q peaks are a truncated SHELXL peak list, not a full residual-density map.
"""
from pathlib import Path
import argparse,collections,hashlib,json,math,re,time
import gemmi
from audit_occupancy import logical_lines,CARDS,audit
from parse_platon_alerts import parse
from refinement_gate import assess

def digest(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def number(v):
 try:
  x=gemmi.cif.as_number(v);return x if math.isfinite(x) else None
 except (ValueError,TypeError):return None
def unquote(v):return gemmi.cif.as_string(v) if v is not None else None
def newjson(p,v):
 p=Path(p)
 if p.exists():raise FileExistsError(str(p))
 p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(v,ensure_ascii=False,indent=2,allow_nan=False),encoding='utf-8')

def res_records(path):
 rows=[];part=0;residue='0';afix=0;atoms=[];after=False;peaks=[]
 text=Path(path).read_text(encoding='latin1');sfac=[];controls=[]
 for line in logical_lines(text):
  f=line.split();key=f[0].upper()
  if key=='END':after=True;continue
  if after:
   if re.fullmatch(r'Q\d+',key) and len(f)>=8:
    try:peaks.append({'label':f[0],'xyz':list(map(float,f[2:5])),'height':float(f[7])})
    except ValueError:pass
   continue
  rows.append(f)
  if key=='SFAC':sfac+=f[1:]
  if key=='PART':part=int(f[1])
  if key=='RESI':residue=' '.join(f[1:]) or '0'
  if key=='AFIX':afix=int(f[1])
  if key in CARDS:
   if key in {'FVAR','WGHT','OMIT','SHEL','TWIN','BASF','HKLF','RIGU','SIMU','ISOR','DELU','DFIX','DANG','SADI','SAME','FLAT','EADP','EXYZ','BLOC','DAMP','XNPD','ABIN','MERG'}:controls.append(line)
   continue
  if len(f)<7:continue
  try:
   idx=int(f[1]);xyz=list(map(float,f[2:5]));sof=float(f[5]);u=list(map(float,f[6:]))
  except ValueError:continue
  if not 1<=idx<=len(sfac):continue
  atoms.append({'label':f[0],'part':part,'residue':residue,'afix':afix,'sfac_index':idx,'element':sfac[idx-1],
   'xyz':[v-10 if 5<v<15 else v for v in xyz],'encoded_sof':sof,'adp_raw':u,'row':f})
 return {'rows':rows,'atoms':atoms,'peaks':peaks,'controls':controls,'sfac':sfac}

def cartesian_tensor(cell,u):
 """CIF Uij -> Ucart = A diag(a*,b*,c*) Uij diag(a*,b*,c*) A^T."""
 rec=cell.reciprocal();a=cell.orth.mat.tolist();lengths=[rec.a,rec.b,rec.c]
 transform=gemmi.Mat33([[a[i][j]*lengths[j] for j in range(3)] for i in range(3)])
 tensor=gemmi.SMat33d(u[0],u[1],u[2],u[3],u[4],u[5]).transformed_by(transform)
 return tensor

def structure(cif,res):
 doc=gemmi.cif.read_file(str(cif));blocks=[b for b in doc if b.find_value('_cell_length_a')]
 if len(blocks)!=1:raise ValueError('Select one structural CIF block')
 b=blocks[0];cellvals=[number(b.find_value('_cell_'+x)) for x in ['length_a','length_b','length_c','angle_alpha','angle_beta','angle_gamma']]
 if any(v is None for v in cellvals):raise ValueError('Missing cell')
 cell=gemmi.UnitCell(*cellvals)
 opstrings=list(b.find_values('_space_group_symop_operation_xyz')) or list(b.find_values('_symmetry_equiv_pos_as_xyz'))
 if not opstrings:raise ValueError('Explicit CIF symmetry operations required')
 ops=[gemmi.Op(unquote(s)) for s in opstrings]
 r=res_records(res);labels=list(b.find_values('_atom_site_label'))
 if not labels:raise ValueError('Missing atom loop')
 columns={k:list(b.find_values('_atom_site_'+k)) for k in ['type_symbol','fract_x','fract_y','fract_z','U_iso_or_equiv','occupancy','adp_type','disorder_group','disorder_assembly']}
 if any(len(columns[k])!=len(labels) for k in ['type_symbol','fract_x','fract_y','fract_z','U_iso_or_equiv','occupancy']):raise ValueError('Incomplete atom loop')
 anis={}
 for row in b.find(['_atom_site_aniso_label']+['_atom_site_aniso_U_'+v for v in ['11','22','33','12','13','23']]):
  vals=[number(v) for v in list(row)[1:]]
  if any(v is None for v in vals):raise ValueError('Invalid ADP tensor')
  anis[unquote(row[0])]=vals
 by_label_element=collections.defaultdict(list)
 for old in r['atoms']:
  by_label_element[(old['label'].upper(),old['element'].upper())].append(old)
 atoms=[]
 for i,l in enumerate(labels):
  label=unquote(l);el=unquote(columns['type_symbol'][i]);xyz=[number(columns[k][i]) for k in ['fract_x','fract_y','fract_z']]
  if any(v is None for v in xyz):raise ValueError('Missing coordinates: '+label)
  candidates=[]
  base=label.split('^',1)[0].split('_',1)[0]
  for old in by_label_element[(base.upper(),el.upper())]:
   dist=cell.find_nearest_pbc_image(gemmi.Fractional(*xyz),gemmi.Fractional(*old['xyz']),0).dist()
   if dist<.015:candidates.append(old)
  context=candidates[0] if len(candidates)==1 else None
  aniso=anis.get(label);cart=cartesian_tensor(cell,aniso) if aniso else None
  eigen=sorted(cart.calculate_eigenvalues()) if cart else None
  ueq=number(columns['U_iso_or_equiv'][i]);derived=cart.trace()/3 if cart else ueq
  atoms.append({'label':label,'element':el,'xyz':xyz,'occupancy':number(columns['occupancy'][i]),
   'Ueq':ueq,'adp_type':'ANI' if aniso else 'ISO','cartesian_eigenvalues':eigen,
   'principal_variance_ratio':eigen[-1]/eigen[0] if eigen and eigen[0]>0 else None,
   'principal_rms_axis_ratio':math.sqrt(eigen[-1]/eigen[0]) if eigen and eigen[0]>0 else None,
   'non_positive_definite':eigen[0]<=0 if eigen else None,'Ueq_from_tensor':derived,
   'Ueq_difference_from_CIF':derived-ueq if derived is not None and ueq is not None else None,
   'cartesian_tensor':cart.as_mat33().tolist() if cart else None,
   'part':context['part'] if context else None,'residue':context['residue'] if context else None,
   'afix':context['afix'] if context else None,'encoded_sof':context['encoded_sof'] if context else None,
   'res_label':context['label'] if context else None,'res_context_status':'matched' if context else 'ambiguous_or_unmatched',
   'disorder_group':unquote(columns['disorder_group'][i]) if columns['disorder_group'] else None})
 return b,cell,ops,atoms,r

def nearest_images(cell,ops,a,b,cutoff):
 return _nearby(cell,a,gemmi.Fractional(*a),_transforms(ops,b),cutoff)

def _transforms(ops,xyz):
 return [(op.triplet(),gemmi.Fractional(*op.apply_to_xyz(xyz))) for op in ops]

def _nearby(cell,a,origin,transforms,cutoff):
 found=[];positions=[]
 for name,pos in transforms:
  img=cell.find_nearest_pbc_image(origin,pos,0)
  d=img.dist()
  if d>=cutoff or d<.001:continue
  shift=list(img.pbc_shift);xyz=[pos[i]+shift[i] for i in range(3)]
  cart=cell.orthogonalize(gemmi.Fractional(*[xyz[i]-a[i] for i in range(3)]))
  if any(sum((xyz[i]-old[i])**2 for i in range(3))<1e-10 for old in positions):continue
  positions.append(xyz);found.append({'distance':d,'symmetry':name,'translation':shift,'vector_cart':[cart.x,cart.y,cart.z]})
 return found

def compatible(a,b,symmetry,translation):
 if a['part'] is None or b['part'] is None:return None
 if a['part'] and b['part'] and a['part']!=b['part']:return False
 if (a['part']<0 or b['part']<0) and (symmetry!='x,y,z' or translation!=[0,0,0]):return False
 return True

def analyse(directory,stem='case',focus=None,case_status=None,*,_parsed=None):
 start=time.perf_counter();d=Path(directory);cif=d/(stem+'.cif');res=d/(stem+'.res');lst=d/(stem+'.lst');chk=d/(stem+'.chk')
 b,cell,ops,atoms,r=_parsed if _parsed is not None else structure(cif,res)
 alerts=parse(chk.read_text(encoding='latin1')) if chk.exists() else {'alerts':[],'warnings':['No CHK supplied'],'counts':{},'report_footer_present':False}
 gate=assess(d,stem);lookup={a['label'].upper():a for a in atoms};ab=[a for a in alerts['alerts'] if a['level'] in ['A','B']]
 targets=set(x.upper() for x in (focus or []));alert_matches=[]
 for alert in ab:
  words=set(re.findall(r'[A-Z][A-Z0-9]*(?:\^[A-Z])?(?:_\d+)?',alert['text'].upper()))
  matches=[key for key in lookup if key in words]
  targets.update(matches);alert_matches.append(dict(alert,atom_labels=[lookup[k]['label'] for k in matches]))
 # Numerical outliers are explicit screening hints, not scientific acceptance thresholds.
 for a in atoms:
  if a['element']!='H' and ((a['principal_rms_axis_ratio'] or 0)>4 or a['non_positive_definite'] or (a['Ueq'] or 0)>.20):targets.add(a['label'].upper())
 if not targets:targets=set(a['label'].upper() for a in sorted(atoms,key=lambda a:a['Ueq'] or 0,reverse=True)[:5] if a['element']!='H')
 regions=[];allcontacts=[]
 transformed={tuple(site['xyz']):_transforms(ops,site['xyz']) for site in atoms+r['peaks']}
 for a in atoms:
  if a['label'].upper() not in targets:continue
  origin=gemmi.Fractional(*a['xyz'])
  neighbors=[]
  for other in atoms:
   for image in _nearby(cell,a['xyz'],origin,transformed[tuple(other['xyz'])],3.5):
    e1=gemmi.Element(a['element']);e2=gemmi.Element(other['element']);cut=e1.covalent_r+e2.covalent_r+.35
    comp=compatible(a,other,image['symmetry'],image['translation']);bondlike=image['distance']<cut
    near={'label':other['label'],'element':other['element'],'part':other['part'],'occupancy':other['occupancy'],'Ueq':other['Ueq'],
     'distance':round(image['distance'],4),'symmetry':image['symmetry'],'translation':image['translation'],
     'part_compatible':comp,'within_covalent_radius_screen':bondlike,
     'contact_type':'alternative_or_negative_PART' if comp is False else 'metal_contact' if e1.is_metal or e2.is_metal else 'geometric_bond_candidate' if bondlike else 'nonbonded_contact',
     'chemical_bond_confirmed':False}
    if image['symmetry']=='x,y,z' and image['translation']==[0,0,0] and a['cartesian_tensor'] and other['cartesian_tensor']:
     direction=[v/image['distance'] for v in image['vector_cart']]
     def along(t):return sum(direction[i]*t[i][j]*direction[j] for i in range(3) for j in range(3))
     near['delta_U_along_line_A2']=along(a['cartesian_tensor'])-along(other['cartesian_tensor'])
     near['delta_U_sigma']=None
    neighbors.append(near)
  peaks=[]
  for p in r['peaks']:
   images=_nearby(cell,a['xyz'],origin,transformed[tuple(p['xyz'])],2.5)
   if images:
    v=min(images,key=lambda x:x['distance']);peaks.append({'label':p['label'],'height':p['height'],'distance':round(v['distance'],4),'symmetry':v['symmetry'],'translation':v['translation']})
  neighbors.sort(key=lambda x:x['distance']);peaks.sort(key=lambda x:(-x['height'],x['distance']))
  relevant=[line for line in r['controls'] if any(re.fullmatch(re.escape(a['res_label'] or a['label']),token,re.I) for token in line.split())]
  regions.append(dict(a,neighbors=neighbors,nearby_reported_Q_peaks=peaks,explicit_controls_mentioning_atom=relevant))
  allcontacts.extend({'atom':a['label'],**n} for n in neighbors if n['within_covalent_radius_screen'])
 accounting=None
 try:accounting=audit(res,gemmi)
 except Exception as e:accounting={'error':str(e),'warnings':['Occupancy audit unavailable; inspect actual CIF/RES pairing and labels.']}
 lsttext=lst.read_text(encoding='latin1') if lst.exists() else ''
 parameter_count=number(b.find_value('_refine_ls_number_parameters'))
 restraint_count=number(b.find_value('_refine_ls_number_restraints'))
 shifts=re.findall(r'Mean shift/esd =\s*([\d.]+)\s+Maximum =\s*(-?[\d.]+) for\s+([^\r\n]+)',lsttext)
 residual=[number(b.find_value('_refine_diff_density_'+v)) for v in ['max','min']]
 result={'schema':1,'source_directory':str(d),'source_hashes':{p.name:digest(p) for p in [cif,res,lst,chk] if p.exists()},
  'case_status':case_status,'cell':list(cell.parameters),'space_group':unquote(b.find_value('_space_group_name_H-M_alt') or b.find_value('_symmetry_space_group_name_H-M')),
  'atom_count':len(atoms),'heavy_atom_count':sum(a['element']!='H' for a in atoms),'all_atoms':atoms,
  'gate':gate,'AB_alerts':alert_matches,'validation_parser':{k:v for k,v in alerts.items() if k!='alerts'},
  'regions':regions,'screened_geometric_contacts':allcontacts,'active_controls':r['controls'],
  'occupancy_audit':accounting,'parameter_count':parameter_count,'restraint_count':restraint_count,
  'last_shifts':shifts[-5:],'difference_density':dict(zip(['max','min'],residual)),
  'restraint_tension':__import__('restraint_tension').parse_final_listing(lsttext),
  'statistics_provenance':{'parameters_restraints_difference_density':'paired CIF scalar fields','refinement_gate':'LST/process logs'},
  'screening_thresholds':{'principal_rms_axis_ratio':4,'Ueq_A2':.2,'neighbors_A':3.5,'Q_peak_distance_A':2.5,'covalent_radius_margin_A':.35},
  'limitations':['Contacts do not establish chemical bonds. Mutually exclusive PART contacts are retained and labelled.',
  'Only nearest periodic image per symmetry operation is listed; very small cells can require additional translations.',
  'Q lists are truncated positive-peak reports, not complete spatial positive/negative residual maps.',
  'Cartesian tensor central values do not include covariance; line-displacement difference has no sigma.',
  'This packet cannot determine solvent identity, protonation, disorder uniqueness or accept a final model.'],
  'elapsed_s':round(time.perf_counter()-start,4),'model_change_permitted':False}
 from diagnostic_priorities import priorities
 result['diagnostic_priorities']=priorities(result)
 return result

def brief(v):
 lines=['原子级异常诊断（只读，不自动接受模型）',f"目录：{v['source_directory']}",f"状态：{v['case_status']}；{v['space_group']}；非氢原子 {v['heavy_atom_count']}",
  '精修：'+json.dumps(v['gate']['metrics'],ensure_ascii=False),
  f"参数/限制：{v['parameter_count']}/{v['restraint_count']}；差值密度 {v['difference_density']}",'A/B：']
 lines += [f"{a['code']}_{a['level']} {a['text']}" for a in v['AB_alerts']]
 tension=v.get('restraint_tension',{})
 if tension.get('needs_review'):
  lines.append('几何限制冲突需复核：'+json.dumps(tension,ensure_ascii=False))
 if v.get('diagnostic_priorities',{}).get('findings'):
  lines.append('诊断优先顺序：'+json.dumps(v['diagnostic_priorities']['findings'],ensure_ascii=False))
 for a in v['regions']:
  lines.append(f"\n{a['label']} ({a['element']}) PART={a['part']} occ={a['occupancy']} Ueq={a['Ueq']} {a['adp_type']} 主轴长度比={a['principal_rms_axis_ratio']}")
  lines.append('近邻：'+'; '.join(f"{n['label']} {n['distance']:.3f}Å ({n['contact_type']};{n['symmetry']};{n['translation']})" for n in a['neighbors'][:8]))
  lines.append('附近已列差值峰：'+'; '.join(f"{p['label']} {p['height']:.2f}e/Å³ 距{p['distance']:.2f}Å" for p in a['nearby_reported_Q_peaks'][:5]))
  if a['explicit_controls_mentioning_atom']:lines.append('显式限制：'+'; '.join(a['explicit_controls_mentioning_atom']))
 lines+=['\n边界：键连为几何筛查；差值峰列表不等于完整密度图；未知项须继续诊断。']
 return '\n'.join(lines)+'\n'

def main():
 p=argparse.ArgumentParser();p.add_argument('directory',type=Path);p.add_argument('--stem',default='case');p.add_argument('--focus',nargs='*');p.add_argument('--status');p.add_argument('--output',required=True,type=Path)
 a=p.parse_args();v=analyse(a.directory,a.stem,a.focus,a.status);newjson(a.output,v)
 textpath=a.output.with_suffix('.txt')
 if textpath.exists():raise FileExistsError(str(textpath))
 textpath.write_text(brief(v),encoding='utf-8');print(json.dumps({'output':str(a.output),'regions':len(v['regions']),'seconds':v['elapsed_s']},ensure_ascii=False))
if __name__=='__main__':main()
