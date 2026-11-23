"""Build an explicitly reviewed two-orientation, ISO fragment seed.

This is a hypothesis generator, never an automatic discovery/acceptance of disorder.
Only full-occupancy general-position, unique, hydrogen-free input fragments.
"""
import math,re
import gemmi

def rotate(v,axis,angle):
 c=math.cos(angle);s=math.sin(angle);dot=sum(v[i]*axis[i] for i in range(3))
 cross=[axis[1]*v[2]-axis[2]*v[1],axis[2]*v[0]-axis[0]*v[2],axis[0]*v[1]-axis[1]*v[0]]
 return [v[i]*c+cross[i]*s+axis[i]*dot*(1-c) for i in range(3)]

def generate(parsed,block,config):
 allowed={'atoms','axis','angles_deg','occupancy_start','parts','basis'}
 if set(config)-allowed or not config.get('basis'):raise ValueError('Explicit fragment/axis/chemistry basis required')
 selected=[x.upper() for x in config['atoms']]
 if not 2<=len(selected)<=20 or len(set(selected))!=len(selected):raise ValueError('Bounded unique complete fragment required')
 atoms={a['label'].upper():a for a in parsed['atoms']}
 if not set(selected)<=set(atoms) or not set(x.upper() for x in config['axis'])<=set(atoms):raise ValueError('Unknown fragment/axis atom')
 if any(x.upper() in selected for x in config['axis']):raise ValueError('Rotation axis anchors must be shared outside split fragment')
 if len(config['axis'])!=2 or len(config['angles_deg'])!=2:raise ValueError('Exactly two orientations required')
 if any(abs(x)>45 for x in config['angles_deg']) or abs(config['angles_deg'][0]-config['angles_deg'][1])<2:raise ValueError('Seed angles outside bounded separated range')
 occ=float(config['occupancy_start'])
 if not .1<=occ<=.9:raise ValueError('Initial occupancy must be interior')
 parts=config['parts'];used={abs(a['part']) for a in parsed['atoms'] if a['part']}
 if len(parts)!=2 or parts[0]==parts[1] or any(not isinstance(p,int) or p<=0 or p in used for p in parts):raise ValueError('Two unused positive PART numbers required')
 for key in selected:
  a=atoms[key]
  if a['part']!=0 or a['afix']!=0 or a['element'].upper()=='H' or a['encoded_sof']!=11:
   raise ValueError('Seed route requires full general-site occupancy, PART0, no AFIX/H: '+key)
 cell=gemmi.UnitCell(*[gemmi.cif.as_number(block.find_value('_cell_'+v)) for v in ['length_a','length_b','length_c','angle_alpha','angle_beta','angle_gamma']])
 ops=[gemmi.Op(gemmi.cif.as_string(v)) for v in block.find_values('_space_group_symop_operation_xyz')]
 if not ops:raise ValueError('Explicit symmetry required')
 for key in selected:
  origin=atoms[key]['xyz'];same=0
  for op in ops:
   if cell.find_nearest_pbc_image(gemmi.Fractional(*origin),gemmi.Fractional(*op.apply_to_xyz(origin)),0).dist()<.001:same+=1
  if same!=1:raise ValueError('Special-position atom unsupported in automatic split seed: '+key)
 ue={gemmi.cif.as_string(r[0]).upper():gemmi.cif.as_number(r[1]) for r in block.find(['_atom_site_label','_atom_site_U_iso_or_equiv'])}
 point=[]
 for key in config['axis']:
  v=cell.orthogonalize(gemmi.Fractional(*atoms[key.upper()]['xyz']));point.append([v.x,v.y,v.z])
 axis=[point[1][i]-point[0][i] for i in range(3)];length=math.sqrt(sum(x*x for x in axis))
 if not .8<length<2.5:raise ValueError('Axis must be a reviewed, assembled local bond; periodic shifts unsupported')
 axis=[x/length for x in axis]
 free=[v for row in parsed['rows'] if row[0].upper()=='FVAR' for v in row[1:]];index=len(free)+1
 if index<2:raise ValueError('FVAR scale missing')
 newlabels=[atoms[key]['label']+suffix for suffix in ['A','B'] for key in selected]
 if any(not re.fullmatch(r'[A-Za-z][A-Za-z0-9]{0,3}',x) for x in newlabels) or len({x.upper() for x in newlabels})!=len(newlabels):raise ValueError('SHELXL label limit/collision')
 if {x.upper() for x in newlabels}.intersection(set(atoms)-set(selected)):raise ValueError('Label collision')
 rows=[];mapping={};max_shift=0
 for branch,(suffix,part,angle) in enumerate(zip(['A','B'],parts,config['angles_deg'])):
  rows.append(['PART',str(part)])
  for key in selected:
   a=atoms[key];p=cell.orthogonalize(gemmi.Fractional(*a['xyz']));old=[p.x,p.y,p.z]
   delta=rotate([old[i]-point[1][i] for i in range(3)],axis,math.radians(angle))
   new=[point[1][i]+delta[i] for i in range(3)];max_shift=max(max_shift,math.sqrt(sum((old[i]-new[i])**2 for i in range(3))))
   f=cell.fractionalize(gemmi.Position(*new));label=a['label']+suffix;u=ue.get(key)
   if not u or not math.isfinite(u) or u<=0:raise ValueError('Paired positive Ueq required')
   rows.append([label,str(a['sfac_index']),*[f'{x:.7f}' for x in [f.x,f.y,f.z]],str((1 if branch==0 else -1)*(10*index+1)),f'{u:.7f}'])
   mapping.setdefault(a['label'],{})[suffix]=label
  rows.append(['PART','0'])
 return {'rows':rows,'selected':selected,'free_variable_number':index,'free_variable_start':occ,'mapping':mapping,
  'max_initial_displacement_A':max_shift,'basis':config['basis'],'starting_ADP':'ISO from paired Ueq',
  'limitations':['Whole fragment is an explicit chemical hypothesis, not an inferred identity.',
  'Occupancies sum to one by FVAR encoding; this does not establish disorder existence or correct populations.',
  'No hydrogen, special-position, pre-existing PART/AFIX or periodic-axis handling in this bounded generator.']}
