"""Vary only the explicit sigmas of one existing, bounded local restraint."""
import argparse,json,math,re
from pathlib import Path
from structure_diagnostics import res_records,newjson
import gemmi

LAYOUT={'DFIX':(2,[1]),'DANG':(2,[1]),'SADI':(1,[0]),'FLAT':(1,[0]),'RIGU':(2,[0,1]),'DELU':(2,[0,1]),'ISOR':(2,[0,1]),'SIMU':(3,[0,1])}

def inspect(base,instruction):
    if not isinstance(instruction,str) or '\n' in instruction or '\r' in instruction:raise ValueError('One explicit restraint instruction required')
    tokens=instruction.upper().split();key=tokens[0] if tokens else ''
    if key not in LAYOUT:raise ValueError('Supported: explicit DFIX/DANG/SADI/FLAT/RIGU/DELU/ISOR/SIMU')
    parsed=res_records(Path(base)/'case.res');matches=[row for row in parsed['rows'] if [x.upper() for x in row]==tokens]
    if len(matches)!=1:raise ValueError('Exactly one matching existing restraint required')
    count,indices=LAYOUT[key];values=tokens[1:1+count];names=tokens[1+count:]
    try:values=list(map(float,values))
    except ValueError:raise ValueError('All numerical arguments, including sigmas, must be explicit')
    if len(values)!=count or any(not math.isfinite(v) or v<=0 for v in values):raise ValueError('Positive finite restraint arguments required')
    known=[a['label'].upper() for a in parsed['atoms']]
    if len(set(known))!=len(known):raise ValueError('Unique labels required')
    if not 2<=len(names)<=24 or any(not re.fullmatch(r'[A-Z][A-Z0-9]{0,3}',n) or n not in known for n in names):raise ValueError('Explicit bounded atom list required; no wildcards, ranges or symmetry selectors')
    if key in {'DFIX','DANG','SADI'} and len(names)%2:raise ValueError('Distance restraints require complete pairs')
    if key in {'SADI','FLAT'} and len(names)<4:raise ValueError('At least four labels required')
    return dict(instruction=' '.join(tokens),kind=key,arguments=values,sigma_indices=indices,atoms=list(dict.fromkeys(names)),ordered_labels=names)

def variants(base,instruction,factors):
    c=inspect(base,instruction)
    if not isinstance(factors,list) or not 2<=len(factors)<=4:raise ValueError('Two to four declared sigma factors required')
    if any(isinstance(x,bool) or not isinstance(x,(int,float)) or not math.isfinite(x) or not .5<=x<=4 for x in factors):raise ValueError('Sigma factors must lie in 0.5..4')
    if len(set(factors))!=len(factors) or 1 in factors:raise ValueError('Distinct changed factors only; unchanged control already covers factor 1')
    if not any(f<1 for f in factors) or not any(f>1 for f in factors):raise ValueError('Include both a stronger and a weaker restraint for a balanced comparison')
    out=[]
    for factor in factors:
        values=list(c['arguments']);lower=.005 if c['kind'] in {'DFIX','DANG','SADI','FLAT'} else .001
        for i in c['sigma_indices']:
            values[i]*=factor
            if not lower<=values[i]<=.5:raise ValueError('Scaled sigma outside supported local range; explicit specialist review required')
        card=c['kind']+' '+' '.join(f'{v:.9g}' for v in values)+' '+' '.join(c['ordered_labels'])
        out.append(dict(factor=factor,original=c['instruction'],replacement=card,atoms=c['atoms'],sigma_indices=c['sigma_indices']))
    return out

def observations(results,output,instruction):
    tokens=instruction.upper().split();key=tokens[0];count=LAYOUT[key][0];labels=tokens[1+count:];rows=[]
    for result in results:
        entry=dict(name=result['name'],status=result['status'],distances_A=None,Ueq_A2=None)
        if result['status']=='completed':
            try:
                b=gemmi.cif.read_file(str(Path(output)/result['name']/'paired/case.cif')).sole_block()
                cell=gemmi.UnitCell(*[gemmi.cif.as_number(b.find_value('_cell_'+x)) for x in ['length_a','length_b','length_c','angle_alpha','angle_beta','angle_gamma']])
                atoms={gemmi.cif.as_string(r[0]).upper():[gemmi.cif.as_number(v) for v in list(r)[1:]] for r in b.find(['_atom_site_label','_atom_site_fract_x','_atom_site_fract_y','_atom_site_fract_z','_atom_site_U_iso_or_equiv'])}
                if any(n not in atoms or any(not math.isfinite(v) for v in atoms[n]) for n in labels):raise ValueError('Missing/nonfinite target atom')
                entry['Ueq_A2']={n:atoms[n][3] for n in dict.fromkeys(labels)}
                if key in {'DFIX','DANG','SADI'}:
                    entry['distances_A']=[dict(atoms=[a,b],value=cell.find_nearest_pbc_image(gemmi.Fractional(*atoms[a][:3]),gemmi.Fractional(*atoms[b][:3]),0).dist()) for a,b in zip(labels[::2],labels[1::2])]
            except Exception as exc:entry['error']=str(exc)
        rows.append(entry)
    return rows

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--directory',required=True);p.add_argument('--instruction',required=True);p.add_argument('--output',required=True)
    a=p.parse_args();v=inspect(a.directory,a.instruction);v.update(model_modified=False,next='Use repair-plan restraint_strength with declared factors below and above 1 and the chemical basis.');newjson(a.output,v);print(json.dumps(v))
if __name__=='__main__':main()
