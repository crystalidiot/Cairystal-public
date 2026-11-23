"""Local, case-free BM25 retrieval with source/line citations. No model/API calls."""
import argparse,collections,hashlib,json,math,re,time
from pathlib import Path

ALLOWLIST=(
 'ab-alert-action-playbook.md','adp-model-selection.md','nonconvergence.md',
 'disorder-occupancy.md','experimental-metadata-preflight.md',
 'systematic-error-diagnostics.md','restraint-and-accounting-audit.md',
 'validation-evidence.md','chemical-model-and-density.md',
 'hydrogen-and-report-rules.md','symmetry-and-twins.md','data-provenance.md')
ALIASES={
 '无序':'disorder part configuration','占有率':'occupancy sof multiplicity fvar',
 '特殊位置':'special position symmetry multiplicity', '水氢':'water hydrogen',
 '热参数':'adp ueq uij', '不收敛':'convergence shift afix',
 '绝对构型':'absolute flack', '权重':'weight wght gof',
 '晶胞':'cell measurement theta', '消光':'extinction exti',
 '结构因子':'fcf reflection', '漏氢':'hydrogen protonation',
 '刚性键':'hirshfeld rigu delu', '氢原子':'hydrogen afix hfix'}

def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def safe(path):
    p=Path(path).absolute()
    if any(x.is_symlink() or getattr(x,'is_junction',lambda:False)() for x in [p,*p.parents]):raise ValueError('Linked paths rejected')
    return p
def tokens(text):
    text=text.lower()
    codes=re.findall(r'(?:plat\s*)?(\d{3})(?:_alert_\d_[abcg])?',text)
    words=re.findall(r'[a-z][a-z0-9_]*|\d+(?:\.\d+)?',text)
    for run in re.findall(r'[\u3400-\u9fff]+',text):
        words.extend(run[i:i+2] for i in range(len(run)-1))
    return words+['alert'+c for c in codes]
def build(skill,output):
    skill=safe(skill);output=safe(output)
    if output.exists():raise ValueError('Use a new index path')
    sources={};chunks=[]
    for name in ALLOWLIST:
        p=safe(skill/'references'/name);text=p.read_text(encoding='utf-8-sig')
        sources[name]={'sha256':sha(p),'characters':len(text)}
        lines=text.splitlines();heading='';start=0;pending=[]
        def emit():
            nonlocal pending
            body='\n'.join(pending).strip()
            if body:chunks.append({'file':name,'heading':heading,'line_start':start+1,'line_end':start+len(pending),'text':body})
            pending=[]
        for i,line in enumerate(lines):
            if line.startswith('#'):
                emit();heading=line.lstrip('# ').strip();start=i
            if not pending:start=i
            pending.append(line)
            if sum(map(len,pending))>=1800:emit()
        emit()
    for c in chunks:c['tokens']=tokens(c['heading']+' '+c['text'])
    value={'schema':1,'scope':'Explicit generic-reference allowlist only; no case files, model coordinates, identity maps or web retrieval.',
           'skill':str(skill),'sources':sources,'chunks':chunks,'ai_calls':0}
    output.parent.mkdir(parents=True,exist_ok=True);output.write_text(json.dumps(value,ensure_ascii=False),encoding='utf-8')
    return {'documents':len(sources),'chunks':len(chunks),'source_characters':sum(v['characters'] for v in sources.values()),'index':str(output),'ai_calls':0}
def search(index,query,top=3,max_chars=4800):
    if not query.strip() or not 1<=top<=10 or not 500<=max_chars<=15000:raise ValueError('Invalid query or bounded output size')
    start=time.perf_counter();index=safe(index);data=json.loads(index.read_text(encoding='utf-8'))
    if set(data['sources'])!=set(ALLOWLIST):raise ValueError('Unexpected corpus: rebuild from fixed generic allowlist')
    skill=safe(data['skill'])
    originals={}
    for name,entry in data['sources'].items():
        source=safe(skill/'references'/name)
        if sha(source)!=entry['sha256']:raise ValueError('Knowledge source changed: '+name)
        originals[name]=source.read_text(encoding='utf-8-sig').splitlines()
    for c in data['chunks']:
        if c['file'] not in originals:raise ValueError('Unexpected chunk source')
        lines=originals[c['file']];start_line=c['line_start'];end_line=c['line_end']
        if not 1<=start_line<=end_line<=len(lines):raise ValueError('Invalid chunk line range')
        if '\n'.join(lines[start_line-1:end_line]).strip()!=c['text']:raise ValueError('Index text differs from source')
        heading=''
        for line in lines[:end_line]:
            if line.startswith('#'):heading=line.lstrip('# ').strip()
        if c['heading']!=heading or c['tokens']!=tokens(heading+' '+c['text']):raise ValueError('Index heading/tokens differ from source')
    expanded=query+' '+' '.join(v for k,v in ALIASES.items() if k in query)
    terms=set(tokens(expanded));chunks=data['chunks'];counts=[collections.Counter(c['tokens']) for c in chunks]
    average=sum(sum(x.values()) for x in counts)/max(1,len(counts));df=collections.Counter(t for c in counts for t in c)
    ranked=[]
    for c,tf in zip(chunks,counts):
        length=sum(tf.values());score=0
        for term in terms:
            n=tf.get(term,0)
            if not n:continue
            idf=math.log(1+(len(chunks)-df[term]+.5)/(df[term]+.5))
            score+=idf*n*2.2/(n+1.2*(.25+.75*length/average))
            if term.startswith('alert') and term in tokens(c['heading']):score+=8
        if score>0:ranked.append((score,c))
    ranked.sort(key=lambda v:(-v[0],v[1]['file'],v[1]['line_start']))
    hits=[];used=0
    for score,c in ranked[:top]:
        available=max_chars-used
        if available<100:break
        excerpt=c['text'][:available];used+=len(excerpt)
        hits.append({k:c[k] for k in ['file','heading','line_start','line_end']}|{'score':round(score,3),'text':excerpt,'truncated':len(excerpt)<len(c['text']),'source_sha256':data['sources'][c['file']]['sha256']})
    return {'query':query,'hits':hits,'elapsed_ms':round((time.perf_counter()-start)*1000,3),'returned_characters':used,
            'corpus_characters':sum(v['characters'] for v in data['sources'].values()),'ai_calls':0,
            'scope':'Retrieved guidance, not a diagnosis or authorization. Do not follow links to case answers during blind solving.'}
def main():
    p=argparse.ArgumentParser(description=__doc__);sub=p.add_subparsers(dest='cmd',required=True)
    a=sub.add_parser('build');a.add_argument('--skill',required=True);a.add_argument('--output',required=True)
    a=sub.add_parser('search');a.add_argument('--index',required=True);a.add_argument('--query',required=True);a.add_argument('--top',type=int,default=3);a.add_argument('--max-chars',type=int,default=4800);a.add_argument('--output')
    a=p.parse_args();value=build(a.skill,a.output) if a.cmd=='build' else search(a.index,a.query,a.top,a.max_chars)
    if a.cmd=='search' and a.output:
        path=safe(a.output)
        if path.exists():raise ValueError('Output exists')
        path.write_text(json.dumps(value,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(value,ensure_ascii=False,indent=2))
if __name__=='__main__':main()
