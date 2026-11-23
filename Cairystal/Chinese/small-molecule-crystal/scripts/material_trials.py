"""Named front ends for reviewed water-H and fixed-reflection native comparisons."""
import argparse,json
from pathlib import Path
from repair_plan import prepare,run

RECIPES={'water':'water_orient','reflections':'reflection_omit'}
def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('kind',choices=RECIPES)
    sub=p.add_subparsers(dest='action',required=True)
    prep=sub.add_parser('prepare')
    for name in ['baseline','request','profile','output']:prep.add_argument('--'+name,required=True)
    prep.add_argument('--stem',default='case')
    execute=sub.add_parser('run');execute.add_argument('--plan',required=True)
    a=p.parse_args()
    try:
        if a.action=='prepare':
            req=json.loads(Path(a.request).read_text('utf-8-sig'))
            if req.get('recipe')!=RECIPES[a.kind]:raise ValueError('Request recipe does not match selected tool')
            result=prepare(a.baseline,a.stem,req,json.loads(Path(a.profile).read_text('utf-8-sig')),a.output)
        else:
            plan=json.loads(Path(a.plan).read_text('utf-8-sig'))
            if plan.get('recipe')!=RECIPES[a.kind]:raise ValueError('Plan recipe does not match selected tool')
            result=run(a.plan)
        print(json.dumps(result,ensure_ascii=False));return 0
    except Exception as exc:print(json.dumps({'status':'failed','error':str(exc),'model_adopted':False},ensure_ascii=False));return 2
if __name__=='__main__':raise SystemExit(main())
