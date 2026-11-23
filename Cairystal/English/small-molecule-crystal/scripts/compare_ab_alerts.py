"""Compare complete local CHK or saved IUCr text reports; never infer a diagnosis."""
import argparse
from collections import Counter
import html
import json
from pathlib import Path
import re
import time

from crystal_runtime import regular, sha
from iucr_validation import parse_official_text
from parse_platon_alerts import parse


def read_report(path):
    p=regular(path);digest=sha(p);data=p.read_bytes()
    try:text=data.decode('utf-8-sig')
    except UnicodeDecodeError:text=data.decode('latin1')
    if re.search(r'ALERT level [ABCG]\s*=',text) or 'Structure factors have been supplied' in text:
        value=parse_official_text(text);kind='saved_iucr_text'
    else:
        value=parse(text);kind='local_chk'
        if not value['report_footer_present'] or value['warnings']:
            raise ValueError('Local report incomplete or counts disagree: '+str(p))
        # Omitted zero levels are allowed by the native local report format;
        # every nonzero level must have a corresponding printed summary.
        if not value['printed_summary'] or any(n and level not in value['printed_summary'] for level,n in value['counts'].items()):
            raise ValueError('Local report summary is absent/incomplete: '+str(p))
    alerts=[]
    for a in value['alerts']:
        m=re.fullmatch(r'(?:PLAT)?(\d+)(?:_ALERT_(\d)_([ABCG]))?',a['code'])
        if not m:raise ValueError('Unsupported alert identifier: '+a['code'])
        typ=int(m[2]) if m[2] else a.get('type')
        if typ is None:raise ValueError('Alert type absent')
        alerts.append({'code':m[1].zfill(3),'type':typ,'level':a['level'],'text':' '.join(a['text'].split())})
    if sha(p)!=digest:raise ValueError('Input report changed during reading')
    return {'path':str(p),'sha256':digest,'kind':kind,'counts':value['counts'],'alerts':alerts}


def compare_reports(before, after):
    start=time.perf_counter();a=read_report(before);b=read_report(after)
    if a['kind']!=b['kind']:raise ValueError('Compare the same validator/report scope; local and official reports are not interchangeable')
    def counter(report):
        return Counter((x['code'],x['type'],x['level'],x['text']) for x in report['alerts'] if x['level'] in 'AB')
    old=counter(a);new=counter(b)
    def rows(values):return [{'code':k[0],'type':k[1],'level':k[2],'text':k[3],'occurrences':v} for k,v in sorted(values.items())]
    code_counts=[]
    for code,typ in sorted({(x['code'],x['type']) for r in [a,b] for x in r['alerts'] if x['level'] in 'AB'}):
        def levels(r):return {l:sum(x['code']==code and x['type']==typ and x['level']==l for x in r['alerts']) for l in 'ABCG'}
        code_counts.append({'code':code,'type':typ,'before':levels(a),'after':levels(b)})
    return {'schema':1,'status':'comparison_complete','ai_calls':0,'seconds':round(time.perf_counter()-start,6),
            'before':a,'after':b,'unchanged_entries':rows(old&new),'before_only_entries':rows(old-new),'after_only_entries':rows(new-old),
            'code_counts':code_counts,'model_pairing_verified':False,
            'limitation':'Exact message multiset comparison. Changed values/labels/levels may appear once on each side. No claim of physical resolution, same CIF/data or identical validator version. Before-only does not mean scientifically fixed.'}


def write_comparison(result, directory):
    p=Path(directory).absolute()
    if p.exists():raise ValueError('Use a new comparison directory')
    if any(x.is_symlink() or getattr(x,'is_junction',lambda:False)() for x in p.parents):raise ValueError('Linked output parent unsupported')
    p.mkdir(parents=True)
    (p/'ab_comparison.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    def entries(key):
        return ''.join('<tr><td>'+html.escape(f"{x['code']}_ALERT_{x['type']}_{x['level']}")+'</td><td>'+str(x['occurrences'])+'</td><td>'+html.escape(x['text'])+'</td></tr>' for x in result[key]) or '<tr><td colspan="3">无</td></tr>'
    sections=''.join('<h2>'+title+'</h2><table><tr><th>警告</th><th>次数</th><th>原文</th></tr>'+entries(key)+'</table>' for key,title in [('before_only_entries','修改前有、修改后未出现的原文'),('after_only_entries','修改后新增或原文发生变化'),('unchanged_entries','原文完全相同、仍存在')])
    counts=''.join('<tr><td>'+html.escape(str(x['code']))+'</td><td>'+str(x['before'])+'</td><td>'+str(x['after'])+'</td></tr>' for x in result['code_counts'])
    page='<!doctype html><html lang="zh"><meta charset="utf-8"><title>A/B 警告对照</title><style>body{font-family:Arial,sans-serif;max-width:1150px;margin:30px auto;padding:0 20px;color:#233}table{border-collapse:collapse;width:100%;margin-bottom:24px}td,th{border:1px solid #ccd;padding:9px;text-align:left}th{background:#edf3f8}p{line-height:1.6}</style><h1>A/B 警告对照</h1><p>只比较完整报告中的文字，不自动认定结构问题已经解决。数值、原子标签或等级变化，会同时出现在前后两栏。C/G 仅用于说明原 A/B 代码的等级变化。</p><p>尚未证明报告对应同一模型/衍射数据或相同验证版本。</p><table><tr><th>原 A/B 代码</th><th>修改前各等级数量</th><th>修改后各等级数量</th></tr>'+counts+'</table>'+sections+'<footer>Cairystal · 自动整理，AI 调用 0 次</footer></html>'
    (p/'index.html').write_text(page,encoding='utf-8')


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--before',required=True,type=Path);p.add_argument('--after',required=True,type=Path);p.add_argument('--output',required=True,type=Path)
    a=p.parse_args();result=compare_reports(a.before,a.after);write_comparison(result,a.output)
    print(json.dumps({'status':result['status'],'before':result['before']['counts'],'after':result['after']['counts'],'seconds':result['seconds'],'output':str(a.output),'ai_calls':0},ensure_ascii=False));return 0


if __name__=='__main__':raise SystemExit(main())
