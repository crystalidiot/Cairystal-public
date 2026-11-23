"""Chemical reporting checks before freezing/uploading, without changing the model."""
from pathlib import Path
import gemmi
from crystal_runtime import sha

def normalize_sg_name(name):
    """Normalize SHELXT screw-axis parentheses only; do not infer/change setting."""
    return name.replace('(', '').replace(')', '')

def review_contacts(path):
    path=Path(path);before=sha(path);doc=gemmi.cif.read_file(str(path));b=doc.sole_block()
    atom_types={r[0]:r[1].upper() for r in b.find(['_atom_site_label','_atom_site_type_symbol'])}
    oxy_neighbors={k:set() for k,v in atom_types.items() if v=='CL'}
    for row in b.find(['_geom_bond_atom_site_label_1','_geom_bond_atom_site_label_2','_geom_bond_distance']):
        for c,o in [(row[0],row[1]),(row[1],row[0])]:
            if c in oxy_neighbors and atom_types.get(o)=='O' and 1.2<gemmi.cif.as_number(row[2])<1.7:oxy_neighbors[c].add(o)
    excluded={c for c,neighbors in oxy_neighbors.items() if len(neighbors)==4}
    loop=b.find_loop('_geom_hbond_atom_site_label_A').get_loop();removed=[];retained=0
    if loop:
        tags=list(loop.tags);width=len(tags);index=tags.index('_geom_hbond_atom_site_label_A')
        rows=[list(loop.values[i:i+width]) for i in range(0,len(loop.values),width)]
        removed=[r for r in rows if r[index] in excluded];kept=[r for r in rows if r[index] not in excluded];retained=len(kept)
        if removed:
            if kept:loop.set_all_values(list(map(list,zip(*kept))))
            else:b.find_loop('_geom_hbond_atom_site_label_A').erase()
            doc.write_file(str(path))
    return {'before_sha256':before,'after_sha256':sha(path),'excluded_central_ClO4_acceptors':sorted(excluded),'removed_reporting_rows':removed,'retained_rows':retained,'scope':'Reporting contacts only. Central Cl with four short O bonds is not a conventional hydrogen-bond acceptor. Free halides are not excluded. All atom/ADP/reflection and embedded native records preserved.'}
