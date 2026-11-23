"""Read the final SHELXL disagreeable-restraint listing; never edit a model."""
import argparse,json,re
from pathlib import Path

NUM=r'[-+]?(?:\d+(?:\.\d*)?|\.\d+)(?:[Ee][-+]?\d+)?'
ROW=re.compile(r'^\s*('+NUM+r')\s+('+NUM+r')\s+('+NUM+r')\s+('+NUM+r')\s+(DFIX|DANG)\s+(.+?)\s*$',re.M)

def parse_final_listing(text,review_sigma=5.0):
    headings=list(re.finditer(r'Disagreeable restraints before cycle\s+(\d+)',text))
    if not headings:
        return {'status':'not_reported','cycle':None,'listed_geometry':[],
                'needs_review':None,'limitation':'No final disagreeable-restraint listing found; absence is not proof of satisfied geometry.'}
    h=headings[-1];tail=text[h.end():]
    end=re.search(r'Summary of restraints applied|GooF\s*=|wR2\s*=',tail)
    block=tail[:end.start()] if end else tail
    values=[]
    for m in ROW.finditer(block):
        observed,target,error,sigma=map(float,m.group(1,2,3,4))
        z=abs(error)/sigma if sigma>0 else None
        values.append({'kind':m[5],'atoms':m[6],'observed_A':observed,'target_A':target,
                       'error_A':error,'sigma_A':sigma,'absolute_error_over_sigma':z})
    unparsed=sum(bool(re.search(r'\b(?:DFIX|DANG)\b',line)) and not bool(ROW.fullmatch(line)) for line in block.splitlines())
    conflict=any(v['absolute_error_over_sigma'] is not None and v['absolute_error_over_sigma']>=review_sigma for v in values)
    incomplete=unparsed>0 or any(v['absolute_error_over_sigma'] is None for v in values)
    return {'status':'incomplete_parse' if incomplete else 'parsed','cycle':int(h[1]),
            'listed_geometry':values,'unparsed_geometry_rows':unparsed,'review_sigma':review_sigma,
            'needs_review':True if conflict or incomplete else False,
            'limitation':'Only listed final DFIX/DANG conflicts are screened. No listed conflict does not establish chemistry, geometry validity or absence of over-restraint. A threshold is a review trigger, not an automatic rejection.'}

def main():
    p=argparse.ArgumentParser();p.add_argument('lst',type=Path);p.add_argument('--output',required=True,type=Path);a=p.parse_args()
    v=parse_final_listing(a.lst.read_text(encoding='latin1'));a.output.write_text(json.dumps(v,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps({'status':v['status'],'needs_review':v['needs_review'],'listed':len(v['listed_geometry'])}))

if __name__=='__main__':main()
