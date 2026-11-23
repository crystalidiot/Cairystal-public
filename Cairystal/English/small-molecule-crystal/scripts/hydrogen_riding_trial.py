"""Bounded edits of an EXISTING riding H group. No H creation or chemical assignment."""
import math
from pathlib import Path
import gemmi
from crystal_runtime import records
from crystal_session import logical_text
from structure_diagnostics import structure

def edit(base, config):
    allowed={'parent','mode','angle_degrees','anchor'}
    if set(config)-allowed:raise ValueError('Unknown hydrogen operation fields')
    mode=config.get('mode','freeze');parent=str(config.get('parent','')).upper()
    if mode not in {'freeze','rotate_oh'}:raise ValueError('Unsupported H operation')
    b,cell,ops,atoms,parsed=structure(Path(base)/'case.cif',Path(base)/'case.res')
    by={a['label'].upper():a for a in parsed['atoms']}
    if len(by)!=len(parsed['atoms']):raise ValueError('Unique labels required for H editing')
    if parent not in by:raise ValueError('Unknown H parent')
    pa=by[parent];rows=records((Path(base)/'case.res').read_text('latin1'))
    if any(r[0].upper()=='HFIX' for r in rows):raise ValueError('Resolve existing HFIX before editing explicit H groups')
    if pa['afix'] or pa['element'].upper() not in {'C','N','O'}:raise ValueError('Independent C/N/O parent required')
    i=next(i for i,r in enumerate(rows) if r[0].upper()==parent)
    j=i+1
    while j<len(rows) and rows[j][0].upper()=='REM':j+=1
    if j>=len(rows) or rows[j][0].upper()!='AFIX':raise ValueError('Explicit adjacent AFIX group required')
    code=int(rows[j][1]);expected={13:1,23:2,33:3,43:1,83:1,93:2,137:3,147:1}
    if code not in set(expected)|{3}:raise ValueError('Only standard explicit riding H groups supported')
    k=j+1
    while k<len(rows) and rows[k][0].upper()!='AFIX':
        # SHELXL may place output/control cards before the final AFIX 0 in its RES.
        if rows[k][0].upper() not in by and rows[k][0].upper() not in {'REM','LIST','ACTA','FMAP','PLAN','L.S.','CGLS','BOND','CONF','MORE'}:raise ValueError('Unexpected instruction inside H group')
        k+=1
    if k==len(rows) or rows[k][1]!='0':raise ValueError('H group requires explicit AFIX 0 closure')
    children=[by[r[0].upper()] for r in rows[j+1:k] if r[0].upper() in by]
    if not 1<=len(children)<=3 or (code in expected and len(children)!=expected[code]):raise ValueError('AFIX hydrogen count mismatch')
    if any(a['element'].upper()!='H' or len(a['adp_raw'])!=1 or a['part']!=pa['part'] or a['residue']!=pa['residue'] for a in children):raise ValueError('H/PART/RESI/ADP parent relationship is ambiguous')
    labels={parent}|{a['label'].upper() for a in children}
    if any(a['res_context_status']!='matched' for a in atoms if a['label'].upper() in labels):raise ValueError('CIF/RES H context unmatched')
    ap={a['label'].upper():a for a in atoms}
    if not labels<=set(ap):raise ValueError('H atoms must be present in paired CIF')
    if any(ap[n]['occupancy'] is None or abs(ap[n]['occupancy']-ap[parent]['occupancy'])>1e-5 for n in labels):raise ValueError('H/parent occupancy differs')
    for r in rows:
        if r[0].upper() in {'EADP','EXYZ','DFIX','DANG','SADI','SAME','FLAT','CHIV'} and any(t.upper() in labels for t in r[1:]):raise ValueError('Referenced H/parent constraints require explicit reviewed mapping')
    for a in [pa]+children:
        if any(not math.isfinite(float(t)) or not -5<float(t)<5 for t in a['row'][2:5]):raise ValueError('Fixed/free-variable coordinates unsupported in H editor')
        if a['residue']!='0':raise ValueError('Qualified residue H editing not yet supported')
    h_before={a['label']:a['xyz'] for a in children};rotation=None
    if mode=='rotate_oh':
        if pa['element'].upper()!='O' or len(children)!=1 or code not in {3,83,147}:raise ValueError('Rotation is limited to a single existing O-H')
        anchor=str(config.get('anchor','')).upper();angle=config.get('angle_degrees')
        if anchor not in by or by[anchor]['element'].upper()!='C':raise ValueError('Explicit carbon anchor required for simple C-O-H rotation')
        if not isinstance(angle,(float,int)) or isinstance(angle,bool) or not math.isfinite(angle) or not -360<=angle<=360:raise ValueError('Finite angle in [-360,360] required')
        if pa['part']!=0 or by[anchor]['part']!=0 or abs(ap[parent]['occupancy']-1)>1e-5:raise ValueError('OH rotation currently requires full occupancy PART 0')
        if by[anchor]['afix'] or by[anchor]['residue']!='0':raise ValueError('Independent carbon anchor required')
        # Reject special-site rotations; symmetry-related H constraints need a different editor.
        for op in ops:
            if op.triplet()!='x,y,z' and cell.find_nearest_pbc_image(gemmi.Fractional(*pa['xyz']),gemmi.Fractional(*op.apply_to_xyz(pa['xyz'])),0).dist()<.05:raise ValueError('Special-position OH requires specialist treatment')
        o=cell.orthogonalize(gemmi.Fractional(*pa['xyz']));c=cell.orthogonalize(gemmi.Fractional(*by[anchor]['xyz']));h=cell.orthogonalize(gemmi.Fractional(*children[0]['xyz']))
        axis=o-c;v=h-o
        if not 1.15<axis.length()<1.65 or not .65<v.length()<1.15:raise ValueError('C-O-H must be gathered with reasonable current bond lengths')
        # More than one close heavy neighbour is not the simple hydroxyl operation.
        from structure_diagnostics import nearest_images
        near=[a['label'].upper() for a in atoms if a['element']!='H' for im in nearest_images(cell,ops,pa['xyz'],a['xyz'],1.85) if im['distance']<gemmi.Element('O').covalent_r+gemmi.Element(a['element']).covalent_r+.25]
        if near!=[anchor]:raise ValueError('OH donor does not have exactly the declared carbon neighbour')
        u=axis/axis.length();theta=math.radians(angle)
        cross=u.cross(v)
        rotated=v*math.cos(theta)+gemmi.Position(cross.x,cross.y,cross.z)*math.sin(theta)+u*(u.dot(v)*(1-math.cos(theta)))
        f=cell.fractionalize(o+rotated)
        target=children[0]['label'].upper()
        for t in range(j+1,k):
            if rows[t][0].upper()==target:rows[t][2:5]=[f'{x:.9f}' for x in (f.x,f.y,f.z)]
        rotation={'anchor':anchor,'angle_degrees':angle,'bond_length_preserved_A':v.length(),'new_H_fractional':[f.x,f.y,f.z], 'evidence':'Geometric trial only; not observed difference density or proven H bond'}
    elif set(config)-{'parent','mode'}:raise ValueError('Freeze accepts parent/mode only')
    # Preserve optional SOF/U overrides and every H atom: only change geometric refinement mode.
    rows[j][1]='3'
    return logical_text(rows),[{'hydrogen_riding':{'parent':parent,'old_AFIX':code,'new_AFIX':3,'hydrogens':h_before,'rotation':rotation,'atom_count_changed':False,'occupancy_or_U_changed':False}}]

def environment(base,parent):
    """Record potential contacts/angles, including symmetry; do not infer acceptor chemistry."""
    from donor_audit import audit
    report=audit(base)
    donor=next((d for d in report['donors'] if d['parent'].upper()==parent.upper()),None)
    if donor is not None:
        for h in donor['hydrogens']:
            h['very_short_contacts_below_0_8_A']=[c for c in h['short_contact_screen'] if c['distance']<.8]
        return dict(donor,ambiguous_hydrogens=report['ambiguous_hydrogens'],limitation=report['limitations'])
    from structure_diagnostics import nearest_images,compatible
    b,cell,ops,atoms,parsed=structure(Path(base)/'case.cif',Path(base)/'case.res')
    by={a['label'].upper():a for a in atoms};pa=by[parent.upper()];children=[];active=False
    for a in parsed['atoms']:
        if a['label'].upper()==parent.upper():active=True;continue
        if active:
            if a['element']=='H' and a['afix']:children.append(by[a['label'].upper()])
            else:break
    data=[]
    for h in children:
        hd=cell.orthogonalize(gemmi.Fractional(*[pa['xyz'][i]-h['xyz'][i] for i in range(3)]));contacts=[];clashes=[]
        for a in atoms:
            for im in nearest_images(cell,ops,h['xyz'],a['xyz'],3.2):
                if compatible(h,a,im['symmetry'],im['translation']) is False:continue
                if a['label'].upper()==parent.upper() and im['symmetry']=='x,y,z' and im['translation']==[0,0,0]:continue
                if im['distance']<.8:clashes.append({'atom':a['label'],**im})
                if a['element'] not in {'N','O','F','Cl'}:continue
                v=im['vector_cart'];cos=sum(x*y for x,y in zip((hd.x,hd.y,hd.z),v))/(hd.length()*im['distance']);angle=math.degrees(math.acos(max(-1,min(1,cos))))
                da=math.sqrt(sum((v[i]-(hd.x,hd.y,hd.z)[i])**2 for i in range(3)))
                contacts.append({'atom':a['label'],'element':a['element'],'H_A_A':im['distance'],'D_A_A':da,'D_H_A_degrees':angle,'symmetry':im['symmetry'],'translation':im['translation'],'acceptor_chemistry_confirmed':False})
        data.append({'hydrogen':h['label'],'D_H_A':hd.length(),'contacts':sorted(contacts,key=lambda c:c['H_A_A']),'very_short_contacts_below_0_8_A':clashes})
    return {'parent':parent,'hydrogens':data,'limitation':'Contacts include only nearest image per symmetry operation and potential N/O/F/Cl sites; protonation and acceptor identity require chemistry review. No density maximum is asserted.'}
