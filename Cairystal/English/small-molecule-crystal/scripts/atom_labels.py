"""Deterministic final atom labels. Never reorder native SHELX atom records.

Only explicit, auditable naming changes: no new atoms, bonds or disorder sites.
The native continuation and original validation/report gates remain mandatory.
"""
import argparse, json, re, string
from collections import Counter, defaultdict
from pathlib import Path
import gemmi
from audit_occupancy import CARDS
from crystal_runtime import records, sha, write_json
from shelx_input_preflight import render_records

class NamingReview(ValueError):
    pass

REF_CARDS=set('ANIS BIND BLOC BOND BUMP CHIV CONF CONN DANG DELU DFIX EADP EXYZ FLAT FREE HFIX HTAB ISOR MPLA NCSY OMIT RIGU RTAB SADI SAME SIMU'.split())
UNSUPPORTED={'FRAG','FEND','MOVE','NEUT'}

def element_key(element):
    e=element.upper()
    return (0 if e=='C' else 2 if e in {'H','D'} else 1, e)

def label_key(label):
    return tuple((0,int(x)) if x.isdigit() else (1,x.upper()) for x in re.split(r'(\d+)',label) if x)

def parse(text):
    rows=records(text)
    if any(r[0].startswith(('+','@')) for r in rows):
        raise NamingReview('Included files require a reviewed combined native input before numbering')
    sfacs=[r for r in rows if r[0].upper()=='SFAC']
    if len(sfacs)!=1 or not all(re.fullmatch('[A-Za-z]{1,2}',x) and gemmi.Element(x).atomic_number for x in sfacs[0][1:]):
        raise NamingReview('Numbering supports one simple element-list SFAC; explicit scattering tables need review')
    elements=[gemmi.Element(x).name for x in sfacs[0][1:]]
    part=0;afix=0;anchor=None;last_heavy=None;atoms=[]
    for i,r in enumerate(rows):
        key=r[0].upper();card=key.split('_')[0]
        if card in CARDS:
            if card in UNSUPPORTED or '_' in key:
                raise NamingReview('Numbering needs review for native control '+key)
            if card=='RESI' and r[1:] not in ([],['0']):
                raise NamingReview('Residue-scoped atom names need an explicit reviewed naming implementation')
            if card=='CHIV' and len(r)>1:
                try:vol=float(r[1])
                except ValueError:vol=0.
                if vol!=0:raise NamingReview('Nonzero CHIV sign depends on alphabetical neighbour order; review before renaming')
            if card=='PART':part=int(r[1])
            if card=='AFIX':afix=int(r[1]);anchor=last_heavy if afix else None
            continue
        if not re.fullmatch('[A-Za-z][A-Za-z0-9]{0,3}',r[0]) or len(r) not in (7,12):
            raise NamingReview('Unsupported atom/control record: '+r[0])
        try:
            sfac=int(r[1]);xyz=list(map(float,r[2:5]));list(map(float,r[5:]))
            if not 1<=sfac<=len(elements):raise ValueError()
        except ValueError:raise NamingReview('Invalid atom record: '+r[0])
        element=elements[sfac-1]
        # Only fixed-coordinate +10 encoding is understood, not FVAR-linked positions.
        if any(abs(v)>=15 or -15<v<=-5 or 5<=v<10 for v in xyz):
            raise NamingReview('Coordinate free-variable encoding needs review before assigning H parents')
        xyz=[v-10 if v>=10 else v for v in xyz]
        atoms.append(dict(index=i,label=r[0],element=element,part=part,afix=afix,anchor=anchor,xyz=xyz))
        if element not in {'H','D'}:last_heavy=r[0]
    labels=[a['label'].upper() for a in atoms]
    if not atoms or len(labels)!=len(set(labels)):raise NamingReview('Missing atoms or duplicate labels; residue/identity review needed')
    return rows,atoms

def _parent(h,heavy,cell):
    candidates=[]
    for a in heavy:
        if a['element'] not in {'C','N','O','S','P','B','Si'}:continue
        if h['part'] and a['part'] and h['part']!=a['part']:continue
        # Only the written molecular image: never infer a symmetry-related parent.
        delta=gemmi.Fractional(*[x-y for x,y in zip(h['xyz'],a['xyz'])])
        d=cell.orthogonalize(delta).length()
        high=1.65 if a['element'] in {'S','P','Si'} else 1.3
        if .5<=d<=high:candidates.append((d,a))
    candidates.sort(key=lambda x:x[0])
    if h['anchor'] and h['afix'] in {3,13,23,33,43,83,93,123,133,137,147,163}:
        chosen=[a for _,a in candidates if a['label']==h['anchor']]
        if len(chosen)==1:return chosen[0],'existing AFIX parent, distance checked'
        raise NamingReview('AFIX hydrogen parent/distance conflict: '+h['label'])
    if len(candidates)==1:return candidates[0][1],'unique written-image bonded-distance candidate'
    raise NamingReview('Hydrogen parent is ambiguous or outside supported geometry: '+h['label'])

def make_plan(text):
    rows,atoms=parse(text);heavy=[a for a in atoms if a['element'] not in {'H','D'}]
    parts=sorted({a['part'] for a in heavy if a['part']})
    if len(parts)>26:raise NamingReview('More than 26 disorder components cannot be named with this convention')
    part_suffix={p:string.ascii_uppercase[i] for i,p in enumerate(parts)}
    # Preserve existing A/B correspondence only when explicitly encoded by the old
    # same-element name stem in different PARTs. Do not invent cross-PART matching.
    groups=defaultdict(list)
    for a in heavy:
        m=re.fullmatch(r'([A-Za-z]+)(\d+)([A-Za-z]?)',a['label'])
        a['name_match']=m.groups() if m else None
        if a['part'] and m and m[3]:groups[(a['element'],m[1].upper(),int(m[2]))].append(a)
    families={}
    for k,group in groups.items():
        if len(group)>1 and len({a['part'] for a in group})==len(group) and len({a['name_match'][2].upper() for a in group})==len(group):
            for a in group:families[a['label']]=k
    # Existing per-PART letters take precedence if consistent and injective.
    proposals={p:{a['name_match'][2].upper() for a in heavy if a['part']==p and a['name_match'] and a['name_match'][2]} for p in parts}
    if parts and all(len(proposals[p])==1 for p in parts) and len({next(iter(proposals[p])) for p in parts})==len(parts):
        part_suffix={p:next(iter(proposals[p])) for p in parts}
    counts=Counter();assigned={};mapping={};details=[]
    for a in heavy:
        family=families.get(a['label'],('site',a['label']))
        key=(a['element'],family)
        if key not in assigned:counts[a['element']]+=1;assigned[key]=counts[a['element']]
        n=assigned[key];new=a['element'].upper()+str(n)+part_suffix.get(a['part'],'')
        mapping[a['label']]=new
        details.append({'old':a['label'],'new':new,'element':a['element'],'part':a['part'],'paired_old_stem':a['label'] in families})
    cell=gemmi.UnitCell(*map(float,next(r[2:] for r in rows if r[0].upper()=='CELL')))
    hgroups=defaultdict(list)
    for h in [a for a in atoms if a['element'] in {'H','D'}]:
        if h['element']=='D':raise NamingReview('Isotope-specific numbering is outside the current scope')
        parent,basis=_parent(h,heavy,cell)
        n=re.search(r'\d+',mapping[parent['label']])[0]
        hgroups[n].append((h,parent,basis))
    for n,group in hgroups.items():
        # For parents sharing a number (C1/N1 or C1A/C1B), suffixes distinguish H
        # sites; the map records the exact parent and PART, without implying a bond.
        if len(group)>26:raise NamingReview('Hydrogen label capacity exceeded for parent number '+n)
        for i,(h,parent,basis) in enumerate(group):
            new='H'+n+(string.ascii_uppercase[i] if len(group)>1 else '')
            mapping[h['label']]=new
            details.append({'old':h['label'],'new':new,'element':'H','part':h['part'],'parent_old':parent['label'],'parent_new':mapping[parent['label']],'parent_basis':basis})
    if any(len(v)>4 or v in CARDS for v in mapping.values()):raise NamingReview('Generated label exceeds SHELX four-character limit or collides with an instruction')
    if len(set(mapping.values()))!=len(mapping):raise NamingReview('Generated atom-label collision')
    result={'schema':1,'status':'ready','mapping':mapping,'atoms':details,'changed':any(k!=v for k,v in mapping.items()),'native_order_preserved':True,'grouping':'C first; other non-H elements alphabetical; H last; natural numeric order','scientific_model_changed':False}
    # Parse/reference transformation must succeed before returning a ready plan.
    transformed=apply_plan(text,result)
    result['native_input']=transformed
    return result

def _rewrite_ref(token,mapping):
    if token.startswith('$'):return token
    lookup={k.upper():v for k,v in mapping.items()}
    def repl(m):
        name,suffix=m.group(1),m.group(2) or ''
        if name.upper() not in lookup:return m[0]
        if suffix and not re.fullmatch(r'_\$\d+',suffix):
            raise NamingReview('Residue-qualified reference needs review: '+m[0])
        return lookup[name.upper()]+suffix
    return re.sub(r'([A-Za-z][A-Za-z0-9]*)(_[A-Za-z0-9$+_-]+)?',repl,token)

def apply_plan(text,plan):
    rows,atoms=parse(text);mapping=plan['mapping'];positions={a['index']:a for a in atoms};out=[]
    for i,r in enumerate(rows):
        row=list(r);key=r[0].upper()
        if i in positions:row[0]=mapping[positions[i]['label']]
        elif key in REF_CARDS:
            start=2 if key=='RTAB' else 1  # RTAB's user-defined table title is not an atom.
            row[start:]=[_rewrite_ref(t,mapping) for t in row[start:]]
        elif key not in {'SFAC','DISP','SYMM','EQIV'}:
            for token in row[1:]:
                if _rewrite_ref(token,mapping)!=token:
                    raise NamingReview('Atom reference in unsupported control '+key+' requires review')
        out.append(row)
    # No sorting: AFIX parents, SAME implicit targets and >/< ranges retain meaning.
    return 'TITL Cairystal final atom numbering; original ordering preserved\n'+render_records(out)

def renumber_ins(text,cycles=12):
    plan=make_plan(text)
    from routine_finish import weight_ins,read_weights
    native=weight_ins(plan.pop('native_input'),read_weights(text)[0],cycles)
    return native,plan

def require_normalized(text):
    plan=make_plan(text);plan.pop('native_input')
    if plan['changed']:raise NamingReview('Final numbering is pending; run routine_finish/complete before checkCIF and Word generation')
    return plan

def remap_narrative(text,mapping):
    lookup={k.upper():v for k,v in mapping.items()}
    return re.sub(r'(?<![A-Za-z0-9_])([A-Za-z][A-Za-z0-9]{0,3})(?![A-Za-z0-9_])',lambda m:lookup.get(m[1].upper(),m[0]),text)

def remap_notes(review,mapping):
    # Free prose can contain formula counts ("C9 H12") as well as atom labels.
    # Never use blind string replacement in chemistry. Preserve old prose and
    # explicitly identify its label namespace; current tables come from new CIF.
    import copy
    result=copy.deepcopy(review)
    if not any(k!=v for k,v in mapping.items()):return result
    messages={'zh':'最终表格使用规范后的原子编号；此前文字复核记录保留原编号，旧新对应及氢母原子见 atom_label_map.json。',
              'en':'Final tables use normalized atom labels. Earlier narrative review records retain their original labels; atom_label_map.json gives the old/new correspondence and hydrogen parents.'}
    notes=result.setdefault('bilingual_notes',{})
    for lang,message in messages.items():
        obj=notes.setdefault(lang,{});obj['limitations']=obj.get('limitations','')+' '+message
    return result

def sort_cif(cif):
    """Move complete atom/aniso rows only; all tokens and other loops preserved."""
    path=Path(cif);doc=gemmi.cif.read_file(str(path));b=doc.sole_block()
    loop=b.find_loop('_atom_site_label').get_loop()
    if loop is None:raise NamingReview('No atom loop to sort')
    tags=list(loop.tags);width=len(tags);li=tags.index('_atom_site_label');ei=tags.index('_atom_site_type_symbol')
    rows=[list(loop.values[i:i+width]) for i in range(0,len(loop.values),width)]
    ordered=sorted(rows,key=lambda r:(element_key(gemmi.cif.as_string(r[ei])),label_key(gemmi.cif.as_string(r[li]))))
    rank={r[li]:i for i,r in enumerate(ordered)}
    loop.set_all_values([[r[c] for r in ordered] for c in range(width)])
    ani=b.find_loop('_atom_site_aniso_label').get_loop()
    if ani is not None:
        w=ani.width();idx=list(ani.tags).index('_atom_site_aniso_label');ar=[list(ani.values[i:i+w]) for i in range(0,len(ani.values),w)]
        ar.sort(key=lambda r:rank[r[idx]])
        ani.set_all_values([[r[c] for r in ar] for c in range(w)])
    doc.write_file(str(path))
    return {'atom_rows':len(rows),'atom_order':[gemmi.cif.as_string(r[li]) for r in ordered],'numerical_tokens_unchanged':True}

def prepare(source,output):
    source=Path(source);output=Path(output)
    if output.exists():raise FileExistsError('Numbering output already exists')
    output.mkdir(parents=True)
    try:
        native,plan=renumber_ins(source.read_text('latin1'))
        (output/'model.ins').write_text(native,encoding='ascii')
        plan['source_sha256']=sha(source);write_json(output/'atom_label_map.json',plan);return plan
    except Exception as e:
        write_json(output/'naming_review.json',{'status':'needs_review','reason':str(e),'source_sha256':sha(source)});raise

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--res',required=True);p.add_argument('--output',required=True)
    a=p.parse_args();print(json.dumps(prepare(a.res,a.output),ensure_ascii=False))
if __name__=='__main__':main()
