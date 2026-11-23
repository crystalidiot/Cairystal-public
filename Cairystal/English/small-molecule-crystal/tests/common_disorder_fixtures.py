"""Artificial local geometries only: never experimental structures/answers."""
from pathlib import Path
import math
import gemmi

def fixture(root,family='cf3',hydrogens=False):
    root=Path(root);root.mkdir(exist_ok=True)
    if family=='cf3':coords=[('C1','C',[-1.5,0,0]),('C2','C',[0,0,0])]+[(f'F{i+1}','F',[.45,1.26*math.cos(2*math.pi*i/3),1.26*math.sin(2*math.pi*i/3)]) for i in range(3)]
    elif family=='tert_butyl':coords=[('C0','C',[-2.05,-1.45,0]),('C1','C',[-1.54,0,0]),('C2','C',[0,0,0])]+[(f'C{i+3}','C',[.51,1.45*math.cos(2*math.pi*i/3),1.45*math.sin(2*math.pi*i/3)]) for i in range(3)]
    elif family=='alkyl_chain':coords=[('C1','C',[-1.5,0,0]),('C2','C',[0,0,0]),('C3','C',[.51,1.45,0]),('C4','C',[2.02,1.57,0])]
    elif family=='solvent':coords=[('O1','O',[0,0,0]),('C1','C',[1.43,0,0]),('C2','C',[1.93,1.42,0])]
    else:raise ValueError(family)
    symbols=list(dict.fromkeys(el for _,el,_ in coords))+(['H'] if hydrogens else [])
    cell=gemmi.UnitCell(14,15,16,90,90,90);xyz={};rows=[];atomdata=[]
    for label,el,v in coords:
        f=cell.fractionalize(gemmi.Position(v[0]+4,v[1]+5,v[2]+6));xyz[label]=[f.x,f.y,f.z]
        rows.append(f'{label} {symbols.index(el)+1} {f.x:.7f} {f.y:.7f} {f.z:.7f} 11 .04')
        atomdata.append([label,el,*[f'{n:.7f}' for n in [f.x,f.y,f.z]],'.04','1','Uiso'])
        if hydrogens and family=='alkyl_chain':
            count=3 if label in {'C1','C4'} else 2;afix=33 if count==3 else 23
            rows.append('AFIX '+str(afix))
            for i in range(count):
                hlabel='H'+label[1:]+chr(65+i);h=[f.x+.04*math.cos(i*2.1),f.y+.04*math.sin(i*2.1),f.z+.05]
                rows.append(f'{hlabel} {symbols.index("H")+1} '+ ' '.join(f'{x:.7f}' for x in h)+' 11 -1.2')
                atomdata.append([hlabel,'H',*[f'{x:.7f}' for x in h],'.048','1','Uiso'])
            rows.append('AFIX 0')
    counts={s:sum(a[1]==s for a in atomdata)*2 for s in symbols}
    text='TITL Artificial disorder regression\nCELL .71073 14 15 16 90 90 90\nZERR 2 .001 .001 .001 0 0 0\nLATT 1\nSFAC '+' '.join(symbols)+'\nUNIT '+' '.join(str(counts[s]) for s in symbols)+'\nTEMP -173.15\nWGHT 0\nFVAR 1\n'+'\n'.join(rows)+'\nL.S. 20\nLIST 4\nACTA\nFMAP 2\nPLAN 100\nHKLF 4\nEND\n'
    (root/'case.res').write_text(text,encoding='ascii')
    doc=gemmi.cif.Document();b=doc.add_new_block('artificial')
    for name,value in zip(['length_a','length_b','length_c','angle_alpha','angle_beta','angle_gamma'],[14,15,16,90,90,90]):b.set_pair('_cell_'+name,str(value))
    b.set_pair('_diffrn_radiation_wavelength','.71073');b.set_pair('_space_group_name_H-M_alt',"'P -1'")
    loop=b.init_loop('_space_group_symop_',['operation_xyz']);loop.add_row(['x,y,z']);loop.add_row(['-x,-y,-z'])
    loop=b.init_loop('_atom_site_',['label','type_symbol','fract_x','fract_y','fract_z','U_iso_or_equiv','occupancy','adp_type'])
    for row in atomdata:loop.add_row(row)
    doc.write_file(str(root/'case.cif'));return root
