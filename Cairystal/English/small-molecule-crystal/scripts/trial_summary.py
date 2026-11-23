"""Compact local diagnostic-trial report; never an official checkCIF report."""
from pathlib import Path
import argparse,html,json,math
from compare_diagnostic_trials import counts

STATUS={'completed':'已完成对照','completed_map':'仅差值图','failed':'失败','not_run':'未运行','skipped_identical_configuration':'相同配置未重复运行'}
def value(v):
    return '—' if v is None or (isinstance(v,float) and not math.isfinite(v)) else html.escape(f'{v:.5g}' if isinstance(v,float) else str(v))
def render(directory):
    d=Path(directory);job=json.loads((d/'job.json').read_text('utf8'));data=json.loads((d/'results.json').read_text('utf8'))
    checkpoint=json.loads((d/'checkpoint.json').read_text('utf8'));done={r['name']:r for r in data['cases']};rows=[];summary=[]
    for planned in job['trials']:
        name=planned['name'];r=done.get(name,{'name':name,'status':'not_run'});status=r['status']
        alerts=r.get('AB') if status=='completed' and isinstance(r.get('AB'),list) else None
        c=counts(alerts);m=r.get('metrics') or {};density=r.get('difference_density') or {}
        record=d/name/'result.json';link=f'<a href="{html.escape(record.as_uri(),quote=True)}">完整记录</a>' if record.is_file() else '—'
        abtext='未获得完整验证' if alerts is None else ('无 A/B' if not alerts else '<br>'.join(html.escape(f"{a['code']} {a['level']} · "+' '.join(a.get('atom_labels') or [])) for a in alerts))
        reason='；'.join(str(e.get('error','')) for e in r.get('errors',[]))
        if alerts:reason+='\n'+'\n'.join(f"{a['code']} {a['level']}: {a.get('text','')}" for a in alerts)
        detail=f'<details><summary>警告详情 / 失败原因</summary><pre>{html.escape(reason)}</pre></details>' if reason.strip() else ''
        group=lambda key:'—' if c is None else f"{c[key]['A']} A / {c[key]['B']} B"
        reuse='复用，未重算' if r.get('resume_reuse') else ('本次运行' if status!='not_run' else '待运行')
        rows.append(f'<tr><td>{html.escape(name)}<br><small>{reuse}</small></td><td>{STATUS.get(status,html.escape(status))}</td><td>{group("metadata")}</td><td>{group("other")}</td><td>{abtext}{detail}</td><td>{value(m.get("R1_observed"))}</td><td>{value(m.get("wR2"))}</td><td>{value(m.get("GooF"))}</td><td>{value(density.get("max"))} / {value(density.get("min"))}</td><td>{link}</td></tr>')
        summary.append({'name':name,'status':status,'reused':bool(r.get('resume_reuse')),'AB_counts':c,'AB':alerts,'metrics':m or None,'result':str(record) if record.is_file() else None})
    html_text='''<!doctype html><html lang="zh-CN"><meta charset="utf-8"><title>Cairystal 对照简表</title><style>body{font:16px/1.6 system-ui,"Microsoft YaHei",sans-serif;margin:28px;color:#15334e}table{border-collapse:collapse;width:100%;font-size:14px}td,th{border-bottom:1px solid #ddd;padding:9px;vertical-align:top;text-align:left}th{background:#eaf2fa}pre{white-space:pre-wrap;max-width:550px}small{color:#506176}.scroll{overflow-x:auto}a{color:#075eae}</style><h1>Cairystal 对照简表</h1>'''
    html_text+=f'<p>本次新执行 {checkpoint.get("started_trials_this_run",0)} 个分支，复用 {checkpoint.get("reused_trials",0)} 个已核验分支；本次运行 {value(checkpoint.get("wall_seconds_this_run"))} 秒。</p>'
    html_text+='<p>按原始对照和各候选逐项查看。实验信息类 A/B 与其余 A/B 分列；失败或未运行用“—”，不计作零警告。这里是本地 PLATON 对照，选定模型后仍需完成精修复核、已授权 IUCr 官网 PDF 和中英文 Word。</p><div class="scroll"><table><tr><th>分支</th><th>状态</th><th>实验信息类</th><th>其余 A/B</th><th>具体警告</th><th>R1</th><th>wR2</th><th>GoF</th><th>残余密度 max/min</th><th>记录</th></tr>'+''.join(rows)+'</table></div><p>未自动选择最终模型；低 R、收敛或零 A/B 都不是结构正确的证明。</p></html>'
    return html_text,{'schema':1,'cases':summary,'official':False,'model_adopted':False,'native_attempts_this_run':checkpoint.get('native_attempts_this_run'),'reused_trials':checkpoint.get('reused_trials')}

def update(directory):
    from crystal_runtime import write_json
    d=Path(directory);text,summary=render(d);tmp=d/'comparison.html.tmp';tmp.write_text(text,encoding='utf8');tmp.replace(d/'comparison.html');write_json(d/'readable_summary.json',summary)

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--directory',required=True);p.add_argument('--output',required=True);a=p.parse_args()
    out=Path(a.output)
    if out.exists():raise FileExistsError(str(out))
    text,_=render(Path(a.directory).resolve());out.write_text(text,encoding='utf8');print(json.dumps({'report':str(out),'official':False}))
if __name__=='__main__':main()
