"""Read explicit run timings; never infer token use or skip scientific checks."""
import argparse
import json
import math
from pathlib import Path


def seconds(value):
    return isinstance(value,(int,float)) and not isinstance(value,bool) and math.isfinite(value) and value>=0


def summarize(timings,elapsed=None):
    if not isinstance(timings,dict):raise ValueError('timings_s must be an object')
    measured=[];unknown=[]
    for stage,value in timings.items():
        if value is None:unknown.append(stage);continue
        if not seconds(value):raise ValueError('Invalid stage duration: '+stage)
        measured.append({'stage':stage,'seconds':value})
    measured.sort(key=lambda x:(-x['seconds'],x['stage']))
    total=sum(x['seconds'] for x in measured)
    for item in measured:item['percent_of_recorded_stages']=round(100*item['seconds']/total,2) if total else None
    if elapsed is not None and not seconds(elapsed):raise ValueError('Invalid elapsed time')
    hints=[]
    for item in measured[:3]:
        stage=item['stage']
        if stage=='official_validation':
            hints.append({'stage':stage,'zh':'查看官网分项：表单、提交与服务端处理、PDF/FCF下载。最终 CIF 冻结后提交；下载失败从已有任务恢复，不重复上传。','en':'Inspect form, POST/server and report GET timings. Submit the frozen final CIF; recover report downloads without repeating the POST.'})
        elif stage=='rendering':
            hints.append({'stage':stage,'zh':'区分导出、逐页图像生成与复用检查；同任务续跑可复用已核对的相同文档页面。保留双语、全部页面及完整排版检查。','en':'Separate export, rasterization and reuse checks. Same-job continuation may reuse verified unchanged document pages; retain both languages, all pages and complete layout QA.'})
        elif 'refin' in stage or 'solv' in stage:
            hints.append({'stage':stage,'zh':'先检查重复尝试和收敛趋势；线程数需在同一输入、轮数及本机资源下比较，不能把更多核数或更大 -b 当作更快。','en':'Check repeated attempts/convergence; compare threads on identical inputs and cycles. More threads or a larger -b are not automatically faster.'})
    return {'schema':1,'scope':'Recorded stages only; nested details must not be added to their parent stages.',
            'stages':measured,'recorded_stage_seconds':round(total,6),'wall_elapsed_seconds':elapsed,
            'unattributed_wall_seconds':round(elapsed-total,6) if elapsed is not None and elapsed>=total else None,
            'stage_sum_exceeds_wall':elapsed is not None and total>elapsed+.02,
            'unknown_stages':unknown,'next_checks':hints,'token_count':None,
            'scientific_checks_skipped':False}


def inspect_run(directory):
    from pipeline_intake import unlinked
    from crystal_runtime import regular,sha
    root=unlinked(directory)
    sources={}
    def read(relative,optional=False):
        path=unlinked(root/relative)
        if optional and not path.exists():return None
        path=regular(path);sources[relative]=sha(path)
        return json.loads(path.read_text('utf-8-sig'))
    record=read('result.json')
    timings=record.get('timings_s',record.get('delivery_timings_s'))
    if not isinstance(timings,dict):raise ValueError('Choose the delivery run containing result.json with timings_s; no recursive search is performed')
    result=summarize(timings,record.get('automated_elapsed_s',record.get('elapsed_s')))
    render=read('qa/render_manifest.json',True)
    official=read('official/submission.json',True)
    qa=read('automatic_qa.json',True)
    result['nested_details']={
        'rendering':None if not render else {'timings_s':render.get('timings_s'),'elapsed_s':render.get('elapsed_s'),'cache_hit':render.get('cache_hit'),'cache_source':render.get('cache_source'),'cache_miss_reason':render.get('cache_miss_reason')},
        'official_validation':None if not official else {'timings_s':official.get('timings_s'),'cache_hit':official.get('cache_hit'),'report_get_attempts':[{k:a.get(k) for k in ['kind','attempt','status','elapsed_s']} for a in official.get('report_get_attempts',[])]}}
    # QA runs after delivery's timed interval; display separately, never silently
    # imply that its time was included in older delivery records.
    result['report_qa_separate']=None if not qa else {'elapsed_s':qa.get('elapsed_s'),'document_timings_s':qa.get('document_timings_s'),'status':qa.get('status')}
    result['source_hashes']=sources;result['run']=str(root)
    return result


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--run',required=True,help='Exact delivery-run directory, not an input dataset')
    p.add_argument('--output',help='New JSON path; omit for stdout only')
    args=p.parse_args()
    try:
        result=inspect_run(args.run)
        if args.output:
            from pipeline_intake import unlinked
            path=unlinked(args.output)
            with path.open('x',encoding='utf-8') as f:json.dump(result,f,ensure_ascii=False,indent=2)
        print(json.dumps(result,ensure_ascii=False,indent=2));return 0
    except (OSError,ValueError,KeyError,TypeError) as e:
        print(json.dumps({'status':'failed','error':str(e)},ensure_ascii=False));return 1


if __name__=='__main__':raise SystemExit(main())
