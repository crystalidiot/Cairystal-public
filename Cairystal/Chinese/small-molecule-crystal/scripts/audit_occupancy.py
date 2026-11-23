"""Read-only SHELX SOF/multiplicity audit; findings are not automatic model repairs.

Requires gemmi. Supports conventional SHELX LATT and simple SFAC element lists.
Reports unsupported instructions rather than silently interpreting them.
"""
import argparse,json,math,re,sys
from pathlib import Path
from collections import defaultdict
from itertools import product

CARDS=set('ABIN ACTA AFIX ANIS ANSC ANSR BASF BIND BLOC BOND BUMP CELL CGLS CHIV CONF CONN DAMP DANG DEFS DELU DFIX DISP EADP END EQIV EXTI EXYZ FEND FLAT FMAP FRAG FREE FVAR GRID HFIX HKLF HTAB ISOR LATT LAUE LIST L.S. MERG MORE MOVE MPLA NCSY NEUT OMIT PART PLAN PRIG REM RESI RIGU RTAB SADI SAME SFAC SHEL SIMU SIZE SPEC STIR SUMP SWAT SYMM TEMP TITL TWIN TWST UNIT WGHT WIGL WPDB XNPD ZERR'.split())

def logical_lines(text):
    pending=''
    for raw in text.splitlines():
        line=raw.split('!',1)[0].rstrip()
        if pending:line=pending+' '+line.strip()
        if line.endswith('='):
            pending=line[:-1];continue
        pending=''
        if line.strip():yield line.strip()
    if pending:raise ValueError('Unfinished SHELX continuation')

def decode_sof(value,free):
    if abs(value)<5:return value
    k=int(abs(value)//10);p=abs(value)-10*k
    if p>=5:raise ValueError(f'Unsupported SOF encoding {value}')
    if k==1:return p if value>=0 else -p
    if k<2 or k>len(free):raise ValueError(f'Missing FVAR {k} for SOF {value}')
    return p*(free[k-1] if value>=0 else 1-free[k-1])

def matches_cif_precision(value,token,source_rounding=0):
    """Compare central values using serialization rounding, not the uncertainty size."""
    match=re.fullmatch(r'([+-]?(?:\d+(?:\.\d*)?|\.\d+))(?:\(\d+\))?([Ee][+-]?\d+)?',token)
    if not match:raise ValueError('Non-numeric CIF value: '+token)
    central=match[1];exponent=int(match[2][1:]) if match[2] else 0
    reported=float(central)*(10**exponent)
    decimals=len(central.split('.')[1]) if '.' in central else 0
    tolerance=(0.5001*10**(exponent-decimals)) if '(' in token or decimals>=2 else 1e-8
    return abs(value-reported)<=max(1e-8,tolerance+source_rounding)

def check_cell_metric(cell,ops,tolerance=1e-4):
    """Check W.T G W = G for direct fractional-coordinate symmetry operations.

    Dimensionless tolerance accommodates serialization; it is not a criterion
    for accepting higher symmetry or a twin law. Never alter cell parameters.
    """
    lengths=[cell.a,cell.b,cell.c]
    angles=[cell.alpha,cell.beta,cell.gamma]
    if any(not math.isfinite(v) or v<=0 for v in lengths):
        raise ValueError('Invalid CELL lengths')
    if any(not math.isfinite(v) or not 0<v<180 for v in angles):
        raise ValueError('Invalid CELL angles')
    ca,cb,cg=[math.cos(math.radians(v)) for v in angles]
    if 1+2*ca*cb*cg-ca*ca-cb*cb-cg*cg<=0:
        raise ValueError('CELL metric is not positive definite')
    a,b,c=lengths
    metric=[[a*a,a*b*cg,a*c*cb],[a*b*cg,b*b,b*c*ca],[a*c*cb,b*c*ca,c*c]]
    maximum=0.0
    for op in ops:
        rotation=[[v/op.DEN for v in row] for row in op.rot]
        error=max(abs(sum(rotation[k][i]*metric[k][l]*rotation[l][j]
                          for k in range(3) for l in range(3))-metric[i][j])
                  /(lengths[i]*lengths[j]) for i in range(3) for j in range(3))
        maximum=max(maximum,error)
        if error>tolerance:
            raise ValueError(f'CELL metric incompatible with SYMM {op.triplet()} '
                             f'(normalized discrepancy {error:.6g} > {tolerance:g}); '
                             'verify cell, setting and reflection transformation; no automatic repair')
    return {'maximum_normalized_discrepancy':maximum,'tolerance':tolerance,
            'scope':'Input consistency only; does not establish the experimental space group'}

def audit(path,gemmi):
    lines=[]
    for line in logical_lines(path.read_text(encoding='latin1')):
        if line.upper().split()[0]=='END':break
        lines.append(line)
    fields=[line.split() for line in lines]
    if any(f[0].startswith('+') for f in fields):raise ValueError('Included instruction files are unsupported; audit their resolved combined input explicitly')
    if sum(f[0].upper()=='SFAC' for f in fields)!=1:raise ValueError('Exactly one simple SFAC list required')
    one=lambda card:next((f[1:] for f in fields if f[0].upper()==card),None)
    cellvals=one('CELL'); lattvals=one('LATT'); sfac=one('SFAC')
    # SHELXL concatenates repeated FVAR cards in input order; the first
    # overall scale appears only once, not once per card.
    freevals=[v for f in fields if f[0].upper()=='FVAR' for v in f[1:]]
    if not all([cellvals,lattvals,sfac,freevals]):raise ValueError('CELL/LATT/simple SFAC/FVAR required')
    if any(not re.fullmatch('[A-Za-z]{1,2}',v) for v in sfac):raise ValueError('Only simple SFAC lists supported')
    free=list(map(float,freevals));cell=gemmi.UnitCell(*map(float,cellvals[1:7]));latt=int(lattvals[0])
    centers={1:[(0,0,0)],2:[(0,0,0),(.5,.5,.5)],
        3:[(0,0,0),(2/3,1/3,1/3),(1/3,2/3,2/3)],
        4:[(0,0,0),(0,.5,.5),(.5,0,.5),(.5,.5,0)],
        5:[(0,0,0),(0,.5,.5)],6:[(0,0,0),(.5,0,.5)],7:[(0,0,0),(.5,.5,0)]}
    if abs(latt) not in centers:raise ValueError('Unsupported LATT')
    primitive=[gemmi.Op('x,y,z')]+[gemmi.Op(''.join(f[1:])) for f in fields if f[0].upper()=='SYMM']
    if latt>0:primitive+=[gemmi.Op('-x,-y,-z')*op for op in list(primitive)]
    ops=[]
    for op in primitive:
        for shift in centers[abs(latt)]:
            new=gemmi.Op(op.triplet());new.tran=[new.tran[i]+round(shift[i]*new.DEN) for i in range(3)]
            new.wrap()
            if new.triplet() not in [v.triplet() for v in ops]:ops.append(new)
    group=gemmi.GroupOps(ops); closed=gemmi.GroupOps(ops);closed.add_missing_elements()
    if len(closed)!=len(group):raise ValueError('SYMM list is not a complete symmetry group')
    metric_check=check_cell_metric(cell,ops)
    sg=gemmi.find_spacegroup_by_ops(group)
    def distance(a,b):
        return cell.find_nearest_pbc_image(gemmi.Fractional(*a),gemmi.Fractional(*b),0).dist()
    # Optional program evidence is separate from exact geometric orbits.
    lst=path.with_suffix('.lst');declared={}
    if lst.exists():
        sections=re.split(r'Special position constraints for\s+',lst.read_text(encoding='latin1'))[1:]
        for section in sections:
            name=section.splitlines()[0].strip().split()[0].upper()
            head=section.split('\n\n',1)[0]
            found=re.search(r'sof\s*=\s*([\d.]+)',head)
            if found:declared[name]=float(found[1])
    atoms=[];orbits=[];part=0;residue='0';override=None;afix_sof=None;warnings=[]
    for f in fields:
        card=f[0].upper()
        if card=='RESI':
            residue=' '.join(f[1:]) or '0';continue
        if card=='PART':
            part=int(f[1]);override=float(f[2]) if len(f)>2 else None;continue
        if card=='AFIX':
            afix_sof=float(f[3]) if len(f)>3 and int(f[1]) else None;continue
        if card in {'SPEC','EXYZ','+','++'} or card.startswith('+'):
            warnings.append('Manual coordinate constraints/includes require separate review: '+' '.join(f))
        if card in CARDS:continue
        if len(f)<5:continue
        try:
            idx=int(f[1]);xyz=list(map(float,f[2:5]))
        except ValueError:continue
        # Generated SHELXL labels can contain punctuation (e.g. H00$).
        # Do not silently omit an otherwise numeric atom record and report
        # a false chemical formula. Renaming needs its own recorded mapping.
        if not re.fullmatch(r'[A-Za-z][A-Za-z0-9]{0,3}',f[0]):
            raise ValueError(f'Unsupported atom label {f[0]!r}; audit stopped to avoid silently dropping atoms. Review/rename consistently on a copy.')
        # SHELXL can retain +10 fixed-coordinate encodings in a refined RES.
        # Decode this exact convention; other coordinate/FVAR encodings remain unsupported.
        xyz=[v-10 if 5<v<15 else v for v in xyz]
        if any(abs(v)>=5 for v in xyz):raise ValueError(f'{f[0]} has unresolved coordinate/FVAR encoding; compare actual CIF coordinates instead')
        if len(f)<7:raise ValueError(f'{f[0]} requires explicit SOF and U for this auditor')
        explicit=float(f[5]);float(f[6])
        if not 1<=idx<=len(sfac):raise ValueError(f'Invalid SFAC index for {f[0]}')
        encoded=override if override is not None else afix_sof if afix_sof is not None else explicit
        sof=decode_sof(encoded,free)
        orbit=[]
        for op in ops:
            pos=[v%1 for v in op.apply_to_xyz(xyz)]
            if not any(distance(pos,v)<0.001 for v in orbit):orbit.append(pos)
        mult=len(orbit);occ=sof*len(ops)/mult
        orbits.append(orbit)
        decimals=len(f[5].split('.')[1]) if '.' in f[5] else 0
        # Five-place RES SOF coefficients cannot represent 1/3, 1/24, etc. exactly.
        rounding=(.5001*10**(-decimals)*len(ops)/mult) if decimals>=4 else 0
        atom={'label':f[0],'element':sfac[idx-1],'part':part,'residue':residue,'xyz':xyz,
            'input_sof':explicit,'effective_encoded_sof':encoded,'decoded_shelx_sof':sof,
            'general_multiplicity':len(ops),'geometric_site_multiplicity':mult,
            'inferred_cif_occupancy':occ,'unit_cell_contribution':sof*len(ops),
            'sof_serialization_rounding_bound':rounding}
        name=f[0].upper()+(('^'+chr(96+abs(part))).upper() if part and abs(part)<=26 else '')
        if name in declared and declared[name]>0:
            program_mult=round(len(ops)*declared[name])
            atom['program_declared_site_multiplicity']=program_mult
            atom['program_declared_cif_occupancy']=sof/declared[name]
            if program_mult!=mult:
                warnings.append(f'{f[0]}: geometric orbit differs from LST special-position constraint; inspect proximity/AFIX geometry, do not auto-change occupancy')
        atoms.append(atom)
        if not -rounding-1e-8<=occ<=1+rounding+1e-8:warnings.append(f'{f[0]}: inferred occupancy outside [0,1]')
        if part<0 and mult<len(ops):warnings.append(f'{f[0]}: negative PART on a special orbit; check overlapping symmetry components manually')
    composition=defaultdict(float)
    for atom in atoms:composition[atom['element']]+=atom['unit_cell_contribution']
    unit=one('UNIT'); unitvals=list(map(float,unit)) if unit else []
    if len(unitvals)!=len(sfac):warnings.append('UNIT length does not match SFAC')
    deviations={el:{'UNIT':u,'model':composition.get(el,0)} for el,u in zip(sfac,unitvals) if abs(u-composition.get(el,0))>0.01}
    if deviations:warnings.append('UNIT disagrees with the modeled cell composition; do not auto-rewrite unknown chemistry')
    if not any(atom['element'].upper()=='H' for atom in atoms):warnings.append('No modeled hydrogen atoms; chemistry may be incomplete')
    # Fractional-coordinate spatial bins avoid O(N^2 * M^2) comparisons in large cages/MOFs.
    tolerance=0.001
    rows=cell.frac.mat.tolist()
    bins=[max(1,int(1/(tolerance*math.sqrt(sum(v*v for v in row))))) for row in rows]
    grid=defaultdict(list);parent=list(range(len(atoms)))
    def find(i):
        while parent[i]!=i:parent[i]=parent[parent[i]];i=parent[i]
        return i
    for i,orbit in enumerate(orbits):
        for pos in orbit:
            key=tuple(int((pos[k]%1)*bins[k])%bins[k] for k in range(3))
            for shift in product((-1,0,1),repeat=3):
                neighbor=tuple((key[k]+shift[k])%bins[k] for k in range(3))
                for j,other in grid.get(neighbor,()):
                    if j!=i and distance(pos,other)<tolerance:parent[find(i)]=find(j)
            grid[key].append((i,pos))
    grouped=defaultdict(list)
    for i in range(len(atoms)):grouped[find(i)].append(i)
    overlap_groups=[]
    for indices in grouped.values():
        if len(indices)<2:continue
        total=sum(atoms[j]['inferred_cif_occupancy'] for j in indices)
        labels=[atoms[j]['label'] for j in indices]
        overlap_groups.append({'labels':labels,'summed_occupancy':total})
        if total>1.0001:warnings.append('Overlapping symmetry orbit overoccupied: '+', '.join(labels))
    return {'path':str(path.resolve()),'space_group':sg.xhm() if sg else None,'general_multiplicity':len(ops),
        'cell_metric_check':metric_check,
        'atoms':atoms,'modeled_unit_cell_composition':dict(composition),'unit_discrepancies':deviations,
        'overlapping_orbit_groups':overlap_groups,
        'warnings':warnings,'scope':'Geometric orbit / SOF accounting, not a proof of chemical correctness; no files changed'}

def main():
    ap=argparse.ArgumentParser();ap.add_argument('file',type=Path);ap.add_argument('--dependency-dir',type=Path)
    args=ap.parse_args()
    if args.dependency_dir:sys.path.insert(0,str(args.dependency_dir.resolve()))
    try:
        import gemmi
    except ModuleNotFoundError:
        print(json.dumps({'status':'dependency_missing','message':'Gemmi is required. Use the available private runtime/package directory, or arrange a local dependency installation before auditing.'}))
        return 2
    try:
        result=audit(args.file,gemmi)
    except (ValueError,OSError) as error:
        print(json.dumps({'status':'not_auditable','message':str(error),'source_unchanged':True},ensure_ascii=False))
        return 1
    print(json.dumps(result,ensure_ascii=False,indent=2))
    return 0
if __name__=='__main__':raise SystemExit(main())
