"""Evidence-based triage only: no atom edit, model acceptance or hidden case lookup."""
import re

def priorities(packet):
 alerts=packet.get('AB_alerts',[]);codes={str(a['code']).split('_ALERT')[0].removeprefix('PLAT') for a in alerts};out=[]
 if codes&{'112','113'}:
  out.append({'priority':1,'code':'symmetry_before_split','evidence':sorted(codes&{'112','113'}),'action':'Test current-data ADDSYM transform, systematic absences and merging before positional disorder. Coordinate fit alone does not establish higher symmetry.'})
 shifts=packet.get('last_shifts',[])
 if shifts:
  last=shifts[-1];target=last[2].strip();value=abs(float(last[1]));same=[float(s[1]) for s in shifts if s[2].strip()==target]
  oscillations=sum(a*b<0 for a,b in zip(same,same[1:]))
  if value>.01:
   kind='hydrogen_rotor' if re.match(r'tors\s+H',target,re.I) else 'ADP_tensor' if re.match(r'U(?:11|22|33|23|13|12|eq|iso)\s',target,re.I) else 'other_parameter'
   out.append({'priority':2,'code':'locate_nonconvergence','parameter':target,'type':kind,'absolute_shift_over_su':value,'sign_changes_in_last_listings':oscillations,'action':'For oscillating H torsion, compare a fixed current riding orientation after checking chemical geometry; for ADP shifts, inspect eigenvalues, labels and nearby density. Do not fix all coordinates indiscriminately.'})
 if packet.get('gate',{}).get('metrics',{}).get('NPD_atoms')==0 and '211' in codes:
  out.append({'priority':2,'code':'near_degenerate_despite_native_NPD_zero','action':'PLAT211 can flag nearly flat tensors even with positive eigenvalues. Retain the official alert and inspect Cartesian eigenvalues.'})
 tension=packet.get('restraint_tension') or {}
 if tension.get('needs_review'):
  out.append({'priority':2,'code':'split_or_topology_not_supported_by_geometry','action':'Retain final DFIX/DANG deviations and rejected alternatives. Lower R or fewer AB alerts do not override incompatible geometry.'})
 return {'findings':out,'automatic_model_changes':False,'scientific_acceptance':False}
