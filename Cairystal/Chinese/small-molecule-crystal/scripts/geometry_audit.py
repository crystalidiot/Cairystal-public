"""Check CIF geometry-table identity and values against its own coordinates/symmetry.

No table rows, labels or coordinates are removed or changed. Tolerances are screening
limits, not a replacement for checkCIF's covariance-aware tests.
"""
import argparse,json,math,re,time
from pathlib import Path
import gemmi
from structure_diagnostics import number,unquote,digest,newjson

def scalar_error(token):
    m=re.fullmatch(r'([+-]?(?:\d+(?:\.\d*)?|\.\d+))(?:\((\d+)\))?([eE][+-]?\d+)?',str(token))
    if not m or m[2] is None:return None
    decimals=len(m[1].partition('.')[2]);power=int(m[3][1:]) if m[3] else 0
    return int(m[2])*10.0**(power-decimals)

def read_context(block):
    values=[number(block.find_value('_cell_'+s)) for s in ['length_a','length_b','length_c','angle_alpha','angle_beta','angle_gamma']]
    if any(v is None for v in values):raise ValueError('Complete cell required')
    cell=gemmi.UnitCell(*values)
    if not math.isfinite(cell.volume) or cell.volume<=0:raise ValueError('Invalid cell')
    atoms={}
    for row in block.find(['_atom_site_label','_atom_site_fract_x','_atom_site_fract_y','_atom_site_fract_z']):
        label=unquote(row[0]);xyz=[number(v) for v in list(row)[1:]]
        if label in atoms or any(v is None for v in xyz):raise ValueError('Duplicate atom label or unknown coordinates')
        atoms[label]=xyz
    if not atoms:raise ValueError('Missing atom coordinate loop')
    op_tag='_space_group_symop_operation_xyz' if block.find_values('_space_group_symop_operation_xyz') else '_symmetry_equiv_pos_as_xyz'
    values=list(block.find_values(op_tag));id_tag='_space_group_symop_id' if op_tag.startswith('_space_group') else '_symmetry_equiv_pos_site_id'
    ids=list(block.find_values(id_tag))
    if ids and len(ids)!=len(values):raise ValueError('Symmetry ID/operation count mismatch')
    ids=[unquote(v) for v in ids] if ids else [str(i+1) for i in range(len(values))]
    if len(set(ids))!=len(ids):raise ValueError('Duplicate symmetry identifiers')
    ops={i:gemmi.Op(unquote(v)) for i,v in zip(ids,values)}
    return cell,atoms,ops

def point(label,code,cell,atoms,ops):
    if label not in atoms:raise ValueError('Geometry label absent from atom list: '+label)
    xyz=atoms[label]
    if code not in (None,'.'):
        if code=='?':raise ValueError('Unknown symmetry code; not assumed identity')
        m=re.fullmatch(r'([^_]+)(?:_([0-9]{3}))?',code)
        if not m or m[1] not in ops:raise ValueError('Unresolved symmetry code: '+code)
        xyz=ops[m[1]].apply_to_xyz(xyz)
        shift=[int(x)-5 for x in m[2]] if m[2] else [0,0,0]
        xyz=[xyz[i]+shift[i] for i in range(3)]
    pos=cell.orthogonalize(gemmi.Fractional(*xyz));return [pos.x,pos.y,pos.z]

def sub(a,b):return [x-y for x,y in zip(a,b)]
def dot(a,b):return sum(x*y for x,y in zip(a,b))
def cross(a,b):return [a[1]*b[2]-a[2]*b[1],a[2]*b[0]-a[0]*b[2],a[0]*b[1]-a[1]*b[0]]
def measure(points):
    if len(points)==2:return math.sqrt(dot(sub(*points),sub(*points)))
    if len(points)==3:
        a=sub(points[0],points[1]);b=sub(points[2],points[1]);den=math.sqrt(dot(a,a)*dot(b,b))
        if den<1e-12:raise ValueError('Degenerate angle')
        return math.degrees(math.acos(max(-1,min(1,dot(a,b)/den))))
    b0=sub(points[0],points[1]);b1=sub(points[2],points[1]);b2=sub(points[3],points[2]);n=math.sqrt(dot(b1,b1))
    if n<1e-12:raise ValueError('Degenerate torsion')
    u=[x/n for x in b1];v=[x-dot(b0,u)*y for x,y in zip(b0,u)];w=[x-dot(b2,u)*y for x,y in zip(b2,u)]
    if dot(v,v)*dot(w,w)<1e-20:raise ValueError('Degenerate torsion')
    return math.degrees(math.atan2(dot(cross(u,v),w),dot(v,w)))

def inspect(block):
    cell,atoms,ops=read_context(block);findings=[];checked=[]
    def inspect_rows(prefix,labels,symmetries,metrics):
        labelcols=[list(block.find_values(prefix+s)) for s in labels]
        if not any(labelcols):return
        n=len(labelcols[0])
        if not n or any(len(c)!=n for c in labelcols):
            findings.append(dict(kind='incomplete_label_columns',table=prefix));return
        scols=[list(block.find_values(prefix+s)) if s else [] for s in symmetries]
        # Core CIF angle/torsion values use the category name itself, unlike
        # _geom_bond_distance or _geom_hbond_angle_DHA.
        vcols={name:list(block.find_values(prefix[:-1] if prefix in {'_geom_angle_','_geom_torsion_'} else prefix+name)) for name,idx in metrics}
        if any(c and len(c)!=n for c in scols+list(vcols.values())):
            findings.append(dict(kind='inconsistent_geometry_columns',table=prefix));return
        for i in range(n):
            names=[unquote(c[i]) for c in labelcols]
            codes=[(str(c[i]) if str(c[i]) in {'?','.'} else unquote(c[i])) if c else None for c in scols]
            try:points=[point(a,c,cell,atoms,ops) for a,c in zip(names,codes)]
            except ValueError as exc:
                findings.append(dict(kind='unresolved_geometry_identity',table=prefix,row=i+1,labels=names,reason=str(exc)));continue
            for name,indices in metrics:
                token=vcols[name][i] if vcols[name] else '?';reported=number(token)
                try:calculated=measure([points[k] for k in indices])
                except ValueError as exc:
                    findings.append(dict(kind='degenerate_geometry',table=prefix,row=i+1,labels=names,reason=str(exc)));continue
                difference=None if reported is None else abs(calculated-reported)
                if len(indices)==4 and difference is not None:difference=abs((calculated-reported+180)%360-180)
                su=scalar_error(token);tolerance=max(.005 if len(indices)==2 else .5,5*su if su is not None else 0)
                result=dict(table=prefix,row=i+1,metric=name,labels=names,symmetries=codes,reported=reported,calculated=calculated,
                    absolute_difference=difference,reported_su=su,screening_tolerance=tolerance,
                    status='unknown_reported_value' if reported is None else 'mismatch' if difference>tolerance else 'consistent_with_screen')
                checked.append(result)
                if result['status']!='consistent_with_screen':findings.append(result)
    for kind,count,value in [('bond',2,'distance'),('contact',2,'distance'),('angle',3,'angle'),('torsion',4,'torsion')]:
        inspect_rows('_geom_'+kind+'_',['atom_site_label_'+str(i) for i in range(1,count+1)],['site_symmetry_'+str(i) for i in range(1,count+1)],[(value,list(range(count)))])
    inspect_rows('_geom_hbond_',['atom_site_label_D','atom_site_label_H','atom_site_label_A'],[None,None,'site_symmetry_A'],
        [('distance_DH',[0,1]),('distance_HA',[1,2]),('distance_DA',[0,2]),('angle_DHA',[0,1,2])])
    for token in block.find_values('_atom_site_aniso_label'):
        if unquote(token) not in atoms:findings.append(dict(kind='unmatched_anisotropic_label',label=unquote(token)))
    return dict(findings=findings,checked_values=checked,checked_value_count=len(checked),
        action='Regenerate geometry from the reviewed current model; check stale label maps, symmetry codes and CIF/RES pairing. Do not delete discrepant rows to hide a problem.',
        limitations=['No full covariance matrix: geometry s.u. values are not recomputed or overwritten.',
        'Explicit reported symmetry images are used; no nearest-image replacement that could hide wrong symmetry codes.',
        'Consistent tables do not prove the molecular connectivity, bond order or model is correct.'])

def audit(directory,stem='case'):
    start=time.perf_counter();p=Path(directory)/(stem+'.cif');h=digest(p);doc=gemmi.cif.read_file(str(p));b=doc.sole_block()
    result=inspect(b)
    if digest(p)!=h:raise ValueError('Source changed during geometry audit')
    result.update(schema=1,status='evidence_ready',source_sha256={str(p):h},source_unchanged=True,model_modified=False,seconds=round(time.perf_counter()-start,4));return result
def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--directory',required=True);p.add_argument('--stem',default='case');p.add_argument('--output',required=True)
    a=p.parse_args();v=audit(a.directory,a.stem);newjson(a.output,v);print(json.dumps({'status':v['status'],'findings':len(v['findings']),'checked_values':v['checked_value_count']}))
if __name__=='__main__':main()
