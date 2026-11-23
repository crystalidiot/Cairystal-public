"""Read-only CIF1.1 syntax and bounded model checks; not full dictionary validation."""
import argparse
import hashlib
import json
import math
from pathlib import Path

SOURCES = ['https://www.iucr.org/what-we-do/digital-standards/cif/cif1/file-syntax',
           'https://gemmi.readthedocs.io/en/latest/cif.html']

def inspect(path, require_single=False, require_model=False):
    import gemmi
    path=Path(path);raw=path.read_bytes()
    result={'schema':1,'sha256':hashlib.sha256(raw).hexdigest(),'errors':[],'warnings':[],
            'blocks':[],'modified':False,'dictionary_validation':False,'scientific_acceptance':False,
            'standard':'CIF1.1 boundary used by this SHELX/checkCIF pipeline','sources':SOURCES}
    def error(code,message):result['errors'].append({'code':code,'message':message})
    if raw.startswith(b'#\\#CIF_2.'):
        error('cif2_not_supported','CIF2 requires a separate explicit conversion/validation route; never relabel it as CIF1.')
    invalid=[(i,b) for i,b in enumerate(raw) if b>126 or (b<32 and b not in (9,10,13))]
    if invalid:
        i,b=invalid[0];error('cif1_character','Invalid byte at offset '+str(i)+': '+hex(b))
    for i,line in enumerate(raw.splitlines(),1):
        if len(line)>2048:error('line_length','CIF1.1 line exceeds 2048 characters at line '+str(i))
    if result['errors']:
        result['status']='invalid';return result
    try:
        doc=gemmi.cif.read_string(raw.decode('ascii'),check_level=1)
        # Explicitly retain both checks even when parser defaults change.
        doc.check_for_duplicates();doc.check_for_missing_values()
        if not len(doc):raise ValueError('No data blocks')
        if require_single and len(doc)!=1:raise ValueError('Select exactly one data block for this operation; do not silently select the first')
        for block in doc:
            if len(block.name)>75:raise ValueError('CIF1.1 block code exceeds 75 characters')
            loops=0
            for item in block:
                if item.frame is not None:raise ValueError('Save frames are dictionary syntax, unsupported in this data-file route')
                tags=[item.pair[0]] if item.pair else list(item.loop.tags) if item.loop else []
                if any(len(t)>75 for t in tags):raise ValueError('CIF1.1 data name exceeds 75 characters')
                if item.loop:
                    loops+=1
                    if not item.loop.width() or len(item.loop.values)%item.loop.width():raise ValueError('Loop width/value count mismatch')
            labels=[gemmi.cif.as_string(x) for x in block.find_values('_atom_site_label')]
            if labels and len(set(labels))!=len(labels):raise ValueError('Repeated atom-site label in '+block.name)
            if require_model:
                if not labels:raise ValueError('No atom-site loop in selected structural block')
                columns=['_atom_site_type_symbol','_atom_site_fract_x','_atom_site_fract_y','_atom_site_fract_z']
                if any(len(block.find_values(t))!=len(labels) for t in columns):raise ValueError('Incomplete atom-site loop')
                values=[]
                for suffix in ['length_a','length_b','length_c','angle_alpha','angle_beta','angle_gamma']:
                    token=block.find_value('_cell_'+suffix)
                    value=gemmi.cif.as_number(token or '?')
                    if not math.isfinite(value):raise ValueError('Missing/invalid unit-cell value: '+suffix)
                    values.append(value)
                if any(x<=0 for x in values[:3]) or any(not 0<x<180 for x in values[3:]):raise ValueError('Nonphysical cell parameter')
                volume=gemmi.UnitCell(*values).volume
                if not math.isfinite(volume) or volume<=0:raise ValueError('Nonphysical cell volume')
                for row in block.find(columns):
                    if not gemmi.Element(gemmi.cif.as_string(row[0])).atomic_number:raise ValueError('Unknown atom element')
                    if any(not math.isfinite(gemmi.cif.as_number(x)) for x in list(row)[1:]):raise ValueError('Missing/nonfinite atom coordinates')
            result['blocks'].append({'name':block.name,'loops':loops,'atoms':len(labels)})
        # Semantics of ? and . remain unchanged, including inside loops.
        result['null_tokens_preserved']=True
    except (RuntimeError,ValueError,TypeError) as exc:
        error('syntax_or_model_layout',str(exc))
    result['status']='invalid' if result['errors'] else 'format_checked'
    return result

def require(path, require_single=True, require_model=False):
    result=inspect(path,require_single,require_model)
    if result['errors']:raise ValueError('CIF format check: '+'; '.join(x['message'] for x in result['errors']))
    return result

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--cif',required=True);p.add_argument('--output')
    p.add_argument('--single-block',action='store_true');p.add_argument('--model',action='store_true');a=p.parse_args()
    result=inspect(a.cif,a.single_block,a.model)
    if a.output:
        with Path(a.output).open('x',encoding='utf-8') as f:json.dump(result,f,ensure_ascii=False,indent=2)
    print(json.dumps(result,ensure_ascii=False));return int(bool(result['errors']))
if __name__=='__main__':raise SystemExit(main())
