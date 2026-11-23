"""Locate correlated SHELXL parameter pairs without fixing or restraining atoms."""
import argparse,json,math,re,time
from pathlib import Path
from structure_diagnostics import digest,newjson,res_records

NUM=r'[+-]?(?:\d*\.\d+|\d+)(?:[Ee][+-]?\d+)?'
PAIR=re.compile(r'(?<!\S)('+NUM+r')\s+(.+?)\s*/\s*(.+?)(?=\s{2,}'+NUM+r'\s+|$)')

def parse_lst(text):
    marker='Largest correlation matrix elements'
    if marker not in text:return dict(status='not_reported',pairs=[],unparsed_lines=[],max_absolute=None)
    lines=text.rsplit(marker,1)[1].splitlines();pairs=[];unparsed=[];started=False
    for line in lines:
        if not line.strip():
            if started:break
            continue
        if not re.match(r'^\s*'+NUM+r'\s+',line):
            if not started and re.search(r'none|no correlations',line,re.I):return dict(status='none_reported',pairs=[],unparsed_lines=[],max_absolute=None)
            if started:break
            unparsed.append(line.strip());break
        started=True;matches=list(PAIR.finditer(line));remaining=PAIR.sub('',line).strip()
        if not matches or remaining:unparsed.append(line.strip())
        for m in matches:
            value=float(m[1])
            if not math.isfinite(value) or abs(value)>1.00001:unparsed.append(m[0]);continue
            pairs.append(dict(coefficient=value,left=' '.join(m[2].split()),right=' '.join(m[3].split())))
    pairs.sort(key=lambda p:abs(p['coefficient']),reverse=True)
    return dict(status='partial_parse' if unparsed else 'parsed' if pairs else 'empty_section',pairs=pairs,unparsed_lines=unparsed,max_absolute=max((abs(p['coefficient']) for p in pairs),default=None))

def identify(value,parsed):
    tokens=value.split();kind=tokens[0].upper() if tokens else '';reference=' '.join(tokens[1:])
    category='coordinate' if kind in {'X','Y','Z'} else 'ADP' if re.fullmatch(r'U(?:ISO|EQ|11|22|33|12|13|23)?',kind) else 'occupancy' if kind in {'SOF','OCC'} else 'free_variable' if kind in {'FVAR','FV'} else 'scale_or_model' if kind in {'OSF','SCALE','EXTI','BASF'} else 'unclassified'
    matches=[dict(label=a['label'],PART=a['part'],RESI=a['residue'],element=a['element']) for a in parsed['atoms'] if a['label'].upper()==reference.upper()]
    return dict(raw=value,parameter=kind,reference=reference,category=category,atom_matches=matches,
        identity='unique_atom' if len(matches)==1 else 'ambiguous_atom' if len(matches)>1 else 'global_or_unresolved')

def audit(directory,stem='case',threshold=.9):
    if isinstance(threshold,bool) or not isinstance(threshold,(float,int)) or not .5<=threshold<=1:raise ValueError('threshold must be in 0.5..1')
    start=time.perf_counter();d=Path(directory);paths=[d/(stem+'.lst'),d/(stem+'.res')];hashes={str(p):digest(p) for p in paths}
    text=paths[0].read_text('latin1');parsed=res_records(paths[1]);value=parse_lst(text)
    for pair in value['pairs']:
        pair['parameters']=[identify(pair[k],parsed) for k in ['left','right']]
        pair['above_threshold']=abs(pair['coefficient'])>=threshold
        categories={p['category'] for p in pair['parameters']}
        pair['review']=('Review population/ADP trade-off and disorder model; compare explicit occupancy-start trials.' if categories&{'free_variable','occupancy'} and 'ADP' in categories else
            'Review coordinate dependence, duplicate/split sites and supported geometry.' if 'coordinate' in categories else
            'Review atom identity, ADP/disorder and existing constraints; correlation is not a diagnosis.')
    from convergence_trend import RECORD
    shifts=list(RECORD.finditer(text));last=shifts[-1] if shifts else None
    value.update(schema=1,source_sha256=hashes,threshold=threshold,
        high_pairs=[p for p in value['pairs'] if p['above_threshold']],
        last_dominant_parameter=last[3].strip() if last else None,
        model_modified=False,fix_coordinates=False,seconds=round(time.perf_counter()-start,4),
        limitations=['Only the printed largest correlations from the last reported section, not the full covariance matrix.',
        'Missing correlation output is unknown, not zero. Signed coefficients and every printed column are preserved.',
        'Ambiguous PART/RESI labels and global/free-variable identities remain unresolved; no automatic coordinate fixing.'])
    value['source_unchanged']=all(digest(Path(p))==h for p,h in hashes.items())
    if not value['source_unchanged']:raise ValueError('Input changed during correlation audit')
    return value

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--directory',required=True);p.add_argument('--stem',default='case');p.add_argument('--threshold',type=float,default=.9);p.add_argument('--output',required=True)
    a=p.parse_args();v=audit(a.directory,a.stem,a.threshold);newjson(a.output,v);print(json.dumps({'status':v['status'],'pairs':len(v['pairs']),'high_pairs':len(v['high_pairs']),'seconds':v['seconds']}))
if __name__=='__main__':main()
