"""Rigid orientation trials for two EXISTING H atoms on an explicitly identified water."""
from pathlib import Path
import math
import re
import numpy as np
import gemmi
from crystal_runtime import records
from crystal_session import logical_text
from structure_diagnostics import structure
from donor_audit import images,screen


def rigid_rotation(source,target):
    """Proper least-squares rotation of two directions; preserve internal geometry."""
    a=np.asarray(source,dtype=float);b=np.asarray(target,dtype=float)
    if a.shape!=(2,3) or b.shape!=(2,3) or not np.isfinite(a).all() or not np.isfinite(b).all():
        raise ValueError('Two finite 3D direction vectors required')
    if np.any(np.linalg.norm(a,axis=1)<1e-6) or np.any(np.linalg.norm(b,axis=1)<1e-6):
        raise ValueError('Zero direction vector')
    a=a/np.linalg.norm(a,axis=1)[:,None];b=b/np.linalg.norm(b,axis=1)[:,None]
    if min(np.linalg.norm(np.cross(*a)),np.linalg.norm(np.cross(*b)))<.2:
        raise ValueError('Collinear directions cannot define a water orientation')
    u,_,vt=np.linalg.svd(a.T@b);d=np.eye(3);d[2,2]=np.linalg.det(vt.T@u.T)
    return vt.T@d@u.T


def edit(base,config):
    allowed={'parent','hydrogens','acceptors','basis','mode'}
    if set(config)!=allowed or not isinstance(config['basis'],str) or not config['basis'].strip():
        raise ValueError('Explicit parent, two existing H, acceptor images, mode and water/acceptor basis required')
    mode=config['mode']
    if mode not in {'freeze','orient'}:raise ValueError('Unsupported water trial mode')
    labels=[config['parent'],*config['hydrogens']]
    if len(labels)!=3 or any(not isinstance(x,str) or not re.fullmatch(r'[A-Za-z][A-Za-z0-9]{0,3}',x) for x in labels):
        raise ValueError('One parent and two explicit short H labels required')
    labels=[x.upper() for x in labels]
    if len(set(labels))!=3:raise ValueError('Repeated atom labels')
    _,cell,ops,atoms,parsed=structure(Path(base)/'case.cif',Path(base)/'case.res')
    by={a['label'].upper():a for a in parsed['atoms']}
    if len(by)!=len(parsed['atoms']) or not set(labels)<=set(by):raise ValueError('Unknown or ambiguous atom labels')
    ap={a['res_label'].upper():a for a in atoms if a['res_context_status']=='matched'}
    if not set(labels)<=set(ap):raise ValueError('CIF/RES mapping mismatch')
    p,h1,h2=[by[x] for x in labels];group=[p,h1,h2]
    if p['element']!='O' or any(h['element']!='H' or len(h['adp_raw'])!=1 for h in [h1,h2]):raise ValueError('One O and two isotropic H required')
    if any(a['part']!=0 or a['residue']!='0' or a['encoded_sof']!=11 or ap[a['label'].upper()]['occupancy']!=1 for a in group):
        raise ValueError('This water tool requires full occupancy, PART 0, RESI 0')
    if p['afix']!=0 or any(h['afix'] not in {0,3} for h in [h1,h2]):raise ValueError('Independent O; free or AFIX 3 water H required')
    for a in group:
        if any(not -5<float(x)<5 for x in a['row'][2:5]):raise ValueError('Fixed/free-variable coordinates unsupported')
    for op in ops:
        if op.triplet()!='x,y,z' and cell.find_nearest_pbc_image(gemmi.Fractional(*p['xyz']),gemmi.Fractional(*op.apply_to_xyz(p['xyz'])),0).dist()<.01:
            raise ValueError('Special-position water requires a different symmetry-aware construction')
    current=screen(cell,ops,atoms)
    donor=next(x for x in current['donors'] if x['parent'].upper()==labels[0])
    if {x['hydrogen'].upper() for x in donor['hydrogens']}!=set(labels[1:]):raise ValueError('Exactly two unambiguously attached existing H required')
    if any(n['covalent_radius_screen'] and not n['metal'] for n in donor['heavy_contacts']):
        raise ValueError('O has a covalent heavy-atom neighbour; water identity is inconsistent')
    cart=lambda xyz:np.array(list(cell.orthogonalize(gemmi.Fractional(*xyz))))
    o=cart(p['xyz']);vectors=np.array([cart(h['xyz'])-o for h in [h1,h2]])
    lengths=np.linalg.norm(vectors,axis=1)
    angle=math.degrees(math.acos(np.clip(np.dot(*vectors)/np.prod(lengths),-1,1)))
    if any(not .65<x<1.1 for x in lengths) or not 80<angle<125:
        raise ValueError('Gathered water geometry outside supported O-H/angle range')
    acceptors=config['acceptors'];rotation=np.eye(3);target_details=[]
    if mode=='freeze' and acceptors:raise ValueError('Freeze trial must not contain unused acceptor targets')
    if mode=='orient':
        if not isinstance(acceptors,list) or len(acceptors)!=2:raise ValueError('Two explicit acceptor images required')
        targets=[];opmap={op.triplet():op for op in ops}
        for a in acceptors:
            if set(a)!={'atom','symmetry','translation'}:raise ValueError('Acceptor needs atom, symmetry and translation')
            key=str(a['atom']).upper();shift=a['translation']
            if key not in ap or key in labels or ap[key]['element'] not in {'N','O','S','F','Cl','Br','I'}:raise ValueError('Unsupported acceptor; its chemistry must be explicitly justified')
            if ap[key]['part']!=0 or ap[key]['occupancy']!=1:raise ValueError('Disordered/partial acceptor needs separate review')
            if a['symmetry'] not in opmap or not isinstance(shift,list) or len(shift)!=3 or any(type(x)!=int or abs(x)>3 for x in shift):raise ValueError('Explicit supported symmetry and bounded translation required')
            xyz=opmap[a['symmetry']].apply_to_xyz(ap[key]['xyz']);v=cart([xyz[i]+shift[i] for i in range(3)])-o
            if not 2.2<float(np.linalg.norm(v))<3.6:raise ValueError('Donor-acceptor distance outside trial range')
            targets.append(v);target_details.append(dict(a,D_A_A=float(np.linalg.norm(v))))
        rotation=rigid_rotation(vectors,targets)
        target_angle=math.degrees(math.acos(np.clip(np.dot(*targets)/np.prod(np.linalg.norm(targets,axis=1)),-1,1)))
        if not 70<target_angle<140:raise ValueError('Acceptor directions incompatible with a bounded water orientation trial')
    moved=(rotation@vectors.T).T
    rows=records((Path(base)/'case.res').read_text('latin1'));indices={r[0].upper():i for i,r in enumerate(rows) if r[0].upper() in by}
    pi=indices[labels[0]];hi=[indices[x] for x in labels[1:]]
    # Parent/children may be free or in one explicit AFIX 3 block. No reorder of other atoms.
    lo,high=min(hi),max(hi)
    between=[r for r in rows[pi+1:high+1] if r[0].upper()!='REM']
    starts=bool(between and between[0][0].upper()=='AFIX')
    expected=([['AFIX','3']] if starts else [])+[by[x]['row'] for x in sorted(labels[1:],key=lambda x:indices[x])]
    if between!=expected or pi>=lo:raise ValueError('Water H must immediately follow O, with only optional AFIX 3')
    if starts and (high+1>=len(rows) or rows[high+1]!=['AFIX','0']):raise ValueError('Existing AFIX 3 needs immediate AFIX 0 closure')
    removed=[];remove=set();selected=set(labels)
    for i,row in enumerate(rows):
        key=row[0].upper()
        if key in by:continue
        if key=='HFIX' or any(t.upper()=='$H' or t in {'>','<'} for t in row[1:]):raise ValueError('Global/ranged H instructions require reviewed expansion')
        if any(t.upper() in set(labels[1:]) for t in row[1:]):
            if key in {'REM','HTAB','RTAB'}:continue
            names={t.upper() for t in row[1:] if t.upper() in by}
            if key not in {'DFIX','DANG'} or not names<=selected:raise ValueError('H restraint/constraint reaches outside this water or is unsupported')
            remove.add(i);removed.append(row)
    newcoords={labels[i+1]:list(cell.fractionalize(gemmi.Position(*(o+moved[i])))) for i in range(2)}
    output=[]
    for i,row in enumerate(rows):
        if i in remove:continue
        if i==lo and not starts:output.append(['AFIX','3'])
        row=list(row)
        if row[0].upper() in newcoords:row[2:5]=[f'{x:.9f}' for x in newcoords[row[0].upper()]]
        output.append(row)
        if i==high and not starts:output.append(['AFIX','0'])
    evidence={'water_orientation':dict(parent=labels[0],hydrogens=labels[1:],mode=mode,acceptors=target_details,basis=config['basis'],
        old_H_fractional=[h1['xyz'],h2['xyz']],new_H_fractional=newcoords,rotation=rotation.tolist(),
        preserved_O_H_A=lengths.tolist(),preserved_H_O_H_degrees=angle,removed_redundant_internal_distance_restraints=removed,
        atom_count_occupancy_U_unchanged=True,chemical_correctness_confirmed=False)}
    return logical_text(output),[evidence]
