"""Local, bounded diagnostic records and minimal share packets; never sends data."""
import argparse,hashlib,html,json,platform,sys,traceback,zipfile
from pathlib import Path
from datetime import datetime,timezone
from report_typography import contact,contact_text

KINDS={
 'scientific_decision':('SCIENCE_REVIEW_REQUIRED','模型暂未解决','根据本次证据复核元素、氢、无序、空间群和 A/B 警告；不能用报告生成成功代替正确解析。'),
 'chemical_graph_required':('INPUT_OR_CHEMISTRY_REVIEW','需要化学判断','先检查当前密度和连接关系；确有关键输入缺失时一次说明。'),
 'input_insufficient':('INPUT_INSUFFICIENT','输入信息不足','检查缺失项和原始文件；不要编造组成或实验参数。'),
 'report_review':('REPORT_REVIEW_REQUIRED','模型或报告待复核','检查文件配对、A/B 警告和报告排版，保留目前结果。'),
 'integrity_error':('INTEGRITY_CHANGED','文件或版本发生变化','核对当前版本及输入哈希；不要直接覆盖或采用变化后的文件。'),
 'upload_authorization_required':('UPLOAD_CHOICE_REQUIRED','等待官网上传选择','复用已记录的本样品授权；未授权时不上传。'),
 'interrupted_action':('ACTION_INTERRUPTED','操作结果待确认','先检查已有输出及官网记录，避免重复上传。'),
 'execution_error':('EXECUTION_FAILED','程序步骤未完成','依据本次命令和日志排错；程序失败不等于晶体无法解析。')}

def safe(path):
    p=Path(path).absolute()
    for q in (p,*p.parents):
        if q.is_symlink() or (hasattr(q,'is_junction') and q.is_junction()):raise ValueError('Diagnostic path must not traverse links')
    return p

def record(run,category,reason,stage='workflow',exception=None):
    root=safe(run)
    if not root.is_dir() or not any((root/n).is_file() for n in ['autorun.json','pipeline.json','state.json','result.json']):
        raise ValueError('A verified current-run state directory is required; no input-directory fallback')
    category=category if category in KINDS else 'execution_error'
    code,title,next_action=KINDS[category]
    key=hashlib.sha256(json.dumps([category,str(reason),str(stage)],ensure_ascii=False).encode()).hexdigest()[:16]
    base=safe(root/'support');base.mkdir(exist_ok=True)
    folder=safe(base/key)
    if folder.exists():
        if not (folder/'incident.json').is_file():raise ValueError('Incomplete diagnostic record retained; use local logs')
        return {'id':key,'code':code,'directory':str(folder),'report':str(folder/'说明.html'),'share_zip':str(folder/'Cairystal_feedback.zip'),'cache_hit':True}
    folder.mkdir()
    released=Path(__file__).resolve().parent.parent/'release_info.json'
    release=json.loads(released.read_text(encoding='utf-8')) if released.is_file() else {'release_id':'development'}
    event={'schema':1,'id':key,'created_at':datetime.now(timezone.utc).isoformat(),'code':code,'category':category,'stage':str(stage),'status':'needs_attention','release_id':release.get('release_id'),'python':platform.python_version(),'platform':platform.system(),'contact':contact(),'scientific_acceptance':False,'transmission':'none'}
    # Keep sensitive operational details local; no raw text, paths, logs or models in ZIP.
    local=dict(event,run_directory=str(root),observed_error=str(reason),exception_type=type(exception).__name__ if exception else None,traceback=''.join(traceback.format_exception(exception)) if exception else None,confirmed_root_cause=None,suspected_causes=[],next_action=next_action,evidence_paths=[str(root/n) for n in ['autorun.json','pipeline.json','state.json','result.json','handoff.json'] if (root/n).is_file()])
    public={k:event[k] for k in ['schema','id','created_at','code','category','release_id','python','platform','scientific_acceptance','transmission']}
    public.update(stage=stage if stage in {'solve','match','finish','deliver','start','complete','workflow','autorun','report'} else 'workflow',exception_type=type(exception).__name__ if exception else None,contents='Minimal metadata only; no scientific data, paths, logs or raw exception messages.')
    for name,data in [('incident.json',local),('feedback.json',public)]:
        (folder/name).write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    with zipfile.ZipFile(folder/'Cairystal_feedback.zip','w',zipfile.ZIP_DEFLATED) as z:
        z.writestr('feedback.json',json.dumps(public,ensure_ascii=False,indent=2))
        z.writestr('README.txt','Cairystal minimal feedback packet. No automatic submission.\n'+contact_text(False)+'\n')
    text='<!doctype html><html lang="zh-CN"><meta charset="utf-8"><title>Cairystal 处理说明</title><style>body{font:17px/1.7 system-ui;max-width:850px;margin:40px auto;padding:20px}pre{white-space:pre-wrap;overflow-wrap:anywhere}</style><h1>'+title+'</h1><p>事件编号：'+key+'；分类：'+code+'</p><p>'+next_action+'</p><p>当前模型和原始记录已保留。此记录不会修改模型、删反射、跳过验证或重新上传。</p><p><a href="Cairystal_feedback.zip">最小反馈包</a>仅含版本、分类等信息，不含晶体、原始错误消息或日志。请自行检查后发送；完整本地记录可能包含路径或敏感信息，不在此包中。</p><details><summary>本地原始报错</summary><pre>'+html.escape(str(reason))+'</pre></details><p>'+html.escape(contact_text())+'</p></html>'
    (folder/'说明.html').write_text(text,encoding='utf-8')
    return {'id':key,'code':code,'directory':str(folder),'report':str(folder/'说明.html'),'share_zip':str(folder/'Cairystal_feedback.zip'),'cache_hit':False}

def try_record(run,category,reason,stage='workflow',exception=None):
    try:return record(run,category,reason,stage,exception)
    except Exception as e:return {'status':'diagnostic_write_failed','error':str(e),'original_error_preserved':True,'contact':contact()}

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--run',required=True);p.add_argument('--category',choices=sorted(KINDS),default='execution_error');p.add_argument('--stage',default='workflow');p.add_argument('--reason',required=True)
    a=p.parse_args();print(json.dumps(record(a.run,a.category,a.reason,a.stage),ensure_ascii=False));return 0
if __name__=='__main__':raise SystemExit(main())
