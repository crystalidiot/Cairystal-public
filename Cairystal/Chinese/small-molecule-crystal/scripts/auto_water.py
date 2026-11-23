"""Bounded orientation hypotheses for an existing, complete water group.

No atom creation, chemical identity confirmation or final-model acceptance.
Native water_h_trial independently checks geometry, symmetry and restraints.
"""
import itertools
from donor_audit import angle

def request(packet,labels):
    evidence=packet.get('donor_evidence') or {}
    donors=evidence.get('donors',[])
    atoms={a['label'].upper():a for a in packet['all_atoms']}
    selected=[d for d in donors if d['parent'].upper() in labels or any(h['hydrogen'].upper() in labels for h in d['hydrogens'])]
    waters=[d for d in selected if d['element']=='O' and len(d['hydrogens'])==2 and not any(n['covalent_radius_screen'] and not n['metal'] for n in d['heavy_contacts'])]
    if len(waters)!=1:raise ValueError('One complete existing O(H)2 group required; no automatic water identity or missing-H assignment')
    water=waters[0]
    def whole(label):
        a=atoms[label.upper()]
        if a.get('res_context_status')!='matched' or a['part']!=0 or a['occupancy']!=1 or a['residue']!='0':
            raise ValueError('Water/acceptor must be an unambiguous full-occupancy PART 0 RESI 0 site')
        return a['res_label']
    parent=whole(water['parent']);hs=[whole(h['hydrogen']) for h in water['hydrogens']]
    candidates=[]
    for n in water['heavy_contacts']:
        if n['element']!='O' or n['part_compatible'] is not True or not 2.2<n['distance']<3.5:continue
        a=next((d for d in donors if d['parent'].upper()==n['atom'].upper()),None)
        if a is None or a['hydrogens']:continue
        bonds=[v for v in a['heavy_contacts'] if v['covalent_radius_screen'] and not v['metal']]
        # Terminal oxygen attached to C/S/P, with no assigned H, is only a
        # potential acceptor. Protonation/charge remain a scientific review.
        if len(bonds)!=1 or bonds[0]['element'] not in {'C','S','P'}:continue
        if any(any(p.get('parent','').upper()==a['parent'].upper() for p in x.get('parent_candidates',[])) for x in evidence.get('ambiguous_hydrogens',[])):continue
        try:label=whole(n['atom'])
        except (ValueError,KeyError):continue
        candidates.append((n,dict(atom=label,symmetry=n['symmetry'],translation=n['translation'])))
    pairs=[]
    for left,right in itertools.combinations(candidates,2):
        theta=angle(left[0]['vector_cart'],right[0]['vector_cart'])
        if theta is not None and 70<theta<140:
            pairs.append((left[0]['distance']+right[0]['distance'],left[1],right[1]))
    if not pairs:raise ValueError('No bounded pair of potential unprotonated O acceptors; retain water evidence for scientific review')
    _,a,b=min(pairs,key=lambda x:(x[0],str(x[1:])) )
    return {'recipe':'water_orient','parameters':{'parent':parent,'hydrogens':hs,'acceptors':[a,b],
        'basis':'Current paired model already contains this complete O(H)2 group. Periodic donor audit found a bounded pair of unprotonated terminal O neighbours attached to C/S/P. Geometry-only hypotheses: freeze and two rigid orientations; chemistry/charge/acceptor identity and final acceptance remain unconfirmed.'}}
