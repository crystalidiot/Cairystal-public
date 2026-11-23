"""Read-only periodic donor/H audit, including freely refined water H atoms."""
import argparse
import itertools
import json
import math
from pathlib import Path
import time
import gemmi
from structure_diagnostics import structure, compatible, newjson
from crystal_runtime import sha, check_stem


def images(cell, ops, origin, target, radius):
    """All images inside a Cartesian sphere, with reciprocal-metric bounds."""
    if not 0 < radius <= 5:
        raise ValueError('Contact radius must be in (0,5] Angstrom')
    reciprocal = [math.sqrt(sum(x*x for x in row)) for row in cell.frac.mat.tolist()]
    found, seen = [], set()
    for op in ops:
        pos = op.apply_to_xyz(target)
        ranges = []
        for i in range(3):
            extent = radius*reciprocal[i] + 1e-9
            centre = origin[i]-pos[i]
            ranges.append(range(math.ceil(centre-extent), math.floor(centre+extent)+1))
        if math.prod(map(len, ranges)) > 50000:
            raise ValueError('Cell/contact enumeration too large; specialist review required')
        for shift in itertools.product(*ranges):
            xyz = [pos[i]+shift[i] for i in range(3)]
            key = tuple(round(x, 7) for x in xyz)
            if key in seen:
                continue
            v = cell.orthogonalize(gemmi.Fractional(*[xyz[i]-origin[i] for i in range(3)]))
            d = v.length()
            if not .001 < d < radius:
                continue
            seen.add(key)
            found.append(dict(distance=d, symmetry=op.triplet(), translation=list(shift),
                              vector_cart=[v.x,v.y,v.z], fractional=xyz))
    return sorted(found, key=lambda x:x['distance'])


def angle(u, v):
    norm = math.sqrt(sum(x*x for x in u)*sum(x*x for x in v))
    return math.degrees(math.acos(max(-1,min(1,sum(x*y for x,y in zip(u,v))/norm)))) if norm else None


def screen(cell, ops, atoms, peaks=()):
    """Geometry is evidence, never a chemical identity or protonation assignment."""
    by = {a['label']:a for a in atoms}
    if len(by) != len(atoms):
        raise ValueError('Unique CIF atom labels required')
    heavy = [a for a in atoms if a['element'] != 'H']
    assigned, ambiguous = {}, []
    for h in (a for a in atoms if a['element']=='H'):
        candidates = []
        for parent in heavy:
            if parent['element'] not in {'C','N','O','S'}:
                continue
            cutoff = min(1.5,gemmi.Element(parent['element']).covalent_r + gemmi.Element('H').covalent_r + .22)
            for im in images(cell,ops,h['xyz'],parent['xyz'],cutoff):
                comp = compatible(h,parent,im['symmetry'],im['translation'])
                if comp is not False:
                    candidates.append(dict(parent=parent['label'],part_compatible=comp,**im))
        if len(candidates)==1 and candidates[0]['part_compatible'] is True:
            assigned[h['label']]=candidates[0]
        else:
            ambiguous.append(dict(hydrogen=h['label'],parent_candidates=candidates,
                                  reason='No unique compatible geometric parent; no automatic assignment'))
    result=[]
    for donor in (a for a in atoms if a['element'] in {'N','O','S'}):
        heavy_contacts=[]
        for other in heavy:
            for im in images(cell,ops,donor['xyz'],other['xyz'],3.5):
                comp=compatible(donor,other,im['symmetry'],im['translation'])
                if comp is False:
                    continue
                metal=gemmi.Element(other['element']).is_metal
                cut=gemmi.Element(donor['element']).covalent_r+gemmi.Element(other['element']).covalent_r+.25
                heavy_contacts.append(dict(atom=other['label'],element=other['element'],
                    part_compatible=comp,metal=metal,covalent_radius_screen=im['distance']<cut,**im))
        covalent=[n for n in heavy_contacts if n['covalent_radius_screen'] and not n['metal']]
        hs=[]
        for label, parent in assigned.items():
            if parent['parent']!=donor['label']:
                continue
            h=by[label];contacts=[];clashes=[]
            for other in atoms:
                for im in images(cell,ops,h['xyz'],other['xyz'],3.2):
                    comp=compatible(h,other,im['symmetry'],im['translation'])
                    # Exclude the actual donor image, not every copy of its atom label.
                    if other['label']==donor['label'] and all(abs(im['fractional'][i]-parent['fractional'][i])<1e-6 for i in range(3)):
                        continue
                    if im['distance'] < (1.8 if other['element']=='H' else .8):
                        clashes.append(dict(atom=other['label'],element=other['element'],part_compatible=comp,**im))
                    if other['element'] not in {'N','O','S','F','Cl','Br','I'}:
                        continue
                    a=angle(parent['vector_cart'],im['vector_cart'])
                    da=math.sqrt(sum((im['vector_cart'][i]-parent['vector_cart'][i])**2 for i in range(3)))
                    contacts.append(dict(atom=other['label'],element=other['element'],H_A_A=im['distance'],D_A_A=da,
                        D_H_A_degrees=a,symmetry=im['symmetry'],translation=im['translation'],
                        part_compatible=comp,geometric_screen=comp is True and im['distance']<=2.6 and da<=3.5 and a>=120,
                        acceptor_chemistry_confirmed=False))
            hs.append(dict(hydrogen=label,AFIX=h.get('afix'),parent_basis='unique geometric neighbour including periodic images',
                D_H_A=parent['distance'],parent_symmetry=parent['symmetry'],parent_translation=parent['translation'],
                contacts=sorted(contacts,key=lambda c:c['H_A_A']),short_contact_screen=clashes))
        q=[]
        for peak in peaks:
            for im in images(cell,ops,donor['xyz'],peak['xyz'],1.3):
                if .6 <= im['distance'] and peak.get('height',0)>0:
                    q.append(dict(label=peak['label'],height=peak['height'],**im))
        result.append(dict(parent=donor['label'],element=donor['element'],part=donor['part'],occupancy=donor.get('occupancy'),
            hydrogens=hs,heavy_contacts=heavy_contacts,nearby_reported_Q_peaks=q,
            possible_water_missing_H=donor['element']=='O' and not covalent and len(hs)<2,
            water_identity_confirmed=False,
            next_action='Review density, valence/charge and disorder before adding or moving H; existing simple C-O-H may use repair-plan oh_rotate'))
    return dict(donors=result,ambiguous_hydrogens=ambiguous,
        limitations=['Geometric cutoffs are screening choices, not the full PLATON hydrogen-bond test.',
                    'Potential acceptors include protonated/chemically unsuitable sites; chemistry is not inferred.',
                    'Missing or ambiguous H is not proof of a water molecule. Q entries are saved RES peaks, not a newly calculated map.',
                    'Cross/negative PART contact candidates are retained with a compatibility flag; PART alone does not establish physical co-occurrence or its absence.',
                    'No hydrogen is added, moved or constrained; no refinement or official validation is replaced.'])


def audit(directory,stem='case'):
    start=time.perf_counter();d=Path(directory);check_stem(stem)
    paths={e:d/(stem+'.'+e) for e in ('cif','res')};before={e:sha(p) for e,p in paths.items()}
    _,cell,ops,atoms,parsed=structure(paths['cif'],paths['res'])
    if any(a['res_context_status']!='matched' for a in atoms):
        raise ValueError('CIF/RES atom contexts do not match; repair pairing before donor audit')
    result=screen(cell,ops,atoms,parsed['peaks'])
    if before!={e:sha(p) for e,p in paths.items()}:
        raise ValueError('Source files changed during donor audit')
    return dict(schema=1,status='evidence_ready',**result,source_sha256=before,source_files={k:str(v) for k,v in paths.items()},
                source_unchanged=True,model_modified=False,seconds=round(time.perf_counter()-start,4))


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--directory',required=True);p.add_argument('--stem',default='case');p.add_argument('--output',required=True)
    a=p.parse_args()
    try:
        r=audit(a.directory,a.stem);newjson(a.output,r)
        print(json.dumps({'status':r['status'],'donors':len(r['donors']),'output':a.output,'seconds':r['seconds']}));return 0
    except (ValueError,OSError,RuntimeError) as e:
        print(json.dumps({'status':'failed','error':str(e)}));return 2

if __name__=='__main__':raise SystemExit(main())
