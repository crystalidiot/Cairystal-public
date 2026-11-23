"""Screen selected disordered CF3 and saturated C–C bonds before comparing models."""
from collections import Counter, defaultdict
from pathlib import Path

import gemmi

from geometry_audit import measure, point, read_context
from structure_diagnostics import res_records, unquote


def token(value):
    return value if value in ('.','?') else unquote(value)


def inspect(cif, res):
    from common_disorder import h_groups
    from crystal_runtime import canonical
    block = gemmi.cif.read_file(str(cif)).sole_block()
    atoms = {unquote(label): unquote(element).upper() for label, element in
             block.find(['_atom_site_label', '_atom_site_type_symbol'])}
    groups = {unquote(label): token(group) for label, group in
              block.find(['_atom_site_label', '_atom_site_disorder_group'])}
    assemblies = {unquote(label): token(value) for label, value in
                  block.find(['_atom_site_label', '_atom_site_disorder_assembly'])}
    def split(label):
        return groups.get(label) not in (None, '.', '?', '0')
    def compatible(first, second):
        return (not (split(first) and split(second)) or
                (groups[first] == groups[second] and assemblies.get(first) == assemblies.get(second)))
    base = {'screen':'disordered_CF3_and_saturated_CC', 'checked':0, 'findings':[],
            'thresholds_A':{'CF3_C-F_short':1.25, 'two_saturated_carbons_short':1.36}}
    if not any(split(label) for label in groups):
        return dict(base, status='no_explicit_disorder_groups')
    bond_labels = block.find(['_geom_bond_atom_site_label_1','_geom_bond_atom_site_label_2'])
    if not bond_labels:
        return dict(base,status='bond_table_unavailable')
    cell, coordinates, ops = read_context(block)
    syms = [list(block.find_values('_geom_bond_site_symmetry_'+str(i))) for i in (1,2)]
    graph = defaultdict(set)
    edges = []
    for i, row in enumerate(bond_labels):
        a,b = map(unquote,row)
        if a not in atoms or b not in atoms or a==b or not compatible(a,b):
            continue
        graph[a].add(b)
        graph[b].add(a)
        edges.append((a,b,[token(col[i]) if col else '.' for col in syms]))
    def same_branch(center, branch):
        return {label for label in graph[center] if compatible(label,branch)}
    saturated = set()
    embedded = gemmi.cif.as_string(block.find_value('_shelx_res_file') or '')
    if embedded and canonical(embedded)==canonical(Path(res).read_text(encoding='latin1')):
        parsed = res_records(res)
        riding,_ = h_groups(parsed)
        multiplicity = Counter(a['label'].upper() for a in parsed['atoms'])
        expected = {13:1,23:2,33:3,137:3}
        for label,hydrogens in riding.items():
            modes = {h['afix'] for h in hydrogens}
            if multiplicity[label]==1 and len(modes)==1 and expected.get(next(iter(modes)))==len(hydrogens):
                saturated.add(label)
    for a,b,codes in edges:
        if not (split(a) or split(b)):
            continue
        kind = None
        if {atoms[a],atoms[b]}=={'C','F'}:
            c,f = (a,b) if atoms[a]=='C' else (b,a)
            neighbours = same_branch(c,f)
            if sum(atoms[n]=='F' for n in neighbours)==3 and same_branch(f,c)=={c}:
                kind='CF3_C-F_short'
        elif atoms[a]==atoms[b]=='C' and {a.upper(),b.upper()}<=saturated:
            kind='two_saturated_carbons_short'
        if kind is None:
            continue
        pts = [point(label,code,cell,coordinates,ops) for label,code in zip((a,b),codes)]
        length = measure(pts)
        base['checked']+=1
        if length < base['thresholds_A'][kind]:
            base['findings'].append({'kind':kind,'labels':[a,b],'length_A':round(length,4),
                                     'groups':[groups.get(a),groups.get(b)],'symmetry':codes})
    return dict(base,status='review_geometry' if base['findings'] else
                'no_outlier_in_screened_bonds' if base['checked'] else 'no_covered_bonds')


def trial_review(directory,stem):
    try:
        return inspect(directory/(stem+'.cif'),directory/(stem+'.res'))
    except (ValueError,RuntimeError,OSError,KeyError,IndexError) as exc:
        return {'status':'unavailable','findings':[],'error':str(exc)}


def annotate(review,notes):
    findings=review['findings']
    if not findings:
        return
    details=', '.join(f"{'-'.join(f['labels'])} {f['length_A']:.3f} Å" for f in findings)
    for lang, sentence in [('zh','无序组分中需复核的短键为 '+details+'。'),
                           ('en','Short bonds requiring review in the disorder model include '+details+'.')]:
        section=notes.setdefault(lang,{})
        if sentence not in section.get('limitations',''):
            section['limitations']=(section.get('limitations','')+' '+sentence).strip()
